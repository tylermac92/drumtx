"""Errors that end a run with a specific exit code (Technical Design Document §4)."""

import sys
from importlib.metadata import requires
from pathlib import Path


class DrumtxError(Exception):
    """An expected failure: the CLI prints the message and exits with `exit_code`."""

    exit_code = 1


class InputError(DrumtxError):
    """Bad option or input file: unreadable, unsupported, too long or too short."""

    exit_code = 2


class MissingDependencyError(DrumtxError):
    """FFmpeg, an optional extra, or a model while offline is missing."""

    exit_code = 3


def install_hint(extra: str) -> str:
    """The exact command that adds an optional extra (`separation`, `plot`) to this installation."""
    marker = f"extra == '{extra}'"  # metadata may quote it either way
    reqs = [
        r.split(";")[0].strip() for r in requires("drumtx") or [] if marker in r.replace('"', "'")
    ]
    specs = " ".join(f'"{r}"' for r in reqs)
    if "pipx" in Path(sys.prefix).parts:
        return f"pipx inject drumtx {specs}"
    return f'"{sys.executable}" -m pip install {specs}'


class ProcessingError(DrumtxError):
    """Processing failed, e.g. a model file failed its SHA-256 check or could not be converted."""

    exit_code = 4
