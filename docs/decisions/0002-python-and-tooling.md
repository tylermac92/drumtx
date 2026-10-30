# 0002 — Python versions and tooling

- **Status:** Accepted, 2026-10-30
- **Task:** M0-1

## Decision

- **Python 3.11–3.13.** `requires-python = ">=3.11"`; CI tests the oldest and newest supported versions (3.11 and 3.13) on Linux, macOS, and Windows. Python 3.14 is added once the audio and ML dependencies chosen in M0-4 and M0-5 support it.
- **uv** manages the environment and the lock file (`uv.lock`); CI installs with `uv sync --locked`.
- **hatchling** builds the package (Technical Design Document §8).
- **ruff** (lint and format), **mypy** in strict mode, and **pytest**.

## Consequences

- Adding a dependency means updating `uv.lock` (`uv lock`) in the same change.
- The CI `pipx install .` step checks M0-1's install criterion on every pull request.
