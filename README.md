# drumtx

Command-line drum transcription from audio to editable notation. A personal project; see `docs/` for the brief, design, and milestone plan. The output formats (`events.json`, `events.csv`, the instrument mapping) are specified in `docs/schema/events-v1.md`.

**Status:** M3 (tempo, quantization and MIDI) is done, and M4 (MusicXML) has started. `drumtx transcribe` writes `events.json`, `events.csv`, a MIDI file and a MusicXML file; `evaluate` and `models` work. `--mark-uncertain` colors doubtful notes red. MusicXML edge cases and compatibility checks (M4-4, M4-5), the review report, `render` and `preview` (M5) are next. Progress notes for contributors are in `CLAUDE.md`.

## Install

Requires Python 3.11–3.13.

```bash
pipx install .
drumtx --help
```

## Develop

Uses [uv](https://docs.astral.sh/uv/) and its lock file (`uv.lock`).

```bash
uv sync
uv run ruff check && uv run ruff format --check
uv run mypy src tests scripts
uv run pytest
```

CI runs these checks plus a `pipx install` smoke test on Linux, macOS, and Windows with Python 3.11 and 3.13.

The evaluation corpus is built locally from public datasets (`scripts/build_corpus.py`); see `docs/decisions/0004-evaluation-corpus.md`.
