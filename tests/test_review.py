"""M3-3: review flags on events and measures."""

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from typer.testing import CliRunner

from drumtx import review
from drumtx.beats import tempo_map
from drumtx.cli import app
from drumtx.ingest import SAMPLE_RATE
from drumtx.quantize import quantize
from drumtx.schema import DrumClass, DrumEvent, MeasureFlags, QuantizedScore
from drumtx.synth import render

runner = CliRunner()


def flagged(times: list[float], bpm: float = 120, confidence: float = 0.9) -> QuantizedScore:
    """Snares at `times` (in beats from bar 1) on a steady 4-bar tempo map at `bpm`."""
    beat_s = 60 / bpm
    t = np.arange(16) * beat_s
    events = [DrumEvent(round(b * beat_s, 4), "snare", confidence, 100) for b in times]
    return review.flag(quantize(events, tempo_map(t, t[::4])))


def by_measure(score: QuantizedScore) -> dict[int, tuple[str, ...]]:
    return {m.measure: m.flags for m in score.measure_flags}


def test_clean_groove_has_no_flags() -> None:
    score = flagged([0, 1, 2, 3, 4.5, 5.25])
    assert score.measure_flags == () and all(e.flags == () for e in score.events)


def test_uncertain() -> None:
    score = flagged([4, 5], confidence=0.25)
    assert all(e.flags == ("uncertain",) for e in score.events)
    assert by_measure(score) == {2: ("uncertain",)}
    strict = review.flag(score, review.Thresholds(confidence=0.2))
    assert strict.measure_flags == () and all(e.flags == () for e in strict.events)


def test_merged() -> None:
    beat_s = 0.5
    t = np.arange(16) * beat_s
    events = [DrumEvent(2.0, "snare", 0.9, 100), DrumEvent(2.04, "snare", 0.7, 100)]
    score = review.flag(quantize(events, tempo_map(t, t[::4])))
    assert [e.flags for e in score.events] == [("merged",)]
    assert by_measure(score) == {2: ("merged",)}


@pytest.mark.parametrize("bpm", [60, 200])
def test_off_grid_uses_a_fraction_of_the_grid_step(bpm: float) -> None:
    """0.45 of a 16th is 112.5 ms at 60 BPM and 34 ms at 200 BPM: both flagged; 0.35 is not."""
    late = [8 + 0.45 / 4, 9 + 0.45 / 4, 10 + 0.45 / 4]  # three hits 0.45 of a 16th late, bar 3
    assert by_measure(flagged(late, bpm)) == {3: ("off_grid",)}
    assert flagged([8 + 0.35 / 4, 9 + 0.35 / 4, 10 + 0.35 / 4], bpm).measure_flags == ()
    assert flagged(late[:2], bpm).measure_flags == ()  # two hits off the grid are allowed


def test_tempo() -> None:
    lengths = np.full(16, 0.5)
    lengths[4:8] = 0.56  # measure 2 is 12% slower
    t = np.concatenate([[0], np.cumsum(lengths)])
    score = review.flag(quantize([DrumEvent(0.0, "kick", 0.9, 100)], tempo_map(t, t[::4])))
    assert by_measure(score) == {2: ("tempo",)}


def test_measure_flags_combine_in_schema_order() -> None:
    score = flagged([8.1125, 9.1125, 10.1125, 9.5], confidence=0.25)
    assert score.measure_flags == (MeasureFlags(3, ("uncertain", "off_grid")),)


def test_flags_in_events_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With every hit uncertain, flags reach events.json (conftest's tracker: bar 1 at 0 s)."""
    wav = tmp_path / "in.wav"
    sf.write(wav, render([(1.0, "snare", 100)], 4.0), SAMPLE_RATE)
    flag = review.flag
    monkeypatch.setattr(review, "flag", lambda s: flag(s, review.Thresholds(1.01)))
    out = tmp_path / "out"
    result = runner.invoke(
        app, ["transcribe", str(wav), "-o", str(out), "-q", "--model", "baseline"]
    )
    assert result.exit_code == 0, result.stderr
    doc = json.loads((out / "in.events.json").read_text())
    snares = [e for e in doc["events"] if e["class"] == "snare"]
    assert snares and all(e["flags"] == ["uncertain"] for e in doc["events"])
    assert {"measure": 1, "flags": ["uncertain"]} in doc["measure_flags"]
    report = (out / "in.report.md").read_text()
    assert "| 0:00.00 | 0:02.00 |" in report  # measure 1, from the stand-in tracker's beats


# M5-1: the review report


def report(score: QuantizedScore, events: list[DrumEvent] | None = None) -> str:
    source = {"file": "song.wav", "duration_s": 8.0, "start_s": None, "end_s": None}
    notes: dict[DrumClass, int] = {"kick": 36, "snare": 38, "hihat": 42, "tom": 47, "cymbal": 49}
    events = list(score.events) if events is None else events
    return review.build_report(score, events, source, {"grid": "auto"}, {"detector": "x"}, notes)


def test_measure_times() -> None:
    t = 1 + np.arange(16) * 0.5  # bar 1 at 1 s
    tm = tempo_map(t, t[::4])
    assert review.measure_times(tm, 1) == (1.0, 3.0)
    assert review.measure_times(tm, 5) == (9.0, 11.0)  # past the last beat (8.5 s)
    assert review.measure_times(tm, 0) == (0.0, 1.0)  # the pickup starts at 0 s at the earliest


def test_report_lists_flagged_measures_with_times() -> None:
    text = report(flagged([4, 5, 8], confidence=0.25))
    assert "| 2       | 0:02.00 | 0:04.00 | 2 uncertain |" in text
    assert "| 3       | 0:04.00 | 0:06.00 | 1 uncertain |" in text
    assert "| snare  | 38        | 3        | 3            | 3         |" in text
    assert "about 120 BPM (estimated), stable: 100% of beats" in text
    assert "**Flagged:** 2 of 4 measures" in text
    for heading in ("Summary", "Hits per class", "Suggested next steps", "Settings", "Limitations"):
        assert f"\n## {heading}\n" in text
    assert "drumtx preview song.wav song.events.json --split-stereo" in text


def test_report_reasons() -> None:
    lengths = np.full(16, 0.5)
    lengths[4:8] = 0.56
    t = np.concatenate([[0], np.cumsum(lengths)])
    tempo = review.flag(quantize([DrumEvent(0.0, "kick", 0.9, 100)], tempo_map(t, t[::4])))
    assert "| 2       | 0:02.00 | 0:04.24 | tempo 107 BPM |" in report(tempo)
    beat_s = 0.5
    t = np.arange(16) * beat_s
    merged_events = [DrumEvent(2.0, "snare", 0.9, 100), DrumEvent(2.04, "snare", 0.7, 100)]
    merged = review.flag(quantize(merged_events, tempo_map(t, t[::4])))
    text = report(merged, merged_events)
    assert "| 2       | 0:02.00 | 0:04.00 | 1 merged |" in text
    assert "| snare  | 38        | 2        | 1            | 0         |" in text
    assert "3 off the grid" in report(flagged([8.1125, 9.1125, 10.1125]))


def test_report_without_beats() -> None:
    score = quantize([DrumEvent(1.0, "kick", 0.9, 100)], tempo_map(np.array([1.0]), np.array([])))
    text = report(score)
    assert "not found (fewer than two beats)" in text and "No measures are flagged" in text


def test_report_tempo_of_a_clamped_pickup() -> None:
    """A beat tracked in the silence before bar 1: measure 0 starts at 0 s in the report, and its
    tempo comes from its beat (0.68 s, 88 BPM), not from that clamped span."""
    t = np.concatenate([[0.32], 1.0 + np.arange(16) * 0.625])
    score = review.flag(quantize([DrumEvent(1.0, "kick", 0.9, 100)], tempo_map(t, t[1::4])))
    assert by_measure(score) == {0: ("tempo",)}
    assert "| 0       | 0:00.00 | 0:01.00 | tempo 88 BPM |" in report(score)
