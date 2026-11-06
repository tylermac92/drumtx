"""Data contracts shared by the pipeline stages (Technical Design Document §6–7).

On disk these are `events.json` schema v1 (`events-v1.schema.json` next to this file) and
`events.csv`, both documented in `docs/schema/events-v1.md`. Field names match the JSON, except
`DrumEvent.cls`, which is `class` in JSON and CSV.
"""

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, get_args

from drumtx.errors import InputError

SCHEMA_VERSION = 1

DrumClass = Literal["kick", "snare", "hihat", "tom", "cymbal"]
CLASSES: tuple[DrumClass, ...] = get_args(DrumClass)
Grid = Literal["16th", "triplet"]
EventFlag = Literal["uncertain", "merged"]
MeasureFlag = Literal["uncertain", "off_grid", "tempo", "merged"]

CSV_COLUMNS = ("time_s", "class", "confidence", "velocity")
# Blank `confidence` and `velocity` cells (rows added by hand) are read as these.
CSV_DEFAULT_CONFIDENCE = 1.0
CSV_DEFAULT_VELOCITY = 100


@dataclass(frozen=True)
class Position:
    """Where the quantizer placed an event. Counts start at 1; a pickup is measure 0."""

    measure: int
    beat: int
    grid: Grid
    slot: int  # 1–4 for 16ths, 1–3 for triplets
    residual_ms: float  # event time minus snapped time: positive means late
    residual_frac: float  # residual_ms as a fraction of the grid step, -0.5 to 0.5


@dataclass(frozen=True)
class DrumEvent:
    time_s: float  # seconds from the start of the source file, also with --start
    cls: DrumClass
    confidence: float  # 0–1
    velocity: int  # 1–127
    quantized: Position | None = None  # None until the quantizer runs
    flags: tuple[EventFlag, ...] = ()


@dataclass(frozen=True)
class Beat:
    time_s: float
    measure: int
    beat: int  # 1 is the downbeat


@dataclass(frozen=True)
class TimeSignature:
    measure: int  # applies from this measure on; a pickup measure uses the first entry
    beats: int
    beat_type: Literal[4]  # N/4 only in the MVP


@dataclass(frozen=True)
class TempoMap:
    beats: tuple[Beat, ...]  # empty until the beat tracker runs
    time_signatures: tuple[TimeSignature, ...]  # one entry in the MVP
    tempo_source: Literal["estimated", "user"]  # "user" when --bpm constrained the tracker
    time_signature_source: Literal["default", "user"]
    first_downbeat_source: Literal["estimated", "user"]


@dataclass(frozen=True)
class MeasureFlags:
    measure: int
    flags: tuple[MeasureFlag, ...]


@dataclass(frozen=True)
class QuantizedScore:
    tempo_map: TempoMap
    events: tuple[DrumEvent, ...]  # sorted by time; positioned unless there are under two beats
    measure_flags: tuple[MeasureFlags, ...] = ()  # flagged measures only


def event_to_json(e: DrumEvent) -> dict[str, Any]:
    """One entry of `events` in events.json."""
    return {
        "time_s": e.time_s,
        "class": e.cls,
        "confidence": e.confidence,
        "velocity": e.velocity,
        "quantized": None if e.quantized is None else asdict(e.quantized),
        "flags": list(e.flags),
    }


def tempo_map_from_json(d: dict[str, Any]) -> TempoMap:
    return TempoMap(
        beats=tuple(Beat(**b) for b in d["beats"]),
        time_signatures=tuple(TimeSignature(**t) for t in d["time_signatures"]),
        tempo_source=d["tempo_source"],
        time_signature_source=d["time_signature_source"],
        first_downbeat_source=d["first_downbeat_source"],
    )


def event_from_json(d: dict[str, Any]) -> DrumEvent:
    q = d["quantized"]
    return DrumEvent(
        time_s=d["time_s"],
        cls=d["class"],
        confidence=d["confidence"],
        velocity=d["velocity"],
        quantized=None if q is None else Position(**q),
        flags=tuple(d["flags"]),
    )


def read_events_csv(path: Path) -> list[DrumEvent]:
    """Read an events.csv (docs/schema/events-v1.md), sorted by time.

    `confidence` and `velocity` may be missing or blank. Every bad row is reported, by line number.
    """
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            if not {"time_s", "class"} <= set(columns) or set(columns) - set(CSV_COLUMNS):
                raise InputError(
                    f"{path.name}: the header must be {','.join(CSV_COLUMNS)} "
                    f"(confidence and velocity are optional); found {','.join(columns)}"
                )
            rows = list(reader)
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"Cannot read {path}: {e}") from e

    events, errors = [], []
    for line, row in enumerate(rows, start=2):
        try:
            time_s = float(row["time_s"])
            conf = float(row.get("confidence") or CSV_DEFAULT_CONFIDENCE)
            vel = int(row.get("velocity") or CSV_DEFAULT_VELOCITY)
            if row["class"] not in CLASSES:
                raise ValueError(f"unknown class {row['class']!r}")
            if not (math.isfinite(time_s) and time_s >= 0):
                raise ValueError(f"time_s {row['time_s']} is not a time")
            if not 0 <= conf <= 1 or not 1 <= vel <= 127:
                raise ValueError("confidence must be 0–1 and velocity 1–127")
        except (TypeError, ValueError) as e:
            errors.append(f"line {line}: {e}")
            continue
        events.append(DrumEvent(time_s, row["class"], conf, vel))
    if errors:
        shown = "\n  ".join(errors[:20]) + ("\n  ..." if len(errors) > 20 else "")
        raise InputError(f"{path.name} has {len(errors)} bad rows:\n  {shown}")
    return sorted(events, key=lambda e: (e.time_s, CLASSES.index(e.cls)))


def read_events(path: Path) -> list[DrumEvent]:
    """The events of an events.json (the score, positions and flags included) or an events.csv."""
    if path.suffix.lower() == ".csv":
        return read_events_csv(path)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        events = [event_from_json(e) for e in doc["events"]]
        if bad := sorted({e.cls for e in events} - set(CLASSES)):
            raise ValueError(f"unknown class {bad[0]!r}")
        return events
    except OSError as e:
        raise InputError(f"Cannot read {path}: {e.strerror}") from e
    except (ValueError, KeyError, TypeError) as e:
        raise InputError(f"{path.name} is not a DrumTx events.json file ({e!r}).") from e
