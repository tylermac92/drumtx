"""Output files (Technical Design Document §5). So far: events.json and events.csv.

`transcribe` never overwrites outputs without --force, and never overwrites an events.csv that was
edited after it was written: its SHA-256 at writing time is stored in events.json.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from drumtx.errors import InputError
from drumtx.schema import CSV_COLUMNS, SCHEMA_VERSION, DrumEvent, event_to_json


def event_paths(out_dir: Path, stem: str) -> tuple[Path, Path]:
    return out_dir / f"{stem}.events.json", out_dir / f"{stem}.events.csv"


def check_outputs(out_dir: Path, stem: str, force: bool) -> None:
    """Refuse to start a run whose outputs would overwrite files it must not."""
    json_path, csv_path = event_paths(out_dir, stem)
    existing = [p for p in (json_path, csv_path) if p.exists()]
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
    events: list[DrumEvent],
    source: dict[str, Any],
    settings: dict[str, Any],
    models: dict[str, str | None],
    csv_sha256: str | None,
) -> dict[str, Any]:
    """A detection-only events.json (schema v1): the tempo map is empty and nothing is quantized."""
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "settings": settings,
        "models": models,
        "csv_sha256": csv_sha256,
        "tempo_map": {
            "beats": [],
            "time_signatures": [{"measure": 1, "beats": 4, "beat_type": 4}],
            "tempo_source": "estimated",
            "time_signature_source": "default",
            "first_downbeat_source": "estimated",
        },
        "events": [event_to_json(e) for e in events],
        "measure_flags": [],
    }


def write_events(out_dir: Path, stem: str, csv_data: bytes, doc: dict[str, Any]) -> list[Path]:
    """Write the CSV, then the JSON that records its hash. Each file is replaced atomically."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = event_paths(out_dir, stem)
    for path, data in (
        (csv_path, csv_data),
        (json_path, (json.dumps(doc, indent=2) + "\n").encode()),
    ):
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    return [json_path, csv_path]
