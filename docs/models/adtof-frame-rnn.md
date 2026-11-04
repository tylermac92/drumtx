# Model card: ADTOF Frame_RNN (`adtof`)

- **Status:** integrated in M2-1, chunked in M2-2, presets tuned in M2-3, confidence and velocity fitted in M2-4, downloaded on first use since M2-5 (2026-11-04). The test-set results (M2-7) are still to come.
- **Chosen in:** decision 0005.

## What it is

The `Frame_RNN_adtofAll_0` checkpoint from [ADTOF](https://github.com/MZehren/ADTOF) by Mickaël Zehren et al. It is a frame-level drum transcription model trained on ADTOF-RGW and ADTOF-YT: real music annotated from rhythm-game charts (decision 0005).

| | |
|---|---|
| License | CC BY-NC-SA 4.0 (decision 0003). Personal, non-commercial use only (decision 0001). The checkpoint and the converted file are never committed. |
| Upstream files | `adtof/models/Frame_RNN_adtofAll_0.{index,data-00000-of-00001}` at commit `b3968fb332f69b65ee07c089fc62f436503755db` |
| Input | (frames, 84) log-filtered spectrogram at 100 fps, from mono 44.1 kHz audio (`drumtx.features`) |
| Network | 2 × (two 3×3 convolutions with batch norm, max pool over frequency), 3 bidirectional GRUs of 60 units, dense layer with sigmoid. 450,125 parameters. |
| Output | (frames, 5) onset probabilities in ADTOF's order: kick, snare, tom, hi-hat, cymbal (GM notes 35, 38, 47, 42, 49) |
| Peak picking | madmom's note peak picking with ADTOF's settings (`detect.pick_peaks`). Per-class thresholds and the minimum gap come from the preset (below). ADTOF's `labelOffset` is 0 for this model, so no time shift. |
| Confidence and velocity | Calibrated confidence and approximate velocity, both computed from the peak activation (below). |

## Presets

`--sensitivity` chooses one of three sets of per-class thresholds. They are stored with the model in `src/drumtx/presets/adtof.json` and tuned on the development set only:

```bash
uv run python scripts/benchmark.py --model adtof --tune
```

| Preset | Use it when | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|---|
| `strict` | You would rather add missed notes than delete wrong ones | 0.318 | 0.100 | 0.283 | 0.357 | 0.401 |
| `balanced` (default) | Best overall accuracy | 0.201 | 0.050 | 0.159 | 0.253 | 0.283 |
| `sensitive` | You would rather delete wrong notes than add missed ones, e.g. for ghost notes | 0.045 | 0.018 | 0.028 | 0.159 | 0.159 |

(ADTOF's own thresholds were kick 0.22, snare 0.24, tom 0.32, hi-hat 0.22, cymbal 0.30.)

**How they were tuned.**
- **Grid:** 39 thresholds from 0.01 to 0.8, spaced evenly on a log scale.
- **Score:** each threshold is scored by F-beta, with β = 0.5 for `strict` (weights precision), 1 for `balanced` and 2 for `sensitive` (weights recall).
- **Subset weighting:** the score is averaged over the drum-only and full-mix subsets, so the many E-GMD clips do not decide alone (decision 0004). Toms use drum-only alone, since the full mixes have only 15 tom hits (decision 0010).
- **Minimum gap:** chosen the same way from 20, 30, 40 and 50 ms. They score almost the same; 30 ms won narrowly.

**Precision and recall** (all development clips, 50 ms):

| Preset | Kick P / R | Snare P / R | Hi-hat P / R | Tom P / R | Cymbal P / R |
|---|---|---|---|---|---|
| `strict` | 0.96 / 0.63 | 0.91 / 0.64 | 0.93 / 0.56 | 0.70 / 0.53 | 0.93 / 0.64 |
| `balanced` | 0.94 / 0.71 | 0.85 / 0.74 | 0.88 / 0.64 | 0.57 / 0.70 | 0.90 / 0.70 |
| `sensitive` | 0.81 / 0.82 | 0.67 / 0.81 | 0.72 / 0.76 | 0.46 / 0.80 | 0.83 / 0.75 |

**M2-3's criterion is met:** `strict` has higher precision and `sensitive` higher recall than `balanced` for every class. This holds on all clips, and on the drum-only and full-mix subsets separately. The one exception is full-mix toms, where recall ties at 14 of 15 hits.

**Trade-off: the low snare threshold.** It recovers many quiet E-GMD notes (snare F 0.57 → 0.80) but adds false hits on IDMT's simple patterns (0.89 → 0.75). The curve is flat between thresholds 0.05 and 0.09. Weighting the three sources equally would choose about 0.07: E-GMD 0.78, MDB 0.75, IDMT 0.80. Revisit this with your own recordings in M7-1.

## Confidence and velocity

Both come from the peak activation `p` of each detected hit, per class. They are fitted together with the presets by `benchmark.py --model adtof --tune` and stored in the same file.

**Confidence** is the estimated probability that the hit is real, i.e. matches a reference hit within 50 ms.
- **Formula:** `sigmoid(b0 + b1 · logit(p))`, a logistic fit (Platt scaling).
- **Fitted on:** every development-set detection at the `sensitive` thresholds. These include the detections of the other presets, so the same values hold for all three.
- **Optimism:** it was fitted and checked on the same clips; the test set (M2-7) gives the unbiased check.

Reliability on the development set: precision of the detections in each confidence bin, with the number of detections in parentheses.

| Class | 0–0.2 | 0.2–0.4 | 0.4–0.6 | 0.6–0.8 | 0.8–1 |
|---|---|---|---|---|---|
| kick | — (1) | 0.32 (1,295) | 0.48 (880) | 0.65 (955) | 0.95 (7,414) |
| snare | 0.11 (2,166) | 0.26 (3,313) | 0.55 (1,787) | 0.80 (2,363) | 0.93 (9,531) |
| hi-hat | 0.23 (639) | 0.32 (3,116) | 0.45 (2,020) | 0.66 (2,449) | 0.93 (10,285) |
| tom | 0.16 (1,510) | 0.28 (1,764) | 0.48 (1,284) | 0.72 (1,450) | 0.86 (954) |
| cymbal | — | 0.34 (244) | 0.47 (281) | 0.74 (348) | 0.94 (2,415) |

**M2-4's first criterion is met:** precision rises with confidence for every class, and lies within or near each bin's range. Low-confidence hits are mostly the extra ones `sensitive` adds; at `balanced`, most hits are in the top bin.

**Velocity is approximate.** It maps the activation through matching quantiles (11 points per class) of the recorded velocities of correctly detected E-GMD hits. E-GMD is the only development source with recorded velocities, from electronic-kit sensors.
- **Monotone:** a stronger activation never gives a quieter note. Velocity is always within 1–127 and spans the reference range, about 5–127.
- **Correlation:** activation tracks the recorded velocity only moderately: correlation 0.35–0.59 by class, versus 0.43–0.81 for the frame's spectral energy.
- **Why not energy:** energy also depends on recording level and on other instruments, so activation is used. A per-file energy measure is a possible later improvement.
- **What to rely on:** treat velocity as a rough loud/soft hint, not a measurement.

## Files

| File | SHA-256 |
|---|---|
| `Frame_RNN_adtofAll_0.index` | `3fe35e421c448c395984168cd3aa1f979def902df784b6766291e55bb9aa069f` |
| `Frame_RNN_adtofAll_0.data-00000-of-00001` | `ff611129cb4a4d30722a54251e893341a58a016a40c419ab1e3786fc77a04779` |
| `frame_rnn_adtof_all_0.onnx` (1.8 MB, converted) | `9e2f06a1b3edf1d7943e885ed276c4983d8308bdee39646c0d4da1389c1c7e8d` |

The conversion is byte-for-byte reproducible: a fresh run in a new environment gave the same ONNX file as the M0-4 spike.

## Installing (download and conversion)

`adtof` is the default model. DrumTx installs it the first time it is needed, or when you run:

```bash
drumtx models download adtof
```

The steps (`drumtx.models`):
1. **Download.** The two checkpoint files come from the pinned ADTOF commit, and each must match its SHA-256 above.
2. **Convert.** ADTOF publishes only a TensorFlow checkpoint, so DrumTx converts it to ONNX once, with `src/drumtx/convert_adtof.py`. That script runs in a throwaway environment that `uv run --isolated` builds with pinned TensorFlow and PyTorch (about 1.5 GB, kept in uv's cache). This needs [uv](https://docs.astral.sh/uv/) installed; DrumTx itself only needs ONNX Runtime. It takes about a minute plus download time.
3. **Check and install.** The ONNX file must match its pinned SHA-256 before it moves into the model directory. DrumTx checks it again every time it loads it.

**Model directory:**
- **Linux:** `~/.cache/drumtx/models`
- **macOS:** `~/Library/Caches/drumtx/models`
- **Windows:** `%LOCALAPPDATA%\drumtx\Cache\models`

The `DRUMTX_CACHE_DIR` variable replaces the `…/drumtx` part. `drumtx models list` shows the directory and what is installed.

**Offline and failures:**
- **`--offline`:** never downloads; it fails with exit code 3 if the model is missing.
- **Failed checks:** a file that fails its check is rejected with exit code 4. `drumtx models download adtof` replaces it.
- **`--model baseline`:** needs nothing.

**Reproducibility:** the `Model conversion` CI workflow runs the download on Linux, macOS and Windows whenever the conversion changes. It checks that every OS produces the pinned file.

The conversion script checks the port twice and stops if either differs by more than 1e-4:
- **PyTorch against a Keras rebuild of the network:** maximum difference 2.7e-7.
- **ONNX Runtime against PyTorch:** maximum difference 2.5e-7 (M2-2 asks for at most 1e-4).

## Chunked inference

`ModelDetector` runs the network on windows of 60 s (`MODEL_CHUNK`, 6,000 frames). Each window also gets 4 s of context on each side (`MODEL_CONTEXT`, 400 frames), which is ADTOF's own warm-up. The context is discarded and only the 60 s center is kept. Peaks are then picked on the joined curve, so a chunk boundary cannot split or duplicate a peak; `tests/test_model.py` checks this with hits on boundary frames.

**Memory.** On a 10-minute file:
- **Whole file in one run:** peak memory 2.2 GB, over the 2 GB budget (technical design §11).
- **Chunked:** 753 MB, of which 643 MB is the test's own audio. Runtime also fell from 15.9 s to 8.3 s.

**Chunked output is not identical to whole-file output.** The bidirectional GRUs carry state across the whole input, so frames anywhere in a window shift slightly, not only near its edges.

| Context per side | Largest activation difference | Onsets that change |
|---|---|---|
| 4 s (chosen) | 0.12 | 94 of 8,920 |
| 10 s | 0.06 | 45 |
| 20 s | 0.05 | 33 |
| 30 s | 0.05 | 18 |

These are 11 development clips longer than 60 s, at `balanced`. Neither version is more correct: ADTOF itself trained on 4-second sequences, and it splits files longer than 10 minutes the same way. Over the whole development set, chunking moved no F-measure by more than 0.003 (any preset, subset, tolerance or class), so the shortest context was kept.

## Feature check against madmom

`drumtx.features` reimplements ADTOF's madmom pipeline (`adtof/io/mir.py`, `openMadmom`). `scripts/check_features.py` compared it once with madmom 0.16.1 on 10 development clips: 3 MDB, 3 IDMT and 4 E-GMD, 37,297 frames in all.
- **Drum-only clips:** the largest difference is 1.3e-5.
- **One stereo mix:** 6.3e-4, because madmom downmixes in 16-bit integers.
- **Detected onsets:** 0 of 2,099 differ.

```bash
~/drumtx-data/madmom-venv/bin/python scripts/check_features.py dump madmom.npz AUDIO...
```

```bash
uv run python scripts/check_features.py compare madmom.npz ~/.cache/drumtx/models/frame_rnn_adtof_all_0.onnx
```

## Development-set results

All 189 development clips (107 minutes), `balanced`, with chunked inference (M2-2) and tuned presets (M2-3), compared with the classical baseline (`eval/results/baseline-dev.json`). Full results, with every preset and with precision and recall, are in `eval/results/adtof-dev.json`.

```bash
uv run python scripts/benchmark.py --model adtof --compare eval/results/baseline-dev.json
```

Per-class F-measure, ADTOF / baseline:

| Subset @ tolerance | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| All @ 50 ms | **0.81** / 0.75 | **0.79** / 0.58 | **0.74** / 0.68 | **0.63** / 0.18 | **0.79** / 0.20 |
| All @ 30 ms | **0.75** / 0.66 | **0.76** / 0.55 | **0.69** / 0.63 | **0.57** / 0.16 | **0.74** / 0.19 |
| Drum-only @ 50 ms | **0.80** / 0.78 | **0.79** / 0.60 | **0.72** / 0.68 | **0.64** / 0.20 | **0.79** / 0.21 |
| Full mix @ 50 ms | **0.84** / 0.44 | **0.75** / 0.42 | **0.89** / 0.74 | **0.16** / 0.01 | **0.84** / 0.13 |

**M2-1's criterion still holds:** at `balanced`, the model beats the baseline on every class, in every subset and at both tolerances.

**Compared with ADTOF's own thresholds (M2-2):**
- **Snare:** F rose from 0.62 to 0.79 on all clips, and from 0.66 to 0.75 on full mixes.
- **Other classes:** within ±0.02.
- **Full-mix toms:** fell from 0.22 to 0.16 (15 hits, reported only).
- **`sensitive`:** loses F on full mixes (kick 0.82 → 0.74, hi-hat 0.89 → 0.79), the price of its higher recall.

**Runtime.** 0.84 s per audio minute for features and chunked inference, on the 4-core sandbox, not the reference machine.

### By source (`balanced`, 50 ms)

| Source | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| E-GMD (drum-only) | 0.76 | 0.80 | 0.64 | 0.67 | 0.78 |
| MDB Drums, drum-only | 0.96 | 0.76 | 0.91 | 0.07 (15 hits) | 0.90 |
| MDB Drums, full mix | 0.84 | 0.75 | 0.89 | 0.16 (15 hits) | 0.84 |
| IDMT-SMT-Drums | 0.99 | 0.75 | 0.97 | — | — |

## Known failure modes

- **Quiet notes are missed.** On E-GMD at `balanced`, precision is 0.87–0.95 for every class except tom, but recall is 0.50–0.71. Recall falls with the note's velocity:

  | E-GMD velocity | Kick | Snare | Hi-hat | Tom | Cymbal |
  |---|---|---|---|---|---|
  | below 40 | 0.20 | 0.37 | 0.26 | 0.03 | 0.13 |
  | 40–79 | 0.75 | 0.75 | 0.53 | 0.55 | 0.65 |
  | 80 and above | 0.99 | 0.91 | 0.66 | 0.80 | 0.89 |

  Rhythm-game charts, which the model was trained on, mostly leave out ghost notes. E-GMD is most of the development set (by hits), so this pulls down every development-set number. M2-3's lower snare threshold brought back most mid-velocity snare notes (recall 0.27 → 0.75). `sensitive` recovers more, at the cost of precision.
- **E-GMD hi-hat stays weak even when loud** (recall 0.66), as decision 0005 found: probably pedal and kit-specific hi-hats.
- **Toms in MDB are mostly false positives** (precision 0.04–0.09 on only 15 reference hits), so those numbers mean little (decision 0004).

## Fallback

If the model falls short on your own recordings, train the same architecture on E-GMD (decision 0005 estimates the effort). E-GMD includes ghost notes, which addresses the main failure above, but a model trained only on E-GMD has no full-mix training data.
