"""Errors that end a run with a specific exit code (Technical Design Document §4)."""


class DrumtxError(Exception):
    """An expected failure: the CLI prints the message and exits with `exit_code`."""

    exit_code = 1


class InputError(DrumtxError):
    """Bad option or input file: unreadable, unsupported, too long or too short."""

    exit_code = 2


class MissingDependencyError(DrumtxError):
    """FFmpeg, an optional extra, or a model while offline is missing."""

    exit_code = 3


class ProcessingError(DrumtxError):
    """Processing failed, e.g. a model file failed its SHA-256 check or could not be converted."""

    exit_code = 4
