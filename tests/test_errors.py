"""M6-2: every exit code in the documented table, its message, and no traceback without -v."""

import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import onnxruntime as ort
import pytest
import soundfile as sf
from typer.testing import CliRunner

from drumtx import detect, ingest, models, separate
from drumtx.cli import app
from drumtx.errors import InputError, MissingDependencyError, ProcessingError
from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import read_events_csv
from drumtx.synth import render

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "docs" / "schema" / "examples"
runner = CliRunner()


def documented(path: Path) -> set[int]:
    """The codes in a Markdown exit-code table (design §4, or CLAUDE.md's)."""
    text = path.read_text(encoding="utf-8")
    section = text.split("### Exit codes")[1].split("\n## ")[0] if "### Exit" in text else text
    if "**Exit codes:**" in section:
        section = section.split("**Exit codes:**")[1]
    return {int(c) for c in re.findall(r"^\s*\| (\d+) \|", section, re.M)}


@pytest.fixture
def wav(tmp_path: Path) -> Path:
    path = tmp_path / "in.wav"
    sf.write(path, render([(1.0, "kick", 100), (1.5, "snare", 100)], 4.0), SAMPLE_RATE)
    return path


def detector_raises(error: BaseException) -> Callable[[pytest.MonkeyPatch], None]:
    def setup(monkeypatch: pytest.MonkeyPatch) -> None:
        def detect_(*args: object) -> None:
            raise error

        monkeypatch.setattr(detect.BaselineDetector, "detect", detect_)

    return setup


# code -> (set-up, extra arguments for `transcribe IN -o OUT --model baseline`, message)
CASES: dict[int, tuple[Callable[[pytest.MonkeyPatch], None], list[str], str]] = {
    0: (lambda mp: None, [], "Report"),
    1: (detector_raises(ZeroDivisionError("oops")), [], "Unexpected error: ZeroDivisionError"),
    2: (lambda mp: None, ["--start", "9"], "Error: --start 9 is outside in.wav"),
    3: (lambda mp: mp.setitem(sys.modules, "matplotlib", None), ["--plot"], "plot extra"),
    4: (
        detector_raises(ort.capi.onnxruntime_pybind11_state.Fail("bad input")),
        [],
        "Running the model failed: bad input",
    ),
    130: (detector_raises(KeyboardInterrupt()), [], "Interrupted."),
}


def test_the_documented_tables_list_the_tested_codes() -> None:
    assert documented(ROOT / "docs" / "technical-design.md") == set(CASES)
    assert documented(ROOT / "CLAUDE.md") == set(CASES)


@pytest.mark.parametrize("code", sorted(CASES))
def test_exit_code(code: int, wav: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup, extra, message = CASES[code]
    setup(monkeypatch)
    args = ["transcribe", str(wav), "-o", str(tmp_path / "out"), "--model", "baseline", *extra]
    result = runner.invoke(app, args)
    assert result.exit_code == code, result.output
    assert message in result.stderr
    assert "Traceback" not in result.output
    if code in (1, 4):  # -v shows where it happened
        result = runner.invoke(app, [*args, "-v", "--force"])
        assert result.exit_code == code and "Traceback" in result.stderr


def test_memory_error(wav: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    detector_raises(MemoryError())(monkeypatch)
    args = ["transcribe", str(wav), "-o", str(tmp_path / "o"), "-q", "--model", "baseline"]
    result = runner.invoke(app, args)
    assert result.exit_code == 4 and "Out of memory" in result.stderr


def test_output_folder_is_a_file(wav: Path, tmp_path: Path) -> None:
    blocker = tmp_path / "taken"
    blocker.write_text("not a folder")
    result = runner.invoke(app, ["transcribe", str(wav), "-o", str(blocker), "--model", "baseline"])
    assert result.exit_code == 2 and "Cannot read or write" in result.stderr
    assert "taken" in result.stderr and "Traceback" not in result.output


def bad_files(tmp_path: Path) -> dict[str, Path]:
    files = {
        "corrupt.events.json": "{not json",
        "gong.score.csv": "time_s,class,confidence,velocity,measure,beat,grid,slot\n"
        "1.0,gong,1,100,1,1,16th,1\n",
        "header.beats.csv": "seconds,beat\n0.5,1\n",
    }
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return {name: tmp_path / name for name in files}


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ["evaluate", "--pred", "P", "--ref", "R", "--tolerance-ms", "-5"],
            "--tolerance-ms must be positive",
        ),
        (["evaluate", "--pred", "{missing}.events.json", "--ref", "R"], "Cannot read"),
        (
            ["evaluate", "--pred", "{corrupt.events.json}", "--ref", "R"],
            "is not a DrumTx events.json",
        ),
        (
            ["evaluate", "--pred", "{groove}", "--ref", "{ref}", "--ref-score", "{gong.score.csv}"],
            "unknown class 'gong'",
        ),
        (
            [
                "evaluate",
                "--pred",
                "{groove}",
                "--ref",
                "{ref}",
                "--ref-beats",
                "{header.beats.csv}",
            ],
            "the header must be time_s,beat",
        ),
        (
            ["evaluate", "--pred", "{groove}", "--ref", "{ref}", "--ref-beats", "{missing}.csv"],
            "Cannot read beats file",
        ),
        (["render", "{corrupt.events.json}"], "is not a DrumTx events.json"),
        (["render", "{groove}", "--first-downbeat", "-1"], "--first-downbeat must be 0 or more"),
        (["preview", "{wav}", "{missing}.events.json"], "Cannot read"),
        (["preview", "{wav}", "{ref}", "-o", "{missing}/x.wav"], "Cannot read or write"),
    ],
)
def test_input_errors(args: list[str], message: str, wav: Path, tmp_path: Path) -> None:
    paths = {
        **{k: str(v) for k, v in bad_files(tmp_path).items()},
        "missing": str(tmp_path / "missing"),
        "groove": str(EXAMPLES / "groove.events.json"),
        "ref": str(EXAMPLES / "groove.events.csv"),
        "wav": str(wav),
    }
    args = [re.sub(r"\{([^}]+)\}", lambda m: paths[m.group(1)], a) for a in args]
    result = runner.invoke(app, args)
    assert result.exit_code == 2, result.output
    assert message in result.stderr and "Traceback" not in result.output


def test_csv_time_must_be_a_time(tmp_path: Path) -> None:
    path = tmp_path / "e.csv"
    path.write_text("time_s,class,confidence,velocity\nnan,kick,,\n-1,snare,,\n")
    with pytest.raises(
        InputError, match=r"line 2: time_s nan is not a time \(0 to 86400 s\)\n  line 3: time_s -1"
    ):
        read_events_csv(path)


def test_source_duration_of_a_folder(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="Cannot read"):
        ingest.source_duration(tmp_path)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs FFmpeg")
def test_ffmpeg_decode_failure(tmp_path: Path) -> None:
    garbage = tmp_path / "x.m4a"
    garbage.write_bytes(np.random.default_rng(0).bytes(4096))
    with pytest.raises(InputError, match="Cannot decode x.m4a"):
        ingest._ffmpeg_decode(garbage, 1, 0.0, 1.0)


def test_model_conversion_needs_uv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(MissingDependencyError, match="needs uv"):
        models._uv_convert("convert_adtof.py", [])(tmp_path)


def test_model_conversion_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/uv")
    failed = subprocess.CompletedProcess([], 1, stdout="", stderr="no wheel for torch")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: failed)
    with pytest.raises(ProcessingError, match="Converting the model failed:\nno wheel for torch"):
        models._uv_convert("convert_adtof.py", [])(tmp_path)


def test_cuda_without_a_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the extra stubbed out: PyTorch that sees no GPU."""
    torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
    stubs = {
        "torch": torch,
        "openunmix": SimpleNamespace(),
        "openunmix.model": SimpleNamespace(OpenUnmix=None, Separator=None),
        "openunmix.utils": SimpleNamespace(bandwidth_to_max_bin=None),
        "safetensors": SimpleNamespace(),
        "safetensors.torch": SimpleNamespace(load_file=None),
    }
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)
    audio = ingest.AudioBuffer(np.zeros((SAMPLE_RATE, 2), np.float32), 0.0, 1.0)
    with pytest.raises(MissingDependencyError, match="PyTorch sees no CUDA GPU"):
        separate.isolate_drums(audio, offline=True, device="cuda")
