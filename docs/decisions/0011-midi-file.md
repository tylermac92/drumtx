# 0011 — MIDI file layout and alignment

- **Status:** Accepted, 2026-11-05
- **Task:** M3-4

## Layout

`<name>.mid` is a type 1 Standard MIDI File with 480 ticks per quarter note, so 16ths (120 ticks) and triplet 8ths (160 ticks) land on whole ticks. The writer is `src/drumtx/midi.py`.

- **Track 1 (conductor):** the time signature and a tempo change at every beat of the tempo map. A DAW's bar grid follows the music, and MIDI time 0 is the start of the audio file.
- **Track 2 (Drums):** notes on channel 10, using the MIDI notes from the instrument mapping. Each note lasts a 32nd note.

**Timing modes (`--midi-timing`):**
- **`quantized` (default):** notes sit at their grid positions, so a player puts them on the beat-grid times of the audio.
- **`performance`:** notes sit at their detected times, converted through the same tempo track. The bar grid stays, but the notes keep their feel.

**Without a tempo map** (fewer than two beats): the file runs at 120 BPM and notes keep their detected times.

## The start of the file

MIDI time 0 must be the start of the audio, but the first beat rarely is. Two layouts were tried and rejected:

| Option | Problem |
|---|---|
| Start on bar 0 and fit the beats before the first beat into the gap | When the first beat came early in the file, three beats were squeezed into 0 s. MuseScore showed a tempo of 60,000,000 BPM. |
| Start on the beat in progress at 0 s, and merge it with the next beat when under half of it was left | On a real full mix (first beat 0.04 s into the file) this moved the downbeat of bar 1 by 250 ms. |

**What we do instead:**
- **Lead-in:** from 0 s to the first beat at or after 0 s, the file has a lead-in of a whole number of 32nd notes, close to the music's tempo. Its own tempo makes it end exactly on that beat.
- **Pickup bar:** the first bar runs from 0 s to the first bar line, with its own time signature, for example `1/4`, `13/32` or `1/32`. Notation apps treat it as a pickup.
- **Lead-in tempo:** it stays near the music's tempo unless the first beat falls very close to 0 s. It goes above 960 BPM, the highest some DAWs accept, only when the first beat is within about 8 ms of the start.
- **Notes in the lead-in:** these are rare (hits before the first tracked beat) and are placed approximately. From the first beat on, quantized notes are on the beat-grid times.

## Checks

**Tick-to-time conversion** (automated, `tests/test_midi.py`). Ten random tempo maps drift ±10%, with 150 hits each, including hits before the first and after the last tracked beat. With mido's tempo-aware playback, every quantized note from the first beat on is within 5 ms of its beat-grid time. Performance notes are within 2 ms of their detected times.

**Real recordings,** with ADTOF and Beat This!; each file starts with a lead-in, `1/32` then `4/4`:

| Recording | Notes | Largest difference from beat-grid time | Tempo range |
|---|---|---|---|
| E-GMD funk, 138 s | 1,499 | 0.03 ms | 115–125 BPM, lead-in 375 |
| MDB Drums `MusicDelta_80sRock` full mix | 200 | 0.0 ms | 107–115 BPM, lead-in 188 |

**MuseScore 3.2.3** (headless import of the `.mid`):
- Both files and the golden groove import as a drum part on channel 10.
- The lead-in becomes an implicit (pickup) measure.
- Bar lines fall on the tracked downbeats.
- The groove reads as the M0-6 pattern: kick on 1 and 3, snare on 2 and 4, 8th-note hi-hats, and the triplet on beat 4 of bar 2.
- The triplet is displayed loosely, because MuseScore re-quantizes MIDI on import. Notation comes from MusicXML (M4), not MIDI.
- Every beat's tempo change shows as a tempo marking. That's expected for a file aligned to the audio.

**DAW check (pending):** this needs a DAW, which isn't available in the development sandbox. To check:
1. Import `tests/golden/groove.quantized.mid`, or the `.mid` from a `transcribe` run, together with its audio.
2. Confirm the hits line up with the drums and the bar lines with the downbeats.
3. Confirm the DAW accepts the lead-in tempo.

Record the DAW and the result here.

## Golden files

`tests/golden/groove.quantized.mid` and `tests/golden/groove.performance.mid` are written from `docs/schema/examples/groove.events.json`. After a deliberate change, regenerate them with `DRUMTX_UPDATE_GOLDEN=1 uv run pytest tests/test_midi.py` and review the change.
