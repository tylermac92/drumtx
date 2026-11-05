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
from drumtx.schema import DrumEvent, MeasureFlags, QuantizedScore
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
    score = flagged([4, 5], confidence=0.45)
    assert all(e.flags == ("uncertain",) for e in score.events)
    assert by_measure(score) == {2: ("uncertain",)}
    strict = review.flag(score, review.Thresholds(confidence=0.4))
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
    """0.3 of a 16th is 75 ms at 60 BPM and 22.5 ms at 200 BPM: both flagged; 0.2 is not."""
    late = [8 + 0.3 / 4, 9 + 0.3 / 4]  # two hits 0.3 of a 16th late, in measure 3
    assert by_measure(flagged(late, bpm)) == {3: ("off_grid",)}
    assert flagged([8 + 0.2 / 4, 9 + 0.2 / 4], bpm).measure_flags == ()
    assert flagged([8 + 0.3 / 4, 9], bpm).measure_flags == ()  # one hit off the grid is allowed


def test_tempo() -> None:
    lengths = np.full(16, 0.5)
    lengths[4:8] = 0.56  # measure 2 is 12% slower
    t = np.concatenate([[0], np.cumsum(lengths)])
    score = review.flag(quantize([DrumEvent(0.0, "kick", 0.9, 100)], tempo_map(t, t[::4])))
    assert by_measure(score) == {2: ("tempo",)}


def test_measure_flags_combine_in_schema_order() -> None:
    score = flagged([8.075, 9.075, 9.5], confidence=0.45)
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
