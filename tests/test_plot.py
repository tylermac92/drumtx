"""M5-6: --plot writes a PNG of the hits over time, with flagged measures shaded."""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from matplotlib.image import imread
from typer.testing import CliRunner

from drumtx import review
from drumtx.cli import app
from drumtx.ingest import SAMPLE_RATE
from drumtx.synth import render

runner = CliRunner()


@pytest.fixture
def wav(tmp_path: Path) -> Path:
    path = tmp_path / "in.wav"
    sf.write(
        path,
        render([(1.0, "kick", 100), (1.5, "snare", 100), (2.5, "hihat", 90)], 4.0),
        SAMPLE_RATE,
    )
    return path


def colors(png: Path) -> tuple[int, int]:
    """Pixels of the uncertain red, and of the orange shading over white."""
    rgb = imread(png)[..., :3]
    red = np.all(np.abs(rgb - [0xE0 / 255, 0, 0]) < 0.1, axis=-1).sum()
    shade = np.all(np.abs(rgb - [1.0, 0.875, 0.75]) < 0.05, axis=-1).sum()
    return int(red), int(shade)


def test_plot_shows_flags(wav: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "out"
    args = ["transcribe", str(wav), "-o", str(out), "--model", "baseline", "--plot"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stderr
    assert "in.report.md, in.plot.png: 0 measures flagged" in result.stderr
    png = out / "in.plot.png"
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    red0, shade0 = colors(png)  # nothing flagged: only the legend's swatches
    assert red0 < 500 and shade0 < 500

    flag = review.flag  # every hit uncertain, so measure 1 is flagged
    monkeypatch.setattr(review, "flag", lambda s: flag(s, review.Thresholds(1.01)))
    assert runner.invoke(app, [*args, "--force", "-q"]).exit_code == 0
    red, shade = colors(png)
    assert red > red0 + 50 and shade > shade0 + 10_000


def test_render_plot(wav: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert (
        runner.invoke(
            app, ["transcribe", str(wav), "-o", str(out), "-q", "--model", "baseline"]
        ).exit_code
        == 0
    )
    assert not (out / "in.plot.png").exists()
    result = runner.invoke(app, ["render", str(out / "in.events.json"), "--plot"])
    assert result.exit_code == 0 and "in.plot.png" in result.stderr
    assert (out / "in.plot.png").exists()


def test_without_the_extra(wav: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "matplotlib", None)  # import fails as if not installed
    out = tmp_path / "out"
    result = runner.invoke(
        app, ["transcribe", str(wav), "-o", str(out), "--model", "baseline", "--plot"]
    )
    assert result.exit_code == 3
    assert "--plot needs the plot extra" in result.stderr
    assert f'"{sys.executable}" -m pip install "matplotlib>=3.8"' in result.stderr
    assert not out.exists()  # it failed before any work
    result = runner.invoke(app, ["render", str(out / "in.events.json"), "--plot"])
    assert result.exit_code == 3 and "plot extra" in result.stderr
