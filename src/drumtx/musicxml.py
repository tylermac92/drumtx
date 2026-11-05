"""The MusicXML writer (Technical Design Document §5; M4-1; decision 0007): MusicXML 4.0, one
percussion part on a five-line staff.

- Measures run from measure 1 (or 0, when the pickup has hits) to the last measure of the tempo
  map or of the hits. One time signature, and one tempo marking: the median tempo.
- Each beat is written on its grid, one note or rest per slot: four 16ths, or an 8th-note
  triplet. A beat with no hits in a voice is a quarter rest; a measure with none, a measure rest.
  Voice 2 is written only in measures where it has hits. (M4-2 makes this readable.)
- The mapping gives each class its instrument name, MIDI note, staff position, notehead and voice;
  voice 1 has stems up, voice 2 stems down.
- Hits without a grid position (with fewer than two beats) are left out.
"""

import xml.etree.ElementTree as ET
from collections import defaultdict

import numpy as np

from drumtx.mapping import Mapping
from drumtx.quantize import SLOTS
from drumtx.schema import CLASSES, DrumClass, Grid, QuantizedScore

DIVISIONS = 12  # per quarter: 16ths (3) and 8th-note triplets (4) are both whole numbers
DOCTYPE = (
    '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
    '"http://www.musicxml.org/dtds/partwise.dtd">'
)


def _sub(parent: ET.Element, tag: str, text: object = None, **attrib: str) -> ET.Element:
    e = ET.SubElement(parent, tag, attrib)
    if text is not None:
        e.text = str(text)
    return e


def _note(
    m: ET.Element,
    classes: list[DrumClass],
    voice: int,
    instruments: Mapping,
    grid: Grid | None = None,  # None: a quarter rest
    tuplet: str | None = None,  # "start" or "stop" on a triplet's first or last slot
) -> None:
    """One slot: a chord of the classes, or a rest."""
    for i, cls in enumerate(classes or [None]):
        n = _sub(m, "note")
        if i:
            _sub(n, "chord")
        if cls is None:
            _sub(n, "rest")
        else:
            u = _sub(n, "unpitched")
            _sub(u, "display-step", instruments[cls].display[0])
            _sub(u, "display-octave", instruments[cls].display[1])
        _sub(n, "duration", DIVISIONS // SLOTS[grid] if grid else DIVISIONS)
        if cls is not None:
            _sub(n, "instrument", id=f"P1-{cls}")
        _sub(n, "voice", voice)
        _sub(n, "type", {None: "quarter", "16th": "16th", "triplet": "eighth"}[grid])
        if grid == "triplet":
            tm = _sub(n, "time-modification")
            _sub(tm, "actual-notes", 3)
            _sub(tm, "normal-notes", 2)
        if cls is not None:
            _sub(n, "stem", "up" if voice == 1 else "down")
            if instruments[cls].notehead == "x":
                _sub(n, "notehead", "x")
        if tuplet and i == 0:
            _sub(_sub(n, "notations"), "tuplet", type=tuplet, bracket="yes")


def musicxml_bytes(score: QuantizedScore, instruments: Mapping) -> bytes:
    tm = score.tempo_map
    per_bar = tm.time_signatures[0].beats
    # (measure, beat, voice) -> slot -> classes, in class order
    cells: dict[tuple[int, int, int], dict[int, list[DrumClass]]] = defaultdict(dict)
    grids: dict[tuple[int, int], Grid] = {}
    for e in sorted(score.events, key=lambda e: CLASSES.index(e.cls)):
        if q := e.quantized:
            key = (q.measure, q.beat, instruments[e.cls].voice)
            cells[key].setdefault(q.slot, []).append(e.cls)
            grids[q.measure, q.beat] = q.grid
    measures = [m for m, _ in grids] + [b.measure for b in tm.beats]
    first, last = min([1, *(m for m, _ in grids)]), max([1, *measures])

    root = ET.Element("score-partwise", version="4.0")
    sp = _sub(_sub(root, "part-list"), "score-part", id="P1")
    _sub(sp, "part-name", "Drums")
    for cls in CLASSES:
        _sub(_sub(sp, "score-instrument", id=f"P1-{cls}"), "instrument-name", instruments[cls].name)
    for cls in CLASSES:
        mi = _sub(sp, "midi-instrument", id=f"P1-{cls}")
        _sub(mi, "midi-channel", 10)
        _sub(mi, "midi-unpitched", instruments[cls].midi_note + 1)  # numbered from 1
    part = _sub(root, "part", id="P1")
    for number in range(first, last + 1):
        m = _sub(part, "measure", number=str(number))
        if number == first:
            attrs = _sub(m, "attributes")
            _sub(attrs, "divisions", DIVISIONS)
            _sub(_sub(attrs, "key"), "fifths", 0)
            t = _sub(attrs, "time")
            _sub(t, "beats", per_bar)
            _sub(t, "beat-type", 4)
            _sub(_sub(attrs, "clef"), "sign", "percussion")
            if len(tm.beats) >= 2:
                bpm = round(60 / float(np.median(np.diff([b.time_s for b in tm.beats]))))
                d = _sub(m, "direction", placement="above")
                metronome = _sub(_sub(d, "direction-type"), "metronome")
                _sub(metronome, "beat-unit", "quarter")
                _sub(metronome, "per-minute", bpm)
                _sub(d, "sound", tempo=str(bpm))
        beats = range(1, per_bar + 1)
        for voice in (1, 2):
            if not any((number, b, voice) in cells for b in beats):
                if voice == 2:
                    continue
                n = _sub(m, "note")
                _sub(n, "rest", measure="yes")
                _sub(n, "duration", per_bar * DIVISIONS)
                _sub(n, "voice", voice)
                continue
            if voice == 2:
                _sub(_sub(m, "backup"), "duration", per_bar * DIVISIONS)
            for b in beats:
                if (number, b, voice) not in cells:
                    _note(m, [], voice, instruments)
                    continue
                slots, grid = cells[number, b, voice], grids[number, b]
                k = SLOTS[grid]
                for s in range(1, k + 1):
                    tuplet = {1: "start", k: "stop"}.get(s) if grid == "triplet" else None
                    _note(m, slots.get(s, []), voice, instruments, grid, tuplet)

    ET.indent(root)
    body = ET.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{DOCTYPE}\n{body}\n'.encode()
