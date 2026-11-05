"""Review flags (Technical Design Document §7, step 7; M3-3): what to check in a transcription.

Events:
- `uncertain`: confidence below `Thresholds.confidence`.
- `merged`: set by the quantizer; other hits in its slot were merged into it.

Measures (only flagged measures are listed):
- `uncertain`: contains an uncertain event.
- `off_grid`: more than `Thresholds.off_grid_events` events are further than
  `Thresholds.residual_frac` of a grid step from their slot. A fraction of the step, not
  milliseconds, so it means the same at any tempo.
- `tempo`: the measure's mean beat length differs from the piece's median by more than
  `Thresholds.tempo`.
- `merged`: contains a merged event.

The defaults are first estimates; M5-5 tunes them on the development set.
"""

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import get_args

import numpy as np

from drumtx.schema import EventFlag, MeasureFlag, MeasureFlags, QuantizedScore


@dataclass(frozen=True)
class Thresholds:
    confidence: float = 0.5  # below it, a hit is more likely false than real (M2-4 reliability)
    residual_frac: float = 0.25  # of a grid step
    off_grid_events: int = 1  # flag when more events than this are off the grid
    tempo: float = 0.08  # relative difference from the median beat length


DEFAULT = Thresholds()


def flag(score: QuantizedScore, thresholds: Thresholds = DEFAULT) -> QuantizedScore:
    """The score with event flags recomputed and measure flags set."""
    measures: defaultdict[int, set[MeasureFlag]] = defaultdict(set)
    off_grid: defaultdict[int, int] = defaultdict(int)
    events = []
    for e in score.events:
        flags: set[EventFlag] = set(e.flags) - {"uncertain"}
        if e.confidence < thresholds.confidence:
            flags.add("uncertain")
        events.append(replace(e, flags=tuple(f for f in get_args(EventFlag) if f in flags)))
        if (q := e.quantized) is None:
            continue
        measures[q.measure] |= flags
        if abs(q.residual_frac) > thresholds.residual_frac:
            off_grid[q.measure] += 1
    for m, count in off_grid.items():
        if count > thresholds.off_grid_events:
            measures[m].add("off_grid")

    beats = score.tempo_map.beats
    if len(beats) > 1:
        length = np.diff([b.time_s for b in beats])
        by_measure: defaultdict[int, list[float]] = defaultdict(list)
        for b, d in zip(beats, length, strict=False):  # each beat's length, in its measure
            by_measure[b.measure].append(float(d))
        median = float(np.median(length))
        for m, lengths in by_measure.items():
            if abs(np.mean(lengths) / median - 1) > thresholds.tempo:
                measures[m].add("tempo")

    measure_flags = tuple(
        MeasureFlags(m, tuple(f for f in get_args(MeasureFlag) if f in found))
        for m, found in sorted(measures.items())
        if found
    )
    return replace(score, events=tuple(events), measure_flags=measure_flags)
