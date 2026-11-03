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

`tests/golden/groove.musicxml` is the custom writer's output, committed as the first golden file for M4-1. `.gitattributes` keeps its line endings byte-exact on Windows.

## Caveats

- **MuseScore version.** The check used MuseScore 3.2.3, the version Ubuntu packages, which renders headlessly. Opening `tests/golden/groove.musicxml` once in your own MuseScore 4 is a one-minute manual check worth doing.
- **Benign import warning.** MuseScore 3 logs `element already exists` at the triplet's first chord, but renders and plays it correctly. M4-1 should look into it.

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
