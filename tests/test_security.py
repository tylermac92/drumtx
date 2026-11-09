"""M6-3: the security checklist's automated checks (docs/security-checklist.md), and fuzzing with
corrupt or truncated files: no outcome but exit codes 0, 2 or 4, and never a traceback."""

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from typer.testing import CliRunner

from drumtx import ingest, render
from drumtx.cli import app
from drumtx.errors import InputError
from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import MAX_TIME_S, SCHEMA_FILE
from drumtx.synth import render as synth

SRC = Path(__file__).parents[1] / "src" / "drumtx"
EXAMPLES = Path(__file__).parents[1] / "docs" / "schema" / "examples"
FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
runner = CliRunner()
OK = (0, 2, 4)  # never 1 (a crash) or anything else


def invoke(args: list[str]) -> int:
    result = runner.invoke(app, [*args, "-q"])
    assert "Traceback" not in result.output, result.output
    assert result.exit_code in OK, (args, result.exit_code, result.stderr)
    return result.exit_code


# Static checks over the package source


FORBIDDEN = {
    r"shell\s*=\s*True": "a subprocess through a shell",
    r"\bos\.(system|popen)\(": "a shell command",
    r"^\s*(import pickle|from pickle)": "pickle",
    r"allow_pickle\s*=\s*True": "pickle inside .npy/.npz",
    r"\b(yaml\.load|marshal\.loads?)\(": "a loader that can run code",
    r"(?<![.\w])(eval|exec)\(": "eval or exec",
}


@pytest.mark.parametrize("path", sorted(SRC.glob("*.py")), ids=lambda p: p.name)
def test_no_shell_and_no_code_loading(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for pattern, what in FORBIDDEN.items():
        assert not re.search(pattern, text, re.M), f"{path.name} uses {what}"
    for line in re.findall(r".*torch\.load\(.*", text):  # only in converters, weights only
        assert "weights_only=True" in line, line


def test_schema_limits_match_the_code() -> None:
    text = SCHEMA_FILE.read_text(encoding="utf-8")
    assert set(re.findall(r'"time_s": \{[^}]*"maximum": (\d+)', text)) == {f"{MAX_TIME_S:.0f}"}


# FFmpeg gets a local file only


def test_ffmpeg_input_is_a_local_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    args = ingest._ffmpeg_input(Path("-x.m4a"))
    assert args[:3] == ["-protocol_whitelist", "file", "-i"]
    assert args[3] == f"file:{tmp_path.resolve() / '-x.m4a'}"


@pytest.mark.skipif(not FFMPEG, reason="needs FFmpeg")
def test_ffmpeg_reads_odd_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A relative name that looks like an option still decodes (it used to be read as one)."""
    wav = tmp_path / "x.wav"
    sf.write(wav, synth([(0.5, "kick", 100)], 3.0), SAMPLE_RATE)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), str(tmp_path / "-x.m4a")], check=True)
    monkeypatch.chdir(tmp_path)
    assert ingest.load_audio(Path("-x.m4a")).duration_s == pytest.approx(3.0, abs=0.1)


@pytest.mark.skipif(not FFMPEG, reason="needs FFmpeg")
def test_playlists_cannot_reach_the_network(tmp_path: Path) -> None:
    playlist = tmp_path / "list.m3u8"
    playlist.write_text(
        "#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\nhttp://127.0.0.1:9/a.ts\n#EXT-X-ENDLIST\n"
    )
    with pytest.raises(InputError, match="Cannot decode list.m3u8"):
        ingest.load_audio(playlist)


# Output paths


def test_outputs_never_overwrite_the_source(tmp_path: Path) -> None:
    source = tmp_path / "in.mid"  # WAV audio under a name that an output uses
    sf.write(source, synth([(1.0, "kick", 100)], 3.0), SAMPLE_RATE, format="WAV")
    before = source.read_bytes()
    args = ["transcribe", str(source), "-o", str(tmp_path), "--model", "baseline", "--force"]
    result = runner.invoke(app, args)
    assert result.exit_code == 2 and "would overwrite in.mid itself" in result.stderr
    assert source.read_bytes() == before


def test_preview_never_overwrites_an_input(tmp_path: Path) -> None:
    wav = tmp_path / "in.wav"
    sf.write(wav, synth([(1.0, "kick", 100)], 3.0), SAMPLE_RATE)
    csv = tmp_path / "in.events.csv"
    csv.write_text("time_s,class,confidence,velocity\n1.0,kick,,\n")
    for target in (wav, csv):
        result = runner.invoke(app, ["preview", str(wav), str(csv), "-o", str(target), "--force"])
        assert result.exit_code == 2 and "would overwrite an input" in result.stderr
    assert csv.read_text() == "time_s,class,confidence,velocity\n1.0,kick,,\n"


# Temporary files


def test_atomic_write_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "out.mid"
    target.write_bytes(b"old")

    def interrupted(self: Path, other: Path) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(Path, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        render.write_atomic(target, b"new")
    assert target.read_bytes() == b"old"
    assert [p.name for p in tmp_path.iterdir()] == ["out.mid"]  # no out.mid.tmp left


# Fuzzing


def mutate(data: bytes, seed: int) -> bytes:
    """Truncated, or with bytes overwritten in the header or anywhere."""
    rng = np.random.default_rng(seed)
    if seed % 3 == 0:
        return data[: int(rng.integers(0, len(data)))]
    out = bytearray(data)
    limit = 200 if seed % 3 == 1 else len(out)
    for i in rng.integers(0, min(limit, len(out)), int(rng.integers(1, 40))):
        out[i] = int(rng.integers(0, 256))
    return bytes(out)


@pytest.mark.parametrize("suffix", [".wav", ".flac", ".ogg", ".m4a"])
def test_fuzz_audio(suffix: str, tmp_path: Path) -> None:
    if suffix == ".m4a" and not FFMPEG:
        pytest.skip("needs FFmpeg")
    y = synth([(0.5 + 0.25 * i, ("kick", "snare", "hihat")[i % 3], 100) for i in range(12)], 4.0)
    wav = tmp_path / "base.wav"
    sf.write(wav, y, SAMPLE_RATE)
    base = tmp_path / f"base{suffix}"
    if suffix == ".m4a":
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), str(base)], check=True)
    elif suffix != ".wav":
        sf.write(base, y, SAMPLE_RATE)
    data = base.read_bytes()
    codes = set()
    for seed in range(15):
        bad = tmp_path / f"fuzz{suffix}"
        bad.write_bytes(mutate(data, seed))
        out = ["-o", str(tmp_path / "out"), "--model", "baseline", "--force"]
        codes.add(invoke(["transcribe", str(bad), *out]))
    assert 2 in codes  # some mutations must be caught


def json_paths(o: Any, p: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    found = [p] if p else []
    if isinstance(o, dict):
        found += [x for k, v in o.items() for x in json_paths(v, (*p, k))]
    elif isinstance(o, list):
        found += [x for i, v in enumerate(o[:3]) for x in json_paths(v, (*p, i))]
    return found


def test_fuzz_events_json(tmp_path: Path) -> None:
    """Valid JSON with fields replaced by wrong types or extreme values."""
    base = json.loads((EXAMPLES / "groove.events.json").read_text())
    paths = json_paths(base)
    values: list[Any] = [None, "x", -1, 1e308, [], {}, True, 10**30, 0]
    wav = tmp_path / "groove.wav"
    sf.write(wav, synth([(1.0, "kick", 100)], 5.0), SAMPLE_RATE)
    for seed in range(60):
        rng = np.random.default_rng(seed)
        doc = copy.deepcopy(base)
        target: Any = doc
        p = paths[int(rng.integers(len(paths)))]
        for key in p[:-1]:
            target = target[key]
        target[p[-1]] = values[int(rng.integers(len(values)))]
        path = tmp_path / "groove.events.json"
        path.write_text(json.dumps(doc))
        shutil.copy(EXAMPLES / "groove.events.csv", tmp_path / "groove.events.csv")
        invoke(["render", str(path)])
        invoke(["preview", str(wav), str(path), "--force"])
        invoke(["evaluate", "--pred", str(path), "--ref", str(EXAMPLES / "groove.events.csv")])


def test_fuzz_events_csv(tmp_path: Path) -> None:
    times = ["0", "1.5", "1e300", "inf", "86401", "", "x", "1,5", "-3", "nan"]
    classes = ["kick", "tom", "gong", "", "KICK"]
    numbers = ["", "0.5", "2", "nan", "0", "128", "99999999999999999999", "-5"]
    shutil.copy(EXAMPLES / "groove.events.json", tmp_path / "groove.events.json")
    csv = tmp_path / "groove.events.csv"
    for seed in range(60):
        rng = np.random.default_rng(seed)
        cells = [x[int(rng.integers(len(x)))] for x in (times, classes, numbers, numbers)]
        rows = [",".join(cells)]
        csv.write_text("time_s,class,confidence,velocity\n" + "\n".join(rows * 2) + "\n")
        invoke(["render", str(csv)])


def test_fuzz_bytes(tmp_path: Path) -> None:
    """Random byte damage to every text input: events.json, events.csv and a mapping."""
    files = {
        "groove.events.json": (EXAMPLES / "groove.events.json").read_bytes(),
        "groove.events.csv": (EXAMPLES / "groove.events.csv").read_bytes(),
        "m.toml": b'[kick]\nmidi_note = 35\ndisplay = "F4"\nvoice = 2\n',
    }
    for seed in range(30):
        for name, data in files.items():
            (tmp_path / name).write_bytes(mutate(data, seed))
        invoke(
            ["render", str(tmp_path / "groove.events.csv"), "--mapping", str(tmp_path / "m.toml")]
        )
        invoke(["render", str(tmp_path / "groove.events.json")])


def test_python_reads_nan_but_events_json_does_not(tmp_path: Path) -> None:
    doc = (
        (EXAMPLES / "groove.events.json").read_text().replace('"time_s": 0.496', '"time_s": NaN', 1)
    )
    path = tmp_path / "groove.events.json"
    path.write_text(doc)
    assert "NaN" in doc
    result = runner.invoke(app, ["render", str(path)])
    assert result.exit_code == 2 and "NaN is not a number" in result.stderr
