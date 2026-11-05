"""The MIDI writer (Technical Design Document §5; M3-4): a type 1 Standard MIDI File.

- Track 0 holds the time signature and a tempo change at every beat of the tempo map. So a DAW's
  bar grid follows the music, and MIDI time 0 is the start of the audio file.
- Track 1 holds the drums on channel 10. With `quantized` timing, notes sit at their grid
  positions, which the tempo track puts on the audio's beat-grid times. With `performance`,
  notes sit at their detected times.
- From 0 s to the first beat, a lead-in lasts a whole number of 32nd notes, near the music's
  tempo (its own tempo makes it end exactly on that beat). Notes in the lead-in are placed
  approximately; from the first beat on, they are on the beat-grid times.
- The first bar runs from 0 s to the first bar line, so it is usually a pickup with its own time
  signature (such as 1/4 or 13/32), as notation apps expect. MIDI bar numbers count from it.
- Without a tempo map (fewer than two beats), the file is at 120 BPM with the detected times.
"""

import io
from collections.abc import Mapping
from typing import Literal

import mido
import numpy as np

from drumtx.quantize import SLOTS, beat_grid
from drumtx.schema import DrumClass, QuantizedScore

MidiTiming = Literal["quantized", "performance"]
TICKS_PER_BEAT = 480  # 16ths (120 ticks) and triplets (160) land on whole ticks
NOTE_TICKS = 60  # a 32nd note; drum sounds ignore the length
CHANNEL = 9  # channel 10, counted from 0
MAX_TEMPO = 0xFFFFFF  # microseconds per beat, the largest a set_tempo event holds
LEAD_TICKS = TICKS_PER_BEAT // 8  # the lead-in is a whole number of 32nds


def _tempo_points(score: QuantizedScore) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Tick and microsecond tempo at each tempo change, the tick of beat number 0 (measure 0
    beat 1; it may be negative), and the length of the first bar in ticks.

    The microseconds are rounded as the file stores them, so the times computed from them are
    the times a MIDI player will use.
    """
    tm = score.tempo_map
    per_bar = tm.time_signatures[0].beats
    if len(tm.beats) < 2:
        return np.array([0]), np.array([500_000]), 0, per_bar * TICKS_PER_BEAT  # 120 BPM
    last = max([e.time_s for e in score.events] + [tm.beats[-1].time_s])
    times, number = beat_grid(tm, 0.0, last)
    first = int(np.searchsorted(times, 0.0))  # the first beat at or after 0 s
    times, number = times[first:], number[first:]
    lead = 0  # ticks from 0 s to that beat, in whole 32nds
    if times[0] > 0:
        lead = LEAD_TICKS * max(1, round(times[0] / (times[1] - times[0]) * 8))
        times = np.insert(times, 0, 0.0)
    ticks = np.concatenate([[0] if lead else [], lead + (number - number[0]) * TICKS_PER_BEAT])
    seconds_per_tick = np.diff(times) / np.diff(ticks)
    tempo = np.clip(np.round(seconds_per_tick * 1e6 * TICKS_PER_BEAT), 1, MAX_TEMPO).astype(int)
    first_bar = lead + int(-number[0] % per_bar) * TICKS_PER_BEAT or per_bar * TICKS_PER_BEAT
    return ticks[:-1].astype(int), tempo, lead - int(number[0]) * TICKS_PER_BEAT, first_bar


def _seconds_to_ticks(t: np.ndarray, ticks: np.ndarray, tempo: np.ndarray) -> np.ndarray:
    """Inverse of the tempo track, extending its last tempo."""
    starts = np.concatenate([[0.0], np.cumsum(np.diff(ticks) * tempo[:-1] / 1e6 / TICKS_PER_BEAT)])
    k = np.searchsorted(starts, t, side="right") - 1
    out: np.ndarray = np.round(ticks[k] + (t - starts[k]) * 1e6 * TICKS_PER_BEAT / tempo[k])
    return out.astype(int)


def _track(messages: list[tuple[int, mido.Message | mido.MetaMessage]]) -> mido.MidiTrack:
    """A track from (absolute tick, message), in order; at one tick, note-offs come first."""
    track = mido.MidiTrack()
    now = 0
    for tick, msg in sorted(messages, key=lambda m: (m[0], m[1].type != "note_off")):
        track.append(msg.copy(time=tick - now))
        now = tick
    return track


def midi_bytes(
    score: QuantizedScore, notes: Mapping[DrumClass, int], timing: MidiTiming = "quantized"
) -> bytes:
    ticks, tempo, zero, first_bar = _tempo_points(score)
    per_bar = score.tempo_map.time_signatures[0].beats
    numerator, denominator = first_bar // LEAD_TICKS, 32
    while numerator % 2 == 0 and denominator > 4:
        numerator, denominator = numerator // 2, denominator // 2
    conductor: list[tuple[int, mido.Message | mido.MetaMessage]] = [
        (0, mido.MetaMessage("time_signature", numerator=numerator, denominator=denominator))
    ]
    if first_bar != per_bar * TICKS_PER_BEAT:
        sig = mido.MetaMessage("time_signature", numerator=per_bar, denominator=4)
        conductor.append((first_bar, sig))
    conductor += [
        (int(k), mido.MetaMessage("set_tempo", tempo=int(us)))
        for k, us in zip(ticks, tempo, strict=True)
    ]

    raw = _seconds_to_ticks(np.array([e.time_s for e in score.events]), ticks, tempo)
    drums: list[tuple[int, mido.Message | mido.MetaMessage]] = [
        (0, mido.MetaMessage("track_name", name="Drums"))
    ]
    for e, at in zip(score.events, raw.tolist(), strict=True):
        if timing == "quantized" and (q := e.quantized):
            n = q.measure * per_bar + q.beat - 1
            at = max(0, zero + n * TICKS_PER_BEAT + (q.slot - 1) * TICKS_PER_BEAT // SLOTS[q.grid])
        note = notes[e.cls]
        drums.append((at, mido.Message("note_on", channel=CHANNEL, note=note, velocity=e.velocity)))
        drums.append((at + NOTE_TICKS, mido.Message("note_off", channel=CHANNEL, note=note)))

    out = io.BytesIO()
    mido.MidiFile(
        type=1, ticks_per_beat=TICKS_PER_BEAT, tracks=[_track(conductor), _track(drums)]
    ).save(file=out)
    return out.getvalue()
