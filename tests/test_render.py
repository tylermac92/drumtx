"""M1-7: transcribe writes events.json and events.csv, and protects existing and edited files."""

import hashlib
import json
import shutil
from pathlib import Path

import make_fixtures as mf
import pytest
from jsonschema import Draft202012Validator
from typer.testing import CliRunner

from drumtx.cli import app
from drumtx.schema import read_events_csv

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "src" / "drumtx" / "events-v1.schema.json").read_text()
)
runner = CliRunner()


@pytest.fixture
def wav(tmp_path: Path) -> Path:
    return mf.write(mf.PATTERNS[0], tmp_path / "in")


def transcribe(wav: Path, out: Path, *extra: str) -> tuple[int, str]:
    result = runner.invoke(
        app, ["transcribe", str(wav), "-o", str(out), "-q", "--model", "baseline", *extra]
    )
    return result.exit_code, result.stderr


def test_outputs(wav: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert transcribe(wav, out, "--start", "0.5") == (0, "")
    doc = json.loads((out / "straight16.events.json").read_text())
    Draft202012Validator(SCHEMA).validate(doc)
    csv_bytes = (out / "straight16.events.csv").read_bytes()
    assert doc["csv_sha256"] == hashlib.sha256(csv_bytes).hexdigest()
    assert doc["source"] == {
        "file": "straight16.wav",
        "sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
        "duration_s": pytest.approx(mf.timed_hits(mf.PATTERNS[0])[-1][0] + mf.TAIL_S),
        "start_s": 0.5,
        "end_s": None,
    }
    # conftest's stand-in tracker: beats every 0.5 s from the excerpt start, in file time
    assert doc["tempo_map"]["beats"][:2] == [
        {"time_s": 0.5, "measure": 1, "beat": 1},
        {"time_s": 1.0, "measure": 1, "beat": 2},
    ]
    assert doc["models"]["beat_tracker"] == "beat-this-final0" and doc["measure_flags"] == []
    assert all(e["quantized"] is None for e in doc["events"]) and doc["events"]
    # The CSV holds the same events as the JSON, at the same precision.
    rows = read_events_csv(out / "straight16.events.csv")
    assert [(e.time_s, e.cls, e.confidence, e.velocity) for e in rows] == [
        (e["time_s"], e["class"], e["confidence"], e["velocity"]) for e in doc["events"]
    ]
    assert min(e.time_s for e in rows) >= 0.5  # source-file times, inside the excerpt


def test_no_overwrite_without_force(wav: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert transcribe(wav, out)[0] == 0
    before = (out / "straight16.events.json").read_bytes()
    code, err = transcribe(wav, out, "--sensitivity", "strict")
    assert code == 2 and "already exists" in err and "--force" in err
    assert (out / "straight16.events.json").read_bytes() == before
    assert transcribe(wav, out, "--sensitivity", "strict", "--force") == (0, "")
    assert (out / "straight16.events.json").read_bytes() != before


def test_force_never_overwrites_an_edited_csv(wav: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert transcribe(wav, out)[0] == 0
    csv = out / "straight16.events.csv"
    edited = csv.read_bytes() + b"9.000,snare,,\n"
    csv.write_bytes(edited)
    code, err = transcribe(wav, out, "--force")
    assert code == 2 and "was edited" in err
    assert csv.read_bytes() == edited
    # Without its events.json, a CSV cannot be shown to be unedited: also kept.
    (out / "straight16.events.json").unlink()
    assert transcribe(wav, out, "--force")[0] == 2
    assert csv.read_bytes() == edited


def test_missing_ffmpeg_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    m4a = tmp_path / "song.m4a"
    m4a.write_bytes(b"\0\0\0\x20ftypM4A " + bytes(4000))
    code, err = transcribe(m4a, tmp_path / "out")
    assert code == 3 and "Install FFmpeg" in err
