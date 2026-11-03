"""Audio ingest: decode, check limits, select an excerpt, resample (Technical Design Document §3).

soundfile decodes WAV, FLAC, AIFF, MP3 and OGG. Anything else goes through FFmpeg, if it is
installed. Limits are checked from the file header before the audio is decoded.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

from drumtx.errors import InputError, MissingDependencyError

SAMPLE_RATE = 44_100
MAX_FILE_BYTES = 2 * 1024**3
MIN_DURATION_S = 2.0
DEFAULT_MAX_DURATION_S = 600.0
# Formats soundfile decodes itself: a failure on one means a bad file, not a missing FFmpeg.
NATIVE_SUFFIXES = {".wav", ".flac", ".aif", ".aiff", ".mp3", ".ogg", ".oga", ".opus"}
FFMPEG_HINT = (
    "Install FFmpeg (https://ffmpeg.org) and make sure `ffmpeg` and `ffprobe` are on PATH."
)


@dataclass(frozen=True)
class AudioBuffer:
    samples: np.ndarray  # float32, shape (frames, channels), at SAMPLE_RATE
    start_s: float  # source-file time of samples[0]; add it to buffer times to get source times
    source_duration_s: float  # length of the whole source file

    @property
    def mono(self) -> np.ndarray:
        mono: np.ndarray = self.samples.mean(axis=1, dtype=np.float32)
        return mono

    @property
    def duration_s(self) -> float:
        return len(self.samples) / SAMPLE_RATE


def load_audio(
    path: Path,
    start: float | None = None,
    end: float | None = None,
    max_duration: float = DEFAULT_MAX_DURATION_S,
) -> AudioBuffer:
    """Decode `path` from `start` to `end` (seconds in the source file).

    The duration limits apply to the selected audio, so an excerpt of a long file is allowed.
    """
    check_file(path)

    try:
        with path.open("rb") as f, sf.SoundFile(f) as snd:
            rate, duration = snd.samplerate, snd.frames / snd.samplerate
            first, last = _excerpt(path, duration, start, end, max_duration)
            snd.seek(round(first * rate))
            audio = snd.read(round(last * rate) - round(first * rate), "float32", always_2d=True)
    except sf.LibsndfileError as e:
        _require_ffmpeg(path, e)
        rate, duration, channels = _probe(path)
        first, last = _excerpt(path, duration, start, end, max_duration)
        audio = _ffmpeg_decode(path, channels, first, last)
    except OSError as e:  # a directory, or no permission to read
        raise InputError(f"Cannot read {path}: {e.strerror}") from e

    if rate != SAMPLE_RATE:
        audio = soxr.resample(audio, rate, SAMPLE_RATE).astype(np.float32, copy=False)
    return AudioBuffer(np.ascontiguousarray(audio), first, duration)


def source_duration(path: Path) -> float:
    """Length of the whole file in seconds, from its header only."""
    check_file(path)
    try:
        with path.open("rb") as f, sf.SoundFile(f) as snd:
            return float(snd.frames / snd.samplerate)
    except sf.LibsndfileError as e:
        _require_ffmpeg(path, e)
        return _probe(path)[1]
    except OSError as e:
        raise InputError(f"Cannot read {path}: {e.strerror}") from e


def _require_ffmpeg(path: Path, e: sf.LibsndfileError) -> None:
    """soundfile failed: raise unless FFmpeg is there to try instead."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        if path.suffix.lower() in NATIVE_SUFFIXES:
            raise InputError(f"Cannot decode {path.name}: {e.error_string}") from e
        raise MissingDependencyError(
            f"Decoding {path.suffix or 'this file'} needs FFmpeg. {FFMPEG_HINT}"
        ) from e


def check_file(path: Path) -> None:
    """Reject a missing or oversized file before anything reads it."""
    try:
        size = path.stat().st_size
    except OSError as e:
        raise InputError(f"Cannot read {path}: {e.strerror}") from e
    if size > MAX_FILE_BYTES:
        raise InputError(f"{path.name} is {size / 1024**3:.1f} GB; the limit is 2 GB.")


def _excerpt(
    path: Path, duration: float, start: float | None, end: float | None, max_duration: float
) -> tuple[float, float]:
    first = 0.0 if start is None else start
    last = duration if end is None else end
    if first < 0 or first >= duration:
        raise InputError(f"--start {first:g} is outside {path.name} (0–{duration:.2f} s).")
    if last <= first or last > duration:
        raise InputError(
            f"--end {last:g} must be after --start and within {path.name} (0–{duration:.2f} s)."
        )
    length = last - first
    if length < MIN_DURATION_S:
        raise InputError(
            f"The audio is {length:.2f} s long; at least {MIN_DURATION_S:g} s is needed."
        )
    if length > max_duration:
        raise InputError(
            f"The audio is {length / 60:.1f} minutes long; the limit is {max_duration / 60:g}. "
            "Use --start/--end for an excerpt, or raise --max-duration."
        )
    return first, last


def _probe(path: Path) -> tuple[int, float, int]:
    """Sample rate, duration and channel count of the first audio stream, from ffprobe."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-of", "json"]
    cmd += ["-show_entries", "stream=sample_rate,channels:format=duration", str(path)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    try:
        info = json.loads(run.stdout)
        stream = info["streams"][0]
        return (
            int(stream["sample_rate"]),
            float(info["format"]["duration"]),
            int(stream["channels"]),
        )
    except (ValueError, KeyError, IndexError) as e:
        raise InputError(f"Cannot decode {path.name}: not a supported audio file.") from e


def _ffmpeg_decode(path: Path, channels: int, first: float, last: float) -> np.ndarray:
    """Decode at the file's own sample rate, as 32-bit float."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{first}", "-t", f"{last - first}"]
    cmd += ["-i", str(path), "-map", "0:a:0", "-ac", str(channels), "-f", "f32le", "-"]
    run = subprocess.run(cmd, capture_output=True)
    if run.returncode != 0 or not run.stdout:
        lines = run.stderr.decode(errors="replace").strip().splitlines()
        raise InputError(f"Cannot decode {path.name}: {lines[-1] if lines else 'no audio'}")
    return np.frombuffer(run.stdout, np.float32).reshape(-1, channels).copy()
