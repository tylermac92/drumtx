"""M0-4 spike helpers: clips, madmom-equivalent features and peak picking, scoring.

Spike code: runs in the separate spike environment (numpy, scipy, soundfile, mir_eval, torch,
onnxruntime), not in the drumtx package. See docs/decisions/0005-detection-approach.md.
"""

import csv
from pathlib import Path

import mir_eval
import numpy as np
import soundfile as sf
from scipy.ndimage import maximum_filter1d, uniform_filter1d

DATA = Path.home() / "drumtx-data"
REPO = Path(__file__).resolve().parents[2]
CLASSES = ("kick", "snare", "hihat", "tom", "cymbal")
SR, FPS, FRAME = 44100, 100, 2048
HOP = SR // FPS

# 10 development clips (decision 0004); IDS from eval/dev.csv.
CLIPS = [
    "egmd/drummer6_session3_4_rock_127_beat_4-4_21",
    "egmd/drummer7_session1_13_funk_102_beat_4-4_35",
    "egmd/drummer4_session1_2_jazz_158_beat_4-4_24",
    "egmd/drummer1_session2_142_gospel_120_beat_4-4_5",
    "egmd/drummer7_session2_58_soul-motown_148_fill_4-4_42",
    "mdb/FusionJazz_Drum",
    "mdb/FusionJazz_MIX",
    "mdb/Disco_MIX",
    "mdb/Shadows_MIX",
    "idmt/RealDrum01_00_MIX",
]


def manifest() -> dict[str, dict[str, str]]:
    return {r["clip_id"]: r for r in csv.DictReader((REPO / "eval" / "dev.csv").open())}


def load_audio(path: Path) -> np.ndarray:
    y, sr = sf.read(path, dtype="float32", always_2d=True)
    assert sr == SR, (path, sr)
    return np.asarray(y.mean(axis=1))


def reference(clip_id: str) -> dict[str, np.ndarray]:
    rows = list(csv.DictReader((DATA / "corpus" / f"{clip_id}.onsets.csv").open()))
    return {
        c: np.array(sorted(float(r["time_s"]) for r in rows if r["class"] == c)) for c in CLASSES
    }


def _filterbank(bands: int = 12, fmin: float = 20, fmax: float = 20000) -> np.ndarray:
    """madmom LogarithmicFilterbank (normalized, unique, overlapping triangular filters)."""
    freqs = np.fft.fftfreq(FRAME, 1 / SR)[: FRAME // 2]
    f = 440 * 2.0 ** (
        np.arange(np.floor(np.log2(fmin / 440) * bands), np.ceil(np.log2(fmax / 440) * bands))
        / bands
    )
    f = f[np.searchsorted(f, fmin) :]
    f = f[: np.searchsorted(f, fmax, "right")]
    idx = np.clip(freqs.searchsorted(f), 1, len(freqs) - 1)
    idx -= (f - freqs[idx - 1]) < (freqs[idx] - f)
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


FILTERBANK = _filterbank()
BAND_HZ = np.fft.fftfreq(FRAME, 1 / SR)[: FRAME // 2] @ FILTERBANK  # filter centroid per band


def features(y: np.ndarray) -> np.ndarray:
    """log10(1 + |STFT| @ filterbank): 100 fps, 2048-sample Hann frames centred on each hop."""
    n = int(np.ceil(len(y) / HOP))
    padded = np.pad(y, (FRAME // 2, FRAME // 2))
    out = np.empty((n, FILTERBANK.shape[1]), np.float32)
    window = np.hanning(FRAME).astype(np.float32)
    for s in range(0, n, 4096):  # chunked to bound memory
        idx = np.arange(FRAME)[None, :] + HOP * np.arange(s, min(n, s + 4096))[:, None]
        spec = np.abs(np.fft.rfft(padded[idx] * window, axis=1))[:, : FRAME // 2]
        out[s : s + len(idx)] = np.log10(spec @ FILTERBANK + 1)
    return out


def peaks(act: np.ndarray, threshold: float) -> np.ndarray:
    """madmom NotePeakPickingProcessor(smooth=0, pre_avg=.1, post_avg=.01, pre_max=.02,
    post_max=.01, combine=.02) at 100 fps, for one activation curve."""
    mov_avg = uniform_filter1d(act, 12, mode="constant", origin=4)
    det = act * (act >= mov_avg + threshold)
    det = det * (det == maximum_filter1d(det, 4, mode="constant", origin=0))
    out: list[float] = []
    for t in np.nonzero(det)[0] / FPS:
        if not out or t - out[-1] > 0.02:
            out.append(t)
    return np.array(out)


def counts(ref: np.ndarray, est: np.ndarray, window: float = 0.05) -> tuple[int, int, int]:
    """(true positives, false positives, false negatives) with mir_eval's onset matching."""
    tp = len(mir_eval.util.match_events(ref, est, window)) if len(ref) and len(est) else 0
    return tp, len(est) - tp, len(ref) - tp


def f_measure(tp: int, fp: int, fn: int) -> float:
    return 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else float("nan")
