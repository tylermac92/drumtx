"""M0-6 spike: write a two-bar drum groove as MusicXML twice, with music21 and a minimal writer.

    python groove.py   # spike-venv; writes groove_custom.musicxml and groove_music21.musicxml

Layout follows the Technical Design Document §5: one percussion staff, voice 1 (stems up) for the
hands, voice 2 (stems down) for the kick, divisions = 12, x noteheads for hi-hat and cymbal.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).parent
DIVISIONS = 12  # per quarter: 16ths (3) and 8th-note triplets (4) are both whole numbers
# class: (MIDI note, display step, display octave, notehead)
MAPPING = {
    "kick": (36, "F", 4, None),
    "snare": (38, "C", 5, None),
    "hihat": (42, "G", 5, "x"),
    "tom": (47, "D", 5, None),
    "cymbal": (49, "A", 5, "x"),
}
NAMES = {"kick": "Kick", "snare": "Snare", "hihat": "Hi-hat", "tom": "Tom", "cymbal": "Cymbal"}

# Per bar, per voice: (duration in divisions, classes); no classes means a rest.
HH, SN_HH = ("hihat",), ("snare", "hihat")
EIGHTHS = [(6, HH), (6, HH), (6, SN_HH), (6, HH), (6, HH), (6, HH)]
GROOVE = [
    {1: [*EIGHTHS, (6, SN_HH), (6, HH)], 2: [(12, ("kick",)), (12, ()), (12, ("kick",)), (12, ())]},
    {
        1: [*EIGHTHS, (4, SN_HH), (4, HH), (4, HH)],  # beat 4: 8th-note triplet
        2: [(12, ("kick",)), (12, ()), (6, ("kick",)), (6, ("kick",)), (12, ())],
    },
]
TYPES = {12: "quarter", 6: "eighth", 4: "eighth", 3: "16th"}


def sub(parent: ET.Element, tag: str, text: object = None, **attrib: str) -> ET.Element:
    e = ET.SubElement(parent, tag, attrib)
    if text is not None:
        e.text = str(text)
    return e


def beams(events: list[tuple[int, tuple[str, ...]]]) -> list[str | None]:
    """Beam eighth-or-shorter notes within each beat: begin / continue / end."""
    out: list[str | None] = [None] * len(events)
    pos, groups = 0, {}  # type: int, dict[int, list[int]]
    for i, (dur, classes) in enumerate(events):
        if dur < DIVISIONS and classes:
            groups.setdefault(pos // DIVISIONS, []).append(i)
        pos += dur
    for idx in groups.values():
        if len(idx) > 1:
            for k, i in enumerate(idx):
                out[i] = "begin" if k == 0 else "end" if k == len(idx) - 1 else "continue"
    return out


def custom() -> bytes:
    root = ET.Element("score-partwise", version="4.0")
    part_list = sub(root, "part-list")
    sp = sub(part_list, "score-part", id="P1")
    sub(sp, "part-name", "Drums")
    for c, (midi, *_rest) in MAPPING.items():
        sub(sub(sp, "score-instrument", id=f"P1-I{midi}"), "instrument-name", NAMES[c])
    for midi, *_rest in MAPPING.values():
        mi = sub(sp, "midi-instrument", id=f"P1-I{midi}")
        sub(mi, "midi-channel", 10)
        sub(mi, "midi-unpitched", midi + 1)  # MusicXML numbers MIDI notes from 1
    part = sub(root, "part", id="P1")
    for bar, voices in enumerate(GROOVE, start=1):
        m = sub(part, "measure", number=str(bar))
        if bar == 1:
            attrs = sub(m, "attributes")
            sub(attrs, "divisions", DIVISIONS)
            sub(sub(attrs, "key"), "fifths", 0)
            t = sub(attrs, "time")
            sub(t, "beats", 4)
            sub(t, "beat-type", 4)
            sub(sub(attrs, "clef"), "sign", "percussion")
        for v, events in voices.items():
            if v == 2:
                sub(sub(m, "backup"), "duration", 4 * DIVISIONS)
            stem = "up" if v == 1 else "down"
            triplet = [i for i, (d, _) in enumerate(events) if d == 4]
            for i, ((dur, classes), beam) in enumerate(zip(events, beams(events), strict=True)):
                for k, c in enumerate(classes or (None,)):
                    n = sub(m, "note")
                    if k:
                        sub(n, "chord")
                    if c is None:
                        sub(n, "rest")
                    else:
                        midi, step, octave, head = MAPPING[c]
                        u = sub(n, "unpitched")
                        sub(u, "display-step", step)
                        sub(u, "display-octave", octave)
                    sub(n, "duration", dur)
                    if c is not None:
                        sub(n, "instrument", id=f"P1-I{midi}")
                    sub(n, "voice", v)
                    sub(n, "type", TYPES[dur])
                    if dur == 4:
                        tm = sub(n, "time-modification")
                        sub(tm, "actual-notes", 3)
                        sub(tm, "normal-notes", 2)
                    if c is not None:
                        sub(n, "stem", stem)
                        if head:
                            sub(n, "notehead", head)
                    if beam and k == 0:
                        sub(n, "beam", beam, number="1")
                    if dur == 4 and k == 0 and i in (triplet[0], triplet[-1]):
                        kind = "start" if i == triplet[0] else "stop"
                        sub(sub(n, "notations"), "tuplet", type=kind, bracket="yes")
    ET.indent(root)
    doctype = (
        '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
        '"http://www.musicxml.org/dtds/partwise.dtd">\n'
    )
    body = ET.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{doctype}{body}\n'.encode()


def with_music21(path: Path) -> None:
    from music21 import duration, meter, note, percussion, stream

    score, part = stream.Score(), stream.Part()
    part.partName = "Drums"
    for bar, voices in enumerate(GROOVE, start=1):
        m = stream.Measure(number=bar)
        if bar == 1:
            m.append(meter.TimeSignature("4/4"))
        for v, events in voices.items():
            voice = stream.Voice(id=str(v))
            for dur, classes in events:
                d = duration.Duration(TYPES[dur])
                if dur == 4:
                    d.appendTuplet(duration.Tuplet(3, 2))
                if not classes:
                    voice.append(note.Rest(duration=d))
                    continue
                notes = []
                for c in classes:
                    _, step, octave, head = MAPPING[c]
                    n = note.Unpitched(displayName=f"{step}{octave}")
                    n.stemDirection = "up" if v == 1 else "down"
                    if head:
                        n.notehead = head
                    notes.append(n)
                el = notes[0] if len(notes) == 1 else percussion.PercussionChord(notes)
                el.duration = d
                voice.append(el)
            m.insert(0, voice)
        part.append(m)
    score.insert(0, part)
    score.write("musicxml", fp=str(path))


if __name__ == "__main__":
    (HERE / "groove_custom.musicxml").write_bytes(custom())
    with_music21(HERE / "groove_music21.musicxml")
    for f in ("groove_custom.musicxml", "groove_music21.musicxml"):
        print(f, (HERE / f).stat().st_size, "bytes")
