"""M2-6: --separate. The real separator needs drumtx[separation]; here it is replaced by a fake."""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from typer.testing import CliRunner

from drumtx import pipeline
from drumtx.cli import app
from drumtx.errors import install_hint
from drumtx.ingest import SAMPLE_RATE, AudioBuffer

runner = CliRunner()


@pytest.fixture
def wav(tmp_path: Path) -> Path:
    path = tmp_path / "in.wav"
    sf.write(path, np.zeros((2 * SAMPLE_RATE, 2), np.float32), SAMPLE_RATE)
    return path


def test_missing_extra_gives_the_install_command(
    wav: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "openunmix", None)  # import fails as if not installed
    result = runner.invoke(app, ["transcribe", str(wav), "--separate", "--model", "baseline"])
    assert result.exit_code == 3
    assert f'"{sys.executable}" -m pip install "openunmix' in result.stderr
    monkeypatch.setattr(sys, "prefix", str(Path("/home/me/.local/share/pipx/venvs/drumtx")))
    assert install_hint("separation").startswith('pipx inject drumtx "openunmix')


def test_separator_is_not_a_detection_model(wav: Path) -> None:
    result = runner.invoke(app, ["transcribe", str(wav), "--model", "umxl-drums"])
    assert result.exit_code == 2 and "not a detection model" in result.stderr


def test_stem_is_cached_and_replaces_the_mix(
    wav: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[AudioBuffer] = []

    def fake(audio: AudioBuffer, offline: bool, device: str) -> AudioBuffer:
        calls.append(audio)
        return AudioBuffer(audio.mono[:, None] + 0.5, audio.start_s, audio.source_duration_s)

    monkeypatch.setattr(pipeline, "isolate_drums", fake)
    config = pipeline.Config(input=wav, out_dir=tmp_path / "out", model="baseline", separate=True)
    out = pipeline.run(pipeline.RunContext.create(config))
    assert len(calls) == 1 and calls[0].samples.shape[1] == 2  # the stereo mix goes in
    assert np.all(out["separate"].samples == 0.5)
    assert len(list((tmp_path / "out" / ".drumtx-cache").glob("separate-*.npz"))) == 1

    strict = pipeline.Config(**{**config.__dict__, "sensitivity": "strict"})
    out = pipeline.run(pipeline.RunContext.create(strict))
    assert len(calls) == 1  # detection re-ran on the cached stem
    assert np.all(out["separate"].samples == 0.5) and out["separate"].samples.dtype == np.float32

    plain = pipeline.Config(**{**config.__dict__, "separate": False})
    assert "separate" not in pipeline.run(pipeline.RunContext.create(plain))
