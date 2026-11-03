"""M1-1: audio ingest."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from drumtx import ingest
from drumtx.errors import InputError, MissingDependencyError
from drumtx.ingest import SAMPLE_RATE, load_audio

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="FFmpeg not installed")


def write(path: Path, seconds: float = 3.0, rate: int = 48_000, click_s: float = 1.0) -> Path:
    """A quiet stereo noise floor with a click at `click_s`."""
    audio = np.random.default_rng(0).normal(0, 0.01, (round(seconds * rate), 2))
    audio[round(click_s * rate)] = 0.9
    sf.write(path, audio.astype(np.float32), rate)
    return path


def click_time(buf: ingest.AudioBuffer) -> float:
    """Source-file time of the loudest sample."""
    return buf.start_s + int(np.argmax(np.abs(buf.mono))) / SAMPLE_RATE


@pytest.fixture
def no_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)


@pytest.mark.parametrize("suffix", [".wav", ".flac", ".aiff", ".mp3", ".ogg"])
def test_formats_decode(tmp_path: Path, suffix: str) -> None:
    buf = load_audio(write(tmp_path / f"in{suffix}"))
    assert buf.samples.dtype == np.float32 and buf.samples.shape[1] == 2
    assert buf.mono.shape == (len(buf.samples),)
    assert buf.duration_s == pytest.approx(3.0, abs=0.1)  # lossy codecs pad a little
    assert buf.start_s == 0 and buf.source_duration_s == pytest.approx(3.0, abs=0.1)
    if suffix in (".wav", ".flac", ".aiff"):
        assert click_time(buf) == pytest.approx(1.0, abs=2 / SAMPLE_RATE)


def test_excerpt_keeps_source_time(tmp_path: Path) -> None:
    buf = load_audio(write(tmp_path / "in.wav", seconds=5, click_s=2.0), start=1.0, end=3.5)
    assert buf.start_s == 1.0 and buf.source_duration_s == 5.0
    assert buf.duration_s == pytest.approx(2.5, abs=1 / SAMPLE_RATE)
    assert click_time(buf) == pytest.approx(2.0, abs=2 / SAMPLE_RATE)


def test_non_ascii_path(tmp_path: Path) -> None:
    assert load_audio(write(tmp_path / "ドラム é.wav")).duration_s == pytest.approx(3.0)


@pytest.mark.parametrize(
    ("seconds", "kwargs"),
    [
        (1.5, {}),  # under 2 s
        (5.0, {"start": 1.0, "end": 2.5}),  # excerpt under 2 s
        (5.0, {"max_duration": 4.0}),  # over the limit
        (5.0, {"start": -1.0}),
        (5.0, {"start": 5.0}),
        (5.0, {"end": 6.0}),
        (5.0, {"start": 3.0, "end": 2.0}),
    ],
)
def test_limits(tmp_path: Path, seconds: float, kwargs: dict[str, float]) -> None:
    with pytest.raises(InputError) as e:
        load_audio(write(tmp_path / "in.wav", seconds=seconds, click_s=0.5), **kwargs)
    assert e.value.exit_code == 2


def test_max_duration_can_be_raised(tmp_path: Path) -> None:
    assert ingest.DEFAULT_MAX_DURATION_S == 600
    path = write(tmp_path / "in.wav", seconds=5)
    assert load_audio(path, max_duration=5.0).duration_s == pytest.approx(5.0)


def test_size_cap_checked_before_decoding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "MAX_FILE_BYTES", 100)
    path = tmp_path / "big.wav"
    path.write_bytes(b"\0" * 101)  # not audio: the size check must come first
    with pytest.raises(InputError, match="limit is 2 GB"):
        load_audio(path)


@pytest.mark.parametrize("name", ["nope.wav", "."])
def test_unreadable_path(tmp_path: Path, name: str) -> None:
    with pytest.raises(InputError, match="Cannot read"):
        load_audio(tmp_path / name)


@pytest.mark.parametrize("ffmpeg", [False, pytest.param(True, marks=needs_ffmpeg)])
def test_corrupt_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ffmpeg: bool) -> None:
    if not ffmpeg:
        monkeypatch.setattr(shutil, "which", lambda _: None)
    path = tmp_path / "bad.wav"
    path.write_bytes(b"RIFF" + bytes(range(256)) * 40)
    with pytest.raises(InputError, match="Cannot decode bad.wav"):
        load_audio(path)


@needs_ffmpeg
def test_unsupported_file_with_ffmpeg(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("not audio\n" * 100)
    with pytest.raises(InputError, match="Cannot decode notes.txt"):
        load_audio(path)


@pytest.mark.usefixtures("no_ffmpeg")
def test_m4a_without_ffmpeg(tmp_path: Path) -> None:
    path = tmp_path / "song.m4a"
    path.write_bytes(b"\0\0\0\x20ftypM4A " + bytes(4000))
    with pytest.raises(MissingDependencyError, match="Install FFmpeg") as e:
        load_audio(path)
    assert e.value.exit_code == 3


@needs_ffmpeg
def test_m4a_through_ffmpeg(tmp_path: Path) -> None:
    wav = write(tmp_path / "src.wav", seconds=5, click_s=2.0)
    m4a = tmp_path / "ドラム.m4a"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(wav), "-c:a", "aac", str(m4a)]
    subprocess.run(cmd, check=True)
    buf = load_audio(m4a, start=1.0, end=4.0)
    assert buf.start_s == 1.0 and buf.source_duration_s == pytest.approx(5.0, abs=0.1)
    assert buf.samples.shape[1] == 2 and buf.duration_s == pytest.approx(3.0, abs=0.05)
    assert click_time(buf) == pytest.approx(2.0, abs=0.005)
