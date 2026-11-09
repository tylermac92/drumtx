# Model card: Beat This! `final0` (`beat-this-final0`)

- **Status:** integrated in M3-1, 2026-11-04.
- **Chosen in:** decision 0006.

## What it is

The beat and downbeat tracker from [Beat This!](https://github.com/CPJKU/beat_this) (Foscarin, Schlüter and Widmer, ISMIR 2024), `final0` checkpoint. It is a transformer that predicts beat and downbeat logits at 50 frames per second from a log-mel spectrogram. DrumTx always runs it on the full mix, also with `--separate`, because the other instruments help locate the beats.

| | |
|---|---|
| License | MIT (code and weights). Some of its training audio is copyrighted (decision 0003). |
| Upstream file | `final0.ckpt` (81 MB) from the `beat_this` package's download location, SHA-256 `8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331` |
| Loaded file | `beat_this_final0.onnx` (83 MB), SHA-256 `729e39fa055c7e5bb8b22c0f0c845eeb22ad36b9ef48255556256472cd670ef5` |
| Input | Mono audio resampled to 22,050 Hz: magnitude STFT (1024 points, hop 441), 128 Slaney mel bands from 30 Hz to 11 kHz, `log1p(1000·x)` (`drumtx.beats.log_mel`) |
| Inference | Chunks of 1,500 frames (30 s). Chunks overlap by 6 frames, which are discarded at each edge; where they overlap, the earlier chunk wins. |
| Postprocessing | Upstream's "minimal" one: a frame is a beat if it is the maximum within ±60 ms and its probability is above 0.5. Adjacent peaks are merged, and each downbeat moves to its nearest beat. |

## Installing

DrumTx installs the model the first time it is needed, or when you run:

```bash
drumtx models download beat-this-final0
```

The checkpoint is a PyTorch pickle. DrumTx never loads it itself: after checking its SHA-256, it converts it to ONNX once with `src/drumtx/convert_beat_this.py`.
- **Conversion environment:** a throwaway `uv run --isolated` environment with `beat-this==1.1.0` from PyPI and PyTorch. That package reads the checkpoint with `torch.load(weights_only=True)`, which reads tensors only.
- **Reproducible output:** the result must match the pinned SHA-256, on Linux, macOS and Windows (the Model conversion workflow). Every weight in the file is a checkpoint tensor, copied or transposed, and nothing is computed from them at export. Until November 2026 the export folded the BatchNorm layers into the convolutions. That arithmetic ran on the CPU's own vector instructions, so the file differed in the last bit between machines, and the download failed on macOS, Windows and some Linux machines. The BatchNorm layers are now kept as they are (`training=PRESERVE`). An older file fails the new SHA-256; `drumtx models download beat-this-final0` replaces it.
- **Accuracy:** ONNX Runtime matches PyTorch within 2.5e-6 on the logits.
- **Network:** with `--offline` and no model installed, `transcribe` exits with code 3. This applies to every detector, including `--model baseline`, because every run tracks beats.

## Check against upstream (M3-1)

`scripts/check_beats.py` runs our NumPy and ONNX path and the upstream `beat_this` 1.1.0 package (PyTorch, `final0`, minimal postprocessing) on the whole development rhythm subset: 67 clips, 91 minutes.

| | Count | More than one frame (20 ms) from upstream | Largest difference |
|---|---|---|---|
| Beats | 10,326 | 0 | 0 ms |
| Downbeats | 2,816 | 0 | 0 ms |

The outputs are identical, so the PyTorch fallback extra (decision 0006) is not needed. The log-mel spectrogram itself differs from torchaudio's by at most 1.2e-4, in values up to 8.

Reproduce in two steps:
1. Run `dump` in an environment with `beat-this` and PyTorch, such as the spike environment.
2. Run `compare` in DrumTx's own environment.

```bash
~/drumtx-data/spike-venv/bin/python scripts/check_beats.py dump upstream.json
```

```bash
uv run python scripts/check_beats.py compare upstream.json
```

## Tempo map and overrides

`transcribe` stores the raw beats and downbeats in the stage cache, and builds the tempo map in `events.json` from them (`drumtx.beats.tempo_map`). So the overrides below never re-run the network.

| Option | What it does | Marked as |
|---|---|---|
| (none) | Bars of 4 beats. Bar 1 starts where most tracked downbeats agree. Beats before it form a pickup, measure 0. | `estimated` / `default` |
| `--time-signature N/4` | Bars of N beats, with N from 1 to 16. Downbeats are still chosen by majority. | `time_signature_source: user` |
| `--first-downbeat SEC` | Bar 1 starts at the beat nearest SEC. Beats more than one bar earlier are left out, because measures cannot be negative. | `first_downbeat_source: user` |
| `--bpm BPM` | Corrects half or double time, and other whole-number ratios. When the tracked tempo is k times too slow, each beat interval is split into k. When it is k times too fast, every k-th beat is kept, choosing the phase that keeps the downbeats. Tempo drift is kept. A tempo that is not within 15% of a whole-number ratio is ignored, with a warning. | `tempo_source: user` |

On the two development songs that the M0-5 spike found tracked at half tempo, `--bpm` with the annotated tempo fixes them:

| Song | Annotated | Tracked | Beat F-measure | With `--bpm` |
|---|---|---|---|---|
| MDB BebopJazz (full mix) | 222 BPM | 111 BPM | 0.68 | 0.98 |
| MDB CoolJazz (full mix) | 109 BPM | 56 BPM | 0.76 | 0.89 |

## Runtime and memory

These were measured on a 10-minute file on the 4-core sandbox, not on the reference machine:
- **Tracking:** about 2 s per audio minute.
- **Whole `transcribe`:** 32 s with ADTOF, at 1.3 GB peak memory.
- **Memory setting:** ONNX Runtime's memory arena is turned off for this model, which saves 0.5 GB of peak memory for about 8% more time.

## Known limitations

- **Half or double tempo** on some songs, mostly fast or swung jazz (decision 0006); use `--bpm`.
- **One meter per piece.** The meter is never estimated: it is 4/4 unless `--time-signature` says otherwise.
- **Optimistic E-GMD scores.** Beat This! was trained on the Groove MIDI Dataset, which has the same performances as E-GMD, so its beat scores on E-GMD clips are optimistic. Beat accuracy targets and their evaluation come in M3-6.
