"""M3-1: beat tracking (Beat This! port, run on a stand-in ONNX model) and the tempo map."""

import json
import logging
from pathlib import Path

import numpy as np
import onnx
import pytest
import soundfile as sf
from onnx import TensorProto, helper
from typer.testing import CliRunner

from drumtx import beats
from drumtx.cli import app
from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import TempoMap

runner = CliRunner()


def clicks(seconds: float, every: float = 0.5, accent: int = 4) -> np.ndarray:
    """Clicks every `every` seconds; every `accent`-th one (from the first) is 4x louder."""
    y = np.zeros(round(seconds * SAMPLE_RATE), np.float32)
    for i, t in enumerate(np.arange(0, seconds - 0.1, every)):
        y[round(t * SAMPLE_RATE)] = 1.0 if i % accent == 0 else 0.25
    return y


def stand_in_tracker(path: Path, quiet: float, loud: float) -> None:
    """Logits from mean log-mel energy: beats above `quiet`, downbeats above the midpoint."""
    w = np.full((128, 2), 1 / 128, np.float32) * 20
    b = np.array([-20 * quiet * 0.5, -20 * (quiet + loud) / 2], np.float32)
    graph = helper.make_graph(
        [
            helper.make_node("MatMul", ["spect", "w"], ["xw"]),
            helper.make_node("Add", ["xw", "b"], ["z"]),
            helper.make_node("Split", ["z"], ["zb", "zd"], axis=2, num_outputs=2),
            helper.make_node("Squeeze", ["zb", "axis"], ["beat"]),
            helper.make_node("Squeeze", ["zd", "axis"], ["downbeat"]),
        ],
        "stand_in",
        [helper.make_tensor_value_info("spect", TensorProto.FLOAT, [1, "frames", 128])],
        [
            helper.make_tensor_value_info("beat", TensorProto.FLOAT, [1, "frames"]),
            helper.make_tensor_value_info("downbeat", TensorProto.FLOAT, [1, "frames"]),
        ],
        [
            onnx.numpy_helper.from_array(w, "w"),
            onnx.numpy_helper.from_array(b, "b"),
            onnx.numpy_helper.from_array(np.array([2], np.int64), "axis"),
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 18)])
    model.ir_version = 8
    onnx.save(model, str(path))


def test_log_mel_frames_and_bands() -> None:
    t = np.arange(2 * SAMPLE_RATE) / SAMPLE_RATE
    x = beats.log_mel(np.sin(2 * np.pi * 1000 * t).astype(np.float32))
    assert x.shape == (1 + 2 * beats.SR // beats.HOP, 128) and x.dtype == np.float32
    assert x[50].argmax() in (36, 37, 38)  # 1 kHz is Slaney mel band 37 of 128 (30 Hz–11 kHz)
    assert not beats.log_mel(np.zeros(SAMPLE_RATE, np.float32)).any()


def test_peaks_threshold_and_dedup() -> None:
    logits = np.full(40, -5.0)
    logits[[5, 20, 21]] = 3.0  # a plateau of two frames becomes their mean
    logits[30] = -0.5  # a local maximum below probability 0.5 is not a beat
    assert beats._peaks(logits).tolist() == [5.0, 20.5]


def test_tracker_over_several_chunks(tmp_path: Path) -> None:
    """70 s of clicks at 120 BPM spans three 30 s chunks: each click is one beat, within a frame."""
    y = clicks(70)
    spect = beats.log_mel(y)
    level = spect.mean(axis=1)
    stand_in_tracker(tmp_path / "bt.onnx", quiet=level[25], loud=level[0])
    found, downbeats = beats.BeatTracker(tmp_path / "bt.onnx").track(y)
    want = np.arange(0, 69.9, 0.5)
    assert len(found) == len(want) and np.abs(found - want).max() <= 1 / beats.FPS
    assert np.allclose(downbeats, want[::4], atol=1 / beats.FPS)


def numbered(tm: TempoMap) -> list[tuple[float, int, int]]:
    return [(b.time_s, b.measure, b.beat) for b in tm.beats]


def test_tempo_map_bars_and_pickup() -> None:
    times = np.arange(10) * 0.5
    tm = beats.tempo_map(times, times[[2, 6]])  # downbeats on the 3rd and 7th beats
    assert numbered(tm)[:4] == [(0.0, 0, 3), (0.5, 0, 4), (1.0, 1, 1), (1.5, 1, 2)]
    assert (tm.tempo_source, tm.time_signature_source, tm.first_downbeat_source) == (
        "estimated",
        "default",
        "estimated",
    )
    waltz = beats.tempo_map(times, times[[2, 5]], beats_per_bar=3, time_signature_given=True)
    assert waltz.time_signatures[0].beats == 3 and waltz.time_signature_source == "user"
    assert numbered(waltz)[2:6] == [(1.0, 1, 1), (1.5, 1, 2), (2.0, 1, 3), (2.5, 2, 1)]


def test_gaps_in_the_tracked_beats_are_filled() -> None:
    """No beats through 20 s of silence: the bars still run on, so measures after it keep their
    numbers. A skipped beat is restored; a slightly long beat (a slowdown) is kept."""
    times = np.concatenate([np.arange(9) * 0.5, 24 + np.arange(13) * 0.5])
    tm = beats.tempo_map(times, times[::4])
    assert (24.0, 13, 1) in numbered(tm) and len(tm.beats) == 61
    assert np.allclose(np.diff([b.time_s for b in tm.beats]), 0.5)
    skipped = np.array([0, 0.5, 1.0, 2.0, 2.5, 3.0, 3.65, 4.15])
    assert [b.time_s for b in beats.tempo_map(skipped, skipped[:1]).beats] == [
        0,
        0.5,
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
        3.65,
        4.15,
    ]


def test_first_downbeat_override() -> None:
    times = np.arange(20) * 0.5
    tm = beats.tempo_map(times, times[::4], first_downbeat=3.03)  # nearest beat: 3.0 s
    assert tm.first_downbeat_source == "user"
    assert (3.0, 1, 1) in numbered(tm)
    assert numbered(tm)[0] == (1.0, 0, 1)  # one pickup bar; earlier beats cannot be numbered


def test_bpm_fixes_half_and_double_time() -> None:
    half = np.arange(8) * 1.0  # tracked at 60 BPM; the music is at 120
    tm = beats.tempo_map(half, half[::2], bpm=120)
    assert tm.tempo_source == "user"
    assert [b.time_s for b in tm.beats] == (np.arange(15) * 0.5).tolist()
    double = np.arange(16) * 0.25  # tracked at 240 BPM
    tm = beats.tempo_map(double, double[[1, 9]], bpm=120)
    assert [b.time_s for b in tm.beats] == (0.25 + np.arange(8) * 0.5).tolist()  # keeps downbeats


def test_bpm_that_does_not_fit_is_ignored(caplog: pytest.LogCaptureFixture) -> None:
    times = np.arange(8) * 0.5  # 120 BPM; 90 is a 3:4 ratio
    with caplog.at_level(logging.WARNING, logger="drumtx"):
        tm = beats.tempo_map(times, times[::4], bpm=90)
    assert tm.tempo_source == "estimated" and len(tm.beats) == 8
    assert "not a whole-number multiple" in caplog.text


def run(tmp_path: Path, *options: str) -> dict:  # type: ignore[type-arg]
    wav = tmp_path / "in.wav"
    sf.write(wav, clicks(6), SAMPLE_RATE)
    out = tmp_path / "out"
    args = ["transcribe", str(wav), "-o", str(out), "--model", "baseline", "-q", "--force"]
    result = runner.invoke(app, [*args, *options])
    assert result.exit_code == 0, result.stderr
    return json.loads((out / "in.events.json").read_text())["tempo_map"]  # type: ignore[no-any-return]


def test_overrides_change_the_stored_tempo_map(tmp_path: Path) -> None:
    """With conftest's stand-in tracker (beats every 0.5 s, downbeats every 2 s)."""
    plain = run(tmp_path)
    assert plain["beats"][4] == {"time_s": 2.0, "measure": 2, "beat": 1}
    assert plain["tempo_source"] == "estimated"
    waltz = run(tmp_path, "--time-signature", "3/4")
    assert waltz["time_signatures"] == [{"measure": 1, "beats": 3, "beat_type": 4}]
    assert waltz["time_signature_source"] == "user" and waltz["beats"][3]["beat"] == 1
    later = run(tmp_path, "--first-downbeat", "1.0")
    assert later["first_downbeat_source"] == "user"
    assert later["beats"][2] == {"time_s": 1.0, "measure": 1, "beat": 1}
    double = run(tmp_path, "--bpm", "240")
    assert double["tempo_source"] == "user" and double["beats"][1]["time_s"] == 0.25


@pytest.mark.parametrize(
    ("option", "value"),
    [("--time-signature", "6/8"), ("--time-signature", "x/4"), ("--bpm", "0"),
     ("--first-downbeat", "-1")],
)  # fmt: skip
def test_bad_overrides_exit_2(tmp_path: Path, option: str, value: str) -> None:
    wav = tmp_path / "in.wav"
    sf.write(wav, clicks(3), SAMPLE_RATE)
    result = runner.invoke(app, ["transcribe", str(wav), "--model", "baseline", option, value])
    assert result.exit_code == 2
