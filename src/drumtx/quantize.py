"""The quantizer (Technical Design Document §7, step 5; M3-2): drum hits onto a per-beat grid.

- Each beat gets a grid: 16ths (4 slots) or 8th-note triplets (3 slots). `auto` picks triplets
  only when they cut the total snapping error by more than TRIPLET_PENALTY, and at least two hits
  in the beat sit closer to a triplet point than to a 16th.
- Each hit snaps to the nearest point of its beat's grid. A hit just before a beat goes to slot 1
  of that beat.
- Hits of the same class in the same slot are merged: the most confident one stays and is flagged
  `merged`. Grids are then chosen again without the merged hits, until nothing more merges, so
  quantizing the result again changes nothing.
- Hits outside the tracked beats are placed by extending the first and last beat intervals. Hits
  before measure 0 (the pickup) cannot be numbered: they are left out of the score, with a warning.
"""

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from typing import Literal

import numpy as np

from drumtx.schema import CLASSES, DrumEvent, Grid, Position, QuantizedScore, TempoMap

log = logging.getLogger("drumtx")
GridOption = Literal["auto", "16th", "triplet"]
SLOTS: dict[Grid, int] = {"16th": 4, "triplet": 3}
TRIPLET_PENALTY = 0.05  # in beats of total snapping error: a duple feel is preferred


def _beat_grid(tempo_map: TempoMap, first_s: float, last_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Beat times spanning first_s to past last_s, and each beat's number: measure * beats per bar
    + beat - 1, so measure 0 beat 1 is 0. The end intervals are repeated past the tracked beats."""
    per_bar = tempo_map.time_signatures[0].beats
    times = np.array([b.time_s for b in tempo_map.beats])
    numbers = np.array([b.measure * per_bar + b.beat - 1 for b in tempo_map.beats])
    head, tail = times[1] - times[0], times[-1] - times[-2]
    before = np.arange(max(0, int(np.ceil((times[0] - first_s) / head))), 0, -1)
    after = np.arange(1, max(0, int(np.ceil((last_s - times[-1]) / tail))) + 2)
    return (
        np.concatenate([times[0] - head * before, times, times[-1] + tail * after]),
        np.concatenate([numbers[0] - before, numbers, numbers[-1] + after]),
    )


def _slots_per_beat(
    interval: np.ndarray, phase: np.ndarray, n: int, grid: GridOption
) -> np.ndarray:
    """4 or 3 for each of the n beat intervals, from the hits' phases within them."""
    if grid != "auto":
        return np.full(n, SLOTS[grid])
    error16, error3 = (np.abs(phase * k - np.floor(phase * k + 0.5)) / k for k in (4, 3))
    saving = np.bincount(interval, error16 - error3, minlength=n)
    fits = np.bincount(interval, error3 < error16, minlength=n)
    return np.where((saving > TRIPLET_PENALTY) & (fits >= 2), 3, 4)


def quantize(
    events: Sequence[DrumEvent], tempo_map: TempoMap, grid: GridOption = "auto"
) -> QuantizedScore:
    """Place every hit on the grid; see the module docstring."""
    events = sorted(events, key=lambda e: (e.time_s, CLASSES.index(e.cls)))
    if not events:
        return QuantizedScore(tempo_map, ())
    if len(tempo_map.beats) < 2:
        log.warning("Fewer than two beats were found, so the hits are not placed on a grid.")
        return QuantizedScore(tempo_map, tuple(events))
    per_bar = tempo_map.time_signatures[0].beats
    beat_s, number = _beat_grid(tempo_map, events[0].time_s, events[-1].time_s)
    dropped = 0
    while True:
        t = np.array([e.time_s for e in events])
        i = np.searchsorted(beat_s, t, side="right") - 1
        length = beat_s[i + 1] - beat_s[i]
        phase = (t - beat_s[i]) / length
        slots = _slots_per_beat(i, phase, len(beat_s), grid)
        k = slots[i]
        j = np.floor(phase * k + 0.5).astype(int)  # j == k: slot 1 of the next beat
        beat = i + (j == k)
        n = number[beat]
        keys = [(int(n[x]), int(j[x] % k[x]), e.cls) for x, e in enumerate(events)]
        winners: dict[tuple[int, int, str], int] = {}
        for x in sorted(range(len(events)), key=lambda x: -events[x].confidence):  # ties: earliest
            winners.setdefault(keys[x], x)
        size = Counter(keys)
        keep = [x for x in winners.values() if n[x] >= 0]
        if len(keep) == len(events):
            break
        dropped += int(np.sum(n < 0))
        events = [
            replace(events[x], flags=(*events[x].flags, "merged"))
            if size[keys[x]] > 1 and "merged" not in events[x].flags
            else events[x]
            for x in sorted(keep)
        ]
    if dropped:
        log.warning(
            "%d hits before measure 0 are left out of the score (they stay in events.csv). "
            "Check --first-downbeat.",
            dropped,
        )
    placed = []
    for x, e in enumerate(events):
        snapped = beat_s[i[x]] + j[x] / k[x] * length[x]
        position = Position(
            measure=int(n[x]) // per_bar,
            beat=int(n[x]) % per_bar + 1,
            grid="triplet" if slots[beat[x]] == 3 else "16th",
            slot=int(j[x] % k[x]) + 1,
            residual_ms=round(float(t[x] - snapped) * 1000, 1),
            residual_frac=round(float(phase[x] * k[x] - j[x]), 3),  # of the step it snapped on
        )
        placed.append(replace(e, quantized=position))
    return QuantizedScore(tempo_map, tuple(placed))
