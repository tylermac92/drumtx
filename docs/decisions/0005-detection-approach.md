# 0005 — Drum detection approach (resolves Q2)

- **Status:** Accepted, 2026-10-30
- **Task:** M0-4

## Decision

Adopt the **ADTOF `Frame_RNN` pretrained model** (`Frame_RNN_adtofAll_0`, CC BY-NC-SA 4.0, decision 0003) as the learned detector.

- **Runtime:** its weights are ported to PyTorch, exported to ONNX and run with ONNX Runtime.
- **Features:** its input is computed in NumPy, as the same madmom-style log-filtered spectrogram it was trained on. So the base install needs neither TensorFlow, PyTorch, madmom nor librosa.
- **Fallbacks:**
  - the classical baseline stays as `--model baseline` and as the regression floor;
  - training our own model on E-GMD (same architecture) is the fallback if ADTOF falls short on your own recordings.

## Comparison

Ten development clips (decision 0004), 14.2 minutes in all:

| Subset | Clips |
|---|---|
| Drum-only (7) | E-GMD rock, funk, jazz and gospel grooves; an E-GMD tom fill; MDB FusionJazz; IDMT RealDrum01_00 |
| Full mix (3) | MDB FusionJazz, Disco, Shadows |

The table shows per-class F-measure at ±50 ms, with reference onset counts in parentheses. Results at ±30 ms are within 0.03 of these for the two leading options.

| Option | Subset | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| Classical (band flux) | drum-only | 0.92 (1038) | 0.62 (1309) | 0.69 (1551) | 0.12 (218) | 0.39 (767) |
| | full mix | 0.53 (286) | 0.57 (301) | 0.80 (838) | 0.02 (13) | 0.24 (237) |
| **ADTOF pretrained** | drum-only | **0.96** | **0.87** | 0.68 | **0.73** | **0.90** |
| | full mix | **0.95** | **0.90** | **0.95** | 0.73 | **0.86** |
| Own CRNN, 40 min CPU training on E-GMD | drum-only | 0.93 | 0.87 | **0.82** | **0.94** | 0.82 |
| | full mix | 0.56 | 0.30 | 0.79 | 0.03 | 0.29 |

Runtime, install footprint and license for each option:

| Option | Runtime (s per audio minute) | Runtime install | License |
|---|---|---|---|
| Classical | 0.4–0.6 features + < 0.01 | NumPy + SciPy ≈ 185 MB | Our code |
| ADTOF pretrained | 0.4–0.6 features + 0.2 inference | NumPy + ONNX Runtime ≈ 125 MB, plus a 1.8 MB model | CC BY-NC-SA 4.0 weights |
| Own CRNN | 0.4–0.6 features + 0.2 inference | Same as ADTOF | Our code, trained on E-GMD (CC BY 4.0) |

- **Runtime.** Measured on this 4-core cloud sandbox, which is not the reference machine (M0-8). All options are far below the 1× real-time target.
- **One-time setup.** Converting the ADTOF checkpoint needs TensorFlow once (about 1.3 GB). Training needs PyTorch (about 765 MB). Neither is needed at runtime.

### How each option was run

- **Classical.** Positive spectral flux summed over one frequency band per class:

  | Class | Band |
  |---|---|
  | kick | 30–90 Hz |
  | tom | 100–300 Hz |
  | snare | 1–4 kHz |
  | cymbal | 4–8 kHz |
  | hihat | 8–16 kHz |

  The flux is normalized per clip and peak-picked with a per-class threshold. Thresholds were tuned on the same ten clips, so these numbers are optimistic.
- **ADTOF.**
  - **Port check.** The TensorFlow checkpoint is read with `tf.train.load_checkpoint` and mapped into a PyTorch CRNN. On a test input, the port matches a Keras rebuild of the same network to within 2.7e-7. Two details mattered:
    - Keras orders GRU gates (z, r, h);
    - TensorFlow's "same" max-pooling splits its padding before and after.
  - **Thresholds and peak picking** are the upstream per-class thresholds (0.22 / 0.24 / 0.32 / 0.22 / 0.30), with madmom's note peak picking reimplemented in NumPy.
  - **Not tuned.** Nothing was tuned on these clips.
- **Own CRNN.** The same architecture, trained from scratch for 1,593 steps (batches of 16 four-second windows) (40 minutes on 4 CPU cores) on 270 E-GMD `train` performances (156 minutes, one kit each). Thresholds were tuned on 30 held-out training performances.

## Why ADTOF

- **Accuracy.** ADTOF is the only option that stays strong on full mixes; the other two drop to F ≈ 0.3 on snare and cymbal there.
- **Our own model's drum-only lead is misleading.** It wins drum-only hi-hat and tom, but five of the seven drum-only clips are E-GMD, the same kind of electronic-kit renders it trained on, so those numbers are in-domain and flattering.
- **Training data.** It was trained on ADTOF-RGW and ADTOF-YT, real music annotated from rhythm-game charts, which matches DrumTx's input better than E-GMD's electronic-kit renders. (The checkpoint name matches the upstream "adtof-all" scenario, which doesn't include MDB Drums, so the MDB results are not contaminated by training data.)
- **Effort.** Adopting it costs a feature extractor and a conversion command, not a training pipeline.
- **Footprint.** The runtime is the same as for our own model, and smaller than the classical option with SciPy.

## Training-effort estimate (the fallback)

- **Drum-only.** 40 minutes of CPU training reached F 0.82–0.94 on every class, so a usable drum-only model is cheap.
- **Full mixes.** That model fails on full mixes because E-GMD has no backing music, and no allowed dataset has enough annotated full mixes. A competitive model would need full-mix training data:
  - for example, mixing E-GMD drums with backing stems;
  - or adding Slakh2100 (CC BY 4.0), which would mean a decision 0003 update.
- **Compute.** One pass over all of E-GMD (about 444 hours of audio) takes about 10 hours on this 4-core CPU at the prototype's rate of about 28 audio-hours per 40 minutes. Full training (several passes, augmentation, tuning) needs a GPU or a few days of CPU time.
- **Overall.** Roughly 1–2 weeks of work for the data pipeline, mixing, training and evaluation, plus GPU time. That is why it is the fallback, not the plan.

## Risks and follow-ups

- **Features not checked against madmom.** They were reimplemented from madmom's algorithm, not compared against madmom output, because madmom installs only from git. The near-upstream accuracy suggests they are close. M2-1 should compare against madmom once, in a throwaway environment.
- **Hi-hat on E-GMD drum-only clips.** It is the weak spot (0.48 on the gospel groove; 0.80–1.00 on MDB and IDMT), probably from pedal and kit-specific hi-hats. Watch it in M1-6 and M2-3.
- **Small sample.** Ten clips; full-mix toms have only 13 reference hits. M1-6 and M2-7 give the real numbers.
- **One-time conversion.** Converting needs TensorFlow once. M2-1 chooses between a dev-only conversion environment and a small reader for the TensorFlow checkpoint format. The converted ONNX file is derived from CC BY-NC-SA weights, so it stays in the per-user model directory and is never committed.
- **Licensing.** The weights are non-commercial (decision 0001 allows this). If the project is ever shared, the own-model fallback becomes the default.

## Reproducing

The spike code is in `spikes/m0-4/`. It runs in a separate environment with NumPy, SciPy, soundfile, mir_eval, ONNX Runtime, PyTorch (CPU), TensorFlow (CPU) and mido. It expects the corpus from decision 0004 and the ADTOF checkpoint files in `~/drumtx-data/models/adtof/`.

Checkpoint SHA-256 values:
- `Frame_RNN_adtofAll_0.index`: `3fe35e42…069f`
- `Frame_RNN_adtofAll_0.data-00000-of-00001`: `ff611129…4779`

Commands:

```bash
python crnn.py convert
```

```bash
python train.py fetch 300
```

```bash
python train.py train 40
```

```bash
python run.py
```
