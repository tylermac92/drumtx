"""Stage orchestration and the stage cache (Technical Design Document §6–7).

Each stage's cache key covers the source file's SHA-256, the stage's name and version, the options
it reads, and the keys of the stages it depends on. So changing a quantize option re-runs quantize
and everything after it, and reuses the cached detection.

- A cached stage (detect, track, quantize) loads its output from the cache when the key matches.
- An uncached stage that others depend on (ingest) runs only when one of them has to run.
- An uncached stage that nothing depends on (render, report) always runs.

The cache keeps only the newest entry per stage, so it cannot grow without limit.
"""

import hashlib
import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Any

from drumtx import ingest
from drumtx.detect import BaselineDetector, Preset
from drumtx.schema import CLASSES, DrumEvent, event_from_json, event_to_json

log = logging.getLogger("drumtx")
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
    no_cache: bool = False


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


def _ingest_summary(ctx: RunContext, audio: ingest.AudioBuffer) -> str:
    minutes, seconds = divmod(round(audio.duration_s), 60)
    channels = {1: "mono", 2: "stereo"}.get(audio.samples.shape[1], f"{audio.samples.shape[1]} ch")
    return f"{ctx.config.input.name}  {minutes}:{seconds:02d}, {channels}"


def _detect_summary(ctx: RunContext, events: list[DrumEvent]) -> str:
    per_class = ", ".join(f"{c} {sum(e.cls == c for e in events):,}" for c in CLASSES)
    return f"{len(events):,} events ({per_class})"


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
    Stage(
        "detect",
        run=lambda ctx, audio: BaselineDetector().detect(audio, ctx.config.sensitivity),
        summary=_detect_summary,
        deps=("ingest",),
        params=("sensitivity",),
        dump=lambda events: json.dumps([event_to_json(e) for e in events]).encode(),
        load=lambda data: [event_from_json(d) for d in json.loads(data)],
    ),
]


def run(ctx: RunContext, stages: Sequence[Stage] = STAGES) -> dict[str, Any]:
    """Run or load every stage that is needed, and return the outputs by stage name."""
    keys: dict[str, str] = {}
    for s in stages:
        params = {p: str(getattr(ctx.config, p)) for p in s.params}
        payload = [version("drumtx"), ctx.source_sha256, s.name, s.version, params]
        payload += [keys[d] for d in s.deps]
        keys[s.name] = hashlib.sha256(json.dumps(payload).encode()).hexdigest()[:16]

    def path(s: Stage) -> Path:
        return ctx.cache_dir / f"{s.name}-{keys[s.name]}.json"

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
                for old in ctx.cache_dir.glob(f"{s.name}-*.json"):  # keep one entry per stage
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
