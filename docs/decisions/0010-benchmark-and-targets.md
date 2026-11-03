# 0010 — Benchmark runner and accuracy targets

- **Status:** Accepted, 2026-11-03
- **Task:** M1-6

## Benchmark runner

`scripts/benchmark.py` runs a detector over the development set and writes `eval/results/<model>-<split>.json` and a Markdown table beside it. Each result records:
- the commit (marked `+dirty` with uncommitted changes), the model ID and the date;
- the clip count, the audio minutes and the detection runtime;
- precision, recall and F-measure for every preset, subset (drum-only, full-mix, all), tolerance (50 and 30 ms) and class.

Safeguards:
- **Test set:** it needs `--release`, so it cannot be touched by accident (decision 0004).
- **Corpus check:** every audio file is checked against its SHA-256 in the manifest before scoring.

**Regressions.** `--compare PREVIOUS.json` lists every F-measure that moved by more than `--margin` (default 0.02). Drops are marked `REGRESSION` and make the script exit with code 1.

**CI.** The `Benchmark` workflow (`.github/workflows/benchmark.yml`) runs on demand and nightly.
1. It restores the corpus from the Actions cache, keyed by the frozen manifests.
2. On a cache miss it rebuilds the corpus:
   - it clones MDB Drums and downloads IDMT-SMT-Drums V2 from Zenodo, checking the zip's SHA-256;
   - it fetches the selected E-GMD clips with `build_corpus.py --fetch-egmd`;
   - it fails if the rebuilt manifests differ from the committed ones.
3. It benchmarks the baseline against `eval/results/baseline-dev.json` and uploads the results.

The datasets are used only for this private evaluation and are never committed (decisions 0001 and 0003).

**First run.** The results matched the floor recorded in M1-3 (decision 0009) to within the margin. Detection takes 0.20 s per audio minute on the 4-core sandbox.

## Targets (reviews the brief's provisional targets)

All targets are per-class onset F-measure at ±50 ms, for the release model on the held-out **test** set (M7-4). The development-set numbers below are the evidence used to set them.

| Class | Drum-only target | Full-mix target | Baseline, dev drum-only / full-mix | ADTOF spike, drum-only / full-mix (decision 0005) |
|---|---|---|---|---|
| kick | ≥ 0.85 (unchanged) | ≥ 0.75 | 0.78 / 0.44 | 0.96 / 0.95 |
| snare | ≥ 0.85 (unchanged) | ≥ 0.70 | 0.60 / 0.42 | 0.87 / 0.90 |
| hi-hat | ≥ 0.75 (unchanged) | ≥ 0.70 | 0.68 / 0.74 | 0.68 / 0.95 |
| tom | ≥ 0.60 (new) | none; reported only | 0.20 / 0.01 | 0.73 / 0.73 |
| cymbal | ≥ 0.60 (new) | ≥ 0.50 (new) | 0.21 / 0.13 | 0.90 / 0.86 |

**Why these numbers:**
- **The baseline only sets a floor.** It is far below every target except drum-only hi-hat, so the targets come from what the learned model reached in the M0-4 spike, with a margin. The spike used only 10 clips, and the test set has other kits and recordings.
- **Kick, snare and hi-hat keep the brief's targets.** The spike exceeded them, except drum-only hi-hat.
- **Drum-only hi-hat at 0.75 is at risk.** The spike reached 0.68, dragged down by one E-GMD kit (decision 0005). The target stays, as the bar M2-3's tuning has to clear, and M2-7 reports whether it is met.
- **Tom and cymbal targets are lower.** Both are merged classes (all toms; crash and ride together) and are often confused with each other and with hi-hat. 0.60 still demands a large improvement over the baseline.
- **Full-mix targets are lower than drum-only** because other instruments trigger false hits, except where the spike showed a full mix helps little. Full-mix toms get no target: the full-mix subset has too few tom hits to give a stable number (decision 0004). They are reported anyway.

**Also required.** In M2-1, the learned model must beat the baseline (`eval/results/baseline-dev.json`) on every class on the development set, not only on kick, snare and hi-hat.

Rhythm targets (downbeat F-measure, grid accuracy) are set in M3-6.
