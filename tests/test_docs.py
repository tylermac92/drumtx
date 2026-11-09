"""M6-6: every command in the `bash` blocks of the user documentation runs, in order, and the CLI
reference matches the program.

Each page gets an empty folder with `song.wav` (two minutes of the correction guide's groove) and
stand-in models installed under the real names. Separation is stubbed out (its extra is not in
the test environment). A line that isn't run here must say where it is covered instead.
"""

import hashlib
import os
import re
import shlex
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import make_guide_sample
import pytest
import soundfile as sf
from test_model import stand_in_model
from typer.testing import CliRunner

from drumtx import models, pipeline, separate
from drumtx.cli import app
from drumtx.ingest import SAMPLE_RATE, AudioBuffer
from drumtx.synth import render

ROOT = Path(__file__).parents[1]
PAGES = [
    "README.md",
    "docs/correction-guide.md",
    "docs/troubleshooting.md",
    "docs/privacy.md",
    "docs/accuracy.md",
    "docs/compatibility.md",
    "docs/schema/events-v1.md",
]
COVERED_ELSEWHERE = {
    r"pipx install \.$": "CI: the wheel is installed with pipx and smoke-tested",
    r"uv sync$": "CI: every job",
    r"uv run (ruff|mypy|pytest)\b": "CI: every job",
    r"uv run typer drumtx\.cli utils docs ": "test_cli_reference_is_current",
    r"uv run python scripts/check_musescore\.py ": "the nightly benchmark workflow",
}


def bash_lines(page: str) -> list[str]:
    text = (ROOT / page).read_text(encoding="utf-8")
    blocks = re.findall(r"^```bash\n(.*?)^```", text, re.S | re.M)
    lines = [line.strip() for block in blocks for line in block.splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    groove = make_guide_sample.hits()
    hits = [(t + 20.0 * k, c, v) for k in range(6) for t, c, v in groove]
    sf.write(tmp_path / "song.wav", render(hits, 120.0), SAMPLE_RATE)
    folder = models.cache_dir()
    folder.mkdir(parents=True)
    stand_in_model(folder / models.spec("adtof").file)
    (folder / models.spec("beat-this-final0").file).write_bytes(b"stand-in: tracking is stubbed")
    for model_id in ("adtof", "beat-this-final0"):
        sha = hashlib.sha256((folder / models.spec(model_id).file).read_bytes()).hexdigest()
        monkeypatch.setitem(models.REGISTRY, model_id, replace(models.spec(model_id), sha256=sha))
    monkeypatch.setattr(separate, "check_installed", lambda: None)
    monkeypatch.setattr(
        pipeline,
        "isolate_drums",
        lambda audio, offline, device: AudioBuffer(
            audio.mono[:, None], audio.start_s, audio.source_duration_s
        ),
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("page", PAGES)
def test_documented_commands_run(
    page: str, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = CliRunner()
    for line in bash_lines(page):
        if line.startswith("cd "):
            os.chdir(line[3:])
        elif line.startswith("drumtx "):
            result = runner.invoke(app, shlex.split(line)[1:])
            assert result.exit_code == 0, (
                f"{page}: `{line}` exited {result.exit_code}:\n{result.output}"
            )
        elif line.startswith("uv run python scripts/make_guide_sample.py "):
            monkeypatch.setattr(sys, "argv", shlex.split(line)[3:])
            make_guide_sample.main()
        else:
            assert any(re.match(p, line) for p in COVERED_ELSEWHERE), (
                f"{page}: `{line}` is neither run by this test nor covered elsewhere"
            )


def test_every_page_has_runnable_commands_where_expected() -> None:
    """The pages that teach commands keep doing so in `bash` blocks."""
    for page in ("README.md", "docs/correction-guide.md", "docs/troubleshooting.md"):
        assert sum(line.startswith("drumtx ") for line in bash_lines(page)) >= 2, page


def test_cli_reference_is_current() -> None:
    command = [sys.executable, "-m", "typer", "drumtx.cli", "utils", "docs", "--name", "drumtx"]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
    assert out.returncode == 0, out.stderr
    committed = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    assert out.stdout.strip() == committed.strip(), (
        "docs/cli.md is out of date: uv run typer drumtx.cli utils docs --name drumtx "
        "--output docs/cli.md"
    )
