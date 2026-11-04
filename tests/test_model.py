"""M2-1 to M2-4: ADTOF features, presets, confidence and velocity, and ModelDetector (run on a
stand-in ONNX model).

The real model is never in the repository (decision 0005); its accuracy is checked by the
benchmark (eval/results/adtof-dev.json) and its features against madmom (the model card).
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper

from drumtx import detect, features
from drumtx.ingest import SAMPLE_RATE, AudioBuffer
from drumtx.schema import CLASSES


def test_spectrogram_frames_and_bands() -> None:
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    x = features.spectrogram(np.sin(2 * np.pi * 1000 * t).astype(np.float32))
    assert x.shape == (100, 84) and x.dtype == np.float32
    freqs = np.fft.fftfreq(features.FRAME, 1 / SAMPLE_RATE)[: features.FRAME // 2]
    peak_hz = (freqs @ features.FILTERBANK)[x[50].argmax()]  # centroid of the loudest band
    assert abs(np.log2(peak_hz / 1000)) < 1 / 12  # within a semitone
    assert not features.spectrogram(np.zeros(441 * 10 + 1, np.float32)).any()
    assert len(features.spectrogram(np.zeros(441 * 10 + 1, np.float32))) == 11


def test_presets_file() -> None:
    """Tuned presets (M2-3): every class, and stricter presets never have lower thresholds."""
    presets = json.loads(detect.MODEL_PRESETS_FILE.read_text("utf-8"))
    assert 0 < presets["min_gap_s"] < 0.1
    th = presets["thresholds"]
    for c in CLASSES:
        assert 0 < th["sensitive"][c] < th["balanced"][c] < th["strict"][c] < 1


def stand_in_model(path: Path) -> None:
    """y = sigmoid(x @ W + b): output 2 (tom, in ADTOF's order) follows overall loudness."""
    w = np.zeros((84, 5), np.float32)
    w[:, 2] = 20 / 84
    b = np.array([-10, -10, -4, -10, -10], np.float32)
    graph = helper.make_graph(
        [
            helper.make_node("MatMul", ["x", "w"], ["xw"]),
            helper.make_node("Add", ["xw", "b"], ["z"]),
            helper.make_node("Sigmoid", ["z"], ["y"]),
        ],
        "stand_in",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, "frames", 84])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, "frames", 5])],
        [onnx.numpy_helper.from_array(w, "w"), onnx.numpy_helper.from_array(b, "b")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.save(model, str(path))


def test_model_detector_maps_outputs_to_classes(tmp_path: Path) -> None:
    stand_in_model(tmp_path / "m.onnx")
    y = np.zeros(3 * SAMPLE_RATE, np.float32)
    y[SAMPLE_RATE] = 1.0  # a click at 1 s
    buf = AudioBuffer(y[:, None], start_s=2.0, source_duration_s=5.0)
    events = detect.ModelDetector(tmp_path / "m.onnx").detect(buf)
    assert [(e.time_s, e.cls) for e in events] == [(3.0, "tom")]
    assert 0.5 < events[0].confidence <= 1 and 1 <= events[0].velocity <= 127


def test_confidence_and_velocity_rise_with_activation(tmp_path: Path) -> None:
    """M2-4: confidence in [0, 1] and velocity in 1–127, both non-decreasing in the activation."""
    stand_in_model(tmp_path / "m.onnx")
    detector = detect.ModelDetector(tmp_path / "m.onnx")
    for c in CLASSES:
        rated = [detector.rate(c, a) for a in np.linspace(0, 1, 201)]
        conf, vel = (np.array(x) for x in zip(*rated, strict=True))
        assert ((conf >= 0) & (conf <= 1)).all() and ((vel >= 1) & (vel <= 127)).all()
        assert (np.diff(conf) >= 0).all() and (np.diff(vel) >= 0).all()
        assert vel[-1] - vel[0] > 50  # velocities span a real range


def test_chunks_are_stitched_without_duplicate_or_missed_peaks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With small chunks, clicks on and next to chunk boundaries are each found exactly once."""
    monkeypatch.setattr(detect, "MODEL_CHUNK", 50)
    monkeypatch.setattr(detect, "MODEL_CONTEXT", 7)
    stand_in_model(tmp_path / "m.onnx")
    detector = detect.ModelDetector(tmp_path / "m.onnx")
    frames = [50, 99, 150, 199]  # chunks are frames 0–49, 50–99, 100–149 and 150–199
    y = np.zeros(2 * SAMPLE_RATE, np.float32)
    y[[f * features.HOP for f in frames]] = 1.0
    x = features.spectrogram(y)
    whole = detector.session.run(None, {"x": x[None]})[0][0]
    chunked = detector.activations(x)
    for i, c in enumerate(detect.MODEL_ORDER):
        np.testing.assert_array_equal(chunked[c], whole[:, i])
    events = detect.ModelDetector(tmp_path / "m.onnx").detect(AudioBuffer(y[:, None], 0.0, 2.0))
    assert [e.time_s for e in events] == [0.5, 0.99, 1.5, 1.99]


def test_ten_minutes_run_in_bounded_windows(tmp_path: Path) -> None:
    stand_in_model(tmp_path / "m.onnx")
    detector = detect.ModelDetector(tmp_path / "m.onnx")
    sizes: list[int] = []
    run = detector.session.run

    def spy(names: Any, feeds: dict[str, np.ndarray]) -> Any:
        sizes.append(feeds["x"].shape[1])
        return run(names, feeds)

    detector.session = SimpleNamespace(run=spy)
    acts = detector.activations(np.zeros((600 * detect.FPS, 84), np.float32))
    assert all(len(a) == 600 * detect.FPS for a in acts.values())
    assert max(sizes) == detect.MODEL_CHUNK + 2 * detect.MODEL_CONTEXT
