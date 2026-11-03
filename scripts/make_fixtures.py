"""Synthetic drum fixtures (M1-5): drum patterns rendered with sounds synthesized in code.

    uv run python scripts/make_fixtures.py OUT_DIR [--noise-db -40] [--backing] [--seed 0]

For each pattern, writes <name>.wav (float32, 44.1 kHz), <name>.mid (the reference: channel 10,
General MIDI drum notes) and <name>.onsets.csv (the same hits as an events.csv).
The seed sets the velocities, the noise and the backing track, so output is reproducible.
"""

import argparse
import hashlib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import mido
import numpy as np
import soundfile as sf

from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import DrumClass
from drumtx.synth import render

NOTES: dict[DrumClass, int] = {"kick": 36, "snare": 38, "hihat": 42, "tom": 47, "cymbal": 49}
TICKS_PER_BEAT = 480  # divisible by 3 and 4, so 16ths and triplets land on whole ticks
LEAD_IN_BEATS = 1  # silence before the first hit
TAIL_S = 1.5  # room for the last hit to ring


@dataclass(frozen=True)
class Pattern:
    name: str
    bpm: float
    hits: tuple[tuple[Fraction, DrumClass], ...]  # (beat from the first downbeat, class)


def _bars(n: int, bar: list[tuple[Fraction, DrumClass]]) -> tuple[tuple[Fraction, DrumClass], ...]:
    return tuple((b + 4 * i, c) for i in range(n) for b, c in bar)


F = Fraction


def _every(step: Fraction, cls: DrumClass, count: int) -> list[tuple[Fraction, DrumClass]]:
    return [(step * i, cls) for i in range(count)]


# Two or three classes on the same instant, every beat.
_SIMULTANEOUS: list[tuple[Fraction, DrumClass]] = [
    (F(0), "kick"), (F(0), "cymbal"), (F(1), "snare"), (F(1), "hihat"),
    (F(2), "kick"), (F(2), "tom"), (F(3), "snare"), (F(3), "tom"), (F(3), "hihat"),
    (F(7, 2), "kick"), (F(7, 2), "hihat"),
]  # fmt: skip
PATTERNS = [
    Pattern(
        "straight16",
        100,
        _bars(
            2,
            _every(F(1, 4), "hihat", 16)
            + [(F(0), "kick"), (F(2), "kick"), (F(5, 2), "kick"), (F(1), "snare"), (F(3), "snare")],
        ),
    ),
    Pattern(
        "triplets",
        90,
        _bars(
            2,
            _every(F(1, 3), "hihat", 12)
            + [(F(0), "kick"), (F(2), "kick"), (F(8, 3), "kick"), (F(1), "snare"), (F(3), "snare")],
        ),
    ),
    Pattern(
        "simultaneous",
        110,
        _bars(2, _SIMULTANEOUS),
    ),
]


def timed_hits(p: Pattern, seed: int = 0) -> list[tuple[float, DrumClass, int]]:
    """(time_s, class, velocity), sorted. Velocities vary by ±15 around 95, from the seed."""
    rng = np.random.default_rng(seed)
    beat_s = 60 / p.bpm
    return [
        (float(b + LEAD_IN_BEATS) * beat_s, c, 95 + int(rng.integers(-15, 16)))
        for b, c in sorted(p.hits, key=lambda h: (h[0], h[1]))
    ]


def _backing(n: int, p: Pattern, rng: np.random.Generator) -> np.ndarray:
    """A bass note per beat and a held chord per bar, so the drums sit in a full mix."""
    t = np.arange(n) / SAMPLE_RATE
    beat_n = round(60 / p.bpm * SAMPLE_RATE)
    y = np.zeros(n)
    for start in range(0, n, beat_n):
        root = 55 * 2 ** (int(rng.choice([0, 3, 5, 7])) / 12)  # A1, C2, D2 or E2
        seg = slice(start, min(n, start + beat_n))
        tt = t[seg] - t[start]
        for k, (mult, level) in enumerate([(1, 1.0), (2, 0.5), (3, 0.3)]):
            y[seg] += level * np.sin(2 * np.pi * root * mult * tt + k) * np.exp(-tt * 3)
        if (start // beat_n) % 4 == 0:  # chord: root, third and fifth, two octaves up
            chord = slice(start, min(n, start + 4 * beat_n))
            tc = t[chord] - t[start]
            for semis in (24, 28, 31):
                y[chord] += 0.3 * np.sin(2 * np.pi * root * 2 ** (semis / 12) * tc)
    return y


def audio(
    p: Pattern, seed: int = 0, noise_db: float | None = None, backing: bool = False
) -> np.ndarray:
    hits = timed_hits(p, seed)
    y = render(hits, hits[-1][0] + TAIL_S).astype(np.float64)
    rng = np.random.default_rng(seed + 1)
    if backing:
        b = _backing(len(y), p, rng)
        y += b / np.abs(b).max() * 10 ** (-12 / 20)  # -12 dBFS peak
    if noise_db is not None:
        y += rng.normal(0, 10 ** (noise_db / 20), len(y))
    return y.astype(np.float32)


def pcm_sha256(y: np.ndarray) -> str:
    """Hash of the audio rounded to 16-bit steps: stable across runs and operating systems."""
    return hashlib.sha256(
        np.round(y.astype(np.float64) * 32767).astype("<i4").tobytes()
    ).hexdigest()


def write(
    p: Pattern, out_dir: Path, seed: int = 0, noise_db: float | None = None, backing: bool = False
) -> Path:
    """Write the three files for one pattern; returns the WAV path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"{p.name}.wav"
    sf.write(wav, audio(p, seed, noise_db, backing), SAMPLE_RATE, subtype="FLOAT")
    hits = timed_hits(p, seed)

    midi = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(p.bpm))])
    midi.tracks.append(track)
    now = 0
    for (b, c), (_, _, vel) in zip(sorted(p.hits, key=lambda h: (h[0], h[1])), hits, strict=True):
        tick = int((b + LEAD_IN_BEATS) * TICKS_PER_BEAT)
        track.append(
            mido.Message("note_on", channel=9, note=NOTES[c], velocity=vel, time=tick - now)
        )
        track.append(mido.Message("note_off", channel=9, note=NOTES[c], velocity=0, time=0))
        now = tick
    midi.save(out_dir / f"{p.name}.mid")

    rows = [f"{t:.6f},{c},1.0,{v}" for t, c, v in hits]
    (out_dir / f"{p.name}.onsets.csv").write_text(
        "\n".join(["time_s,class,confidence,velocity", *rows]) + "\n", encoding="utf-8"
    )
    return wav


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--noise-db", type=float, help="white noise level, dBFS (e.g. -40)")
    parser.add_argument("--backing", action="store_true", help="add a bass and chord track")
    args = parser.parse_args()
    for p in PATTERNS:
        wav = write(p, args.out_dir, args.seed, args.noise_db, args.backing)
        print(wav, pcm_sha256(audio(p, args.seed, args.noise_db, args.backing)))


if __name__ == "__main__":
    main()
