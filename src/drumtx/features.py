"""Input features for the ADTOF model: madmom's log-filtered spectrogram, in NumPy (decision 0005).

ADTOF computes them with madmom's `LogarithmicFilteredSpectrogramProcessor`: 2048-sample Hann
frames at 100 fps, 12 bands per octave from 20 Hz to 20 kHz (84 bands), log10(1 + x). This is a
reimplementation, checked against madmom 0.16.1 (docs/models/adtof-frame-rnn.md).
"""

import numpy as np

from drumtx.ingest import SAMPLE_RATE

FPS = 100
FRAME = 2048
HOP = SAMPLE_RATE // FPS


def _filterbank(bands: int = 12, fmin: float = 20, fmax: float = 20000) -> np.ndarray:
    """madmom's LogarithmicFilterbank: normalized, overlapping triangular filters, unique bins."""
    freqs = np.fft.fftfreq(FRAME, 1 / SAMPLE_RATE)[: FRAME // 2]
    steps = np.arange(np.floor(np.log2(fmin / 440) * bands), np.ceil(np.log2(fmax / 440) * bands))
    f = 440 * 2.0 ** (steps / bands)
    f = f[(f >= fmin) & (f <= fmax)]
    idx = np.clip(freqs.searchsorted(f), 1, len(freqs) - 1)
    idx -= (f - freqs[idx - 1]) < (freqs[idx] - f)  # nearest FFT bin
    bins = np.unique(idx)
    fb = np.zeros((len(freqs), len(bins) - 2), np.float32)
    for i, (start, center, stop) in enumerate(zip(bins, bins[1:], bins[2:], strict=False)):
        if stop - start < 2:
            center, stop = start, start + 1
        tri = np.concatenate(
            [
                np.linspace(0, 1, center - start, endpoint=False),
                np.linspace(1, 0, stop - center, endpoint=False),
            ]
        )
        fb[start:stop, i] = tri / tri.sum()
    return fb


FILTERBANK = _filterbank()  # (1024 FFT bins, 84 bands)


def spectrogram(y: np.ndarray) -> np.ndarray:
    """Mono audio at 44.1 kHz → (frames, 84) float32. Frame i is centered on sample i * HOP."""
    n = int(np.ceil(len(y) / HOP))
    padded = np.pad(y.astype(np.float32), (FRAME // 2, FRAME // 2))  # madmom pads with zeros
    window = np.hanning(FRAME).astype(np.float32)
    out = np.empty((n, FILTERBANK.shape[1]), np.float32)
    for s in range(0, n, 4096):  # chunks bound memory
        idx = np.arange(FRAME)[None, :] + HOP * np.arange(s, min(n, s + 4096))[:, None]
        mag = np.abs(np.fft.rfft(padded[idx] * window, axis=1))[:, : FRAME // 2]
        out[s : s + len(idx)] = np.log10(mag @ FILTERBANK + 1)
    return out
