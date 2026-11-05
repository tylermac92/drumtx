"""M3-5: the instrument mapping, the default and --mapping."""

from pathlib import Path

import mido
import pytest
import soundfile as sf
from typer.testing import CliRunner

from drumtx import mapping
from drumtx.cli import app
from drumtx.errors import InputError
from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import CLASSES
from drumtx.synth import render

runner = CliRunner()


def toml(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "my-mapping.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_default_passes_its_own_checks() -> None:
    default = mapping.load()
    assert list(default) == list(CLASSES)
    assert mapping.load(mapping.DEFAULT) == default
    assert (default["kick"].midi_note, default["kick"].display, default["kick"].voice) == (
        36,
        "F4",
        2,
    )


def test_custom_mapping_overrides_only_what_it_sets(tmp_path: Path) -> None:
    custom = mapping.load(toml(tmp_path, '[kick]\nmidi_note = 35\ndisplay = "E4"\n'))
    assert (custom["kick"].midi_note, custom["kick"].display) == (35, "E4")  # MIDI and staff
    assert custom["kick"].notehead == "normal" and custom["snare"] == mapping.load()["snare"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[snares]\nvoice = 1\n", "[snares] is not a class"),
        ("[snare]\nnotehed = 'x'\n", "[snare] notehed is not a key"),
        ("[snare]\nmidi_note = 200\n", "[snare] midi_note must be a whole number from 0 to 127"),
        ("[snare]\nmidi_note = 38.0\n", "[snare] midi_note must be a whole number"),
        ("[hihat]\ndisplay = 'H5'\n", "[hihat] display must be a step and octave"),
        ("[tom]\nnotehead = 'diamond'\n", '[tom] notehead must be "normal" or "x"'),
        ("[kick]\nvoice = 3\n", "[kick] voice must be 1 or 2"),
        ("[kick]\nname = ''\n", "[kick] name must be a non-empty string"),
        ("kick = 36\n", "kick must be a table"),
        ("[kick\n", "is not valid TOML"),
    ],
)
def test_bad_files_name_the_key(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(InputError) as e:
        mapping.load(toml(tmp_path, text))
    assert message in str(e.value)


def test_every_error_is_reported(tmp_path: Path) -> None:
    with pytest.raises(InputError) as e:
        mapping.load(toml(tmp_path, "[kick]\nvoice = 3\n[snare]\nmidi_note = -1\n"))
    assert "[kick] voice" in str(e.value) and "[snare] midi_note" in str(e.value)


def run(tmp_path: Path, *options: str) -> tuple[int, str]:
    wav = tmp_path / "in.wav"
    sf.write(wav, render([(1.0, "kick", 100)], 3.0), SAMPLE_RATE)
    args = ["transcribe", str(wav), "-o", str(tmp_path / "out"), "-q", "--model", "baseline"]
    result = runner.invoke(app, [*args, "--force", *options])
    return result.exit_code, result.stderr


def test_mapping_option_changes_the_midi_notes(tmp_path: Path) -> None:
    path = toml(tmp_path, "[kick]\nmidi_note = 35\n")
    assert run(tmp_path, "--mapping", str(path))[0] == 0
    notes = {m.note for m in mido.MidiFile(tmp_path / "out" / "in.mid") if m.type == "note_on"}
    assert 35 in notes and 36 not in notes


def test_bad_mapping_option_exits_2(tmp_path: Path) -> None:
    code, err = run(tmp_path, "--mapping", str(toml(tmp_path, "[kick]\nvoice = 3\n")))
    assert code == 2 and "[kick] voice must be 1 or 2" in err
    assert not (tmp_path / "out").exists()  # checked before any work
    code, err = run(tmp_path, "--mapping", str(tmp_path / "missing.toml"))
    assert code == 2 and "Cannot read the mapping" in err
