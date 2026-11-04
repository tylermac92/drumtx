"""Model registry, download and verification (Technical Design Document §7; M2-5).

Models come from their upstream sources (decision 0001: DrumTx hosts nothing) into a per-user
cache directory. Every downloaded file and every model file DrumTx loads is checked against the
SHA-256 pinned here. Only ONNX or safetensors files are ever loaded.

ADTOF ships as a TensorFlow checkpoint, so "downloading" it also converts it to ONNX once, in a
throwaway environment that uv builds with TensorFlow and PyTorch (`convert_adtof.py`). The
conversion is byte-for-byte reproducible, so its output is checked against a pinned SHA-256 too.
"""

import hashlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from drumtx.errors import InputError, MissingDependencyError, ProcessingError

log = logging.getLogger("drumtx")
BASELINE = "baseline"  # the classical detector: built in, nothing to download
DEFAULT = "adtof"
LOADABLE = (".onnx", ".safetensors")


@dataclass(frozen=True)
class Model:
    id: str
    version: str
    license: str
    url: str  # upstream location of `sources`
    sources: dict[str, str]  # files to download → SHA-256
    file: str  # the file DrumTx loads, in the cache directory
    sha256: str
    convert: Callable[[Path], None] | None = None  # turns `sources` into `file` in one folder


def _convert_adtof(folder: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise MissingDependencyError(
            "Converting the ADTOF model needs uv (https://docs.astral.sh/uv/). Install it, "
            "then run `drumtx models download adtof`."
        )
    if sys.platform == "darwin":  # no CPU-only builds for macOS; the plain ones are CPU-only
        packages, index = ["tensorflow==2.21.0", "torch==2.15.0"], []
    else:
        packages = ["tensorflow-cpu==2.21.0", "torch==2.15.0+cpu"]
        index = ["--index", "https://download.pytorch.org/whl/cpu"]
        index += ["--index-strategy", "unsafe-best-match"]
    packages += ["onnx==1.23.2", "onnxruntime==1.31.1"]
    command = [uv, "run", "--isolated", "--no-project", "--python", "3.12", *index]
    command += [arg for p in packages for arg in ("--with", p)]
    command += ["python", str(Path(__file__).with_name("convert_adtof.py"))]
    command += ["--model-dir", str(folder)]
    log.info(
        "Converting the checkpoint to ONNX (once). uv fetches TensorFlow and PyTorch into its "
        "cache for this, about 1.5 GB; this can take several minutes."
    )
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise ProcessingError(f"Converting the ADTOF model failed:\n{result.stderr[-3000:]}")


_ADTOF_COMMIT = "b3968fb332f69b65ee07c089fc62f436503755db"
REGISTRY = {
    "adtof": Model(
        id="adtof",
        version="Frame_RNN_adtofAll_0",
        license="CC BY-NC-SA 4.0 (personal, non-commercial use)",
        url=f"https://raw.githubusercontent.com/MZehren/ADTOF/{_ADTOF_COMMIT}/adtof/models/",
        sources={
            "Frame_RNN_adtofAll_0.index": (
                "3fe35e421c448c395984168cd3aa1f979def902df784b6766291e55bb9aa069f"
            ),
            "Frame_RNN_adtofAll_0.data-00000-of-00001": (
                "ff611129cb4a4d30722a54251e893341a58a016a40c419ab1e3786fc77a04779"
            ),
        },
        file="frame_rnn_adtof_all_0.onnx",
        sha256="9e2f06a1b3edf1d7943e885ed276c4983d8308bdee39646c0d4da1389c1c7e8d",
        convert=_convert_adtof,
    ),
}


def cache_dir() -> Path:
    """Per-user model directory; DRUMTX_CACHE_DIR overrides the platform default."""
    if env := os.environ.get("DRUMTX_CACHE_DIR"):
        base = Path(env)
    elif sys.platform == "win32":
        base = (
            Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "drumtx/Cache"
        )
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches/drumtx"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "drumtx"
    return base / "models"


def spec(model_id: str) -> Model:
    if model_id not in REGISTRY:
        known = ", ".join([BASELINE, *REGISTRY])
        raise InputError(f"Unknown model {model_id!r}. Available: {known}.")
    return REGISTRY[model_id]


def _verify(path: Path, sha256: str, model_id: str) -> None:
    with path.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != sha256:
            raise ProcessingError(
                f"{path} does not match its pinned SHA-256: it is corrupted or was modified. "
                f"Run `drumtx models download {model_id}` to replace it."
            )


def get_model(model_id: str, offline: bool) -> Path:
    """Path of the verified model file, downloading it first unless `offline`."""
    m = spec(model_id)
    path = cache_dir() / m.file
    if path.suffix not in LOADABLE:
        raise ProcessingError(f"{m.file}: DrumTx loads only ONNX or safetensors files.")
    if not path.exists():
        if offline:
            raise MissingDependencyError(
                f"Model {model_id} is not installed, and --offline forbids downloading it. "
                f"Run `drumtx models download {model_id}` while online, or use --model baseline."
            )
        download(m)
    _verify(path, m.sha256, model_id)
    return path


def download(m: Model) -> Path:
    """Fetch and verify the sources, convert if needed, verify, then move into the cache."""
    log.info("Downloading model %s (%s; license %s)", m.id, m.version, m.license)
    folder = cache_dir()
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        work = Path(tmp)
        for name, sha256 in m.sources.items():
            try:
                urllib.request.urlretrieve(m.url + name, work / name)
            except OSError as e:  # URLError is an OSError
                raise MissingDependencyError(
                    f"Model {m.id} is not installed and could not be downloaded from {m.url}: {e}"
                ) from e
            _verify(work / name, sha256, m.id)
        if m.convert is not None:
            m.convert(work)
        _verify(work / m.file, m.sha256, m.id)
        (work / m.file).replace(folder / m.file)
    log.info("Installed %s", folder / m.file)
    return folder / m.file
