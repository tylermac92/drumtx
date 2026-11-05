"""M3-2: the quantizer: grids per beat, slots, merges, residuals, and its invariants."""

import json
import logging
from pathlib import Path

import make_fixtures as mf
import numpy as np
import pytest
from typer.testing import CliRunner

from drumtx import pipeline
from drumtx.beats import tempo_map
from drumtx.cli import app
from drumtx.quantize import GridOption, quantize
from drumtx.schema import CLASSES, DrumEvent, QuantizedScore, TempoMap

runner = CliRunner()


def steady(bpm: float, bars: int = 8, per_bar: int = 4, start: float = 2.0) -> TempoMap:
    """Beats at `bpm`, with bar 1 at `start`."""
    t = start + np.arange(bars * per_bar) * 60 / bpm
    return tempo_map(t, t[::per_bar], beats_per_bar=per_bar)


def hit(t: float, cls: str = "snare", confidence: float = 0.9) -> DrumEvent:
    return DrumEvent(round(t, 4), cls, confidence, 100)  # type: ignore[arg-type]


def where(score: QuantizedScore) -> list[tuple[str, int, int, str, int]]:
    return [(e.cls, q.measure, q.beat, q.grid, q.slot) for e in score.events if (q := e.quantized)]


def groove(bpm: float, per_beat: int, seed: int) -> tuple[list[DrumEvent], list[float], list]:  # type: ignore[type-arg]
    """Two bars of hi-hats on every grid point, kick on 1 and 3, snare on 2 and 4, each moved by
    up to ±12% of a grid step. Returns the hits, their offsets in ms and their positions."""
    rng = np.random.default_rng(seed)
    beat_s = 60 / bpm
    events, offsets, want = [], [], []
    for b in range(8):
        parts = [("hihat", s) for s in range(per_beat)] + [("kick" if b % 2 == 0 else "snare", 0)]
        for cls, s in parts:
            offset = rng.uniform(-0.12, 0.12) * beat_s / per_beat
            events.append(hit(2.0 + beat_s * (b + s / per_beat) + offset, cls))
            offsets.append(offset * 1000)
            grid = "16th" if per_beat == 4 else "triplet"
            want.append((cls, 1 + b // 4, b % 4 + 1, grid, s + 1))
    return events, offsets, want


@pytest.mark.parametrize("bpm", [60, 120, 200])
@pytest.mark.parametrize("per_beat", [4, 3])
def test_grooves_at_known_tempo(bpm: float, per_beat: int) -> None:
    """Straight 16ths and triplets: every position exact, residuals within 1 ms of the offsets."""
    for seed in range(5):
        events, offsets, want = groove(bpm, per_beat, seed)
        score = quantize(events, steady(bpm))
        got = {(e.time_s, e.cls): e for e in score.events}
        for e, offset, w in zip(events, offsets, want, strict=True):
            placed = got[e.time_s, e.cls]
            assert where(QuantizedScore(score.tempo_map, (placed,))) == [w]
            assert placed.quantized and abs(placed.quantized.residual_ms - offset) < 1


def test_auto_picks_the_grid_per_beat() -> None:
    beat_s = 0.5  # 120 BPM, from 2.0 s (bar 1)
    events = [hit(2.0 + x * beat_s, "hihat") for x in (0, 0.25, 0.5, 0.75)]  # 16ths
    events += [hit(2.5 + x * beat_s, "hihat") for x in (0, 1 / 3, 2 / 3)]  # triplets
    events += [hit(3.0, "hihat"), hit(3.0 + 2 / 3 * beat_s, "hihat")]  # one swung 8th: 16ths
    grids = {(m, b): g for _, m, b, g, _ in where(quantize(events, steady(120)))}
    assert grids == {(1, 1): "16th", (1, 2): "triplet", (1, 3): "16th"}
    forced = {g for *_, g, _ in where(quantize(events, steady(120), grid="triplet"))}
    assert forced == {"triplet"}


def test_hit_just_before_a_beat_goes_to_that_beat() -> None:
    score = quantize([hit(2.49)], steady(120))
    assert where(score) == [("snare", 1, 2, "16th", 1)]
    assert score.events[0].quantized and score.events[0].quantized.residual_ms == -10.0
    assert score.events[0].quantized.residual_frac == -0.08


def test_collisions_merge_into_the_most_confident_hit() -> None:
    events = [hit(2.0, confidence=0.6), hit(2.03, confidence=0.9), hit(2.0, "kick")]
    score = quantize(events, steady(120))
    assert [(e.cls, e.time_s, e.flags) for e in score.events] == [
        ("kick", 2.0, ()),
        ("snare", 2.03, ("merged",)),
    ]


def test_hits_beyond_the_tracked_beats() -> None:
    tm = steady(120, bars=2, start=1.0)  # measures 1–2: beats from 1.0 s to 4.5 s
    score = quantize([hit(0.75), hit(5.25), hit(0.2)], tm)
    assert where(score) == [
        ("snare", 0, 3, "16th", 3),  # measure 0 (the pickup) spans -1.0 s to 1.0 s
        ("snare", 0, 4, "16th", 3),
        ("snare", 3, 1, "16th", 3),
    ]


def test_hits_before_measure_0_are_left_out(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="drumtx"):
        score = quantize([hit(0.2), hit(1.0)], steady(120, start=3.0))  # measure 0 from 1.0 s
    assert [e.time_s for e in score.events] == [1.0]
    assert "1 hits before measure 0" in caplog.text


def test_without_beats_nothing_is_placed() -> None:
    tm = tempo_map(np.array([1.0]), np.array([1.0]))
    assert quantize([hit(1.2)], tm).events[0].quantized is None


@pytest.mark.parametrize("grid", ["auto", "16th", "triplet"])
def test_invariants_on_random_input(grid: GridOption) -> None:
    """Property test (seeded): each hit gets one position, every lost hit is covered by a merge,
    snapped times agree with the beats, and quantizing again changes nothing."""
    rng = np.random.default_rng(0)
    lost = 0
    for _ in range(200):
        per_bar = int(rng.integers(2, 8))
        intervals = 60 / rng.uniform(50, 220) * rng.uniform(0.9, 1.1, size=int(rng.integers(2, 40)))
        t = 0.3 + np.concatenate([[0], np.cumsum(intervals)])
        tm = tempo_map(t, t[int(rng.integers(0, len(t))) :: per_bar], beats_per_bar=per_bar)
        times = rng.uniform(t[0], t[-1] + 2, size=int(rng.integers(1, 80)))
        events = [
            DrumEvent(round(float(x), 3), CLASSES[int(rng.integers(0, 5))], float(rng.random()), 64)
            for x in times
        ]
        score = quantize(events, tm, grid)
        assert quantize(score.events, tm, grid) == score
        kept = {(e.time_s, e.cls) for e in score.events}
        merged = [e for e in score.events if "merged" in e.flags]
        first = tm.beats[0]
        measure_0 = first.time_s - (first.measure * per_bar + first.beat - 1) * (t[1] - t[0])
        beat_s = {(b.measure, b.beat): b.time_s for b in tm.beats}
        for e in score.events:
            q = e.quantized
            assert q is not None and q.measure >= 0 and 1 <= q.beat <= per_bar
            assert 1 <= q.slot <= (4 if q.grid == "16th" else 3) and abs(q.residual_frac) <= 0.5
            if (q.measure, q.beat) in beat_s and q.slot == 1:
                assert abs(e.time_s - q.residual_ms / 1000 - beat_s[q.measure, q.beat]) < 1e-3
        for e in events:  # a lost hit was merged into one of its class, or is before measure 0
            if (e.time_s, e.cls) not in kept and e.time_s > measure_0 + intervals.max():
                assert any(
                    m.cls == e.cls and abs(m.time_s - e.time_s) < intervals.max() / 3
                    for m in merged
                ), e
        lost += len(events) - len(score.events)
    assert lost > 100  # the cases do exercise merging


def placed_fixture(tmp_path: Path, p: mf.Pattern, monkeypatch: pytest.MonkeyPatch) -> list:  # type: ignore[type-arg]
    """Transcribe a synthetic fixture with beats at its tempo (bar 1 at the first hit)."""
    beat_s = 60 / p.bpm
    beat_times = np.arange(0, mf.timed_hits(p)[-1][0] + mf.TAIL_S, beat_s).round(3)
    monkeypatch.setattr(
        pipeline,
        "track_beats",
        lambda audio, offline: {
            "beats": beat_times.tolist(),
            "downbeats": beat_times[1::4].tolist(),
        },
    )
    wav = mf.write(p, tmp_path)
    result = runner.invoke(
        app, ["transcribe", str(wav), "-o", str(tmp_path), "-q", "--model", "baseline"]
    )
    assert result.exit_code == 0, result.stderr
    return json.loads((tmp_path / f"{p.name}.events.json").read_text())["events"]  # type: ignore[no-any-return]


@pytest.mark.parametrize("name", ["straight16", "triplets"])
def test_synthetic_audio_end_to_end(
    tmp_path: Path, name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rendered audio → baseline detector → quantizer: every hit of the pattern is at its exact
    position. Extra hits are not checked: the baseline's band bleed adds many (decision 0009)."""
    p = next(p for p in mf.PATTERNS if p.name == name)
    k = 4 if name == "straight16" else 3
    want = {
        (c, int(b // 4) + 1, int(b % 4) + 1, "16th" if k == 4 else "triplet", int(b % 1 * k) + 1)
        for b, c in p.hits
    }
    events = placed_fixture(tmp_path, p, monkeypatch)
    got = {
        (e["class"], q["measure"], q["beat"], q["grid"], q["slot"])
        for e in events
        if (q := e["quantized"])
    }
    assert len(want) == len(p.hits) and want <= got
