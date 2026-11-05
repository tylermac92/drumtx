# Notation readability checklist (M4-2)

A transcription's MusicXML should read like a drum chart a drummer would write by hand. Check each item in MuseScore. The writer (`src/drumtx/musicxml.py`) implements the rules; the unit tests in `tests/test_musicxml.py` cover each one.

**Status:** written and checked by the developer. A review by a drummer is still open; record it at the end of this file.

## The checklist

**Layout**
1. One five-line staff with a percussion clef. One time signature and one tempo marking (♩ = median tempo), at the start.
2. Each instrument is on its mapped line or space (`mapping.toml`). Hi-hat and cymbal have x noteheads.
3. Hands (voice 1) have stems up. Feet (voice 2) have stems down.

**Durations**

4. Within a beat, each note lasts until the next hit in its voice, or the end of the beat. A beat with one hit on the beat is a quarter note, never a 16th and three rests.
5. A rest appears inside a beat only before its first hit. It is a single rest: a 16th, 8th or dotted 8th, or a triplet 8th or quarter.
6. Notes never tie across a beat.

**Beams**

7. Beams group the 8ths and 16ths of one beat, and never cross a beat.
8. 16ths have a second beam, shared with a neighbouring 16th, or a short hook (as in dotted 8th + 16th).

**Rests across beats**

9. An empty beat is a quarter rest. Two empty beats on beats 1–2 or 3–4 are a half rest, never on beats 2–3, so beat 3 stays visible in 4/4.
10. An empty measure is a whole-measure rest in voice 1. Voice 2 appears only in measures where it has hits.

**Triplets**

11. Every triplet beat shows its 3.
12. A triplet of three beamed 8ths shows the 3 without a bracket. With a rest or a triplet quarter, it gets a bracket.

**Files**

13. Every measure adds up: MuseScore shows no irregular-measure warning.
14. The file opens in MuseScore without import errors. It also validates against the MusicXML 4.0 XSD, which CI checks.

## Development-set check (2026-11-05)

Ten development-set clips were checked in MuseScore 3.2.3, chosen for varied styles, meters and sources. Each clip's first 30 s (or the whole clip, if shorter) went through `drumtx transcribe` with the default detector and tracker (`--time-signature 3/4` for the chacarera). Each output was then rendered to PNG and to MIDI with `mscore3`. The images aren't kept, because they show third-party recordings (decision 0001).

| Clip | Source | Measures | Checklist |
|---|---|---|---|
| `drummer3_session2_5_rock_100_beat_4-4_43` | E-GMD rock | 13 | Pass |
| `drummer7_session1_13_funk_102_beat_4-4_35` | E-GMD funk | 13 | Pass |
| `drummer3_session1_15_jazz_120_beat_4-4_58` | E-GMD jazz | 16 | Pass (issue A) |
| `drummer3_session2_25_hiphop_92_beat_4-4_2` | E-GMD hip-hop | 12 | Pass |
| `drummer1_session2_1_latin-chacarera_157_beat_3-4_19` | E-GMD, 3/4 | 27 | Pass |
| `drummer6_session1_4_rock_80_beat_6-8_31` | E-GMD, 6/8 | 10 | Pass (issues A, D) |
| `RealDrum01_00#MIX` | IDMT-SMT-Drums | 11 | Pass |
| `TechnoDrum01_00#MIX` | IDMT-SMT-Drums | 7 | Pass |
| `MusicDelta_Reggae_Drum` | MDB Drums, shuffle | 9 | Pass |
| `MusicDelta_80sRock_MIX` | MDB Drums, full mix | 14 | Pass (issue E) |

All ten pass all 14 items:
- All ten validate against the XSD.
- MuseScore converts each one with no message other than the benign `element already exists` (decision 0007).
- The reggae shuffle reads as triplet quarter + 8th pairs with brackets, which is the usual way to write it.

## Remaining issues

These are logged for later tasks. None of them breaks a checklist rule.

- **A. Swing written as 16ths.** Jazz swing and the 6/8 groove come out partly as dotted 8th + 16th, not triplets. This is the quantizer's grid choice: `TRIPLET_PENALTY` prefers a duple grid (M3-2, decision 0012), not the writer. The MDB reggae shuffle, by contrast, comes out as triplets.
- **B. Voice 2 rests.** In measures where the kick plays only a few times, voice 2 fills the rest of the measure with quarter and half rests below the staff. This is correct, but busier than many hand-written charts, which leave out the lower voice's rests. MuseScore can hide them (select, then V). Candidate for a later option.
- **C. Leading rests in measure 1.** When the music starts mid-measure, measure 1 begins with rests rather than a pickup measure. This is M4-4.
- **D. Compound meters.** The 6/8 groove is written in 4/4, one dotted-quarter beat per quarter. Compound meters are post-MVP (Technical Design Document §5).
- **E. Detection errors show in the notation.** In the full-mix clip, many hits are detected as tom (D5) and stacked on snare chords. This is detection accuracy (`docs/accuracy.md`), not notation.

## Drummer review

Not yet done. Reviewer, date and findings:
