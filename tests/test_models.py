"""M2-5: model registry, download, verification, --model and --offline (all without network)."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from test_beats import stand_in_tracker
from test_model import stand_in_model
from typer.testing import CliRunner

from drumtx import models
from drumtx.cli import app
from drumtx.errors import MissingDependencyError, ProcessingError
from drumtx.ingest import SAMPLE_RATE

runner = CliRunner()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def wav(tmp_path: Path) -> Path:
    path = tmp_path / "in.wav"
    y = np.zeros(3 * SAMPLE_RATE, np.float32)
    y[SAMPLE_RATE] = 1.0
    sf.write(path, y, SAMPLE_RATE)
    return path


@pytest.fixture
def upstream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> models.Model:
    """`adtof` re-pointed at a local folder; its "conversion" copies a stand-in ONNX model."""
    src = tmp_path / "upstream"
    src.mkdir()
    (src / "weights.bin").write_bytes(b"checkpoint")
    stand_in_model(tmp_path / "stand_in.onnx")

    def convert(folder: Path) -> None:
        (folder / "model.onnx").write_bytes((tmp_path / "stand_in.onnx").read_bytes())

    m = models.Model(
        id="adtof",
        version="test",
        license="test",
        url=src.as_uri() + "/",
        sources={"weights.bin": sha(src / "weights.bin")},
        file="model.onnx",
        sha256=sha(tmp_path / "stand_in.onnx"),
        convert=convert,
    )
    monkeypatch.setitem(models.REGISTRY, "adtof", m)
    return m


def transcribe(wav: Path, *extra: str) -> tuple[int, str]:
    result = runner.invoke(app, ["transcribe", str(wav), "-o", str(wav.parent / "out"), *extra])
    return result.exit_code, result.stderr


def test_registry_loads_only_onnx_or_safetensors() -> None:
    assert models.DEFAULT in models.REGISTRY
    assert all(Path(m.file).suffix in models.LOADABLE for m in models.REGISTRY.values())


def test_other_formats_are_refused(upstream: models.Model, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(models.REGISTRY, "adtof", replace(upstream, file="model.pkl"))
    with pytest.raises(ProcessingError, match="only ONNX or safetensors"):
        models.get_model("adtof", offline=False)


@pytest.mark.real_tracker
def test_baseline_offline_needs_only_the_beat_tracker(
    wav: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--model baseline needs no detection model, but beat tracking (M3-1) needs its model."""
    code, err = transcribe(wav, "--model", "baseline", "--offline")
    assert code == 3 and "Model beat-this-final0 is not installed" in err
    stand_in_tracker(tmp_path / "bt.onnx", quiet=1.0, loud=2.0)
    tracker = replace(models.spec("beat-this-final0"), sha256=sha(tmp_path / "bt.onnx"))
    monkeypatch.setitem(models.REGISTRY, "beat-this-final0", tracker)
    models.cache_dir().mkdir(parents=True)
    (models.cache_dir() / tracker.file).write_bytes((tmp_path / "bt.onnx").read_bytes())
    assert transcribe(wav, "--model", "baseline", "--offline", "-q") == (0, "")
    assert [p.name for p in models.cache_dir().iterdir()] == [tracker.file]  # nothing downloaded


def test_offline_without_the_model_exits_3(wav: Path) -> None:
    code, err = transcribe(wav, "--offline")
    assert code == 3 and "--offline forbids downloading it" in err


def test_unknown_model_exits_2(wav: Path) -> None:
    code, err = transcribe(wav, "--model", "nope")
    assert code == 2 and "Available: baseline, adtof" in err


def test_download_then_offline(wav: Path, upstream: models.Model) -> None:
    result = runner.invoke(app, ["models", "download"])
    assert result.exit_code == 0, result.stderr
    assert (models.cache_dir() / "model.onnx").exists()
    assert not [p for p in models.cache_dir().iterdir() if p.name != "model.onnx"]  # no leftovers
    assert transcribe(wav, "--offline", "-q") == (0, "")
    doc = json.loads((wav.parent / "out" / "in.events.json").read_text())
    assert doc["models"]["detector"] == "adtof"
    assert [(e["time_s"], e["class"]) for e in doc["events"]] == [(1.0, "tom")]


def test_first_use_downloads(wav: Path, upstream: models.Model) -> None:
    assert transcribe(wav, "-q")[0] == 0
    assert (models.cache_dir() / "model.onnx").exists()


def test_tampered_model_is_rejected_with_exit_4(wav: Path, upstream: models.Model) -> None:
    models.download(upstream)
    path = models.cache_dir() / "model.onnx"
    path.write_bytes(path.read_bytes()[:-1] + b"\0")
    code, err = transcribe(wav, "--offline")
    assert code == 4 and "does not match its pinned SHA-256" in err
    # `models download` replaces the bad file.
    assert runner.invoke(app, ["models", "download"]).exit_code == 0
    assert sha(path) == upstream.sha256


def test_tampered_download_is_rejected(tmp_path: Path, upstream: models.Model) -> None:
    (tmp_path / "upstream" / "weights.bin").write_bytes(b"something else")
    with pytest.raises(ProcessingError, match="pinned SHA-256"):
        models.download(upstream)
    assert not (models.cache_dir() / "model.onnx").exists()


def test_bad_conversion_is_rejected(
    upstream: models.Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    def convert(folder: Path) -> None:
        (folder / "model.onnx").write_bytes(b"not the pinned model")

    monkeypatch.setitem(models.REGISTRY, "adtof", replace(upstream, convert=convert))
    with pytest.raises(ProcessingError):
        models.get_model("adtof", offline=False)
    assert not (models.cache_dir() / "model.onnx").exists()


def test_unreachable_source_exits_3(upstream: models.Model) -> None:
    with pytest.raises(MissingDependencyError, match="could not be downloaded"):
        models.download(replace(upstream, url="https://example.invalid/"))


def test_models_list(upstream: models.Model) -> None:
    out = runner.invoke(app, ["models", "list"]).stdout
    assert "baseline" in out and "adtof (default)" in out and "not installed" in out
    models.download(upstream)
    assert str(models.cache_dir()) in out
    rows = runner.invoke(app, ["models", "list"]).stdout.splitlines()
    assert "not installed" not in next(r for r in rows if r.startswith("adtof"))
