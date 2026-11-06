"""M5-3: `drumtx render` quantizes and renders (edited) events again, without the audio."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from test_midi import notes_s
from typer.testing import CliRunner

from drumtx import beats, pipeline
from drumtx.cli import app
from drumtx.ingest import SAMPLE_RATE
from drumtx.synth import render as synth

runner = CliRunner()
HEADER = "time_s,class,confidence,velocity\n"


@pytest.fixture
def out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A transcription (conftest's tracker: beats every 0.5 s, bar 1 at 0 s), with the audio
    deleted and the pipeline disabled, so render cannot detect or track."""
    wav, out = tmp_path / "in.wav", tmp_path / "out"
    sf.write(wav, synth([(1.0, "snare", 100)], 4.0), SAMPLE_RATE)
    args = ["transcribe", str(wav), "-o", str(out), "-q", "--model", "baseline"]
    assert runner.invoke(app, args).exit_code == 0
    wav.unlink()
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: pytest.fail("the pipeline ran"))
    return out


def render(*args: str) -> tuple[int, str]:
    result = runner.invoke(app, ["render", *args, "-q"])
    return result.exit_code, result.stderr


def doc(out: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((out / "in.events.json").read_text())
    return data


def test_csv_edits_reach_the_score_and_midi(out: Path) -> None:
    csv = out / "in.events.csv"
    before = doc(out)
    # Rewritten by hand: kept, reclassified (row 3, snare -> tom), and added with blank cells.
    csv.write_text(HEADER + "0.000,kick,0.9,80\n1.000,tom,0.9,90\n3.250,tom,,\n")
    edited = csv.read_bytes()
    assert render(str(csv)) == (0, "")
    assert csv.read_bytes() == edited  # never modified

    after = doc(out)
    places = [
        (e["class"], e["quantized"]["measure"], e["quantized"]["beat"]) for e in after["events"]
    ]
    assert places == [("kick", 1, 1), ("tom", 1, 3), ("tom", 2, 3)]
    assert after["events"][2]["confidence"] == 1.0 and after["events"][2]["velocity"] == 100
    assert after["events"][2]["quantized"]["slot"] == 3  # the "and" of beat 3
    for key in ("source", "models", "csv_sha256", "tempo_map"):
        assert after[key] == before[key]
    assert after["settings"] == before["settings"]

    midi = [(round(t, 3), note, v) for t, _, note, v in notes_s((out / "in.mid").read_bytes())]
    assert midi == [(0.0, 36, 80), (1.0, 47, 90), (3.25, 47, 100)]
    musicxml = (out / "in.musicxml").read_text()
    assert musicxml.count('<instrument id="P1-tom"') == 2
    assert musicxml.count('<instrument id="P1-snare"') == 0
    assert "| tom    | 47        | 2        | 2" in (out / "in.report.md").read_text()

    # Delete a row: it leaves every output.
    csv.write_text(HEADER + "0.000,kick,0.9,80\n3.250,tom,,\n")
    assert render(str(csv)) == (0, "")
    assert [e["class"] for e in doc(out)["events"]] == ["kick", "tom"]
    assert len(notes_s((out / "in.mid").read_bytes())) == 2


def first_note_of_bar_1(out: Path) -> str:
    measure = (out / "in.musicxml").read_text().split('<measure number="1"')[1]
    return measure.split("<note>")[1].split("</note>")[0]


def test_first_downbeat_moves_barlines_without_audio(out: Path) -> None:
    assert "<rest />" in first_note_of_bar_1(out)  # bar 1 at 0 s; the hits are on beat 3
    assert render(str(out / "in.events.json"), "--first-downbeat", "1.0") == (0, "")
    d = doc(out)
    bar1 = next(b for b in d["tempo_map"]["beats"] if b["measure"] == 1 and b["beat"] == 1)
    assert bar1["time_s"] == 1.0 and d["tempo_map"]["first_downbeat_source"] == "user"
    assert d["settings"]["first_downbeat"] == 1.0
    snare = next(e for e in d["events"] if e["class"] == "snare")
    assert snare["quantized"]["measure"] == 1 and snare["quantized"]["beat"] == 1
    assert "<rest />" not in first_note_of_bar_1(out)

    # A later render without the option keeps bar 1 where it was moved.
    assert render(str(out / "in.events.json")) == (0, "")
    assert doc(out)["tempo_map"] == d["tempo_map"]


def test_renumber() -> None:
    t = np.arange(12) * 0.5
    stored = beats.tempo_map(t, t[1::4])
    assert beats.renumber(stored, None, None) == stored  # bar 1 at 0.5 s, from the downbeats
    three = beats.renumber(stored, None, 3)
    assert [(b.time_s, b.measure, b.beat) for b in three.beats[:5]] == [
        (0.0, 0, 3),
        (0.5, 1, 1),
        (1.0, 1, 2),
        (1.5, 1, 3),
        (2.0, 2, 1),
    ]
    assert three.time_signatures[0].beats == 3 and three.time_signature_source == "user"
    assert three.first_downbeat_source == "estimated"


def test_formats(out: Path) -> None:
    musicxml = (out / "in.musicxml").read_bytes()
    (out / "in.mid").unlink()
    assert render(str(out / "in.events.json"), "--formats", "midi", "--grid", "16th") == (0, "")
    assert (out / "in.mid").exists() and (out / "in.musicxml").read_bytes() == musicxml
    assert doc(out)["settings"]["grid"] == "16th"
    code, err = render(str(out / "in.events.json"), "--formats", "midi,csv")
    assert code == 2 and "--formats takes musicxml, midi and report, got csv" in err


def test_errors(out: Path, tmp_path: Path) -> None:
    csv = out / "in.events.csv"
    csv.write_text(HEADER + "0.000,kick,0.9,80\n1.000,gong,0.9,90\nsoon,snare,,\n")
    code, err = render(str(csv))
    assert code == 2 and "line 3: unknown class 'gong'" in err and "line 4:" in err

    lone = tmp_path / "lone.events.csv"
    lone.write_text(HEADER + "0.000,kick,0.9,80\n")
    code, err = render(str(lone))
    assert code == 2 and "lone.events.json" in err and "tempo map" in err

    code, err = render(str(out / "in.events.json"), "--time-signature", "6/8")
    assert code == 2 and "N/4" in err


def test_merged_flag_survives_a_render_from_json(out: Path) -> None:
    csv = out / "in.events.csv"
    csv.write_text(HEADER + "1.000,snare,0.9,90\n1.020,snare,0.6,70\n")
    assert render(str(csv)) == (0, "")
    assert [e["flags"] for e in doc(out)["events"]] == [["merged"]]
    assert render(str(out / "in.events.json")) == (0, "")  # the merged-away hit is not in it
    assert [e["flags"] for e in doc(out)["events"]] == [["merged"]]
    assert doc(out)["measure_flags"] == [{"measure": 1, "flags": ["merged"]}]
