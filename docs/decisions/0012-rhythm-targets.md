# 0012 — Rhythm metrics and targets

- **Status:** Accepted, 2026-11-05
- **Task:** M3-6

## Metrics

**Beat and downbeat F-measure:** mir_eval's beat F-measure (±70 ms) against the reference beats (`<clip>.beats.csv`, decision 0004). Downbeats are the beats numbered 1.

**Grid accuracy:** the share of a reference score's placed hits (`<clip>.score.csv`) that DrumTx puts in the same measure, beat and slot.
- **Matching:** a reference hit is matched to a predicted hit of the same class within 50 ms, one to one, as for onsets.
- **Grids:** slot 1 is the beat itself in both grids. On any other slot, the grid must agree too.
- **Two numbers:**
  - **Over all placed hits:** a hit the detector missed counts as wrong.
  - **Over the hits found:** this leaves detection out and measures rhythm alone.
- **Not scored:** reference hits too far from the grid to place (empty position fields) are skipped.

`drumtx evaluate --ref-score` reports both numbers. `scripts/benchmark.py` reports all the rhythm metrics per subset, per source and for "all":
- **Beat and downbeat F:** the mean over clips that have reference beats.
- **Grid accuracy:** pooled over the hits of clips that have a reference score.
- **Inputs:** the `balanced` detections, quantized on the tracked beats. The meter comes from the reference beats, as if passed with `--time-signature`, because DrumTx never estimates it (M3-1).
- **`--compare`:** flags a drop of more than the margin in any of these metrics, as it does for the onset F-measures.

## First run (development set, ADTOF, 2026-11-05)

| Subset | Clips | Beat F | Downbeat F | Grid accuracy, all placed hits | Grid accuracy, hits found |
|---|---|---|---|---|---|
| Drum-only | 55 | 0.98 | 0.87 | 0.44 (34,099 hits) | 0.71 |
| Full mix | 12 | 0.93 | 0.86 | — | — |
| All | 67 | 0.98 | 0.87 | 0.44 | 0.71 |

- **Reference scores** exist only for E-GMD (drum-only) clips. The full-mix clips are MDB Drums and have beats but no score.
- **Runtime:** beat tracking and quantizing took 298 s for the 67 clips (91 minutes of audio) on the 4-core sandbox.

**Where grid errors come from** (M3-2's check, same models, 42 clips with reference scores):
- **Detection:** the detector finds about two thirds of the reference hits. Most misses are quiet notes and ghost notes (decision 0005). That's why the all-hits number is much lower.
- **Beat tracking:** with the reference beats instead of the tracked ones, 89% of found hits get the right position, against 71% on tracked beats.
  - **Whole bars off:** in 6 clips, every hit is off by one or more bars because the downbeat was wrong.
  - **Beat phase off:** in 4 clips, the tracked beats fall between the true beats.
  - **Fix:** `--first-downbeat` and `--bpm` correct both cases.
- **Grid choice:** most of the remaining 11% are single swung 8th notes. DrumTx keeps them on 16ths, while the reference's automatic rule calls them triplets (M3-2). Swing is post-MVP.

## Targets

For the release model on the held-out **test** set, checked in M7-4, alongside the onset targets in decision 0010:

| Measure | Target | Development set now |
|---|---|---|
| Downbeat F-measure (±70 ms), drum-only and full mix | ≥ 0.85 each | 0.89 / 0.86 (M4-4) |
| Grid accuracy over the hits found, drum-only | ≥ 0.75 | 0.77 (M4-4) |
| Grid accuracy over all placed hits | reported, no target | 0.48 (M4-4) |

**Why these numbers:**
- **Downbeat F-measure** is set just below the current level, as a guard. A wrong downbeat shifts every bar of the score, and Beat This! is pretrained and not tuned on our development set, so the development-set number should carry over to the test set.
- **Grid accuracy over the hits found** isolates rhythm. 0.75 asks for a modest improvement over 0.71: in beat tracking and downbeats, or in the triplet rule (the reference-beat check shows 0.89 is reachable with perfect beats).
- **Grid accuracy over all placed hits** has no target. It is the found-hits accuracy times detection recall, and recall already has targets: the onset targets in decision 0010.
- **No full-mix grid target:** the test set's full-mix clips have no reference scores either.

## Update: gap filling (M4-4, 2026-11-05)

M4-4 made `beats.tempo_map` fill any tracked interval of 1.75 median beats or more with beats at the median tempo (decision 0007). It was added for silences, but it mostly fixes single skipped beats: one missing beat shifts every later bar line by a beat.

The development-set benchmark (`eval/results/adtof-dev.json`, detection unchanged) moves as follows:

| Subset | Downbeat F | Grid accuracy, all placed hits | Grid accuracy, hits found |
|---|---|---|---|
| Drum-only | 0.87 → **0.89** | 0.44 → **0.48** | 0.71 → **0.77** |
| Full mix | 0.86 → 0.86 | — | — |

- **Grid accuracy over the hits found is now above its 0.75 target.**
- **Six drum-only clips changed.** In four, a skipped beat (about 2 median beats long) was restored, and downbeat F rose from 0.53–0.60 to 0.99–1.0. One short clip barely changed. One (`latin-venezuelan-joropo_80`) fell from 0.66 to 0.49.
- **The cutoff.** A first cutoff of 1.5 median beats also split a 1.6-beat interval in `MusicDelta_BebopJazz_MIX` into two beats. That halved its downbeat F (0.56 → 0.28) and pulled the full-mix mean below the margin (0.856 → 0.833). At 1.75 that clip is unchanged.
