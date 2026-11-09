"""M6-5: `drumtx doctor`, with and without FFmpeg, the extras and the models; and output that a
Windows code page can't show."""

import hashlib
import importlib.util
import platform
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import soundfile as sf
from test_model import stand_in_model
from typer.testing import CliRunner

from drumtx import doctor, models
from drumtx.cli import app
from drumtx.errors import install_hint
from drumtx.ingest import SAMPLE_RATE
from drumtx.synth import render

runner = CliRunner()


def rows() -> dict[str, str]:
    return dict(doctor.report())


def test_doctor_describes_this_machine() -> None:
    """No stubs: what CI's runner on each operating system really has."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    for name in ("drumtx", "Python", "Decoder", "FFmpeg", "Extra [plot]", "Model adtof", "Device"):
        assert name in result.stdout
    r = rows()
    assert r["Python"].startswith(platform.python_version())
    assert "WAV" in r["Decoder"] and "FLAC" in r["Decoder"]
    has_ffmpeg = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
    assert r["FFmpeg"].startswith("not found") is not has_ffmpeg
    for extra, modules in doctor.EXTRAS.items():
        installed = all(importlib.util.find_spec(m) for m in modules)
        assert r[f"Extra [{extra}]"].startswith("installed") is installed
    assert all(r[f"Model {m}"].startswith("not installed") for m in models.REGISTRY)  # conftest


def test_without_ffmpeg_and_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    r = rows()
    assert r["FFmpeg"].startswith("not found") and "Install FFmpeg" in r["FFmpeg"]
    assert r["Extra [plot]"] == f"not installed (--plot needs it). Install: {install_hint('plot')}"
    assert '"matplotlib>=3.8"' in r["Extra [plot]"]
    assert r["Extra [separation]"].startswith("not installed (--separate needs it)")
    assert r["Device"].endswith("CUDA (--separate --device cuda) needs the separation extra")


def test_with_ffmpeg_and_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: f"/opt/bin/{name}")
    banner = "ffmpeg version 7.1 Copyright (c) 2000-2024 the FFmpeg developers\n"
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, banner, "")
    )
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: SimpleNamespace(name=name))
    gpu = SimpleNamespace(is_available=lambda: True, get_device_name=lambda i: "RTX 4060")
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=gpu))
    r = rows()
    assert r["FFmpeg"] == "ffmpeg version 7.1 (/opt/bin/ffmpeg)"
    assert r["Extra [plot]"].startswith("installed (matplotlib ")
    assert r["Extra [separation]"].startswith("installed (openunmix ")
    assert r["Device"].endswith("CUDA GPU for --separate: RTX 4060")


def test_models_installed_damaged_or_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = models.cache_dir()
    folder.mkdir(parents=True)
    stand_in_model(folder / models.spec("adtof").file)
    sha = hashlib.sha256((folder / models.spec("adtof").file).read_bytes()).hexdigest()
    monkeypatch.setitem(models.REGISTRY, "adtof", replace(models.spec("adtof"), sha256=sha))
    (folder / models.spec("beat-this-final0").file).write_bytes(b"not a model")
    r = rows()
    assert r["Model adtof"].startswith("installed, SHA-256 OK")
    assert r["Model beat-this-final0"].startswith("damaged:")
    assert "drumtx models download beat-this-final0" in r["Model beat-this-final0"]
    assert r["Model umxl-drums"].startswith("not installed; downloaded on first use")


def test_names_a_windows_code_page_cannot_show(tmp_path: Path) -> None:
    """Under cp1252 (a Windows console that is redirected), a file name outside it is escaped,
    not a crash."""
    wav = tmp_path / "ドラム.wav"
    sf.write(wav, render([(1.0, "kick", 100)], 4.0), SAMPLE_RATE)
    out = tmp_path / "out"
    args = ["transcribe", str(wav), "-o", str(out), "--model", "baseline"]
    cp1252 = CliRunner(charset="cp1252")
    assert cp1252.invoke(app, args).exit_code == 0
    events = out / "ドラム.events.json"
    ref = out / "ドラム.events.csv"
    result = cp1252.invoke(app, ["evaluate", "--pred", str(events), "--ref", str(ref)])
    assert result.exit_code == 0, result.output
    assert "\\u30c9\\u30e9\\u30e0.events.json" in result.stdout
