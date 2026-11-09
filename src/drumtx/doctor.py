"""`drumtx doctor` (M6-5): what this installation can do, and what to install for the rest.

Each line is a component, a status, and for anything missing, the command that fixes it. Nothing
is downloaded. Extras are looked up without importing them, except PyTorch, which is imported
to ask whether it sees a CUDA GPU.
"""

import importlib.util
import os
import platform
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError, version

import soundfile as sf

from drumtx import models
from drumtx.errors import DrumtxError, install_hint
from drumtx.ingest import FFMPEG_HINT

EXTRAS = {"separation": ("openunmix", "torch", "safetensors"), "plot": ("matplotlib",)}
USE = {"separation": "--separate", "plot": "--plot"}


def _version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def _native() -> list[str]:
    """The common formats this libsndfile reads (MP3 needs libsndfile 1.1 or later)."""
    return [f for f in ("WAV", "FLAC", "OGG", "MP3", "AIFF") if f in sf.available_formats()]


def _ffmpeg() -> str:
    found = [shutil.which(tool) for tool in ("ffmpeg", "ffprobe")]
    if not all(found):
        return f"not found: M4A/AAC and other formats libsndfile can't read need it. {FFMPEG_HINT}"
    run = subprocess.run([found[0] or "ffmpeg", "-version"], capture_output=True, text=True)
    first = (run.stdout.splitlines() or ["ffmpeg"])[0]
    return f"{' '.join(first.split()[:3])} ({found[0]})"


def _extra(name: str) -> str:
    missing = [m for m in EXTRAS[name] if importlib.util.find_spec(m) is None]
    if missing:
        return f"not installed ({USE[name]} needs it). Install: {install_hint(name)}"
    packages = ", ".join(f"{m} {_version(m)}" for m in EXTRAS[name])
    return f"installed ({packages})"


def _model(model_id: str) -> str:
    path = models.cache_dir() / models.spec(model_id).file
    if not path.exists():
        return f"not installed; downloaded on first use, or: drumtx models download {model_id}"
    try:
        models.get_model(model_id, offline=True)  # checks the SHA-256
    except DrumtxError as e:
        return f"damaged: {e}"
    return f"installed, SHA-256 OK ({path})"


def _device() -> str:
    cpu = f"CPU, {os.cpu_count()} logical cores"
    if importlib.util.find_spec("torch") is None:
        return f"{cpu}. CUDA (--separate --device cuda) needs the separation extra"
    import torch

    if torch.cuda.is_available():
        return f"{cpu}; CUDA GPU for --separate: {torch.cuda.get_device_name(0)}"
    return f"{cpu}; no CUDA GPU (--separate runs on the CPU)"


def report() -> list[tuple[str, str]]:
    """(component, status) lines, in display order."""
    impl = platform.python_implementation()
    lines = [
        ("drumtx", _version("drumtx") or "unknown"),
        ("Python", f"{platform.python_version()} ({impl}, {platform.platform()})"),
        ("Decoder", f"libsndfile {sf.__libsndfile_version__}: {', '.join(_native())}"),
        ("FFmpeg", _ffmpeg()),
        ("ONNX Runtime", f"{_version('onnxruntime')} (CPU)"),
    ]
    lines += [(f"Extra [{name}]", _extra(name)) for name in EXTRAS]
    lines += [(f"Model {m}", _model(m)) for m in models.REGISTRY]
    lines += [("Model folder", str(models.cache_dir())), ("Device", _device())]
    return lines
