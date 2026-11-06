# DrumTx: working notes for Claude Code

DrumTx is a personal command-line tool. It turns drum audio into MusicXML, MIDI, `events.json`/`events.csv` and a review report. Everything about it is planned in `docs/`:

| File | What it holds |
|---|---|
| `docs/project-brief.md` | Goals, scope and targets |
| `docs/technical-design.md` | Architecture, CLI and file formats |
| `docs/milestone-tasks.md` | Every task, with acceptance criteria and dependencies |
| `docs/decisions/` | One record per decision (0001–0013). Read the ones a task depends on. |
| `docs/schema/events-v1.md` | The `events.json`/`events.csv` and mapping formats |
| `docs/accuracy.md` | User-facing accuracy |
| `docs/compatibility.md` | Notation apps checked, and the MuseScore check script |
| `docs/models/` | Model cards |

## Status (2026-11-05)

- **Done and merged:** M0 to M5-4, through PR #40.
- **In review: M5-5, the correction guide** (`docs/correction-guide.md`, `scripts/make_guide_sample.py`). Then M5-6 (stretch) or M6-1, in the order of `docs/milestone-tasks.md`.

**Open items carried forward:**
- **Correction guide on your own recording** (M5-5): the owner follows `docs/correction-guide.md` end to end on one of their own recordings, using only its steps, and adds a row to its "Walk-throughs" table. The guide's example is a generated recording, so it can be committed.
- **Drummer review of the notation checklist** (M4-2): by the owner, if a drummer is available. Record it at the end of `docs/notation-checklist.md`.
- **MuseScore 4 check:** open `tests/golden/triplet.musicxml` once in MuseScore 4, and a file written with `--mark-uncertain` to see the red notes. Record it in `docs/compatibility.md`.
- **DAW check for the MIDI file** (M3-4): manual, by the owner. Steps and the place to record the result are in decision 0011.
- **Long silences** (M4-4): around a 20 s silence, Beat This! adds spurious half-beats, so bar numbers after it are wrong (decision 0007). No task is planned for it.
- **Nightly CI benchmark:** it converts the beat model and ADTOF on every run, because the models aren't cached. It also runs the MuseScore check (`scripts/check_musescore.py`, M4-5).

**What the M4 tasks build on:**
- **Spike and MuseScore check:** decision 0007 (M0-6). The spike's output is `spikes/m0-6/groove_custom.musicxml`.
- **Mapping:** `drumtx.mapping.load()` returns, per class, the name, MIDI note, `display` (staff step and octave), notehead and voice.
- **Score data:** `QuantizedScore` comes from `quantize.quantize` plus `review.flag`.
- **Where to write it:** the render stage in `pipeline.py` writes the outputs, through `render.write_outputs`.
- **XSD validation:** the MusicXML 4.0 XSD isn't in the repo. `scripts/fetch_musicxml_xsd.py` downloads `musicxml.xsd`, `xml.xsd` and `xlink.xsd` from <https://github.com/w3c/musicxml/tree/v4.0/schema>, SHA-256 checked.

## How each task is done

1. **Branch:** start from the latest `main`, on the branch the session names: `git fetch origin main && git checkout -B <branch> origin/main`. Do one task per branch.
2. **Read** the task's acceptance criteria and its dependencies' decisions.
3. **Smallest complete change.** Tests are required for new logic. Run the checks before every commit.
4. **Real data:** where the task touches accuracy, check against real data (the corpus below) and record the numbers in the docs or a decision record.
5. **Update the docs** that the change affects: design, schema doc, accuracy and decisions.
6. **Commit, push and open a PR** at the end of every task. This is a standing request. Then ask whether to watch the PR.
7. **Wait for the owner** to say "PR has merged, proceed to <next task>". Don't start the next task before that.

Put no model IDs in commits or PRs.

## Commands

```bash
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
for p in linux darwin win32; do uv run mypy --platform $p src tests scripts; done
uv run --python 3.11 pytest -q
```

- **CI runs** Linux, macOS and Windows, with Python 3.11 and 3.13.
- **Why the per-platform mypy loop:** mypy has failed only on macOS before, from platform branches in `models.py`. If mypy acts strangely, run `rm -rf .mypy_cache`.
- **Golden files** (`tests/golden/`) are compared byte for byte. After a deliberate change, regenerate them with `DRUMTX_UPDATE_GOLDEN=1 uv run pytest tests/test_midi.py tests/test_musicxml.py` and review the diff.
- **MusicXML tests** need the XSD: run `uv run python scripts/fetch_musicxml_xsd.py <dir>` once and set `DRUMTX_MUSICXML_XSD=<dir>`. Without it they skip, except in CI.
- **Running the CLI:** use `uv run drumtx …`. `python -m drumtx.cli` does nothing, because there is no `__main__`.

## How the code fits together

**The pipeline** (`pipeline.py`) runs these stages: ingest → (separate) → detect → track → quantize → render. The cache is in `<out>/.drumtx-cache/`.
- **Cached:** separate, detect and track.
- **Not cached:** ingest, and quantize, which takes milliseconds and also builds the tempo map and applies the review flags.

| Module | Role |
|---|---|
| `detect.py` | ADTOF model (the default) or the classical baseline. The presets are in `presets/adtof.json`. |
| `beats.py` | Beat This! tracker and `tempo_map` |
| `quantize.py` | Grid per beat, merges, residuals |
| `review.py` | Flags and their thresholds; the review report |
| `midi.py` | MIDI writer (decision 0011) |
| `musicxml.py` | MusicXML writer (decision 0007) |
| `mapping.py` | Instrument mapping (`mapping.toml`) |
| `evaluate.py` | Onset, beat and grid metrics |
| `models.py` | Model registry |

**Models** are downloaded and converted on first use to ONNX or safetensors, with the SHA-256 verified, in a throwaway uv environment. They go to `~/.cache/drumtx/models`; `DRUMTX_CACHE_DIR` overrides that. To install them ahead of time, run `uv run drumtx models download <id>` for `adtof`, `beat-this-final0` and `umxl-drums`.

**Tests** (`tests/conftest.py`):
- **Network blocked:** tests can't reach the network, and `DRUMTX_CACHE_DIR` points to a temporary folder.
- **Stand-in tracker:** `pipeline.track_beats` is replaced by a stand-in with beats every 0.5 s and downbeats every 2 s. A test marked `real_tracker` opts out.
- **Stand-in models:** they are built with `onnx.helper`.

## Evaluation data (not in the repo)

The corpus lives in `~/drumtx-data`, outside the repo. A new cloud session starts without it, and without the models.
- **To rebuild it,** follow `.github/workflows/benchmark.yml`:
  1. Clone MDB Drums.
  2. Download IDMT-SMT-Drums V2 and check its SHA-256.
  3. Run `uv run python scripts/build_corpus.py ~/drumtx-data --fetch-egmd`.
- **Check:** afterwards, `git diff eval/` must be empty.
- **What's in it:** `eval/dev.csv` and `eval/test.csv` are the frozen manifests. Reference onsets, beats (`.beats.csv`) and scores (`.score.csv`) end up in `~/drumtx-data/corpus/`.

**Benchmark:**
- **Dev run:** `uv run python scripts/benchmark.py --model adtof --compare eval/results/adtof-dev.json`.
- **Test set:** only with `--release`, for M2-7 and M7-4 (decision 0004).
- **Flag thresholds:** `uv run python scripts/tune_flags.py` (decision 0013). It caches detections and beats in `~/drumtx-data/flags-cache.json`.

## Rules that must hold

- **No third-party data or weights in the repo.** This is personal use only (decisions 0001 and 0003).
- **No pickle at runtime.** Models are ONNX or safetensors with a verified SHA-256 (design §12). Converters run in throwaway uv environments, never in the drumtx environment.
- **Untrusted downloads:**
  - Keep downloaded or cloned third-party code and data in their own directories.
  - Read them, but don't run their code from inside those directories.
  - Run Python that reads them with `-I`.
  - Don't install packages from git sources.
- **Never overwrite user files:** `transcribe` must not overwrite outputs without `--force`, and never an `events.csv` the user has edited.
- **Exit codes:**

  | Code | Meaning | Raised by |
  |---|---|---|
  | 0 | OK | |
  | 1 | Unexpected error | |
  | 2 | Input error | `InputError` |
  | 3 | Missing dependency or model | `MissingDependencyError` |
  | 4 | Processing failure | `ProcessingError` |
