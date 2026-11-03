# 0009 — Baseline detector and its regression floor

- **Status:** Accepted, 2026-11-03
- **Task:** M1-3

## Decision

`BaselineDetector` (`src/drumtx/detect.py`) is the classical detector from the M0-4 spike, with three changes:

1. **Shorter window.** It uses a 1024-sample Hann window instead of 2048 samples. On synthetic hits from silence, the 2048-sample window placed onsets 4–17 ms early, because the flux jumps as soon as the window's edge touches the onset. With 1024 samples, every class lands within −7 to +4 ms, which meets M1-3's ±10 ms criterion.
2. **Level normalization instead of per-clip scaling.** The spike divided each activation curve by its own 99.5th percentile, which turns a quiet clip's noise into hits. Now the audio is peak-normalized, with the gain capped at 4 (+12 dB). With a +20 dB cap, a file of -60 dB noise still produced false hits at `sensitive`; with +12 dB, no preset does.
3. **Mirrored padding at the file edges**, so the start of a file is not mistaken for an onset.

The rest follows the spike:
- **Activations:** the positive spectral flux of log10(1 + |STFT|) at 100 frames per second, averaged over one band per class: kick 30–90 Hz, tom 100–300 Hz, snare 1–4 kHz, cymbal 4–8 kHz, hi-hat 8–16 kHz.
- **Peak picking:** madmom-style, with a 100 ms moving average and a local maximum over 2 frames before and 1 after. Peaks closer than 30 ms count as one hit.

**Thresholds and confidence.** Each class has its own threshold for `balanced` (kick 0.35, snare 0.03, hi-hat 0.014, tom 0.2, cymbal 0.03). These were chosen for the best F-measure on the whole development set (`scripts/benchmark.py --tune`, on a geometric grid; `scripts/eval_baseline.py` until M1-6). They were tuned with the earlier +20 dB cap; the results below use the final +12 dB cap. `strict` multiplies the thresholds by 1.5 and `sensitive` by 0.67.

Confidence is `activation / (activation + threshold)`, which is 0.5 at the threshold, and velocity is `127 × confidence`. Neither is calibrated; calibration is M2-4.

## Regression floor (development set, `balanced`)

All 189 development clips (107 minutes), scored with `mir_eval` onset matching. The machine-readable results, with every preset and with counts, are in `eval/results/baseline-dev.json`. The benchmark (M1-6, `scripts/benchmark.py`) compares against that file.

F-measure:

| Subset | Tolerance | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|---|
| All | 50 ms | 0.75 | 0.58 | 0.68 | 0.18 | 0.20 |
| All | 30 ms | 0.66 | 0.55 | 0.63 | 0.16 | 0.19 |
| Drum-only (177 clips) | 50 ms | 0.78 | 0.60 | 0.68 | 0.20 | 0.21 |
| Full mix (12 clips) | 50 ms | 0.44 | 0.42 | 0.74 | 0.01 | 0.13 |

Precision and recall for each preset (all clips, 50 ms):

| Preset | Kick P / R | Snare P / R | Hi-hat P / R | Tom P / R | Cymbal P / R |
|---|---|---|---|---|---|
| `strict` | 0.87 / 0.58 | 0.49 / 0.68 | 0.63 / 0.73 | 0.10 / 0.42 | 0.12 / 0.62 |
| `balanced` | 0.73 / 0.77 | 0.47 / 0.76 | 0.59 / 0.80 | 0.11 / 0.56 | 0.12 / 0.74 |
| `sensitive` | 0.53 / 0.88 | 0.44 / 0.82 | 0.56 / 0.85 | 0.10 / 0.68 | 0.11 / 0.84 |

For kick, snare and hi-hat, `strict` has higher precision and `sensitive` higher recall, as the presets intend. For tom and cymbal, precision is too low for presets to matter.

## Known weaknesses

- **Tom and cymbal are mostly false positives** (precision about 0.1). Any hit puts energy into the 100–300 Hz and 4–8 kHz bands: kicks and snares bleed into the tom band, and hi-hats and snares into the cymbal band.
- **Noisy decays re-trigger.** A synthetic cymbal is detected on time but fires again during its decay. The test checks only the first detection for cymbals.
- **Full mixes:** other instruments trigger the kick and snare bands. Full-mix tom has only 15 reference hits, so its number means little (decision 0004).

These are expected for a band-energy detector. The learned detector (M2, decision 0005) replaces it; the baseline stays as the regression floor and as `--model baseline`.

## Reproducing

This reads the corpus from `~/drumtx-data` (decision 0004) and takes about 4 minutes.

```bash
uv run python scripts/benchmark.py --tune
```
