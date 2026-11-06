# 0013 — Review flag thresholds

- **Status:** Accepted, 2026-11-06
- **Task:** M5-4

## Decision

The defaults in `review.Thresholds` are now:

| Threshold | Old (M3-3) | New |
|---|---|---|
| `confidence`: a hit below it is `uncertain` | 0.5 | **0.3** |
| `residual_frac`: a hit further than this share of a grid step from its slot is off the grid | 0.25 | **0.4** |
| `off_grid_events`: a measure is `off_grid` with more off-grid hits than this | 1 | **2** |
| `tempo`: a measure is `tempo` when its mean beat length differs more than this from the median | 0.08 | 0.08 |
| `merged` | on | on |

With them, a quarter of the development measures are flagged instead of 64%, and four in ten of the badly wrong measures are among them. Two in three flagged measures are badly wrong, against about two in five overall.

## How it was measured

`scripts/tune_flags.py` transcribes each development clip as `transcribe` does with the defaults: ADTOF `balanced`, the tracked beats, and the meter from the reference beats where there are any (as in `benchmark.py`). 182 of the 189 clips have at least two beats: 3,210 measures. Each measure's hits are compared with the reference:
- **Extra:** a detected hit with no reference hit of its class within 50 ms.
- **Missed:** a reference hit with no detected hit. A wrong class counts as one extra and one missed.
- **Misplaced:** only on clips with a reference score (E-GMD). A matched hit at another beat, grid or slot. The measure number is not compared: a wrong downbeat moves every bar, and is fixed once for the piece with `--first-downbeat`, not measure by measure.

**What counts as an erroneous measure:** nearly every measure has at least one wrong hit (88%), mostly quiet notes the detector misses (decision 0005). With that definition every flag looks precise, and the share of errors flagged just follows the share of measures flagged. So a measure counts as erroneous when **at least half of its hits** (matched, extra and missed) are wrong: 39% of the development measures. At a quarter of the hits, 69% are erroneous, and the new defaults flag 33% of them, with 90% of flagged measures erroneous.

The script scores every combination of 6 confidence values, 6 residual values, 6 off-grid counts and 5 tempo values, with `merged` on and off. It checks that its fast evaluation gives exactly the measures `review.flag` gives at the defaults.

## Trade-off (development set)

"Erroneous" is at least half of the measure's hits wrong. The last three columns are the share of erroneous measures with that kind of error that are flagged.

| Thresholds | Measures flagged | Erroneous flagged | Flagged that are erroneous | Extra | Missed | Misplaced |
|---|---|---|---|---|---|---|
| none (base rate) | 100% | 100% | 39% | 100% | 100% | 100% |
| uncertain < 0.5 alone | 39% | 53% | 54% | 67% | 53% | 50% |
| off-grid > 1 at 0.25 alone | 40% | 46% | 46% | 51% | 47% | 59% |
| tempo > 8% alone | 3% | 4% | 56% | 5% | 4% | 2% |
| merged alone | 11% | 21% | 72% | 22% | 22% | 32% |
| old defaults (M3-3) | 64% | 76% | 47% | 86% | 76% | 81% |
| **new defaults** | **25%** | **43%** | **66%** | 47% | 43% | 46% |

The best share of erroneous measures flagged, for each cap on the share of all measures flagged:

| Cap | Thresholds (confidence, residual, off-grid >, tempo, merged) | Measures flagged | Erroneous flagged | Flagged that are erroneous |
|---|---|---|---|---|
| 10% | 0.2, 0.4, 1, 0.2, off | 10% | 13% | 52% |
| 15% | 0.3, 0.45, 3, 0.2, off | 15% | 27% | 70% |
| 20% | 0.3, 0.3, 4, 0.08, off | 20% | 32% | 64% |
| 25% | 0.3, 0.45, 2, 0.05, on | 25% | 42% | 67% |
| 30% | 0.3, 0.3, 3, 0.08, on | 30% | 45% | 61% |
| 40% | 0.4, 0.4, 1, 0.08, on | 40% | 57% | 56% |
| 50% | 0.5, 0.4, 1, 0.08, on | 50% | 67% | 53% |

By source, with the new defaults:

| Source | Measures | Flagged | Erroneous | Erroneous flagged |
|---|---|---|---|---|
| E-GMD (drum-only) | 2,176 | 29% | 50% | 44% |
| IDMT-SMT-Drums (drum-only) | 380 | 14% | 4% | 27% |
| MDB Drums, drum-only | 357 | 17% | 25% | 32% |
| MDB Drums, full mix | 297 | 23% | 26% | 40% |

## Why these values

- **A quarter of the piece.** The task asks for flags that don't cover most of the piece. Up to about 25% of measures flagged, each extra point flagged catches more than a point of erroneous measures (20% → 25% flagged: 32% → 42% caught). Beyond it, each extra point catches less than a point, and the flagged measures get less precise: 61% at 30%, 53% at 50%.
- **Stable neighbourhood.** The winner for each cap changes from cap to cap, which is noise from searching 1,800 combinations. Around the chosen point it doesn't matter. With confidence 0.3, residual 0.35–0.45, off-grid > 2 or > 3 and tempo 8% or 12%, every combination flags 24–30% of measures and catches 41–45% of the erroneous ones. The confidence threshold is the main control: at 0.4, 37% of measures are flagged.
- **Merged stays on.** It is the most precise flag (72%) and nearly free.
- **Tempo stays at 8%.** It flags few measures, and those few are mostly wrong.

## Consequences

- **`--mark-uncertain`** colors fewer notes red: those below 0.3 instead of 0.5.
- **What flags can't do:** about half of the badly wrong measures are not flagged. A flag can only point at hits that were detected, and most of the errors are missed quiet notes. The report says that unflagged measures can be wrong too.
- **Re-running:** `uv run python scripts/tune_flags.py`. Detections and beats are cached in `~/drumtx-data/flags-cache.json`; the first run takes about 12 minutes on the 4-core sandbox.
