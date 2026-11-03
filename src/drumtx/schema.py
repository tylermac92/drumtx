"""Data contracts shared by the pipeline stages (Technical Design Document §6–7).

On disk these are `events.json` schema v1 (`events-v1.schema.json` next to this file) and
`events.csv`, both documented in `docs/schema/events-v1.md`. Field names match the JSON, except
`DrumEvent.cls`, which is `class` in JSON and CSV.
"""

from dataclasses import asdict, dataclass
from typing import Any, Literal, get_args

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
    events: tuple[DrumEvent, ...]  # sorted by time; every event has a position
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
