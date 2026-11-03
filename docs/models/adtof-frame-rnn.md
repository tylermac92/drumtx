# Model card: ADTOF Frame_RNN (`adtof`)

- **Status:** integrated in M2-1, 2026-11-03. Chunked inference (M2-2), tuned presets (M2-3), calibrated confidence (M2-4), download on first use (M2-5) and the test-set results (M2-7) are still to come.
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
| Peak picking | madmom's note peak picking with ADTOF's settings (`detect.pick_peaks`); peaks within 20 ms combined. ADTOF's `labelOffset` is 0 for this model, so no time shift. |
| Thresholds (`balanced`) | ADTOF's own: kick 0.22, snare 0.24, tom 0.32, hi-hat 0.22, cymbal 0.30. `strict` and `sensitive` scale them by 1.5 and 0.67 (not tuned yet; M2-3). |
| Confidence and velocity | Not calibrated yet (M2-4): `p / (p + threshold)`, and velocity = 127 × confidence. |

## Files

| File | SHA-256 |
|---|---|
| `Frame_RNN_adtofAll_0.index` | `3fe35e421c448c395984168cd3aa1f979def902df784b6766291e55bb9aa069f` |
| `Frame_RNN_adtofAll_0.data-00000-of-00001` | `ff611129cb4a4d30722a54251e893341a58a016a40c419ab1e3786fc77a04779` |
| `frame_rnn_adtof_all_0.onnx` (1.8 MB, converted) | `9e2f06a1b3edf1d7943e885ed276c4983d8308bdee39646c0d4da1389c1c7e8d` |

The conversion is byte-for-byte reproducible: a fresh run in a new environment gave the same ONNX file as the M0-4 spike.

## Converting

This downloads the checkpoint (if not already there), checks its SHA-256, and writes the ONNX file to `~/drumtx-data/models/adtof/` (`--model-dir` changes this). It runs in a throwaway environment with TensorFlow and PyTorch (about 1.5 GB, cached by uv). DrumTx itself only needs ONNX Runtime. It takes about a minute plus download time.

```bash
uv run --isolated --no-project --python 3.12 --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match --with tensorflow-cpu==2.21.0 --with torch==2.15.0+cpu --with onnx==1.23.2 --with onnxruntime==1.31.1 python scripts/convert_adtof.py
```

The script checks the port twice and stops if either differs by more than 1e-4:
- **PyTorch against a Keras rebuild of the network:** maximum difference 2.7e-7.
- **ONNX Runtime against PyTorch:** maximum difference 2.5e-7.

## Feature check against madmom

`drumtx.features` reimplements ADTOF's madmom pipeline (`adtof/io/mir.py`, `openMadmom`). `scripts/check_features.py` compared it once with madmom 0.16.1 on 10 development clips: 3 MDB, 3 IDMT and 4 E-GMD, 37,297 frames in all.
- **Drum-only clips:** the largest difference is 1.3e-5.
- **One stereo mix:** 6.3e-4, because madmom downmixes in 16-bit integers.
- **Detected onsets:** 0 of 2,099 differ.

```bash
~/drumtx-data/madmom-venv/bin/python scripts/check_features.py dump madmom.npz AUDIO...
```

```bash
uv run python scripts/check_features.py compare madmom.npz ~/drumtx-data/models/adtof/frame_rnn_adtof_all_0.onnx
```

## Development-set results

All 189 development clips (107 minutes), `balanced`, compared with the classical baseline (`eval/results/baseline-dev.json`). Full results, with every preset and with precision and recall, are in `eval/results/adtof-dev.json`.

```bash
uv run python scripts/benchmark.py --model adtof --compare eval/results/baseline-dev.json
```

Per-class F-measure, ADTOF / baseline:

| Subset @ tolerance | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| All @ 50 ms | **0.80** / 0.75 | **0.62** / 0.58 | **0.73** / 0.68 | **0.63** / 0.18 | **0.79** / 0.20 |
| All @ 30 ms | **0.75** / 0.66 | **0.60** / 0.55 | **0.68** / 0.63 | **0.57** / 0.16 | **0.73** / 0.19 |
| Drum-only @ 50 ms | **0.80** / 0.78 | **0.62** / 0.60 | **0.71** / 0.68 | **0.64** / 0.20 | **0.78** / 0.21 |
| Full mix @ 50 ms | **0.84** / 0.44 | **0.66** / 0.42 | **0.89** / 0.74 | **0.22** / 0.01 | **0.84** / 0.13 |

**M2-1's criterion is met:** at `balanced`, the model beats the baseline on every class, in every subset and at both tolerances.

**Other presets.** `strict` snare is below the baseline's `strict` (0.52 vs 0.57 on all clips at 50 ms). The preset scaling is untuned until M2-3; the benchmark's `--compare` lists this as its only regressions.

**Runtime.** 0.75 s per audio minute for features and inference, on the 4-core sandbox, not the reference machine.

### By source (`balanced`, 50 ms)

| Source | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| E-GMD (drum-only) | 0.75 | 0.57 | 0.61 | 0.65 | 0.78 |
| MDB Drums, drum-only | 0.96 | 0.74 | 0.90 | 0.13 (15 hits) | 0.89 |
| MDB Drums, full mix | 0.84 | 0.66 | 0.89 | 0.22 (15 hits) | 0.84 |
| IDMT-SMT-Drums | 0.99 | 0.89 | 0.96 | — | — |

## Known failure modes

- **Quiet notes are missed.** On E-GMD, precision is 0.89–0.99 for every class except tom, but recall is 0.40–0.67. Recall falls with the note's velocity:

  | E-GMD velocity | Kick | Snare | Hi-hat | Tom | Cymbal |
  |---|---|---|---|---|---|
  | below 40 | 0.19 | 0.07 | 0.22 | 0.00 | 0.12 |
  | 40–79 | 0.73 | 0.27 | 0.48 | 0.41 | 0.65 |
  | 80 and above | 0.99 | 0.74 | 0.64 | 0.70 | 0.89 |

  Rhythm-game charts, which the model was trained on, mostly leave out ghost notes. E-GMD is most of the development set (by hits), so this pulls down every development-set number, most of all snare. M2-3 should tune the thresholds lower to see how much recall comes back.
- **E-GMD hi-hat stays weak even when loud** (recall 0.64), as decision 0005 found: probably pedal and kit-specific hi-hats.
- **Toms in MDB are mostly false positives** (precision 0.07–0.13 on only 15 reference hits), so those numbers mean little (decision 0004).
- **Memory.** The whole file goes through the network in one run; M2-2 adds chunking.

## Fallback

If the model falls short on your own recordings, train the same architecture on E-GMD (decision 0005 estimates the effort). E-GMD includes ghost notes, which addresses the main failure above, but a model trained only on E-GMD has no full-mix training data.
