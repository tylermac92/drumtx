# Privacy

DrumTx runs entirely on your computer. Your recordings, and everything made from them, stay there.

## What never happens

- **No upload.** Audio and outputs never leave your computer.
- **No telemetry,** analytics, crash reports or update checks. DrumTx also switches off ONNX Runtime's own telemetry, which its Windows builds turn on by default.
- **No network access while transcribing.** `transcribe`, `render`, `preview` and `evaluate` never go online, except to download a model that isn't installed yet (see below). FFmpeg is only allowed to open local files, so even an audio file that is really a playlist of web addresses can't make it connect anywhere.

## The one exception: downloading models

DrumTx's detection, beat-tracking and separation models are not part of the install. They are downloaded once, the first time they're needed, or ahead of time with `drumtx models download`. Only these fixed addresses are used, and every file is checked against a pinned SHA-256 fingerprint:

| Model | Downloaded from |
|---|---|
| `adtof` (drum detection, the default) | raw.githubusercontent.com (the ADTOF repository, at a fixed commit) |
| `beat-this-final0` (beat tracking) | cloud.cp.jku.at (the Beat This! authors) |
| `umxl-drums` (`--separate` only) | zenodo.org (Open-Unmix) |

`adtof` and `beat-this-final0` are converted to ONNX once, after downloading. The conversion uses [uv](https://docs.astral.sh/uv/), which downloads the Python packages it needs from PyPI (pypi.org, files.pythonhosted.org) and the PyTorch package index (download.pytorch.org). If needed, it also downloads a Python interpreter. These go into uv's cache, not into DrumTx.

**To make sure DrumTx never goes online,** download the models once, then add `--offline`:

```bash
drumtx models download adtof
```

```bash
drumtx models download beat-this-final0
```

```bash
drumtx transcribe song.wav --offline
```

With `--offline`, a missing model is an error (exit code 3) and nothing is downloaded. `--model baseline` uses the built-in classical detector, so it needs only the beat-tracking model.

## What DrumTx writes, and where

| Where | What | Notes |
|---|---|---|
| The output folder (`<name>_drumtx/`, or `-o`) | The score, MIDI file, `events.json`, `events.csv`, report, and optionally the plot and preview | `events.json` and the report record the source file's **name**, its SHA-256 fingerprint and its duration, and the settings used. They do not contain the audio. |
| `<output folder>/.drumtx-cache/` | Detected hits and beats; with `--separate`, the **drum stem: audio separated from your recording** | Delete it before sharing an output folder. Deleting it is always safe: DrumTx recomputes it. |
| `drumtx preview`'s WAV file | Your recording, mixed with synthesized hits | It's audio: share it only if you may share the recording. |
| The model folder (`~/.cache/drumtx/models`, or `DRUMTX_CACHE_DIR`) | The downloaded models | Nothing about your recordings. |
| uv's cache | Packages used once to convert models | Nothing about your recordings. |

Output folders are named after your audio files, so a shared folder reveals the file name.

## Your responsibility

You need the rights to the audio you transcribe, and to share what you make from it. DrumTx is for personal use (decision 0001). The models it downloads have their own licenses, some non-commercial (decision 0003; `drumtx models list` shows them).

## How this is checked

- **Every test runs with networking blocked** (`tests/conftest.py`).
- **`tests/test_privacy.py`** runs the whole pipeline in CI with `--offline` on Linux, macOS and Windows. It covers `transcribe` (with ADTOF and Beat This! on stand-in models, and the plot), then `render`, `preview`, `evaluate` and `models list`. A Python audit hook records every socket, host lookup, URL request and new process, and the test requires that there are none. A control test checks that the hook does see a model download.
- **`tests/test_security.py`** checks that FFmpeg can't follow a playlist to the network.
- **With the real models and no network at all:** on Linux, in a network namespace with no interfaces (`unshare -n`), `drumtx transcribe --offline --plot` and `drumtx render` ran to the end with ADTOF and Beat This! and gave the same results as online (2026-11-09).
- **The limit of these checks:** the audit hook sees what Python does. It doesn't see inside the compiled libraries: ONNX Runtime, libsndfile, NumPy and, with `--separate`, PyTorch. None of these opens network connections for this kind of use.
