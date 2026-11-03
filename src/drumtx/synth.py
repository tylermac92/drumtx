"""Drum sounds synthesized in code, so no third-party samples are needed (decision 0003).

Used for test fixtures (M1-5) and the audio preview (M5-2). Each sound is deterministic and puts
most of its energy in its class's band in `detect.BANDS_HZ`. They are stand-ins, not realistic kits.
"""

from collections.abc import Iterable

import numpy as np

from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import CLASSES, DrumClass


def _noise(n: int, lo: float, hi: float, seed: int) -> np.ndarray:
    """White noise band-limited to lo–hi Hz, at unit peak."""
    spec = np.fft.rfft(np.random.default_rng(seed).normal(size=n))
    freqs = np.fft.rfftfreq(n, 1 / SAMPLE_RATE)
    y = np.fft.irfft(spec * ((freqs >= lo) & (freqs < hi)), n)
    out: np.ndarray = y / np.abs(y).max()
    return out


def _sweep(t: np.ndarray, start_hz: float, end_hz: float, rate: float) -> np.ndarray:
    """A sine whose pitch falls exponentially from start_hz to end_hz."""
    freq = end_hz + (start_hz - end_hz) * np.exp(-t * rate)
    return np.sin(2 * np.pi * np.cumsum(freq) / SAMPLE_RATE)


def drum_hit(cls: DrumClass, velocity: int = 100) -> np.ndarray:
    """One hit as mono float32 at SAMPLE_RATE, with a peak of about velocity / 127."""
    seconds = {"kick": 0.4, "snare": 0.25, "hihat": 0.1, "tom": 0.4, "cymbal": 1.2}[cls]
    n = round(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    seed = CLASSES.index(cls)
    if cls == "kick":
        y = _sweep(t, 120, 50, 40) * np.exp(-t * 12)
    elif cls == "snare":
        tone = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 25)
        y = 0.3 * tone + _noise(n, 1000, 5000, seed) * np.exp(-t * 18)
    elif cls == "hihat":
        y = _noise(n, 8000, 16000, seed) * np.exp(-t * 60)
    elif cls == "tom":
        y = _sweep(t, 220, 130, 20) * np.exp(-t * 8)
    else:
        y = _noise(n, 4000, 8000, seed) * np.exp(-t * 4)
    y[:32] *= np.linspace(0, 1, 32)  # 0.7 ms fade-in avoids a click in every band
    out: np.ndarray = (y / np.abs(y).max() * velocity / 127).astype(np.float32)
    return out


def render(hits: Iterable[tuple[float, DrumClass, int]], seconds: float) -> np.ndarray:
    """Mix (time_s, class, velocity) hits into mono float32 audio. Overlaps add, unclipped."""
    y = np.zeros(round(seconds * SAMPLE_RATE), np.float32)
    for time_s, cls, velocity in hits:
        start = round(time_s * SAMPLE_RATE)
        h = drum_hit(cls, velocity)[: max(0, len(y) - start)]
        y[start : start + len(h)] += h
    return y
