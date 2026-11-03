"""M1-4: evaluate, on fixtures whose results are worked out by hand."""

import json
from pathlib import Path

import mido
import pytest
from typer.testing import CliRunner

from drumtx import evaluate as ev
from drumtx.cli import app
from drumtx.errors import InputError
from drumtx.schema import read_events_csv

EXAMPLES = Path(__file__).resolve().parents[1] / "docs" / "schema" / "examples"
runner = CliRunner()


def write_csv(
    path: Path, rows: list[str], header: str = "time_s,class,confidence,velocity"
) -> Path:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    ref = write_csv(tmp_path / "ref.csv", ["1.0,kick,,", "2.0,kick,,", "3.0,kick,,", "1.5,snare,,"])
    pred = write_csv(
        tmp_path / "pred.csv",
        # kick: 40 ms late, 60 ms late, exact, extra. snare: 20 ms late. hihat: extra.
        [
            "1.04,kick,0.9,90",
            "2.06,kick,0.9,90",
            "3.0,kick,0.9,90",
            "4.0,kick,0.9,90",
            "1.52,snare,0.9,90",
            "2.5,hihat,0.9,90",
        ],
    )
    return pred, ref


def test_onset_scores_by_hand(pair: tuple[Path, Path]) -> None:
    pred, ref = pair
    result = ev.evaluate(ev.load_prediction(pred), ev.load_reference(ref))
    at50, at30 = result["onsets"]
    assert (at50["tolerance_ms"], at30["tolerance_ms"]) == (50, 30)
    # ±50 ms: kick hits 1.04 and 3.0; 2.06 and 4.0 are false; 2.0 is missed.
    assert at50["classes"]["kick"] == {"tp": 2, "fp": 2, "fn": 1, "p": 0.5, "r": 2 / 3, "f": 4 / 7}
    assert at50["classes"]["snare"] == {"tp": 1, "fp": 0, "fn": 0, "p": 1.0, "r": 1.0, "f": 1.0}
    assert at50["classes"]["hihat"] == {"tp": 0, "fp": 1, "fn": 0, "p": 0.0, "r": 0.0, "f": 0.0}
    assert at50["classes"]["tom"] == {"tp": 0, "fp": 0, "fn": 0, "p": 0.0, "r": 0.0, "f": 0.0}
    assert at50["all"] == {"tp": 3, "fp": 3, "fn": 1, "p": 0.5, "r": 0.75, "f": 0.6}
    # ±30 ms: 1.04 is now too late too.
    assert at30["classes"]["kick"] == {"tp": 1, "fp": 3, "fn": 2, "p": 0.25, "r": 1 / 3, "f": 2 / 7}
    assert at30["all"] == {"tp": 2, "fp": 4, "fn": 2, "p": 1 / 3, "r": 0.5, "f": 0.4}
    assert result["beats"] is None


def test_custom_tolerance(pair: tuple[Path, Path]) -> None:
    pred, ref = pair
    (at70,) = ev.evaluate(ev.load_prediction(pred), ev.load_reference(ref), (70,))["onsets"]
    assert at70["classes"]["kick"]["tp"] == 3


def test_midi_reference(tmp_path: Path) -> None:
    midi = mido.MidiFile(ticks_per_beat=480)  # default tempo: 120 BPM, so 960 ticks per second
    track = mido.MidiTrack()
    midi.tracks.append(track)
    for delta, note, channel in [(960, 36, 9), (480, 38, 9), (480, 39, 9), (480, 60, 0)]:
        track.append(mido.Message("note_on", note=note, velocity=100, channel=channel, time=delta))
        track.append(mido.Message("note_off", note=note, velocity=0, channel=channel, time=0))
    midi.save(tmp_path / "ref.mid")
    ref = ev.load_reference(tmp_path / "ref.mid")
    assert ref.onsets["kick"].tolist() == [1.0]
    assert ref.onsets["snare"].tolist() == [1.5]
    assert ref.unknown_notes == {39: 1}  # hand clap: reported, not scored
    assert ref.other_channel_notes == 1
    result = ev.evaluate(ev.Track(ref.onsets), ref)
    assert result["not_scored"] == {"unknown_midi_notes": {"39": 1}, "notes_not_on_channel_10": 1}
    report = ev.markdown(result, Path("p"), Path("ref.mid"))
    assert "MIDI note 39: 1 hits" in report and "1 notes on channels other than 10" in report


def test_beats(tmp_path: Path) -> None:
    times = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]  # the example's tempo map
    times[3] += 0.1  # one reference beat is 100 ms away: 7 of 8 match
    rows = [f"{t},{i % 4 + 1}" for i, t in enumerate(times)]
    beats = write_csv(tmp_path / "ref.beats.csv", rows, header="time_s,beat")
    ref = write_csv(tmp_path / "ref.csv", [])
    result = ev.evaluate(
        ev.load_prediction(EXAMPLES / "groove.events.json"), ev.load_reference(ref, beats)
    )
    assert result["beats"] == {"pred_has_beats": True, "beat_f": 0.875, "downbeat_f": 1.0}
    no_beats = ev.load_prediction(EXAMPLES / "detection-only.events.json")
    result = ev.evaluate(no_beats, ev.load_reference(ref, beats))
    assert result["beats"] == {"pred_has_beats": False, "beat_f": 0.0, "downbeat_f": 0.0}


def test_example_json_matches_its_csv() -> None:
    pred = ev.load_prediction(EXAMPLES / "groove.events.json")
    ref = ev.load_reference(EXAMPLES / "groove.events.csv")
    assert ev.evaluate(pred, ref)["onsets"][1]["all"]["f"] == 1.0


def test_csv_reader(tmp_path: Path) -> None:
    rows = ["2.0,snare,,", "1.0,kick,0.5,64"]
    events = read_events_csv(write_csv(tmp_path / "a.csv", rows))
    assert [(e.time_s, e.cls, e.confidence, e.velocity) for e in events] == [
        (1.0, "kick", 0.5, 64),
        (2.0, "snare", 1.0, 100),  # blank cells read as 1.0 and 100
    ]
    assert read_events_csv(write_csv(tmp_path / "b.csv", ["1,tom"], header="time_s,class"))
    bad = write_csv(tmp_path / "c.csv", ["1.0,cowbell,,", "x,kick,,", "1.0,kick,2,", "1,kick,,"])
    with pytest.raises(InputError, match="3 bad rows") as e:
        read_events_csv(bad)
    assert "line 2: unknown class 'cowbell'" in str(e.value)
    assert "line 3:" in str(e.value) and "line 4:" in str(e.value) and "line 5" not in str(e.value)
    with pytest.raises(InputError, match="the header must be"):
        read_events_csv(write_csv(tmp_path / "d.csv", ["1,kick"], header="time,instrument"))


def test_cli(pair: tuple[Path, Path], tmp_path: Path) -> None:
    pred, ref = pair
    args = ["evaluate", "--pred", str(pred), "--ref", str(ref), "--out", str(tmp_path / "res")]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "## Onsets, ±50 ms" in result.stdout and "## Onsets, ±30 ms" in result.stdout
    assert "| **all** | 0.500 | 0.750 | 0.600 | 3 | 3 | 1 |" in result.stdout
    assert "| tom | – | – | – | 0 | 0 | 0 |" in result.stdout
    assert json.loads((tmp_path / "res.json").read_text())["onsets"][0]["all"]["f"] == 0.6
    assert (tmp_path / "res.md").read_text(encoding="utf-8") == result.stdout
    only20 = runner.invoke(app, [*args[:5], "--tolerance-ms", "20"])
    assert "±20 ms" in only20.stdout and "±50 ms" not in only20.stdout


def test_cli_input_errors(pair: tuple[Path, Path], tmp_path: Path) -> None:
    pred, ref = pair
    bad = write_csv(tmp_path / "bad.csv", ["1.0,cowbell,,"])
    result = runner.invoke(app, ["evaluate", "--pred", str(bad), "--ref", str(ref)])
    assert result.exit_code == 2 and "line 2: unknown class 'cowbell'" in result.stderr
    result = runner.invoke(app, ["evaluate", "--pred", str(ref), "--ref", str(tmp_path / "x.mid")])
    assert result.exit_code == 2 and "Cannot read MIDI file x.mid" in result.stderr
