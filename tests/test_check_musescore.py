"""M4-5: how scripts/check_musescore.py reads MuseScore's output and MIDI export."""

import io

import mido
from check_musescore import midi_problems, problems

# Output of `mscore3 -o x.mid x.musicxml` (3.2.3), for a good file and for broken ones.
GOOD = """convert <ok.musicxml>...
instr 'P1-kick', tick 0/16 (0): element already exists
instr '', tick 5/16 (600): element already exists
QStandardPaths: XDG_RUNTIME_DIR not set, defaulting to '/tmp/runtime-root'
\tto <ok.mid>
... success!
"""
OVERFULL = """convert <overfull.musicxml>...
Error at line 80 col 13: calculated duration (1/8) not equal to specified duration (7/48)
\tto <overfull.mid>
ExportMidi: unknown time signature 75/64
... success!
"""
INVALID = """convert <invalid.musicxml>...
importMusicXml() file 'invalid.musicxml' is not a valid MusicXML file
MusicXMLStepAltOct2Pitch: illegal step -1
\tto <invalid.mid>
... success!
"""


def test_output_problems() -> None:
    assert problems(GOOD) == []
    assert problems(OVERFULL) == [
        "Error at line 80 col 13: calculated duration (1/8) not equal to specified duration (7/48)",
        "ExportMidi: unknown time signature 75/64",
    ]
    assert len(problems(INVALID)) == 2


def midi(channels: list[int]) -> bytes:
    track = mido.MidiTrack(
        [mido.Message("note_on", channel=c, note=36, velocity=100, time=10) for c in channels]
    )
    out = io.BytesIO()
    mido.MidiFile(tracks=[track]).save(file=out)
    return out.getvalue()


def test_midi_problems() -> None:
    assert midi_problems(midi([9, 9]), 2) == []
    assert midi_problems(midi([9]), 2) == ["MIDI has 1 notes, the score 2"]
    assert midi_problems(midi([9, 0]), 2) == ["MIDI notes outside channel 10"]
