"""M6-4: the full pipeline, offline and with networking blocked, opens no socket, looks up no host
and starts no process. Only a model download goes online (design §12, docs/privacy.md).

Every stage runs for real: ADTOF detection and Beat This! tracking on stand-in ONNX models that
are installed under the real models' names, then quantize, render, the report and the plot.
"""

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import soundfile as sf
from test_beats import clicks, stand_in_tracker
from test_model import stand_in_model
from typer.testing import CliRunner

from drumtx import beats, models
from drumtx.cli import app
from drumtx.errors import MissingDependencyError
from drumtx.ingest import SAMPLE_RATE

# Audit events for anything that leaves the process: sockets, name lookups, URLs, new processes.
WATCHED = ("socket.", "urllib.", "http.", "ftplib.", "smtplib.", "webbrowser.", "subprocess.") + (
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "os.startfile",
)
seen: list[str] = []
watching = False


def _audit(event: str, args: tuple[object, ...]) -> None:
    if watching and event.startswith(WATCHED):
        seen.append(event)


sys.addaudithook(_audit)  # audit hooks can't be removed, so it records only while `watching`


@pytest.fixture
def watch() -> object:
    global watching
    seen.clear()
    watching = True
    yield seen
    watching = False


def install(model_id: str, path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stand-in model under the real one's name and file, with its own SHA-256 pinned."""
    target = models.cache_dir() / models.spec(model_id).file
    target.parent.mkdir(parents=True, exist_ok=True)
    path.replace(target)
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    monkeypatch.setitem(models.REGISTRY, model_id, replace(models.spec(model_id), sha256=sha))


@pytest.mark.real_tracker
def test_full_pipeline_offline_stays_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, watch: list[str]
) -> None:
    y = clicks(8.0)
    wav = tmp_path / "groove.wav"
    sf.write(wav, y, SAMPLE_RATE)
    level = beats.log_mel(y).mean(axis=1)
    stand_in_tracker(tmp_path / "bt.onnx", quiet=level[25], loud=level[0])
    install("beat-this-final0", tmp_path / "bt.onnx", monkeypatch)
    stand_in_model(tmp_path / "adtof.onnx")
    install("adtof", tmp_path / "adtof.onnx", monkeypatch)

    out = tmp_path / "out"
    events = out / "groove.events.json"
    commands = [
        ["transcribe", str(wav), "-o", str(out), "--offline", "--plot"],
        ["render", str(events), "--first-downbeat", "0.5", "--plot"],
        ["preview", str(wav), str(events), "--split-stereo"],
        ["evaluate", "--pred", str(events), "--ref", str(out / "groove.events.csv")],
        ["models", "list"],
    ]
    for args in commands:
        result = CliRunner().invoke(app, args)
        assert result.exit_code == 0, (args, result.output)
    assert "6/6] Report" in CliRunner().invoke(app, [*commands[0], "--force"]).stderr
    assert (out / "groove.musicxml").exists() and (out / "groove.plot.png").exists()
    assert seen == []  # no socket, name lookup, URL or subprocess at all


def test_the_audit_hook_sees_a_download(watch: list[str]) -> None:
    """The control: a model download does show up, so an empty list above means something."""
    with pytest.raises(MissingDependencyError, match="could not be downloaded"):
        models.get_model("adtof", offline=False)  # conftest blocks the connection itself
    assert "urllib.Request" in seen


def test_the_audit_hook_sees_a_subprocess(watch: list[str]) -> None:
    import subprocess

    subprocess.run([sys.executable, "-c", "pass"], check=True)
    assert "subprocess.Popen" in seen


def test_no_telemetry_dependencies() -> None:
    """No package that phones home: no analytics or crash-reporting SDK anywhere in the lock."""
    lock = (Path(__file__).parents[1] / "uv.lock").read_text(encoding="utf-8")
    names = {line.split('"')[1] for line in lock.splitlines() if line.startswith("name = ")}
    for sdk in ("sentry-sdk", "posthog", "mixpanel", "segment-analytics-python", "rollbar"):
        assert sdk not in names
