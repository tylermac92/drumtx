"""Stage orchestration and the stage cache (Technical Design Document §6–7).

Each stage's cache key covers the source file's SHA-256, the stage's name and version, the options
it reads, and the keys of the stages it depends on. So changing a quantize option re-runs quantize
and everything after it, and reuses the cached detection.

- A cached stage (separate, detect, track) loads its output from the cache when the key matches.
- An uncached stage that others depend on (ingest, quantize) runs only when one of them has to run.
- An uncached stage that nothing depends on (render, report) always runs.

The cache keeps only the newest entry per stage, so it cannot grow without limit.
"""

import dataclasses
import hashlib
import io
import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np

from drumtx import beats, detect, ingest, mapping, models, render, review
from drumtx.detect import Preset
from drumtx.midi import MidiTiming, midi_bytes
from drumtx.musicxml import musicxml_bytes
from drumtx.quantize import GridOption, quantize
from drumtx.schema import CLASSES, DrumEvent, QuantizedScore, event_from_json, event_to_json
from drumtx.separate import SEPARATOR, Device, isolate_drums

log = logging.getLogger("drumtx")
TRACKER = "beat-this-final0"
CACHE_DIR = ".drumtx-cache"


@dataclass(frozen=True)
class Config:
    """Options of one run. Stages name the fields they read in `Stage.params`."""

    input: Path
    out_dir: Path
    start: float | None = None
    end: float | None = None
    max_duration: float = ingest.DEFAULT_MAX_DURATION_S
    sensitivity: Preset = "balanced"
    model: str = models.DEFAULT
    offline: bool = False
    separate: bool = False
    bpm: float | None = None
    beats_per_bar: int | None = None  # --time-signature N/4; None is the 4/4 default
    first_downbeat: float | None = None
    grid: GridOption = "auto"
    midi_timing: MidiTiming = "quantized"
    mapping: Path | None = None  # --mapping; None is the default mapping.toml
    mark_uncertain: bool = False
    device: Device = "cpu"  # for --separate only; does not change the stem
    no_cache: bool = False
    force: bool = False

    @property
    def model_fingerprint(self) -> str:
        """Changes when the model file or its presets do, so cached detections are not reused."""
        if self.model == models.BASELINE:
            return self.model
        presets = hashlib.sha256(detect.MODEL_PRESETS_FILE.read_bytes()).hexdigest()
        return f"{self.model}:{models.spec(self.model).sha256}:{presets}"

    @property
    def tracker_fingerprint(self) -> str:
        return models.spec(TRACKER).sha256

    @property
    def separator_fingerprint(self) -> str:
        return models.spec(SEPARATOR).sha256


@dataclass(frozen=True)
class RunContext:
    config: Config
    source_sha256: str

    @classmethod
    def create(cls, config: Config) -> "RunContext":
        ingest.check_file(config.input)
        with config.input.open("rb") as f:
            return cls(config, hashlib.file_digest(f, "sha256").hexdigest())

    @property
    def cache_dir(self) -> Path:
        return self.config.out_dir / CACHE_DIR


@dataclass(frozen=True)
class Stage:
    name: str
    run: Callable[..., Any]  # run(ctx, *outputs of deps)
    summary: Callable[[RunContext, Any], str]  # one progress line, from the output
    deps: tuple[str, ...] = ()
    params: tuple[str, ...] = ()  # Config fields that change the output
    cached: bool = True
    version: int = 1  # bump when the stage's output changes for the same inputs
    dump: Callable[[Any], bytes] = field(default=lambda out: json.dumps(out).encode())
    load: Callable[[bytes], Any] = field(default=json.loads)
    suffix: str = ".json"  # of the cache file


def _ingest_summary(ctx: RunContext, audio: ingest.AudioBuffer) -> str:
    minutes, seconds = divmod(round(audio.duration_s), 60)
    channels = {1: "mono", 2: "stereo"}.get(audio.samples.shape[1], f"{audio.samples.shape[1]} ch")
    return f"{ctx.config.input.name}  {minutes}:{seconds:02d}, {channels}"


def _detect_summary(ctx: RunContext, events: list[DrumEvent]) -> str:
    per_class = ", ".join(f"{c} {sum(e.cls == c for e in events):,}" for c in CLASSES)
    return f"{len(events):,} events ({per_class})"


def track_beats(audio: ingest.AudioBuffer, offline: bool) -> dict[str, list[float]]:
    """Beats and downbeats in source-file seconds, from the full mix (never the drum stem)."""
    tracker = beats.BeatTracker(models.get_model(TRACKER, offline))
    beat_times, downbeat_times = (audio.start_s + t for t in tracker.track(audio.mono))
    return {"beats": beat_times.round(3).tolist(), "downbeats": downbeat_times.round(3).tolist()}


def _track_summary(ctx: RunContext, tracked: dict[str, list[float]]) -> str:
    b = tracked["beats"]
    tempo = f", about {60 / float(np.median(np.diff(b))):.0f} BPM" if len(b) > 1 else ""
    return f"{len(b):,} beats{tempo}"


def _quantize(
    ctx: RunContext, events: list[DrumEvent], tracked: dict[str, list[float]]
) -> QuantizedScore:
    cfg = ctx.config
    tempo_map = beats.tempo_map(
        np.array(tracked["beats"]),
        np.array(tracked["downbeats"]),
        beats_per_bar=cfg.beats_per_bar or 4,
        bpm=cfg.bpm,
        first_downbeat=cfg.first_downbeat,
        time_signature_given=cfg.beats_per_bar is not None,
    )
    return review.flag(quantize(events, tempo_map, cfg.grid))


def _quantize_summary(ctx: RunContext, score: QuantizedScore) -> str:
    grids = {(q.measure, q.beat): q.grid for e in score.events if (q := e.quantized)}
    triplets = sum(g == "triplet" for g in grids.values())
    merged = sum("merged" in e.flags for e in score.events)
    return f"grid {ctx.config.grid}: {triplets} of {len(grids)} beats in triplets, {merged} merged"


def _metadata(ctx: RunContext) -> dict[str, Any]:
    """The source, settings and models sections of events.json, also used by the report."""
    cfg = ctx.config
    return {
        "source": {
            "file": cfg.input.name,
            "sha256": ctx.source_sha256,
            "duration_s": ingest.source_duration(cfg.input),  # header only: ingest may be cached
            "start_s": cfg.start,
            "end_s": cfg.end,
        },
        "settings": {
            "sensitivity": cfg.sensitivity,
            "start": cfg.start,
            "end": cfg.end,
            "max_duration": cfg.max_duration,
            "separate": cfg.separate,
            "bpm": cfg.bpm,
            "time_signature": f"{cfg.beats_per_bar}/4" if cfg.beats_per_bar else None,
            "first_downbeat": cfg.first_downbeat,
            "grid": cfg.grid,
            "midi_timing": cfg.midi_timing,
            "mapping": cfg.mapping.name if cfg.mapping else None,
            "mark_uncertain": cfg.mark_uncertain,
        },
        "models": {
            "detector": cfg.model,
            "beat_tracker": TRACKER,
            "separator": SEPARATOR if cfg.separate else None,
        },
    }


def _render(ctx: RunContext, events: list[DrumEvent], score: QuantizedScore) -> list[Path]:
    """events.csv gets every detected hit; events.json the score, without merged-away hits."""
    cfg = ctx.config
    csv_data = render.events_csv(events)
    doc = render.events_json(
        score, **_metadata(ctx), csv_sha256=hashlib.sha256(csv_data).hexdigest()
    )
    if not events:
        log.warning("No drum events detected.")
    instruments = mapping.load(cfg.mapping)
    midi = midi_bytes(score, {cls: i.midi_note for cls, i in instruments.items()}, cfg.midi_timing)
    musicxml = musicxml_bytes(score, instruments, cfg.mark_uncertain)
    return render.write_outputs(cfg.out_dir, cfg.input.stem, csv_data, doc, midi, musicxml)


def _report(ctx: RunContext, events: list[DrumEvent], score: QuantizedScore) -> tuple[Path, int]:
    """The report's path, and the number of flagged measures for the progress line."""
    notes = {cls: i.midi_note for cls, i in mapping.load(ctx.config.mapping).items()}
    text = review.build_report(score, events, **_metadata(ctx), midi_notes=notes)
    path = render.write_report(ctx.config.out_dir, ctx.config.input.stem, text)
    return path, len(score.measure_flags)


def _detect(ctx: RunContext, audio: ingest.AudioBuffer) -> list[DrumEvent]:
    cfg = ctx.config
    detector: detect.Detector
    if cfg.model == models.BASELINE:
        detector = detect.BaselineDetector()
    else:
        detector = detect.ModelDetector(models.get_model(cfg.model, cfg.offline))
    return detector.detect(audio, cfg.sensitivity)


def _dump_audio(audio: ingest.AudioBuffer) -> bytes:
    out = io.BytesIO()  # .npz holds plain arrays only: no pickle on load
    np.savez(out, samples=audio.samples, start_s=audio.start_s, duration=audio.source_duration_s)
    return out.getvalue()


def _load_audio(data: bytes) -> ingest.AudioBuffer:
    with np.load(io.BytesIO(data), allow_pickle=False) as z:
        return ingest.AudioBuffer(z["samples"], float(z["start_s"]), float(z["duration"]))


STAGES = [
    Stage(
        "ingest",
        run=lambda ctx: ingest.load_audio(
            ctx.config.input, ctx.config.start, ctx.config.end, ctx.config.max_duration
        ),
        summary=_ingest_summary,
        params=("start", "end", "max_duration"),
        cached=False,
    ),
    # Only with --separate: the drum stem (mono) replaces the mix for detection. Cached, since it
    # is slow; a 10-minute stem takes about 100 MB.
    Stage(
        "separate",
        run=lambda ctx, audio: isolate_drums(audio, ctx.config.offline, ctx.config.device),
        summary=lambda ctx, stem: "drum stem",
        deps=("ingest",),
        params=("separator_fingerprint",),
        dump=_dump_audio,
        load=_load_audio,
        suffix=".npz",
    ),
    Stage(
        "detect",
        run=_detect,
        summary=_detect_summary,
        deps=("ingest",),
        params=("sensitivity", "model_fingerprint"),
        dump=lambda events: json.dumps([event_to_json(e) for e in events]).encode(),
        load=lambda data: [event_from_json(d) for d in json.loads(data)],
    ),
    # Raw beats only: the tempo map (with --bpm, --time-signature, --first-downbeat) is built when
    # quantizing, so changing those options never re-runs the network.
    Stage(
        "track",
        run=lambda ctx, audio: track_beats(audio, ctx.config.offline),
        summary=_track_summary,
        deps=("ingest",),
        params=("tracker_fingerprint",),
    ),
    # Not cached: it takes milliseconds.
    Stage(
        "quantize",
        run=_quantize,
        summary=_quantize_summary,
        deps=("detect", "track"),
        cached=False,
    ),
    Stage(
        "render",
        run=_render,
        summary=lambda ctx, paths: ", ".join(p.name for p in paths),
        deps=("detect", "quantize"),
        cached=False,
    ),
    Stage(
        "report",
        run=_report,
        summary=lambda ctx, out: f"{out[0].name}: {out[1]} measures flagged for review",
        deps=("detect", "quantize"),
        cached=False,
    ),
]


def stages_for(config: Config) -> list[Stage]:
    """STAGES for this run: with --separate, detection reads the drum stem instead of the mix."""
    if not config.separate:
        return [s for s in STAGES if s.name != "separate"]
    return [dataclasses.replace(s, deps=("separate",)) if s.name == "detect" else s for s in STAGES]


def run(ctx: RunContext, stages: Sequence[Stage] | None = None) -> dict[str, Any]:
    """Run or load every stage that is needed, and return the outputs by stage name."""
    stages = stages_for(ctx.config) if stages is None else stages
    keys: dict[str, str] = {}
    for s in stages:
        params = {p: str(getattr(ctx.config, p)) for p in s.params}
        payload = [version("drumtx"), ctx.source_sha256, s.name, s.version, params]
        payload += [keys[d] for d in s.deps]
        keys[s.name] = hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:16]

    def path(s: Stage) -> Path:
        return ctx.cache_dir / f"{s.name}-{keys[s.name]}{s.suffix}"

    hit = {s.name: s.cached and not ctx.config.no_cache and path(s).exists() for s in stages}
    runs: set[str] = set()
    for s in reversed(stages):
        dependents = [t for t in stages if s.name in t.deps]
        if s.cached:
            needed = not hit[s.name]
        else:
            needed = not dependents or any(t.name in runs for t in dependents)
        if needed:
            runs.add(s.name)

    out: dict[str, Any] = {}
    for i, s in enumerate(stages, start=1):
        if s.name in runs:
            out[s.name] = s.run(ctx, *(out[d] for d in s.deps))
            if s.cached:
                ctx.cache_dir.mkdir(parents=True, exist_ok=True)
                tmp = path(s).with_suffix(".tmp")  # a crash mid-write leaves no partial entry
                tmp.write_bytes(s.dump(out[s.name]))
                tmp.replace(path(s))
                for old in ctx.cache_dir.glob(f"{s.name}-*{s.suffix}"):  # one entry per stage
                    if old != path(s):
                        old.unlink()
            status = s.summary(ctx, out[s.name])
        elif hit[s.name]:
            out[s.name] = s.load(path(s).read_bytes())
            status = s.summary(ctx, out[s.name]) + " (cached)"
        else:
            status = "skipped: later stages are cached"
        log.info("[%d/%d] %-10s %s", i, len(stages), s.name.capitalize(), status)
        log.debug("        key %s", keys[s.name])
    return out
