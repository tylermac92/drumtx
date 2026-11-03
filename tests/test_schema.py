"""M0-7 data contracts: the JSON Schema, its examples, the Python types, the CSV, the mapping."""

import copy
import csv
import dataclasses
import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any, get_args

import pytest
from jsonschema import Draft202012Validator

from drumtx import schema

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "drumtx"
EXAMPLES = ROOT / "docs" / "schema" / "examples"
SCHEMA = json.loads((PACKAGE / "events-v1.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
GROOVE = json.loads((EXAMPLES / "groove.events.json").read_text(encoding="utf-8"))


def test_schema_is_valid_json_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.events.json")), ids=lambda p: p.name)
def test_examples_validate(path: Path) -> None:
    VALIDATOR.validate(json.loads(path.read_text(encoding="utf-8")))


def _set(doc: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    doc = copy.deepcopy(doc)
    *keys, last = path.split(".")
    node: Any = doc
    for k in keys:
        node = node[int(k)] if k.isdigit() else node[k]
    node[int(last) if last.isdigit() else last] = value
    return doc


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("schema_version", 2),
        ("events.0.class", "cowbell"),
        ("events.0.velocity", 0),
        ("events.0.confidence", 1.5),
        ("events.0.flags", ["off_grid"]),  # a measure flag, not an event flag
        ("events.0.quantized.grid", "32nd"),
        ("events.0.quantized.residual_frac", 0.6),
        ("tempo_map.time_signatures.0.beat_type", 8),
        ("source.sha256", "not-a-hash"),
        ("unknown_key", 1),
    ],
)
def test_invalid_documents_are_rejected(path: str, value: Any) -> None:
    assert not VALIDATOR.is_valid(_set(GROOVE, path, value))


def _props(*path: str) -> dict[str, Any]:
    node = SCHEMA
    for key in path:
        node = node[key]
    if "oneOf" in node:  # nullable object
        node = next(n for n in node["oneOf"] if n.get("type") == "object")
    props: dict[str, Any] = (node["items"] if node.get("type") == "array" else node)["properties"]
    return props


@pytest.mark.parametrize(
    ("cls", "path"),
    [
        (schema.DrumEvent, ("properties", "events")),
        (schema.Position, ("properties", "events", "items", "properties", "quantized")),
        (schema.TempoMap, ("properties", "tempo_map")),
        (schema.Beat, ("properties", "tempo_map", "properties", "beats")),
        (schema.TimeSignature, ("properties", "tempo_map", "properties", "time_signatures")),
        (schema.MeasureFlags, ("properties", "measure_flags")),
    ],
)
def test_types_match_schema_fields(cls: type, path: tuple[str, ...]) -> None:
    names = {"class" if f.name == "cls" else f.name for f in dataclasses.fields(cls)}
    assert names == set(_props(*path))


def test_vocabularies_match_schema() -> None:
    event = _props("properties", "events")
    measure_flags = _props("properties", "measure_flags")["flags"]["items"]["enum"]
    assert list(schema.CLASSES) == event["class"]["enum"]
    assert (
        list(get_args(schema.Grid))
        == _props("properties", "events", "items", "properties", "quantized")["grid"]["enum"]
    )
    assert list(get_args(schema.EventFlag)) == event["flags"]["items"]["enum"]
    assert list(get_args(schema.MeasureFlag)) == measure_flags
    assert SCHEMA["properties"]["schema_version"]["const"] == schema.SCHEMA_VERSION


def test_example_csv_matches_json() -> None:
    raw = (EXAMPLES / "groove.events.csv").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == GROOVE["csv_sha256"]
    rows = list(csv.reader(raw.decode("utf-8").splitlines()))
    assert tuple(rows[0]) == schema.CSV_COLUMNS
    want = [[e["time_s"], e["class"], e["confidence"], e["velocity"]] for e in GROOVE["events"]]
    got = [[float(t), c, float(conf), int(v)] for t, c, conf, v in rows[1:]]
    assert got == want


def test_default_mapping_matches_design_doc() -> None:
    """The TOML file and the table in Technical Design Document §5 agree."""
    mapping = tomllib.loads((PACKAGE / "mapping.toml").read_text(encoding="utf-8"))
    design = (ROOT / "docs" / "technical-design.md").read_text(encoding="utf-8")
    table = design.split("### Default instrument mapping")[1].split("###")[0]
    rows = re.findall(r"^\| `(\w+)` \| (\d+)[^|]*\| (\w\d)[^|]*\| (\w+) \| ([^|]*)\|", table, re.M)
    want = {
        cls: {
            "midi_note": int(note),
            "display": display,
            "notehead": head,
            "voice": 2 if "Voice 2" in remark else 1,
        }
        for cls, note, display, head, remark in rows
    }
    assert list(want) == list(schema.CLASSES)
    assert {cls: {k: v for k, v in t.items() if k != "name"} for cls, t in mapping.items()} == want
