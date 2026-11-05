"""The MusicXML writer (Technical Design Document §5; M4-1; decision 0007): MusicXML 4.0, one
percussion part on a five-line staff.

- Measures run from measure 1 to the last measure of the tempo map or of the hits, numbered as in
  events.json (M4-4). Hits before the first downbeat go in a pickup, measure 0: a full measure,
  padded with rests, marked implicit so notation apps number the next measure 1. A partial last
  measure is padded with rests too; silences are measure rests. One time signature, and one
  tempo marking: the median tempo.
- Readability (M4-2; checklist in docs/notation-checklist.md): within each beat and voice, a rest
  runs up to the first hit and each hit lasts until the next one or the end of the beat. Notes
  shorter than a quarter are beamed per beat, with a second beam or hook for 16ths. A triplet beat
  gets a bracket, unless it is three beamed notes, which show only the 3. A beat with no hits in a
  voice is a quarter rest; two on beats 1–2 or 3–4 a half rest; a measure with none, a measure
  rest. Voice 2 is written only in measures where it has hits.
- The mapping gives each class its instrument name, MIDI note, staff position, notehead and voice;
  voice 1 has stems up, voice 2 stems down.
- Hits without a grid position (with fewer than two beats) are left out.
- With `mark_uncertain` (`--mark-uncertain`, M4-3), notes flagged `uncertain` by the review are
  colored UNCERTAIN_COLOR. Without it, no color is written.
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from drumtx.mapping import Mapping
from drumtx.quantize import SLOTS
from drumtx.schema import CLASSES, DrumEvent, Grid, QuantizedScore

UNCERTAIN_COLOR = "#E00000"  # red
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


# (duration in divisions, part of a triplet) -> (type, dots)
TYPES: dict[tuple[int, bool], tuple[str, int]] = {
    (3, False): ("16th", 0),
    (6, False): ("eighth", 0),
    (9, False): ("eighth", 1),
    (12, False): ("quarter", 0),
    (24, False): ("half", 0),
    (4, True): ("eighth", 0),
    (8, True): ("quarter", 0),
}


@dataclass
class _Item:
    """A note (a chord of hits) or a rest (no hits) in one voice."""

    duration: int
    hits: list[DrumEvent]
    triplet: bool = False
    beams: tuple[str, ...] = ()  # one entry per beam level
    tuplet: dict[str, str] | None = None  # attributes of <tuplet> on a triplet's first or last item


def _beat(slots: dict[int, list[DrumEvent]], grid: Grid) -> list[_Item]:
    """One beat of one voice: a rest up to the first hit, then each hit lasting to the next."""
    k = SLOTS[grid]
    step, hits = DIVISIONS // k, sorted(slots)
    items = [_Item((hits[0] - 1) * step, [])] if hits[0] > 1 else []
    items += [
        _Item((b - a) * step, slots[a]) for a, b in zip(hits, [*hits[1:], k + 1], strict=True)
    ]
    triplet = grid == "triplet" and len(items) > 1  # one hit filling the beat is a plain quarter
    for x in items:
        x.triplet = triplet
    beamed = [x for x in items if x.hits and TYPES[x.duration, triplet][0] != "quarter"]
    if triplet:
        # A triplet of three beamed notes shows only its number; any rest or quarter, a bracket.
        bracket = "no" if len(beamed) == len(items) else "yes"
        items[0].tuplet, items[-1].tuplet = {"type": "start", "bracket": bracket}, {"type": "stop"}
    if len(beamed) > 1:
        for i, x in enumerate(beamed):
            x.beams = ("begin" if i == 0 else "end" if i == len(beamed) - 1 else "continue",)
            if not triplet and x.duration == 3:  # a 16th: a second beam, or a hook
                before = i > 0 and beamed[i - 1].duration == 3
                after = i < len(beamed) - 1 and beamed[i + 1].duration == 3
                joins = {(True, True): "continue", (True, False): "end", (False, True): "begin"}
                hook = "forward hook" if i == 0 else "backward hook"
                x.beams += (joins.get((before, after), hook),)
    return items


def _measure(
    cells: dict[int, dict[int, list[DrumEvent]]], grids: dict[int, Grid], per_bar: int
) -> list[_Item]:
    """One measure of one voice, from its hits per beat. Empty beats are quarter rests, two of
    them starting on an odd beat (1–2, 3–4) a half rest."""
    items: list[_Item] = []
    b = 1
    while b <= per_bar:
        if b in cells:
            items += _beat(cells[b], grids[b])
        elif b % 2 and b < per_bar and b + 1 not in cells:
            items.append(_Item(2 * DIVISIONS, []))
            b += 1
        else:
            items.append(_Item(DIVISIONS, []))
        b += 1
    return items


def _note(m: ET.Element, x: _Item, voice: int, instruments: Mapping, mark_uncertain: bool) -> None:
    kind, dots = TYPES[x.duration, x.triplet]
    for i, e in enumerate(x.hits or [None]):
        cls = None if e is None else e.cls
        uncertain = mark_uncertain and e is not None and "uncertain" in e.flags
        n = _sub(m, "note", **({"color": UNCERTAIN_COLOR} if uncertain else {}))
        if i:
            _sub(n, "chord")
        if cls is None:
            _sub(n, "rest")
        else:
            u = _sub(n, "unpitched")
            _sub(u, "display-step", instruments[cls].display[0])
            _sub(u, "display-octave", instruments[cls].display[1])
        _sub(n, "duration", x.duration)
        if cls is not None:
            _sub(n, "instrument", id=f"P1-{cls}")
        _sub(n, "voice", voice)
        _sub(n, "type", kind)
        for _ in range(dots):
            _sub(n, "dot")
        if x.triplet:
            tm = _sub(n, "time-modification")
            _sub(tm, "actual-notes", 3)
            _sub(tm, "normal-notes", 2)
        if cls is not None:
            _sub(n, "stem", "up" if voice == 1 else "down")
            if instruments[cls].notehead == "x":
                _sub(n, "notehead", "x")
        if i == 0:
            for level, beam in enumerate(x.beams, start=1):
                _sub(n, "beam", beam, number=str(level))
            if x.tuplet:
                _sub(_sub(n, "notations"), "tuplet", **x.tuplet)


def musicxml_bytes(
    score: QuantizedScore, instruments: Mapping, mark_uncertain: bool = False
) -> bytes:
    tm = score.tempo_map
    per_bar = tm.time_signatures[0].beats
    # (measure, voice) -> beat -> slot -> classes, in class order; (measure) -> beat -> grid
    cells: dict[tuple[int, int], dict[int, dict[int, list[DrumEvent]]]] = defaultdict(dict)
    grids: dict[int, dict[int, Grid]] = defaultdict(dict)
    for e in sorted(score.events, key=lambda e: CLASSES.index(e.cls)):
        if q := e.quantized:
            beat = cells[q.measure, instruments[e.cls].voice].setdefault(q.beat, {})
            beat.setdefault(q.slot, []).append(e)
            grids[q.measure][q.beat] = q.grid
    first = min([1, *grids])
    last = max([1, *grids, *(b.measure for b in tm.beats)])

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
        m = _sub(
            part, "measure", number=str(number), **({"implicit": "yes"} if number == 0 else {})
        )
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
        for voice in (1, 2):
            if (number, voice) not in cells:
                if voice == 2:
                    continue
                n = _sub(m, "note")
                _sub(n, "rest", measure="yes")
                _sub(n, "duration", per_bar * DIVISIONS)
                _sub(n, "voice", voice)
                continue
            if voice == 2:
                _sub(_sub(m, "backup"), "duration", per_bar * DIVISIONS)
            for x in _measure(cells[number, voice], grids[number], per_bar):
                _note(m, x, voice, instruments, mark_uncertain)

    ET.indent(root)
    body = ET.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{DOCTYPE}\n{body}\n'.encode()
