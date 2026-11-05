# Events format, version 1

DrumTx writes every run's detected hits to two files, `<name>.events.json` and `<name>.events.csv`.

- **`events.json`** is the authoritative record of a run. Its JSON Schema is [`src/drumtx/events-v1.schema.json`](../../src/drumtx/events-v1.schema.json), which ships inside the package.
- **`events.csv`** holds the same hits in four columns, for editing in a spreadsheet. It keeps every detected hit, including the few that `events.json` leaves out: hits merged into another in the same slot, and hits before measure 0 (see [Events](#events)).

The Python types for these contracts are in [`src/drumtx/schema.py`](../../src/drumtx/schema.py): `DrumEvent`, `Position`, `TempoMap` (with `Beat` and `TimeSignature`), `MeasureFlags` and `QuantizedScore`. Their field names match the JSON keys, with one exception: `DrumEvent.cls` is `class` in JSON and CSV. Tests keep the types, the schema and the examples in step.

## Examples

These files are validated in `tests/test_schema.py`. They encode the two-bar groove from spike M0-6 at 120 BPM.

| File | Shows |
|---|---|
| [`examples/groove.events.json`](examples/groove.events.json) | A full run: tempo map, quantized positions, event flags and measure flags. |
| [`examples/detection-only.events.json`](examples/detection-only.events.json) | What `transcribe` writes before beat tracking exists (M1-7): `beats` is empty, `quantized` is `null`, and `beat_tracker` is `null`. |
| [`examples/groove.events.csv`](examples/groove.events.csv) | The matching CSV. Its SHA-256 is the `csv_sha256` in both JSON examples. |

## Conventions

- **Times** are in seconds from the start of the source file, even when `--start` selects an excerpt.
- **Positions** count from 1: `measure`, `beat` and `slot`. A pickup measure before the first downbeat is measure 0.
- **Every key is required.** A value that does not apply yet is `null` (or an empty list), never a missing key. Unknown keys are rejected, except inside `settings`.

## `events.json`

| Key | Type | Meaning |
|---|---|---|
| `schema_version` | `1` | Format version. Any change to the format increments it. |
| `source.file` | string | Input file name, without its directory. |
| `source.sha256` | hex string | SHA-256 of the input file. It is also the cache key. |
| `source.duration_s` | number | Length of the whole input file. |
| `source.start_s`, `source.end_s` | number or `null` | Excerpt bounds from `--start` and `--end`; `null` when not given. |
| `settings` | object | The options the run used, after defaults were applied. For information only; nothing reads it back. |
| `models.detector` | string | Detection model ID, or `baseline` for the classical detector. |
| `models.beat_tracker` | string or `null` | Beat-tracker model ID; `null` until beat tracking has run. |
| `models.separator` | string or `null` | Separation model ID; `null` without `--separate`. |
| `csv_sha256` | hex string or `null` | SHA-256 of `events.csv` as `transcribe` wrote it, so a hand-edited CSV is never overwritten. `null` when no CSV was written. `render` keeps this value. |
| `tempo_map` | object | See [Tempo map](#tempo-map). |
| `events` | list | One entry per hit in the score, sorted by time. Hits merged into another (flag `merged`) and hits before measure 0, which cannot be numbered, are left out. See [Events](#events). |
| `measure_flags` | list | Measures to review. Only flagged measures are listed. See [Flags](#flags). |

### Tempo map

| Key | Type | Meaning |
|---|---|---|
| `beats` | list of `{time_s, measure, beat}` | Every tracked beat. `beat` 1 is a downbeat. Empty before beat tracking. |
| `time_signatures` | list of `{measure, beats, beat_type}` | Each entry applies from its measure onward; a pickup measure uses the first entry. The MVP writes exactly one, and `beat_type` is always 4. |
| `tempo_source` | `estimated` or `user` | `user` when `--bpm` constrained the beat tracker. |
| `time_signature_source` | `default` or `user` | `default` is 4/4; `user` means `--time-signature` was given. Meter is never estimated. |
| `first_downbeat_source` | `estimated` or `user` | `user` when `--first-downbeat` was given. |

Storing the measure and beat number of every beat, rather than a single meter, is what lets a later version support meter changes without a new format.

### Events

| Key | Type | Meaning |
|---|---|---|
| `time_s` | number ≥ 0 | When the hit happened. |
| `class` | class name | One of the [instrument classes](#instrument-classes). |
| `confidence` | 0–1 | The detector's calibrated peak activation (not calibrated for `--model baseline`). |
| `velocity` | integer 1–127 | Estimated loudness (approximate). |
| `quantized` | object or `null` | Grid position; `null` before quantization. |
| `quantized.measure`, `.beat` | integer | The beat the hit belongs to. |
| `quantized.grid` | `16th` or `triplet` | That beat's grid. |
| `quantized.slot` | integer | Position within the beat: 1–4 for `16th`, 1–3 for `triplet`. |
| `quantized.residual_ms` | number | The hit's time minus its snapped time. Positive means late. |
| `quantized.residual_frac` | −0.5 to 0.5 | `residual_ms` as a fraction of the grid step, so the same value means the same thing at any tempo. For a hit just before a beat, the step is that of the beat before. |
| `flags` | list | Event flags; usually empty. See [Flags](#flags). |

### Flags

| Flag | On events | On measures | Meaning |
|---|---|---|---|
| `uncertain` | Yes | Yes | Confidence is below the review threshold (0.5 by default), or the measure contains such an event. |
| `merged` | Yes | Yes | Other hits of the same class in the same slot were merged into this one (the highest confidence wins), or the measure contains such a merge. |
| `off_grid` | — | Yes | More than one event in the measure has a residual above the threshold (25% of a grid step by default). |
| `tempo` | — | Yes | The local tempo differs from the median by more than the threshold (8% by default). |

The defaults are in `review.Thresholds` (`src/drumtx/review.py`). They are first estimates: with them, 67% of the measures in the development score subset are flagged, so M5-5 tunes them to flag fewer. A measure's tempo is its mean beat length, compared with the median beat length of the piece.

## `events.csv`

```csv
time_s,class,confidence,velocity
0.496,hihat,0.78,73
0.502,kick,0.96,83
```

- UTF-8 with a header row and these four columns in this order. DrumTx writes LF line endings, `.` as the decimal point, times to the millisecond, and rows in time order.
- When reading an edited file, rows may be in any order. In rows added by hand, `confidence` and `velocity` may be left blank; they are read as 1.0 and 100.
- The CSV has no tempo map. `render` takes it from the `events.json` file beside the CSV.
- The same columns are used for onset annotations in the evaluation corpus (decision 0004).

A spreadsheet set to a locale that writes `,` as the decimal point will break the file. Check the separator before saving.

## Instrument classes

`kick`, `snare`, `hihat`, `tom`, `cymbal`. They are `schema.CLASSES` in code and the `class` enum in the schema. Hi-hats are not split into open and closed, toms are merged into one class, and crash and ride are merged into `cymbal`; finer classes are post-MVP.

## Instrument mapping

[`src/drumtx/mapping.toml`](../../src/drumtx/mapping.toml) is the default mapping from class to notation and MIDI (Technical Design Document §5). A test checks that it matches the table in §5. To change it, write a TOML file with the tables and keys you want to change and pass it with `--mapping`; anything it leaves out keeps the default, so a copy of the whole file also works. `events.json` records the file name in `settings.mapping`. A bad file stops the run before any work (exit code 2), with every bad class, key or value named, such as `[snare] midi_note must be a whole number from 0 to 127, got 200`. Each class has one table:

| Key | Meaning |
|---|---|
| `name` | Instrument name in the MusicXML part. |
| `midi_note` | General MIDI drum note, written on channel 10. |
| `display` | Staff position as step and octave, read as if on a treble clef (for example `F4`). |
| `notehead` | `normal` or `x`. |
| `voice` | 1 (stems up, hands) or 2 (stems down, feet). |
