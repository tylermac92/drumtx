"""M1-2: stage orchestration, the stage cache, progress output and exit codes."""

from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from typer.testing import CliRunner

from drumtx import pipeline
from drumtx.cli import app
from drumtx.pipeline import Config, RunContext, Stage


@dataclass(frozen=True)
class FakeConfig(Config):
    grid: str = "auto"  # stands in for a quantize option until M3-2 adds the real one


def fake_stages(calls: Counter[str]) -> list[Stage]:
    """Ingest, detect, quantize, render, standing in for the real ones; each counts its runs."""

    def stage(name: str, **kw: Any) -> Stage:
        def run(ctx: RunContext, *inputs: Any) -> list[Any]:
            calls[name] += 1
            return [name, *inputs]

        return Stage(name, run=run, summary=lambda ctx, out: "done", **kw)

    return [
        stage("ingest", params=("start", "end"), cached=False),
        stage("detect", deps=("ingest",)),
        stage("quantize", deps=("detect",), params=("grid",)),
        stage("render", deps=("quantize",), cached=False),
    ]


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    path = tmp_path / "in.wav"
    sf.write(path, np.zeros((3 * 8000, 2), np.float32), 8000)
    return path


def runs(config: Config, stages: list[Stage], calls: Counter[str]) -> dict[str, int]:
    calls.clear()
    pipeline.run(RunContext.create(config), stages)
    return dict(calls)


def test_cache_skips_unchanged_stages(audio: Path, tmp_path: Path) -> None:
    calls: Counter[str] = Counter()
    stages = fake_stages(calls)
    config = FakeConfig(input=audio, out_dir=tmp_path / "out")
    everything = {"ingest": 1, "detect": 1, "quantize": 1, "render": 1}

    assert runs(config, stages, calls) == everything
    assert runs(config, stages, calls) == {"render": 1}
    # Only a quantize option changed: ingest and detect are skipped.
    assert runs(replace(config, grid="16th"), stages, calls) == {"quantize": 1, "render": 1}
    assert len(list((tmp_path / "out" / ".drumtx-cache").glob("quantize-*"))) == 1
    # An ingest option changes every key after it.
    assert runs(replace(config, end=2.5), stages, calls) == everything
    assert runs(replace(config, no_cache=True), stages, calls) == everything
    # A different source file has a different hash.
    sf.write(audio, np.ones((3 * 8000, 2), np.float32) * 0.1, 8000)
    assert runs(config, stages, calls) == everything


def test_cached_output_is_passed_on(audio: Path, tmp_path: Path) -> None:
    calls: Counter[str] = Counter()
    config = FakeConfig(input=audio, out_dir=tmp_path / "out")
    first = pipeline.run(RunContext.create(config), fake_stages(calls))
    second = pipeline.run(RunContext.create(replace(config, grid="x")), fake_stages(calls))
    assert second["quantize"][1] == first["detect"]


def test_cache_stays_inside_output_dir(audio: Path, tmp_path: Path) -> None:
    calls: Counter[str] = Counter()
    pipeline.run(
        RunContext.create(FakeConfig(input=audio, out_dir=tmp_path / "out")), fake_stages(calls)
    )
    written = {p for p in tmp_path.rglob("*") if p.is_file()} - {audio}
    assert written and all(p.is_relative_to(tmp_path / "out" / ".drumtx-cache") for p in written)


runner = CliRunner()


def test_transcribe_progress(audio: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["transcribe", str(audio), "--model", "baseline", "-o", str(tmp_path / "out")]
    )
    assert result.exit_code == 0, result.output
    assert "[1/3] Ingest     in.wav  0:03, stereo" in result.stderr
    assert "[2/3] Detect     0 events (kick 0, snare 0, hihat 0, tom 0, cymbal 0)" in result.stderr
    assert "[3/3] Render     in.events.json, in.events.csv" in result.stderr
    assert result.stdout == ""


def test_transcribe_quiet(audio: Path) -> None:
    result = runner.invoke(
        app, ["transcribe", str(audio), "--model", "baseline", "-q", "-o", str(audio.parent)]
    )
    # Warnings still show with -q; a run with nothing detected succeeds (exit code 0).
    assert result.exit_code == 0 and result.stderr == "No drum events detected.\n"


def test_transcribe_input_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["transcribe", str(tmp_path / "missing.wav")])
    assert result.exit_code == 2
    assert "Error: Cannot read" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("verbose", [False, True])
def test_transcribe_unexpected_error(
    audio: Path, monkeypatch: pytest.MonkeyPatch, verbose: bool
) -> None:
    def boom(*args: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "run", boom)
    result = runner.invoke(app, ["transcribe", str(audio), *(["-v"] if verbose else [])])
    assert result.exit_code == 1
    assert "boom" in result.stderr
    assert ("Traceback" in result.stderr) == verbose
    assert ("Run again with -v" in result.stderr) != verbose
