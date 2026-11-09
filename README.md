# DrumTx

DrumTx turns a drum recording into a drum score you can open in MuseScore, a MIDI file, an editable list of every hit, and a report that points to the bars most likely to be wrong. It runs on your own computer, on an ordinary CPU, from the command line. It is a personal project, for personal use (decision 0001).

## What it does

- **Hits:** finds kick, snare, hi-hat, tom and cymbal hits, with a confidence and a loudness for each.
- **Rhythm:** finds the beats and bar lines, and writes each hit on a 16th-note or 8th-note-triplet grid, chosen beat by beat.
- **Outputs:** MusicXML (one percussion staff), a MIDI file whose notes line up with the original audio in a DAW, `events.json` and `events.csv`, and a review report.
- **Correcting:** helps you correct the result. The report flags the bars to check, `drumtx preview` lets you hear the detected hits against the recording, and after you fix bar lines or edit the hit list, `drumtx render` writes everything again.
- **Full mixes:** works on whole songs too, best with `--separate`, which isolates the drums first.

## What it does not do

- **It is not always right.** A transcription is a draft. Expect to correct it: on drum-only recordings it finds about three quarters of the hits, and adds some that aren't there ([accuracy](docs/accuracy.md)).
- **Five classes only:** all toms are one class, crash and ride are one class, and open and closed hi-hat are one class.
- **Quiet notes:** it often misses ghost notes and other quiet notes.
- **Meter and feel:** it doesn't detect the time signature (4/4 unless you pass `--time-signature`) or swing, which is written as straight 16ths.
- **Notation:** no dynamics, accents or articulations. MuseScore is the only notation app it has been checked with ([compatibility](docs/compatibility.md)).
- **Scope:** it doesn't transcribe other instruments, and it doesn't work in real time.

## Install

Requires Python 3.11–3.13 and [pipx](https://pipx.pypa.io/). From a clone of this repository:

```bash
pipx install .
```

```bash
drumtx doctor
```

`drumtx doctor` shows what the installation can do (FFmpeg, the extras, the models, the device), with the command that adds anything missing.

- **First run.** The models are downloaded and converted once, on first use, or ahead of time with `drumtx models download`. The conversion needs [uv](https://docs.astral.sh/uv/).
- **Other formats.** WAV, FLAC, OGG, MP3 and AIFF are read directly. Other formats, such as M4A, need [FFmpeg](https://ffmpeg.org).
- **Extras:** `[separation]` for `--separate` (PyTorch, large) and `[plot]` for `--plot` (matplotlib). Install with, for example, `pipx install ".[plot]"`, or add one later with `pipx inject drumtx matplotlib`.

## Quick start

```bash
drumtx transcribe song.wav
```

```bash
drumtx preview song.wav song_drumtx/song.events.json --split-stereo
```

The first command writes `song_drumtx/`:

| File | What it is |
|---|---|
| `song.musicxml` | The score. Open it in MuseScore. |
| `song.mid` | MIDI on channel 10, aligned with the audio. |
| `song.events.csv` | One row per hit. Edit it and run `drumtx render`. |
| `song.events.json` | The hits with their positions, the tempo map and the settings. |
| `song.report.md` | What to check: the tempo, bar 1, the flagged bars, and next steps. |

The second writes `song_drumtx/song.preview.wav`: the recording on the left, the detected hits on the right.

## Documentation

| Page | For |
|---|---|
| [Correction guide](docs/correction-guide.md) | From a first transcription to a corrected score, step by step |
| [CLI reference](docs/cli.md) | Every command and option, generated from the program itself |
| [Accuracy and limitations](docs/accuracy.md) | What to expect, on drum-only recordings and on full mixes |
| [Troubleshooting](docs/troubleshooting.md) | Error messages, and results that look wrong |
| [Output formats](docs/schema/events-v1.md) | `events.json`, `events.csv` and the instrument mapping |
| [Privacy](docs/privacy.md) | What stays on your computer (everything) and the one download |
| [Compatibility](docs/compatibility.md) | Notation apps checked |

`tests/test_docs.py` runs every command in the `bash` blocks of these pages, so they stay current.

## Develop

Uses [uv](https://docs.astral.sh/uv/) and its lock file (`uv.lock`).

```bash
uv sync
```

```bash
uv run ruff check && uv run ruff format --check
```

```bash
uv run mypy src tests scripts
```

```bash
uv run pytest
```

CI runs these on Linux, macOS and Windows with Python 3.11 and 3.13, and installs the built wheel with pipx as a smoke test. After changing a command or an option, regenerate the CLI reference:

```bash
uv run typer drumtx.cli utils docs --name drumtx --output docs/cli.md
```

- **Plans:** the brief, design, decisions and milestone plan are in `docs/`.
- **Progress notes for contributors:** `CLAUDE.md`.
- **Evaluation corpus:** built locally from public datasets (`scripts/build_corpus.py`, decision 0004).
