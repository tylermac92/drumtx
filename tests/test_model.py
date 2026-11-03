"""M2-1: ADTOF input features, and ModelDetector run on a stand-in ONNX model.

The real model is never in the repository (decision 0005); its accuracy is checked by the
benchmark (eval/results/adtof-dev.json) and its features against madmom (the model card).
"""

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper

from drumtx import detect, features
from drumtx.ingest import SAMPLE_RATE, AudioBuffer


def test_spectrogram_frames_and_bands() -> None:
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    x = features.spectrogram(np.sin(2 * np.pi * 1000 * t).astype(np.float32))
    assert x.shape == (100, 84) and x.dtype == np.float32
    freqs = np.fft.fftfreq(features.FRAME, 1 / SAMPLE_RATE)[: features.FRAME // 2]
    peak_hz = (freqs @ features.FILTERBANK)[x[50].argmax()]  # centroid of the loudest band
    assert abs(np.log2(peak_hz / 1000)) < 1 / 12  # within a semitone
    assert not features.spectrogram(np.zeros(441 * 10 + 1, np.float32)).any()
    assert len(features.spectrogram(np.zeros(441 * 10 + 1, np.float32))) == 11


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
