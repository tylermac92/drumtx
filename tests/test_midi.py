"""M3-4: the MIDI writer: tempo track, channel 10, quantized and performance timing."""

import io
import json
import os
from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile as sf
from typer.testing import CliRunner

from drumtx import mapping
from drumtx.beats import tempo_map
from drumtx.cli import app
from drumtx.ingest import SAMPLE_RATE
from drumtx.midi import midi_bytes
from drumtx.quantize import quantize
from drumtx.schema import (
    CLASSES,
    Beat,
    DrumEvent,
    QuantizedScore,
    TempoMap,
    TimeSignature,
    event_from_json,
)
from drumtx.synth import render

NOTES = {cls: i.midi_note for cls, i in mapping.load().items()}
GOLDEN = Path(__file__).parent / "golden"
EXAMPLE = Path(__file__).parents[1] / "docs" / "schema" / "examples" / "groove.events.json"


def notes_s(data: bytes) -> list[tuple[float, int, int, int]]:
    """(seconds, channel, note, velocity) of every note-on, as a MIDI player times them."""
    now, out = 0.0, []
    for msg in mido.MidiFile(file=io.BytesIO(data)):
        now += msg.time
        if msg.type == "note_on":
            out.append((now, msg.channel, msg.note, msg.velocity))
    return out


def drifting(seed: int) -> TempoMap:
    """A tempo map from 1.7 s with a pickup, drifting ±10% around a random tempo."""
    rng = np.random.default_rng(seed)
    t = 1.7 + np.concatenate(
        [[0], np.cumsum(60 / rng.uniform(60, 200) * rng.uniform(0.9, 1.1, 40))]
    )
    return tempo_map(t, t[2::4])


@pytest.mark.parametrize("seed", range(10))
def test_quantized_notes_are_on_the_beat_grid(seed: int) -> None:
    """Within ±5 ms of their snapped times, from the first beat at or after 0 s."""
    tm = drifting(seed)
    rng = np.random.default_rng(seed)
    events = [
        DrumEvent(float(x), CLASSES[int(rng.integers(0, 5))], 0.9, int(rng.integers(1, 128)))
        for x in np.sort(rng.uniform(0, tm.beats[-1].time_s + 2, 150)).round(3)
    ]
    score = quantize(events, tm)
    head = tm.beats[1].time_s - tm.beats[0].time_s
    first = tm.beats[0].time_s - head * int(tm.beats[0].time_s / head)  # first grid beat >= 0 s
    snapped = sorted(
        (NOTES[e.cls], e.time_s - e.quantized.residual_ms / 1000, e.velocity)
        for e in score.events
        if e.quantized
    )
    got = notes_s(midi_bytes(score, NOTES))
    assert len(got) == len(snapped) and {c for _, c, _, _ in got} == {9}
    for (note, want_s, velocity), (got_s, _, got_note, got_velocity) in zip(
        snapped, sorted(got, key=lambda n: (n[2], n[0])), strict=True
    ):
        if want_s >= first - 1e-9:
            assert abs(got_s - want_s) <= 0.005
            assert (got_note, got_velocity) == (note, velocity)


def test_performance_timing_keeps_the_detected_times() -> None:
    score = quantize([DrumEvent(t, "snare", 0.9, 90) for t in (1.913, 2.402, 30.0)], drifting(0))
    got = [round(s, 3) for s, *_ in notes_s(midi_bytes(score, NOTES, "performance"))]
    assert np.allclose(got, [1.913, 2.402, 30.0], atol=0.002)


def test_bars_follow_the_tempo_map() -> None:
    """Measure 1 starts on a bar line: tick 0 is measure 0, a full pickup bar before 2.0 s."""
    t = 2.0 + np.arange(16) * 0.5
    data = midi_bytes(quantize([DrumEvent(2.0, "kick", 0.9, 100)], tempo_map(t, t[::4])), NOTES)
    mid = mido.MidiFile(file=io.BytesIO(data))
    assert mid.type == 1 and mid.ticks_per_beat == 480 and len(mid.tracks) == 2
    sig = next(m for m in mid.tracks[0] if m.type == "time_signature")
    assert (sig.numerator, sig.denominator) == (4, 4)
    on = next(m for m in mid.tracks[1] if m.type == "note_on")
    # measure 0 starts at 0.0 s, so no lead-in bar: measure 1 beat 1 is tick 4 * 480
    assert sum(m.time for m in mid.tracks[1][: mid.tracks[1].index(on) + 1]) == 4 * 480


def test_lead_in_bar_when_measure_0_starts_after_0_s() -> None:
    t = 3.0 + np.arange(8) * 0.5  # measure 0 would start at 1.0 s
    tm = TempoMap(
        tuple(Beat(round(x, 3), i // 4, i % 4 + 1) for i, x in enumerate(t)),
        (TimeSignature(1, 4, 4),),
        "estimated",
        "default",
        "estimated",
    )
    data = midi_bytes(quantize([DrumEvent(3.0, "kick", 0.9, 100)], tm), NOTES)
    assert abs(notes_s(data)[0][0] - 3.0) <= 0.005


def test_without_a_tempo_map_notes_keep_their_times() -> None:
    score = QuantizedScore(
        tempo_map(np.array([1.0]), np.array([1.0])), (DrumEvent(1.25, "kick", 0.9, 100),)
    )
    assert notes_s(midi_bytes(score, NOTES))[0][:3] == pytest.approx((1.25, 9, 36), abs=0.002)


@pytest.mark.parametrize("timing", ["quantized", "performance"])
def test_golden(timing: str) -> None:
    """The schema example groove. DRUMTX_UPDATE_GOLDEN=1 rewrites it after a deliberate change."""
    doc = json.loads(EXAMPLE.read_text())
    tm = doc["tempo_map"]
    score = QuantizedScore(
        TempoMap(
            tuple(Beat(**b) for b in tm["beats"]),
            tuple(TimeSignature(**s) for s in tm["time_signatures"]),
            tm["tempo_source"],
            tm["time_signature_source"],
            tm["first_downbeat_source"],
        ),
        tuple(event_from_json(e) for e in doc["events"]),
    )
    data = midi_bytes(score, NOTES, timing)  # type: ignore[arg-type]
    path = GOLDEN / f"groove.{timing}.mid"
    if os.environ.get("DRUMTX_UPDATE_GOLDEN"):
        path.write_bytes(data)
    assert data == path.read_bytes()


def test_transcribe_writes_the_midi_file(tmp_path: Path) -> None:
    wav, out = tmp_path / "in.wav", tmp_path / "out"
    sf.write(wav, render([(1.0, "kick", 100), (1.5, "snare", 100)], 4.0), SAMPLE_RATE)
    args = ["transcribe", str(wav), "-o", str(out), "-q", "--model", "baseline"]
    assert CliRunner().invoke(app, [*args, "--midi-timing", "performance"]).exit_code == 0
    assert mido.MidiFile(out / "in.mid").type == 1
    (out / "in.events.json").unlink()
    (out / "in.events.csv").unlink()
    (out / "in.musicxml").unlink()
    result = CliRunner().invoke(app, args)  # only in.mid is left, and it is not overwritten
    assert result.exit_code == 2 and "in.mid already exists" in result.stderr
