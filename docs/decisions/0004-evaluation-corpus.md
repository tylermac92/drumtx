# 0004 — Evaluation corpus and annotation formats

- **Status:** Accepted, 2026-10-30
- **Task:** M0-3
- **Frozen manifests:**
  - `eval/dev.csv`: SHA-256 `0b18c0cbf9442693330c6bf537218299e22bd80947f173728a0d204b837be1b8`
  - `eval/test.csv`: SHA-256 `0f00ce72a2a7c96809e182274c172f4a76d7aa358cb2ecc6f3d00c06cb407bc3`

## Q5: isolated drums or full mixes

The default is accepted: optimize for both, and report each separately. The full-mix subset is much smaller than the drum-only one. That reflects how little permitted full-mix data exists (decision 0003), not a lower priority; see "Known gaps".

## Annotation formats

All files are UTF-8 CSV with a header row and LF line endings. Times are in seconds from the start of the audio file.

- **Onsets** (`<clip>.onsets.csv`, every clip): `time_s,class,confidence,velocity`. These are the same columns as `events.csv`. `confidence` is always `1.0`; `velocity` is the MIDI velocity where the source has one, otherwise `100`.
- **Beats** (`<clip>.beats.csv`, rhythm subset): `time_s,beat`. `beat` is the position in the bar, and `1` marks a downbeat.
- **Reference score** (`<clip>.score.csv`, score subset): the onset columns plus `measure,beat,grid,slot`.
  - `grid` is `16th` or `triplet`.
  - Positions are 1-based, as in the Technical Design Document §7.
  - Hits too far from the grid to place with confidence have these four fields empty and are not scored for grid accuracy.

## Sources, splits and conversion

`scripts/build_corpus.py` builds everything from the datasets in `~/drumtx-data` and is deterministic.

```bash
uv run python scripts/build_corpus.py ~/drumtx-data --fetch-egmd
```

- **Annotation files** go to `~/drumtx-data/corpus/` and are never committed: they are derived from third-party data.
- **Manifests** `eval/dev.csv` and `eval/test.csv` are committed. Each row gives the clip's source, license, split, subset, style, audio path, audio SHA-256, duration, which rhythm annotations it has, and onset counts per class.
- **`--fetch-egmd`** downloads only the selected E-GMD clips (about 0.7 GB) from the 90 GB archive, using HTTP range requests.

| Source | Our dev split | Our test split | Conversion |
|---|---|---|---|
| E-GMD | E-GMD `validation` | E-GMD `test` | MIDI notes mapped to the 5 classes (see below). Each performance is used once, with one kit chosen in rotation; kits that remap notes to tambourine, clap or cowbell are skipped. |
| MDB Drums | MIREX 2017 training tracks (12) | MIREX 2017 test tracks (11) | `class` annotations; `OT` (other) is dropped. Each track appears as a drum-only clip and a full-mix clip. Beats come from the dataset's own beat annotations. |
| IDMT-SMT-Drums | Even loop numbers | Odd loop numbers | `#MIX` files only. Kick, snare and hi-hat only. Used for evaluation only (decision 0003). |

- **Why E-GMD's own split.** Using E-GMD's validation and test splits keeps E-GMD's `train` split free for training a model (M0-4, M2) without leaking evaluation performances.
- **E-GMD class map.** The 5-class grouping used in ADTOF:

  | Class | MIDI notes |
  |---|---|
  | kick | 36 |
  | snare | 37, 38, 40 |
  | hihat | 22, 26, 42, 44, 46 (includes pedal 44) |
  | tom | 43, 45, 47, 48, 50, 58 |
  | cymbal | 49, 51, 52, 53, 55, 57, 59 |

- **E-GMD rhythm annotations.** Only grooves (`beat_type = beat`) in 4/4 or 3/4 get rhythm annotations; fills are a few seconds long. E-GMD was recorded to a click, and every MIDI file has one tempo and one time signature, both matching the metadata. So beats come from the tempo, with bar 1 at time 0. A check confirmed that rock backbeats fall on beats 2 and 4.
- **Reference scores.** Hits are placed on that click grid.
  - Each beat takes the grid with the lower total snapping error: the 16th grid if all its hits are on the beat or on a tie, otherwise the 8th-note-triplet grid.
  - A hit more than 35% of a grid step from its slot is left unscored.
  - 90–92% of hits are scored. The rest are mostly flams, ghost notes and 32nd notes.
- **Audio alignment.** A spot check of 12 E-GMD and MDB clips found the annotations within ±20 ms of the audio's energy onsets (at 5 ms resolution).

## Subset sizes

Onset counts per class, with the number of clips containing the class in parentheses:

| Split / subset | Clips | Minutes | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|---|
| dev / drum-only | 177 | 96.3 | 9736 (157) | 14457 (174) | 15834 (146) | 4010 (105) | 3361 (63) |
| dev / full-mix | 12 | 11.2 | 661 (12) | 1304 (12) | 1603 (10) | **15 (2)** | 267 (9) |
| test / drum-only | 181 | 93.4 | 9375 (168) | 12906 (178) | 15953 (153) | 2436 (78) | 3598 (52) |
| test / full-mix | 11 | 10.6 | 878 (11) | 1350 (10) | 1036 (10) | **75 (5)** | 735 (8) |

Rhythm and score subsets:

| Split / subset | Rhythm subset (beats and downbeats) | Score subset |
|---|---|---|
| dev / drum-only | 55 clips, 79.8 min (E-GMD 43, MDB 12) | 43 E-GMD clips, 68.6 min, 34,099 scored hits |
| dev / full-mix | 12 MDB clips, 11.2 min | none |
| test / drum-only | 83 clips, 79.2 min (E-GMD 72, MDB 11) | 72 E-GMD clips, 68.6 min, 32,445 scored hits |
| test / full-mix | 11 MDB clips, 10.6 min | none |

- **Style mix.** The drum-only subsets cover 13–14 styles each, led by rock, funk, latin, jazz and soul. The style split comes from the datasets' own splits.
- **Hand annotation.** None was needed for this version: every annotation is derived from the datasets' own MIDI, onset and beat files.

### Minimum for stable per-class numbers

A class in a subset needs **at least 250 onsets spread over at least 8 clips**.

- **Why 250 onsets.** At F ≈ 0.8, that gives a 95% confidence interval of about ±5 points (1.96 × √(0.8 × 0.2 / 250) ≈ 0.05).
- **Why 8 clips.** Hits within one clip are correlated, and spreading them over 8 clips keeps any single clip from dominating.
- **Result.** Every class meets the minimum in both drum-only subsets. In the full-mix subsets, every class meets it except **tom** (dev 15 in 2 clips, test 75 in 5 clips). Full-mix tom results are reported as "below minimum", not as a number.

## Rules

- **The test set is for release evaluation only:** M2-7 (model release evaluation) and M7-4 (final evaluation). Tuning, model selection and threshold choices use the dev set. The M1-6 benchmark runner reads `eval/test.csv` only in release mode.
- **The splits are frozen.**
  - A test (`tests/test_eval_manifests.py`) checks the manifests' hashes.
  - A clip never moves between splits, and test annotations are never edited.
  - Adding clips, such as your own recordings, means appending rows in a new decision record, with new hashes. An annotation error is fixed the same way, and the fix is recorded.

## Known gaps

- **Full-mix toms.** These are below the minimum, and the full-mix subset is about 11 minutes per split. The fix is full-mix recordings of your own with tom fills, annotated by hand: about 250 tom hits per split, or roughly 5–10 songs per split. Expect 1–2 hours of hand annotation per minute of full mix if every class is annotated. A score subset for full mixes would also come from these recordings.
- **Reference scores** are derived automatically from the click grid. They are not checked by ear, and they represent grooves played to a click.
- **Beat This! and E-GMD.** Beat This! was trained on the Groove MIDI Dataset, which contains the same performances as E-GMD. Its beat scores on E-GMD clips would be optimistic, so M0-5 should compare trackers on the MDB rhythm clips as well.
