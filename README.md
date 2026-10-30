# drumtx

Command-line drum transcription from audio to editable notation. A personal project; see `docs/` for the brief, design, and milestone plan.

**Status:** M0 (project skeleton). Every command is a stub that exits with "not implemented yet".

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
uv run mypy src tests
uv run pytest
```

CI runs these checks plus a `pipx install` smoke test on Linux, macOS, and Windows with Python 3.11 and 3.13.
