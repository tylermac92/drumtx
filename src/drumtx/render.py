"""Output files (Technical Design Document §5). So far: events.json, events.csv, the MIDI
file and the MusicXML file.

`transcribe` never overwrites outputs without --force, and never overwrites an events.csv that was
edited after it was written: its SHA-256 at writing time is stored in events.json.
"""

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

from drumtx.errors import InputError
from drumtx.schema import CSV_COLUMNS, SCHEMA_VERSION, DrumEvent, QuantizedScore, event_to_json


def event_paths(out_dir: Path, stem: str) -> tuple[Path, Path]:
    return out_dir / f"{stem}.events.json", out_dir / f"{stem}.events.csv"


def check_outputs(out_dir: Path, stem: str, force: bool) -> None:
    """Refuse to start a run whose outputs would overwrite files it must not."""
    json_path, csv_path = event_paths(out_dir, stem)
    others = (out_dir / f"{stem}.mid", out_dir / f"{stem}.musicxml")
    existing = [p for p in (json_path, csv_path, *others) if p.exists()]
    if existing and not force:
        names = ", ".join(p.name for p in existing)
        raise InputError(f"{names} already exists in {out_dir}. Use --force to overwrite.")
    if csv_path.exists() and _stored_csv_hash(json_path) != _sha256(csv_path.read_bytes()):
        raise InputError(
            f"{csv_path} was edited after DrumTx wrote it (or its events.json is missing), so "
            "--force will not overwrite it. Move or rename it first; `drumtx render` uses it."
        )


def _stored_csv_hash(json_path: Path) -> str | None:
    try:
        value = json.loads(json_path.read_text(encoding="utf-8")).get("csv_sha256")
        return value if isinstance(value, str) else None
    except (OSError, ValueError, AttributeError):
        return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def events_csv(events: list[DrumEvent]) -> bytes:
    rows = [",".join(CSV_COLUMNS)]
    rows += [f"{e.time_s:.3f},{e.cls},{e.confidence:.3f},{e.velocity}" for e in events]
    return ("\n".join(rows) + "\n").encode()


def events_json(
    score: QuantizedScore,
    source: dict[str, Any],
    settings: dict[str, Any],
    models: dict[str, str | None],
    csv_sha256: str | None,
) -> dict[str, Any]:
    """events.json (schema v1): the tempo map and the score's hits with their positions."""
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "settings": settings,
        "models": models,
        "csv_sha256": csv_sha256,
        "tempo_map": dataclasses.asdict(score.tempo_map),
        "events": [event_to_json(e) for e in score.events],
        "measure_flags": [dataclasses.asdict(m) for m in score.measure_flags],
    }


def write_outputs(
    out_dir: Path, stem: str, csv_data: bytes, doc: dict[str, Any], midi: bytes, musicxml: bytes
) -> list[Path]:
    """Write the MusicXML and MIDI files, the CSV, then the JSON that records the CSV's hash.
    Each file is replaced atomically."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = event_paths(out_dir, stem)
    midi_path, musicxml_path = out_dir / f"{stem}.mid", out_dir / f"{stem}.musicxml"
    for path, data in (
        (musicxml_path, musicxml),
        (midi_path, midi),
        (csv_path, csv_data),
        (json_path, (json.dumps(doc, indent=2) + "\n").encode()),
    ):
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    return [json_path, csv_path, midi_path, musicxml_path]
