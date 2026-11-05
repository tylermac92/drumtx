"""M4-1: the MusicXML writer. Every output is checked against the MusicXML 4.0 XSD, which
scripts/fetch_musicxml_xsd.py downloads; without it these checks skip, except in CI."""

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from lxml import etree
from typer.testing import CliRunner

from drumtx import mapping, review
from drumtx.beats import tempo_map
from drumtx.cli import app
from drumtx.ingest import SAMPLE_RATE
from drumtx.musicxml import (
    DIVISIONS,
    TYPES,
    UNCERTAIN_COLOR,
    _beat,
    _Item,
    _measure,
    musicxml_bytes,
)
from drumtx.quantize import quantize
from drumtx.schema import (
    CLASSES,
    Beat,
    DrumEvent,
    QuantizedScore,
    TempoMap,
    TimeSignature,
    event_from_json,
)
from drumtx.synth import render

GOLDEN = Path(__file__).parent / "golden"
EXAMPLE = Path(__file__).parents[1] / "docs" / "schema" / "examples" / "groove.events.json"
INSTRUMENTS = mapping.load()
SNARE = DrumEvent(1.0, "snare", 0.9, 100)


@pytest.fixture(scope="module")
def xsd() -> Any:
    folder = os.environ.get("DRUMTX_MUSICXML_XSD")
    if not folder:
        if os.environ.get("CI"):
            pytest.fail("DRUMTX_MUSICXML_XSD is not set: CI must validate MusicXML")
        pytest.skip("Set DRUMTX_MUSICXML_XSD; see scripts/fetch_musicxml_xsd.py")
    local = Path(folder)

    class Local(etree.Resolver):  # type: ignore[misc]
        """musicxml.xsd imports xml.xsd and xlink.xsd by URL: read the local copies."""

        def resolve(self, url: str, pubid: str, context: Any) -> Any:
            return self.resolve_filename(str(local / url.rsplit("/", 1)[-1]), context)

    parser = etree.XMLParser(no_network=True)
    parser.resolvers.add(Local())
    return etree.XMLSchema(etree.parse(str(local / "musicxml.xsd"), parser))


def check(xsd: Any, data: bytes) -> ET.Element:
    """Valid against the XSD, and every voice fills every measure exactly."""
    xsd.assertValid(etree.fromstring(data, etree.XMLParser(no_network=True)))
    root = ET.fromstring(data)
    beats = int(root.findtext(".//time/beats") or 0)
    for m in root.iter("measure"):
        filled: dict[str, int] = {}
        for n in m.iter("note"):
            if n.find("chord") is None:
                voice = n.findtext("voice") or ""
                filled[voice] = filled.get(voice, 0) + int(n.findtext("duration") or 0)
        assert "1" in filled and set(filled.values()) == {beats * DIVISIONS}, m.get("number")
    return root


def example(measures: tuple[int, ...]) -> QuantizedScore:
    """The schema example groove, with only the hits of these measures."""
    doc = json.loads(EXAMPLE.read_text())
    tm = doc["tempo_map"]
    return QuantizedScore(
        TempoMap(
            tuple(Beat(**b) for b in tm["beats"]),
            tuple(TimeSignature(**s) for s in tm["time_signatures"]),
            tm["tempo_source"],
            tm["time_signature_source"],
            tm["first_downbeat_source"],
        ),
        tuple(event_from_json(e) for e in doc["events"] if e["quantized"]["measure"] in measures),
    )


# straight: 16ths in bar 1 and a rest in bar 2; triplet: the whole groove (bar 2 ends with a
# triplet); empty-measure: bar 1 empty.
CASES = {"straight": (1,), "triplet": (1, 2), "empty-measure": (2,)}


@pytest.mark.parametrize("case", CASES)
def test_golden(xsd: Any, case: str) -> None:
    """DRUMTX_UPDATE_GOLDEN=1 rewrites them after a deliberate change."""
    data = musicxml_bytes(example(CASES[case]), INSTRUMENTS)
    check(xsd, data)
    path = GOLDEN / f"{case}.musicxml"
    if os.environ.get("DRUMTX_UPDATE_GOLDEN"):
        path.write_bytes(data)
    assert data == path.read_bytes()


@pytest.mark.parametrize("seed", range(10))
def test_random_scores_are_valid(xsd: Any, seed: int) -> None:
    """Drifting tempo, a pickup, 2–7 beats per bar, every class: every hit is written once."""
    rng = np.random.default_rng(seed)
    t = 1.7 + np.cumsum(60 / rng.uniform(60, 200) * rng.uniform(0.9, 1.1, 40))
    per_bar = int(rng.integers(2, 8))
    tm = tempo_map(t, t[2::per_bar], beats_per_bar=per_bar)
    events = [
        DrumEvent(float(x), CLASSES[int(rng.integers(0, 5))], 0.9, 100)
        for x in np.sort(rng.uniform(0, t[-1] + 2, 150)).round(3)
    ]
    score = quantize(events, tm)
    root = check(xsd, musicxml_bytes(score, INSTRUMENTS))
    assert len(root.findall(".//note/unpitched")) == len(score.events)
    hit_measures = [e.quantized.measure for e in score.events if e.quantized]
    first, last = min([1, *hit_measures]), max(hit_measures + [b.measure for b in tm.beats])
    numbers = [int(m.get("number") or "") for m in root.iter("measure")]
    assert numbers == list(range(first, last + 1))


def test_mapping_and_tempo(xsd: Any, tmp_path: Path) -> None:
    custom = tmp_path / "mapping.toml"
    custom.write_text(
        '[kick]\nname = "Bass drum"\nmidi_note = 35\ndisplay = "E4"\nnotehead = "x"\n'
    )
    t = 1.0 + np.arange(8) * 0.6  # 100 BPM
    score = quantize([DrumEvent(1.0, "kick", 0.9, 100)], tempo_map(t, t[::4]))
    root = check(xsd, musicxml_bytes(score, mapping.load(custom)))
    assert root.findtext(".//score-instrument[@id='P1-kick']/instrument-name") == "Bass drum"
    assert root.findtext(".//midi-instrument[@id='P1-kick']/midi-unpitched") == "36"
    note = root.find(".//note[instrument]")
    assert note is not None
    assert [note.findtext(k) for k in ("unpitched/display-step", "unpitched/display-octave")] == [
        "E",
        "4",
    ]
    assert [note.findtext(k) for k in ("voice", "stem", "notehead")] == ["2", "down", "x"]
    assert root.findtext(".//metronome/per-minute") == "100"
    assert root.find(".//sound").get("tempo") == "100"  # type: ignore[union-attr]


def test_without_a_tempo_map(xsd: Any) -> None:
    """Fewer than two beats: no hit has a position, so one empty measure and no tempo marking."""
    score = QuantizedScore(
        tempo_map(np.array([1.0]), np.array([1.0])), (DrumEvent(1.25, "kick", 0.9, 100),)
    )
    root = check(xsd, musicxml_bytes(score, INSTRUMENTS))
    assert len(root.findall(".//measure")) == 1 and root.find(".//metronome") is None
    assert root.find(".//rest").get("measure") == "yes"  # type: ignore[union-attr]


def test_pickup_hits_get_measure_0(xsd: Any) -> None:
    t = 1.0 + np.arange(12) * 0.5
    tm = tempo_map(t, t[2::4])  # beats 1–2 are a pickup, measure 0
    score = quantize([DrumEvent(1.5, "snare", 0.9, 100), DrumEvent(2.0, "kick", 0.9, 100)], tm)
    assert [e.quantized.measure for e in score.events if e.quantized] == [0, 1]
    root = check(xsd, musicxml_bytes(score, INSTRUMENTS))
    assert [m.get("number") for m in root.iter("measure")] == ["0", "1", "2", "3"]


def test_transcribe_writes_musicxml(xsd: Any, tmp_path: Path) -> None:
    wav, out = tmp_path / "in.wav", tmp_path / "out"
    sf.write(wav, render([(1.0, "kick", 100), (1.5, "snare", 100)], 4.0), SAMPLE_RATE)
    args = ["transcribe", str(wav), "-o", str(out), "-q", "--model", "baseline"]
    assert CliRunner().invoke(app, args).exit_code == 0
    root = check(xsd, (out / "in.musicxml").read_bytes())
    events = json.loads((out / "in.events.json").read_text())["events"]
    assert len(root.findall(".//note/unpitched")) == len(events) > 0
    for name in ("in.events.json", "in.events.csv", "in.mid"):
        (out / name).unlink()
    result = CliRunner().invoke(app, args)  # only in.musicxml is left, and it is not overwritten
    assert result.exit_code == 2 and "in.musicxml already exists" in result.stderr


def show(items: list[_Item]) -> list[str]:
    """Each item as rest or note, type, dots, triplet, and beams: "16 begin/forward hook"."""
    out = []
    for x in items:
        kind, dots = TYPES[x.duration, x.triplet]
        name = ("" if x.hits else "rest ") + kind + "." * dots + " 3" * x.triplet
        out.append(" ".join([name, "/".join(x.beams)]).strip())
    return out


@pytest.mark.parametrize(
    ("slots", "want"),
    [
        ((1,), ["quarter"]),
        ((1, 3), ["eighth begin", "eighth end"]),
        ((2,), ["rest 16th", "eighth."]),
        ((3,), ["rest eighth", "eighth"]),
        ((4,), ["rest eighth.", "16th"]),
        ((1, 4), ["eighth. begin", "16th end/backward hook"]),
        ((2, 4), ["rest 16th", "eighth begin", "16th end/backward hook"]),
        ((1, 2, 4), ["16th begin/forward hook", "eighth continue", "16th end/backward hook"]),
        ((1, 3, 4), ["eighth begin", "16th continue/begin", "16th end/end"]),
        (
            (1, 2, 3, 4),
            [
                "16th begin/begin",
                "16th continue/continue",
                "16th continue/continue",
                "16th end/end",
            ],
        ),
    ],
)
def test_16th_beats(slots: tuple[int, ...], want: list[str]) -> None:
    """Notes last until the next hit in the beat; a rest fills the start; beams per beat."""
    assert show(_beat({s: [SNARE] for s in slots}, "16th")) == want


@pytest.mark.parametrize(
    ("slots", "want", "bracket"),
    [
        ((1,), ["quarter"], None),  # one hit filling the beat: no triplet at all
        ((1, 2, 3), ["eighth 3 begin", "eighth 3 continue", "eighth 3 end"], "no"),
        ((1, 3), ["quarter 3", "eighth 3"], "yes"),
        ((1, 2), ["eighth 3", "quarter 3"], "yes"),
        ((2, 3), ["rest eighth 3", "eighth 3 begin", "eighth 3 end"], "yes"),
        ((3,), ["rest quarter 3", "eighth 3"], "yes"),
    ],
)
def test_triplet_beats(slots: tuple[int, ...], want: list[str], bracket: str | None) -> None:
    """Three beamed notes show only the 3; with a rest or a quarter, the bracket too."""
    items = _beat({s: [SNARE] for s in slots}, "triplet")
    assert show(items) == want
    assert (items[0].tuplet or {}).get("bracket") == bracket
    assert (items[-1].tuplet or {}).get("type") == ("stop" if bracket else None)


@pytest.mark.parametrize(
    ("per_bar", "beats", "want"),
    [
        (4, (1,), ["quarter", "rest quarter", "rest half"]),
        (4, (2,), ["rest quarter", "quarter", "rest half"]),
        (4, (4,), ["rest half", "rest quarter", "quarter"]),
        (4, (1, 4), ["quarter", "rest quarter", "rest quarter", "quarter"]),  # never across 2–3
        (3, (3,), ["rest half", "quarter"]),
        (5, (1,), ["quarter", "rest quarter", "rest half", "rest quarter"]),
    ],
)
def test_empty_beats_are_consolidated(
    per_bar: int, beats: tuple[int, ...], want: list[str]
) -> None:
    hits = {b: {1: [SNARE]} for b in beats}
    assert show(_measure(hits, {b: "16th" for b in beats}, per_bar)) == want


def test_mark_uncertain(xsd: Any) -> None:
    """The groove has one uncertain hi-hat. Only it is colored, and only with mark_uncertain."""
    score = review.flag(example((1, 2)))
    assert sum("uncertain" in e.flags for e in score.events) == 1
    assert b"color" not in musicxml_bytes(score, INSTRUMENTS)
    root = check(xsd, musicxml_bytes(score, INSTRUMENTS, mark_uncertain=True))
    colored = [n for n in root.iter("note") if n.get("color")]
    assert [(n.get("color"), n.find("instrument").get("id")) for n in colored] == [  # type: ignore[union-attr]
        (UNCERTAIN_COLOR, "P1-hihat")
    ]


def test_transcribe_mark_uncertain(tmp_path: Path) -> None:
    wav, out = tmp_path / "in.wav", tmp_path / "out"
    sf.write(wav, render([(1.0, "kick", 100), (1.5, "snare", 100)], 4.0), SAMPLE_RATE)
    args = ["transcribe", str(wav), "-o", str(out), "-q", "--model", "baseline", "--force"]
    assert CliRunner().invoke(app, args).exit_code == 0
    assert b"color=" not in (out / "in.musicxml").read_bytes()
    assert CliRunner().invoke(app, [*args, "--mark-uncertain"]).exit_code == 0
    doc = json.loads((out / "in.events.json").read_text())
    assert doc["settings"]["mark_uncertain"] is True
    uncertain = sum("uncertain" in e["flags"] for e in doc["events"])
    assert (out / "in.musicxml").read_bytes().count(b'color="') == uncertain
