# 0007 — MusicXML writer and notation apps (resolves Q4)

- **Status:** Accepted, 2026-11-03
- **Task:** M0-6

## Decisions

- **Q4: MuseScore is the only supported notation app.** Compatibility checks (Technical Design Document §10, M3-4, M4) target MuseScore alone.
- **Writer: a minimal custom writer on the standard library's `xml.etree.ElementTree`.** music21 is not used. This is about 100 lines in `spikes/m0-6/groove.py` (`custom()`), and it is the starting point for M4-1.

## The spike

`spikes/m0-6/groove.py` writes the same two-bar groove twice:

- kick on beats 1 and 3, plus two 8ths on beat 3 of bar 2;
- snare on beats 2 and 4;
- 8th-note hi-hats;
- an 8th-note triplet (snare and hi-hat, then two hi-hats) on beat 4 of bar 2.

The layout follows the Technical Design Document §5:
- one percussion staff, `divisions = 12`;
- voice 1, stems up, for the hands; voice 2, stems down, for the kick;
- kick F4, snare C5, hi-hat G5 with an x notehead.

Both files were checked three ways:

| Check | Custom writer | music21 10.5.2 |
|---|---|---|
| MusicXML 4.0 XSD (offline, lxml) | Valid | Valid |
| MuseScore 3.2.3 render: staff positions, x noteheads, two voices, beaming per beat, triplet bracket | All correct | All correct |
| Clef | Percussion | **Treble** |
| Drum instrument in MuseScore (export to MIDI) | Imported as a drum kit, channel 10: kick 36 ×5, snare 38 ×4, hi-hat 42 ×17 (all correct) | **Imported as a pitched part on channel 1** (notes 65 / 72 / 79), so playback is wrong. MuseScore reports "no instrument found for part". |
| Extra output | — | Default "Music21 Fragment" title and "Music21" composer |
| Install footprint | None (standard library) | music21 112 MB, plus matplotlib, jsonpickle, chardet, joblib, requests and webcolors |

music21 could be made to emit a percussion clef, per-note instruments and MIDI mappings. But that means fighting its defaults to reach elements the custom writer writes directly (`<unpitched>`, `<instrument>`, `<midi-unpitched>`, `<notehead>`, `<time-modification>`, `<beam>`), at a large dependency cost.

## Golden file

The spike's output was committed as `tests/golden/groove.musicxml`. M4-1 replaced it with the writer's own golden files (below); the spike's copy stays in `spikes/m0-6/groove_custom.musicxml`.

## Caveats

- **MuseScore version.** The check used MuseScore 3.2.3, the version Ubuntu packages, which renders headlessly. Opening `tests/golden/triplet.musicxml` once in your own MuseScore 4 is a one-minute manual check worth doing.
- **Benign import warning.** MuseScore 3 logs `element already exists` at the triplet's first chord, but renders and plays it correctly. Resolved in M4-1, below.

## Reproducing

Run these in the spike environment (decision 0005) with `music21` and `lxml` added. The XSD imports must point at local copies of `xml.xsd` and `xlink.xsd` from <https://github.com/w3c/musicxml/tree/v4.0/schema>.

```bash
python spikes/m0-6/groove.py
```

```bash
xvfb-run -a mscore3 -o groove.png spikes/m0-6/groove_custom.musicxml
```

```bash
xvfb-run -a mscore3 -o groove.mid spikes/m0-6/groove_custom.musicxml
```

## M4-1: the writer (`src/drumtx/musicxml.py`)

The writer follows the spike, with these choices:

- **Measures** run from measure 1 (or 0, when the pickup has hits) to the last measure of the tempo map or of the hits, so the score covers the audio. Proper pickup and trailing measures are M4-4.
- **Grid per beat.** Each beat is on a 16th or an 8th-note triplet grid (with `<time-modification>` and a `<tuplet>`). M4-1 wrote one note or rest per slot. M4-2 added readability: notes last until the next hit in the beat, beams per beat with 16th hooks, consolidated rests, and a triplet bracket only when the group isn't three beamed notes. The rules, and the check on ten development-set clips, are in `docs/notation-checklist.md`.
- **Voice 2 only where it has hits.** Voice 1 always fills the measure.
- **Instrument IDs are per class** (`P1-kick`), so a mapping that gives two classes the same MIDI note still writes unique IDs.
- **Tempo:** one `<metronome>` and `<sound tempo>`, the median beat interval rounded to whole BPM. None without a tempo map.
- **Hits without a position** (fewer than two beats) are left out; the MIDI file still has them.

**Golden files** (`tests/golden/`), from `docs/schema/examples/groove.events.json`:

| File | Case |
|---|---|
| `straight.musicxml` | Bar 1 of the groove (16ths), bar 2 empty |
| `triplet.musicxml` | The whole groove; bar 2 ends with an 8th-note triplet |
| `empty-measure.musicxml` | Bar 2 of the groove only, so bar 1 is a measure rest |

After a deliberate change, regenerate them with `DRUMTX_UPDATE_GOLDEN=1 uv run pytest tests/test_musicxml.py` and review the diff.

**XSD validation.** `tests/test_musicxml.py` validates every output it writes (golden files, ten random scores with 2–7 beats per bar and a pickup, and a `transcribe` run) against the MusicXML 4.0 XSD, with lxml (a dev dependency). The XSD is not in the repo: `scripts/fetch_musicxml_xsd.py DIR` downloads it from the `v4.0` tag with its SHA-256 checked, and the tests read it from `DRUMTX_MUSICXML_XSD=DIR`. CI does both; elsewhere the tests skip without it.

**MuseScore 3.2.3 check** (2026-11-05). All three golden files render as expected (percussion clef, x noteheads, two voices, the triplet bracket, ♩ = 120). Exported to MIDI, every hit is on channel 10 with the right note: the triplet case gives kick 36 ×5, snare 38 ×4, hi-hat 42 ×17, as in the groove. The `element already exists` lines are benign: MuseScore 3 logs one whenever two notes or rests of the part start on the same tick (a chord, or the two voices), as it records an instrument per tick. Every two-voice drum score triggers it; it does not change the import.
