# Model card: ADTOF Frame_RNN (`adtof`)

- **Status:** integrated in M2-1, chunked in M2-2, presets tuned in M2-3, confidence and velocity fitted in M2-4, downloaded on first use since M2-5, evaluated once on the test set in M2-7 (2026-11-04).
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

## Test-set results (M2-7)

This is the one-time release evaluation on the frozen test set (decision 0004): 192 clips, 104 minutes (181 drum-only, 11 full mixes). Nothing was tuned on it. The model and its M2-3/M2-4 presets were fixed before the run, at commit `23696ca`. Full results, with every preset and every source, are in `eval/results/adtof-test.json`. The same tables are in `docs/accuracy.md`.

```bash
uv run python scripts/benchmark.py --split test --release --model adtof
```

**Precision / recall / F-measure at `balanced`** (the default):

| Subset | Tolerance | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|---|
| Drum-only | 50 ms | 0.87 / 0.75 / **0.81** | 0.74 / 0.68 / **0.71** | 0.83 / 0.70 / **0.76** | 0.68 / 0.67 / **0.68** | 0.86 / 0.85 / **0.85** |
| Drum-only | 30 ms | 0.80 / 0.69 / **0.74** | 0.63 / 0.57 / **0.60** | 0.75 / 0.63 / **0.69** | 0.55 / 0.54 / **0.55** | 0.84 / 0.83 / **0.83** |
| Full mix | 50 ms | 0.77 / 0.93 / **0.84** | 0.63 / 0.84 / **0.72** | 0.81 / 0.72 / **0.76** | 0.40 / 0.57 / **0.47** | 0.80 / 0.92 / **0.85** |
| Full mix | 30 ms | 0.76 / 0.91 / **0.83** | 0.62 / 0.83 / **0.71** | 0.81 / 0.72 / **0.76** | 0.40 / 0.57 / **0.47** | 0.78 / 0.90 / **0.84** |
| All | 50 ms | 0.86 / 0.76 / **0.81** | 0.73 / 0.69 / **0.71** | 0.83 / 0.70 / **0.76** | 0.67 / 0.67 / **0.67** | 0.84 / 0.86 / **0.85** |
| All | 30 ms | 0.79 / 0.70 / **0.75** | 0.63 / 0.60 / **0.61** | 0.76 / 0.64 / **0.69** | 0.54 / 0.54 / **0.54** | 0.83 / 0.84 / **0.84** |

Reference hits: drum-only 9,375 / 12,906 / 15,953 / 2,436 / 3,598; full mix 878 / 1,350 / 1,036 / 75 / 735.

**Against the targets** (decision 0010; the formal check is M7-4):

| | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| Drum-only, target | 0.85 | 0.85 | 0.75 | 0.60 | 0.60 |
| Drum-only, test | 0.81 ✗ | 0.71 ✗ | 0.76 ✓ | 0.68 ✓ | 0.85 ✓ |
| Full mix, target | 0.75 | 0.70 | 0.70 | reported only | 0.50 |
| Full mix, test | 0.84 ✓ | 0.72 ✓ | 0.76 ✓ | 0.47 | 0.85 ✓ |

**Other presets** (F-measure at 50 ms, drum-only / full mix):

| Preset | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| `strict` | 0.76 / 0.85 | 0.69 / 0.76 | 0.73 / 0.77 | 0.59 / 0.53 | 0.84 / 0.85 |
| `balanced` | 0.81 / 0.84 | 0.71 / 0.72 | 0.76 / 0.76 | 0.68 / 0.47 | 0.85 / 0.85 |
| `sensitive` | 0.76 / 0.76 | 0.67 / 0.64 | 0.76 / 0.71 | 0.64 / 0.39 | 0.83 / 0.81 |

The presets keep their order on the test set: `strict` has the highest precision and `sensitive` the highest recall for every class, in both subsets.

**By source** (`balanced`, 50 ms, F-measure, with precision / recall):

| Source | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| E-GMD (drum-only, 123 clips) | 0.75 (0.83 / 0.69) | 0.69 (0.77 / 0.63) | 0.72 (0.81 / 0.66) | 0.70 (0.72 / 0.67) | 0.87 (0.91 / 0.83) |
| MDB Drums (drum-only and full mix, 22 clips) | 0.91 (0.86 / 0.96) | 0.77 (0.68 / 0.87) | 0.78 (0.83 / 0.73) | 0.50 (0.42 / 0.61) | 0.85 (0.79 / 0.92) |
| IDMT-SMT-Drums (47 clips) | 0.99 (0.99 / 0.98) | 0.73 (0.58 / 0.99) | 0.95 (0.96 / 0.94) | — | — |

**Confidence on the test set** (`sensitive` detections, 50 ms): precision per confidence bin.

| Class | 0–0.2 | 0.2–0.4 | 0.4–0.6 | 0.6–0.8 | 0.8–1 |
|---|---|---|---|---|---|
| kick | — (1) | 0.12 | 0.28 | 0.52 | 0.88 |
| snare | 0.13 | 0.21 | 0.33 | 0.58 | 0.87 |
| hi-hat | 0.33 | 0.32 | 0.38 | 0.61 | 0.87 |
| tom | 0.16 | 0.31 | 0.62 | 0.87 | 0.93 |
| cymbal | — | 0.20 | 0.33 | 0.49 | 0.90 |

**How well the confidence holds up:**
- **It still ranks hits:** higher confidence means higher precision for every class, except hi-hat's two lowest bins, which are level (0.33, 0.32).
- **It is less well calibrated than on the development set:** kick, snare and cymbal are overconfident in the middle bins (0.4–0.8), and tom is underconfident.
- **The development-set table was optimistic, as expected (M2-4).**

**With `--separate`** on the 11 full-mix test clips (`eval/results/adtof-test-full-mix-separate.json`), F-measure at 50 ms, without → with:

| Preset | Kick | Snare | Hi-hat | Tom (75 hits) | Cymbal |
|---|---|---|---|---|---|
| `balanced` | 0.84 → **0.90** | 0.72 → **0.79** | **0.76** → 0.74 | 0.47 → **0.51** | **0.85** → 0.82 |
| `strict` | 0.85 → **0.89** | 0.76 → **0.81** | 0.77 → 0.76 | **0.53** → 0.51 | **0.85** → 0.80 |
| `sensitive` | 0.76 → **0.85** | 0.64 → **0.73** | 0.71 → **0.74** | 0.39 → **0.47** | 0.81 → 0.81 |

- **Separation:** 13.0 s per audio minute on the 4-core sandbox CPU. Detection alone takes 0.67 s.
- **Unlike the development set, snare improves here.** Kick improves on both sets, and cymbal loses on both. `--separate` stays off by default (Q3).

**Runtime.** 0.67 s per audio minute for features and inference, on the 4-core sandbox.

## Known failure modes

These are confirmed on the test set unless marked otherwise.

- **Quiet notes are missed.** On E-GMD at `balanced`, precision is 0.87–0.95 for every class except tom, but recall is 0.50–0.71. Recall falls with the note's velocity:

  | E-GMD velocity | Kick | Snare | Hi-hat | Tom | Cymbal |
  |---|---|---|---|---|---|
  | below 40 | 0.20 | 0.37 | 0.26 | 0.03 | 0.13 |
  | 40–79 | 0.75 | 0.75 | 0.53 | 0.55 | 0.65 |
  | 80 and above | 0.99 | 0.91 | 0.66 | 0.80 | 0.89 |

  Rhythm-game charts, which the model was trained on, mostly leave out ghost notes. E-GMD is most of the development set (by hits), so this pulls down every development-set number. M2-3's lower snare threshold brought back most mid-velocity snare notes (recall 0.27 → 0.75). `sensitive` recovers more, at the cost of precision.

  On the test set, E-GMD recall is still only 0.63–0.69 for kick, snare and hi-hat, so drum-only kick and snare miss their targets. A model that hears ghost notes (the fallback below) is the main way to close the gap.
- **The low snare threshold adds false hits on real kits.** M2-3 chose snare 0.05 for E-GMD's quiet notes. On the test set, snare precision is 0.58 on IDMT and 0.68 on MDB, against 0.99 recall on IDMT, and overall snare F falls from 0.79 (development) to 0.71. This is the trade-off M2-3 flagged; weighting sources equally would choose about 0.07. Re-tune on the development set only, after the M7-1 trial, never on these test numbers.
- **Timing is looser for snare and toms.** From 50 ms to 30 ms, drum-only F drops by 0.11 for snare and 0.13 for tom, against 0.02 for cymbal. Many of those hits land 30–50 ms from the reference.
- **E-GMD hi-hat stays weak even when loud** (development recall 0.66; test F 0.72), as decision 0005 found: probably pedal and kit-specific hi-hats.
- **Toms in full mixes are unreliable:** precision 0.40 on the test set's 75 full-mix tom hits; `--separate` helps a little. On the development set's 15 hits, precision was 0.04–0.09.
- **Confidence is overconfident in its middle range** on unseen audio (see the table above): treat 0.4–0.8 as "check this".

## Fallback

If the model falls short on your own recordings, train the same architecture on E-GMD (decision 0005 estimates the effort). E-GMD includes ghost notes, which addresses the main failure above, but a model trained only on E-GMD has no full-mix training data.
