# 0006 — Beat and downbeat tracker

- **Status:** Accepted, 2026-10-31
- **Task:** M0-5

## Decision

- **Tracker: Beat This!, `final0` checkpoint (MIT code and weights), run through ONNX Runtime in the base install.**
  - No PyTorch is needed at runtime, so the tracker does not go in an extra.
  - The model is exported to ONNX once.
  - Its log-mel spectrogram, chunking and peak picking are reimplemented in NumPy (resampling with `soxr`), as for the detection model (decision 0005).
- **Fallback: the upstream `beat_this` package with PyTorch, in an optional extra.**
  - It is used only if the NumPy and ONNX path cannot be made to match upstream output (M3-1).
  - For a wrong result on a particular song, the fallback is the manual overrides `--bpm`, `--time-signature` and `--first-downbeat`. They fix every failure seen in this spike.
- **Rejected:**
  - **madmom:** its last release only installs on Python 3.9; its model files are pickles; its weights are non-commercial; and it put the bar line in the wrong place on 8 of 34 clips.
  - **librosa:** weak beats, no downbeats, and about 240 MB of dependencies.

## Comparison

The clips are the development rhythm subset (decision 0004): all 12 MDB Drums tracks, both drum-only and full mix, plus 10 E-GMD grooves, including one in 3/4. That is 34 clips.

The table shows mean beat and downbeat F-measure at ±70 ms (`mir_eval`). There is no 5-second trimming, because the clips are short.

| Tracker | MDB drum-only beat / downbeat | MDB full mix beat / downbeat | E-GMD beat / downbeat* | Failures (34 clips) |
|---|---|---|---|---|
| **Beat This! `final0`** | **0.98 / 0.93** | 0.93 / **0.95** | 1.00 / 0.87 | 2 half tempo |
| Beat This! `small0` | 0.99 / 0.89 | 0.93 / 0.97 | 0.93 / 0.80 | 2 half tempo, 2 bar offset, 1 unstable |
| madmom 0.16.1 (RNN + DBN, 3/4 and 4/4) | 0.96 / 0.74 | **0.97** / 0.75 | 0.89 / 0.42 | 8 bar offset, 2 half, 1 double, 1 unstable |
| librosa 1.0 `beat_track` (+ given first downbeat and meter) | 0.84 / 0.32 | 0.85 / 0.49 | 0.69 / 0.05 | 14 bar offset, 6 other tempo ratio, 3 half, 1 unstable |

\* Beat This! was trained on the Groove MIDI Dataset, which contains the same performances as E-GMD, so its E-GMD column is optimistic. The MDB columns are free of training overlap for all trackers.

### Failure modes

- **Beat This! `final0`.** It goes half tempo on two jazz full mixes:
  - BebopJazz: annotated at 222 BPM, tracked at 111 BPM, which is an arguably valid reading;
  - CoolJazz: annotated at 109 BPM, tracked at 56 BPM.

  It made no bar-offset errors. `--bpm` fixes both failures (M3-1).
- **madmom.** Most of its errors are bar offsets (beats right, downbeat on the wrong beat), including the 3/4 groove. It also went half tempo on BebopJazz, in both versions, and double tempo on one samba.
- **librosa.** Its beats drift off phase. Even when given the first downbeat and the meter, its downbeats rarely line up.

### Runtime, footprint, Python support and license

| Tracker | Runtime (s per audio minute, 4-core sandbox) | Install footprint | Python support | License |
|---|---|---|---|---|
| Beat This! `final0`, PyTorch | 2.8 | PyTorch + torchaudio ≈ 780 MB; checkpoint 81 MB | Any version PyTorch supports | MIT (some training audio is copyrighted; see decision 0003) |
| Beat This! `final0`, ONNX | about 2 (model only, measured on 30 s chunks) | ONNX Runtime (already in the base install) + `soxr` 0.5 MB; ONNX model 83 MB | Any version ONNX Runtime supports (3.11–3.13 tested in CI for the base install) | MIT |
| Beat This! `small0` | 1.4 | Same; model 8.5 MB (ONNX 11 MB) | Same | MIT |
| madmom 0.16.1 | 10.5 | about 30 MB, plus NumPy and SciPy | **Python ≤ 3.9 and NumPy < 1.20** (PyPI release); the unreleased git version was not tested | Code BSD; models CC BY-NC-SA (pickles) |
| librosa 1.0 | 0.6 | about 240 MB (llvmlite, numba, scikit-learn) | 1.0: Python ≥ 3.12; 0.11: ≥ 3.8 | ISC |

## Inference without PyTorch

`spikes/m0-5/onnx_check.py` exports the Beat This! model to ONNX (opset 17, dynamic length) and compares it with PyTorch on six 30-second chunks.

- **Accuracy:** the maximum logit difference is 4.8e-5 (`final0`) and 1.0e-4 (`small0`).
- **Speed:** ONNX Runtime was about 25% slower than PyTorch on this machine; both run well under real time.
- **Pickle checkpoints:** the upstream checkpoints are PyTorch pickles, which the design does not allow loading (Technical Design Document §12). The ONNX export avoids that. The export runs once, in a dev environment, and the ONNX file goes in the per-user model directory.

## Why `final0` over `small0`

`small0` is 8× smaller and twice as fast. But it made more downbeat errors (two bar offsets and one unstable clip), and downbeat errors garble the whole score. An 83 MB one-time download is acceptable for a personal tool.

## Follow-ups for M3-1

- Reimplement Beat This!'s log-mel spectrogram, `split_predict_aggregate` chunking and its minimal postprocessor in NumPy. The reference is torchaudio's `MelSpectrogram`:
  - 22,050 Hz audio, 1024-point FFT, hop of 441 samples (50 frames per second);
  - 128 Slaney mel bands from 30 Hz to 11 kHz;
  - magnitude spectrum, `log1p(1000·x)`.
- Accept the NumPy and ONNX path only if its beats match the upstream package within 1 frame on the development rhythm subset. Otherwise, use the PyTorch fallback extra.

## Reproducing

The spike code is in `spikes/m0-5/`.

- **Beat This! and librosa** run in the M0-4 spike environment, with `beat-this`, `librosa`, `soxr`, `einops`, `rotary-embedding-torch` and the CPU builds of `torch` and `torchaudio`.
- **madmom** runs in a Python 3.9 environment with `numpy<1.20`, `scipy<1.8`, `setuptools<70`, and `madmom==0.16.1` built without build isolation.

Each `track.py` command writes its predictions to `~/drumtx-data/spike5/`.

```bash
python track.py beat_this final0
```

```bash
python track.py beat_this small0
```

```bash
python track.py librosa
```

```bash
python track.py madmom
```

Then score the saved predictions and run the ONNX check:

```bash
python evaluate.py
```

```bash
python onnx_check.py final0
```
