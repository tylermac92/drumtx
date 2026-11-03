"""Drum detection: activation curves per class, then peak picking (Technical Design Document §7).

`BaselineDetector` is the classical detector: positive spectral flux of the log-magnitude
spectrogram, averaged over one frequency band per class. It needs no model and is the regression
floor for the learned detector. `ModelDetector` runs the ADTOF model (decision 0005,
docs/models/adtof-frame-rnn.md).
"""

from pathlib import Path
from typing import Literal, Protocol

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from drumtx import features
from drumtx.ingest import SAMPLE_RATE, AudioBuffer
from drumtx.schema import CLASSES, DrumClass, DrumEvent

Preset = Literal["strict", "balanced", "sensitive"]
FPS = 100  # activation frames per second
MIN_GAP_S = 0.03  # peaks of one class closer than this are one hit
# A 1024-sample window keeps sharp onsets within -7 to +4 ms; a 2048-sample one is 4–17 ms early.
FRAME = 1024
MAX_GAIN = 4.0  # peak normalization stops at +12 dB, so near-silence is not blown up into hits

# Frequency band per class, in Hz. Real kits overlap these, which is why this is only a baseline.
BANDS_HZ: dict[DrumClass, tuple[float, float]] = {
    "kick": (30, 90),
    "snare": (1000, 4000),
    "hihat": (8000, 16000),
    "tom": (100, 300),
    "cymbal": (4000, 8000),
}
# Per-class peak thresholds for `balanced`, tuned for F-measure on the development set
# (decision 0009). `strict` and `sensitive` scale them.
THRESHOLDS: dict[DrumClass, float] = {
    "kick": 0.35,
    "snare": 0.03,
    "hihat": 0.014,
    "tom": 0.2,
    "cymbal": 0.03,
}
PRESET_SCALE: dict[Preset, float] = {"strict": 1.5, "balanced": 1.0, "sensitive": 0.67}

# ADTOF's output order (its LABELS_5: GM notes 35, 38, 47, 42, 49), and its own peak picking:
# per-class thresholds from its hyperparameters, and peaks within 20 ms combined.
MODEL_ORDER: tuple[DrumClass, ...] = ("kick", "snare", "tom", "hihat", "cymbal")
MODEL_THRESHOLDS: dict[DrumClass, float] = {
    "kick": 0.22,
    "snare": 0.24,
    "tom": 0.32,
    "hihat": 0.22,
    "cymbal": 0.30,
}
MODEL_MIN_GAP_S = 0.02
# Chunked inference: frames kept per network run, and context frames discarded on each side
# (ADTOF's warm-up). Effect on memory and accuracy: docs/models/adtof-frame-rnn.md.
MODEL_CHUNK = 6000
MODEL_CONTEXT = 400


class Detector(Protocol):
    def detect(self, audio: AudioBuffer, preset: Preset) -> list[DrumEvent]: ...


def baseline_activations(y: np.ndarray) -> dict[DrumClass, np.ndarray]:
    """Mono audio at 44.1 kHz → one activation curve per class, at FPS frames per second."""
    y = y * min(1 / max(float(np.abs(y).max()), 1e-9), MAX_GAIN)  # thresholds ignore level
    hop = SAMPLE_RATE // FPS
    n = int(np.ceil(len(y) / hop))
    # Frame i is centered on sample i * hop. Mirrored padding: zeros would look like an onset.
    padded = np.pad(y, (FRAME // 2, FRAME // 2), mode="reflect")
    window = np.hanning(FRAME).astype(np.float32)
    freqs = np.fft.rfftfreq(FRAME, 1 / SAMPLE_RATE)
    masks = {c: (freqs >= lo) & (freqs < hi) for c, (lo, hi) in BANDS_HZ.items()}
    bands = {c: np.empty(n, np.float32) for c in BANDS_HZ}
    for s in range(0, n, 4096):  # chunks bound memory
        idx = np.arange(FRAME)[None, :] + hop * np.arange(s, min(n, s + 4096))[:, None]
        mag = np.log10(1 + np.abs(np.fft.rfft(padded[idx] * window, axis=1)))
        for c, mask in masks.items():
            bands[c][s : s + len(idx)] = mag[:, mask].mean(axis=1)
    return {c: np.maximum(np.diff(b, prepend=b[:1]), 0) for c, b in bands.items()}


def pick_peaks(act: np.ndarray, threshold: float, min_gap_s: float = MIN_GAP_S) -> np.ndarray:
    """Frame indices of peaks, as madmom's NotePeakPickingProcessor does it at 100 fps.

    A peak is a local maximum (2 frames before, 1 after) that exceeds the moving average over the
    preceding 100 ms by `threshold`. Peaks closer than `min_gap_s` keep the first.
    """

    def window(a: np.ndarray, before: int, after: int) -> np.ndarray:
        return sliding_window_view(np.pad(a, (before, after)), before + after + 1)

    det = np.where(act >= window(act, 10, 1).mean(axis=1) + threshold, act, 0)
    frames = np.nonzero((det > 0) & (det == window(det, 2, 1).max(axis=1)))[0]
    out: list[int] = []
    for f in frames:
        if not out or f - out[-1] > min_gap_s * FPS:
            out.append(int(f))
    return np.array(out, dtype=int)


def to_events(
    acts: dict[DrumClass, np.ndarray],
    thresholds: dict[DrumClass, float],
    preset: Preset,
    start_s: float,
    min_gap_s: float = MIN_GAP_S,
) -> list[DrumEvent]:
    events = []
    for c, act in acts.items():
        threshold = thresholds[c] * PRESET_SCALE[preset]
        for f in pick_peaks(act, threshold, min_gap_s).tolist():
            # Not calibrated (that is M2-4): 0.5 at the threshold, rising toward 1.
            confidence = float(act[f] / (act[f] + threshold))
            events.append(
                DrumEvent(
                    time_s=round(start_s + f / FPS, 3),
                    cls=c,
                    confidence=round(confidence, 3),
                    velocity=max(1, min(127, round(127 * confidence))),
                )
            )
    return sorted(events, key=lambda e: (e.time_s, CLASSES.index(e.cls)))


class BaselineDetector:
    def detect(self, audio: AudioBuffer, preset: Preset = "balanced") -> list[DrumEvent]:
        return to_events(baseline_activations(audio.mono), THRESHOLDS, preset, audio.start_s)


class ModelDetector:
    """The ADTOF Frame_RNN model as ONNX, made by scripts/convert_adtof.py."""

    def __init__(self, path: Path) -> None:
        import onnxruntime as ort

        self.session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

    def activations(self, spectrogram: np.ndarray) -> dict[DrumClass, np.ndarray]:
        """Run the network over overlapping windows, to bound memory.

        Each window adds MODEL_CONTEXT frames on both sides and keeps only its center, so every
        frame is computed with at least 4 s of context, as ADTOF's own `predict` does.
        """
        n = len(spectrogram)
        y = np.empty((n, len(MODEL_ORDER)), np.float32)
        for s in range(0, n, MODEL_CHUNK):
            lo, hi = max(0, s - MODEL_CONTEXT), min(n, s + MODEL_CHUNK + MODEL_CONTEXT)
            out = self.session.run(None, {"x": spectrogram[None, lo:hi]})[0][0]
            y[s : s + MODEL_CHUNK] = out[s - lo : s - lo + MODEL_CHUNK]
        return {c: y[:, i] for i, c in enumerate(MODEL_ORDER)}

    def detect(self, audio: AudioBuffer, preset: Preset = "balanced") -> list[DrumEvent]:
        acts = self.activations(features.spectrogram(audio.mono))
        return to_events(acts, MODEL_THRESHOLDS, preset, audio.start_s, MODEL_MIN_GAP_S)
