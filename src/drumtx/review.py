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

The defaults are first estimates; M5-4 tunes them on the development set.

`build_report` writes the review report (M5-1): `<name>.report.md`.
"""

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from importlib.metadata import version
from pathlib import Path
from typing import Any, get_args

import numpy as np

from drumtx.schema import (
    CLASSES,
    DrumClass,
    DrumEvent,
    EventFlag,
    MeasureFlag,
    MeasureFlags,
    QuantizedScore,
    TempoMap,
)


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


REASONS: dict[MeasureFlag, str] = {
    "uncertain": "hits with confidence below {confidence}: likely extra notes",
    "off_grid": "more than {off_grid_events} hit further than {residual_frac:.0%} of a grid step "
    "from its slot: the timing or the beats may be off",
    "tempo": "beats more than {tempo:.0%} longer or shorter than the median: a tempo change, or "
    "a beat-tracking error",
    "merged": "hits of the same instrument in one slot, merged into one note: a flam, a double "
    "hit, or the grid is too coarse",
}


def _clock(t: float) -> str:
    """Seconds as m:ss.ss."""
    minutes, cs = divmod(round(t * 100), 6000)
    return f"{minutes}:{cs // 100:02d}.{cs % 100:02d}"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """A Markdown table with padded columns, so it also reads as plain text."""
    widths = [max(len(r[i]) for r in (header, *rows)) for i in range(len(header))]

    def line(r: Sequence[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)) + " |"

    rule = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    return "\n".join([line(header), rule, *map(line, rows)])


def measure_times(tempo_map: TempoMap, measure: int) -> tuple[float, float]:
    """Start and end of a measure in source-file seconds. Past the tracked beats, the end beat
    intervals are repeated, as the quantizer does. Needs at least two beats."""
    per_bar = tempo_map.time_signatures[0].beats
    times = np.array([b.time_s for b in tempo_map.beats])
    numbers = np.array([b.measure * per_bar + b.beat - 1 for b in tempo_map.beats])

    def at(n: int) -> float:
        if n < numbers[0]:
            return float(times[0] - (numbers[0] - n) * (times[1] - times[0]))
        if n > numbers[-1]:
            return float(times[-1] + (n - numbers[-1]) * (times[-1] - times[-2]))
        return float(np.interp(n, numbers, times))

    return max(0.0, at(measure * per_bar)), at((measure + 1) * per_bar)


def build_report(
    score: QuantizedScore,
    events: Sequence[DrumEvent],
    source: dict[str, Any],
    settings: dict[str, Any],
    models: dict[str, str | None],
    midi_notes: dict[DrumClass, int],
    thresholds: Thresholds = DEFAULT,
) -> str:
    """The review report, in Markdown. `events` is every detected hit (as in events.csv), the
    score holds them without merged-away hits; `source`, `settings` and `models` are the
    events.json sections."""
    tm = score.tempo_map
    stem = Path(source["file"]).stem
    ts = tm.time_signatures[0]
    per_bar = ts.beats
    placed = [(e, q) for e in score.events if (q := e.quantized)]

    excerpt = ""
    if source.get("start_s") is not None or source.get("end_s") is not None:
        start, end = source.get("start_s") or 0.0, source.get("end_s") or source["duration_s"]
        excerpt = f", excerpt {_clock(start)} to {_clock(end)}"
    summary = [f"- **Source:** {source['file']}, {_clock(source['duration_s'])}{excerpt}"]
    if len(tm.beats) > 1:
        length = np.diff([b.time_s for b in tm.beats])
        median = float(np.median(length))
        steady = float(np.mean(np.abs(length / median - 1) <= thresholds.tempo))
        stability = "stable" if steady >= 0.95 else "varies"
        summary.append(
            f"- **Tempo:** about {60 / median:.0f} BPM ({tm.tempo_source}), {stability}: "
            f"{steady:.0%} of beats are within {thresholds.tempo:.0%} of it"
        )
        bar1 = next((b.time_s for b in tm.beats if b.measure == 1 and b.beat == 1), None)
        if bar1 is not None:
            summary.append(
                f"- **First downbeat** (measure 1): {_clock(bar1)} ({tm.first_downbeat_source})"
            )
    else:
        summary.append("- **Tempo:** not found (fewer than two beats), so hits are not on a grid")
    summary.append(f"- **Time signature:** {ts.beats}/{ts.beat_type} ({tm.time_signature_source})")
    if placed:
        first = min(q.measure for _, q in placed)
        last = max(max(b.measure for b in tm.beats), max(q.measure for _, q in placed))
        flagged = len(score.measure_flags)
        summary.append(
            f"- **Flagged:** {flagged} of {last - min(first, 1) + 1} measures need checking"
        )

    in_score = Counter(e.cls for e in score.events)
    uncertain = Counter(e.cls for e in score.events if "uncertain" in e.flags)
    detected = Counter(e.cls for e in events)
    counts = _table(
        ["Class", "MIDI note", "Detected", "In the score", "Uncertain"],
        [
            [c, str(midi_notes[c]), str(detected[c]), str(in_score[c]), str(uncertain[c])]
            for c in CLASSES
        ],
    )

    per_measure: defaultdict[int, Counter[str]] = defaultdict(Counter)
    for e, q in placed:
        per_measure[q.measure].update(e.flags)
        per_measure[q.measure]["off_grid"] += abs(q.residual_frac) > thresholds.residual_frac
    rows = []
    for m in score.measure_flags:
        start, end = measure_times(tm, m.measure)
        n = per_measure[m.measure]
        reasons = {
            "uncertain": f"{n['uncertain']} uncertain",
            "off_grid": f"{n['off_grid']} off the grid",
            "tempo": f"tempo {60 * per_bar / (end - start):.0f} BPM",
            "merged": f"{n['merged']} merged",
        }
        rows.append(
            [str(m.measure), _clock(start), _clock(end), ", ".join(reasons[f] for f in m.flags)]
        )
    if rows:
        legend = "\n".join(f"- **{f}**: {r.format(**vars(thresholds))}" for f, r in REASONS.items())
        flagged_text = (
            "Times are from the start of the source file. Measure numbers are those in the "
            "MusicXML and in events.json; a pickup before the first downbeat is measure 0.\n\n"
            + _table(["Measure", "Start", "End", "Why"], rows)
            + "\n\nWhy a measure is flagged:\n\n"
            + legend
        )
    else:
        flagged_text = "No measures are flagged. Unflagged measures can still be wrong."

    def value(v: Any) -> str:
        return "-" if v is None else "on" if v is True else "off" if v is False else str(v)

    setting_rows = [[k, value(v)] for k, v in settings.items()]
    setting_rows += [[f"model: {k}", value(v)] for k, v in models.items()]
    setting_rows.append(["drumtx", version("drumtx")])

    audio, events_file = source["file"], f"{stem}.events.json"
    steps = "\n".join(
        [
            "1. **Check the rhythm first.** If bar lines are shifted or the whole score looks "
            "garbled, fix it with options before editing any hits: "
            f"`drumtx render {events_file} --first-downbeat SEC` or `--time-signature N/4`. "
            f"A half- or double-speed tempo needs `drumtx transcribe {audio} --bpm BPM --force`, "
            "which reuses the cached detection.",
            f"2. **Listen:** `drumtx preview {audio} {events_file} --split-stereo` plays the "
            "original on the left and the detected hits on the right.",
            f"3. **Fix hits** in MuseScore ({stem}.musicxml) or a DAW ({stem}.mid), or edit "
            f"{stem}.events.csv and run `drumtx render {stem}.events.csv`. `--mark-uncertain` "
            "colors uncertain notes red.",
        ]
    )

    return f"""# DrumTx review report: {source["file"]}

Automatic transcription contains errors. Check the flagged measures first.

## Summary

{chr(10).join(summary)}

## Hits per class

"In the score" leaves out hits merged into another (they stay in {stem}.events.csv).

{counts}

## Flagged measures

{flagged_text}

## Suggested next steps

{steps}

## Settings

{_table(["Setting", "Value"], setting_rows)}

## Limitations

- DrumTx cannot tell whether a transcription is correct. Flags point to likely problems;
  unflagged measures can be wrong too.
- Results are best on isolated drum recordings, and worse on full mixes, live recordings,
  heavily processed or electronic kits, and lo-fi sources.
- Quiet notes and ghost notes are often missed. Velocity is only a rough loud/soft estimate.
- Five instrument classes only: toms are one class, crash and ride are one class, and open and
  closed hi-hat are one class. Swing is written as straight 16ths.
- Accuracy figures are in docs/accuracy.md.
"""
