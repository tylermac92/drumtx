"""Beat and downbeat tracking with Beat This! `final0` (decision 0006; M3-1), and the tempo map.

The model runs through ONNX Runtime. Its log-mel spectrogram, chunked inference and "minimal"
postprocessing are NumPy ports of the upstream `beat_this` 1.1.0 package (`LogMelSpect`,
`split_predict_aggregate`, `Postprocessor`). `scripts/check_beats.py` compares them with it.
"""

import logging
from pathlib import Path
from typing import Literal

import numpy as np
import soxr
from numpy.lib.stride_tricks import sliding_window_view

from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import Beat, TempoMap, TimeSignature

log = logging.getLogger("drumtx")
SR = 22050  # the model's input: 22,050 Hz, 1024-point FFT, hop 441 (50 frames per second)
N_FFT = 1024
HOP = 441
FPS = 50
CHUNK = 1500  # frames per network run (30 s), as upstream
BORDER = 6  # frames discarded at each chunk edge; chunks overlap by this much


def _mel_filterbank() -> np.ndarray:
    """torchaudio's melscale_fbanks: 128 Slaney-scale triangles, 30 Hz–11 kHz, no area norm."""

    def hz_to_mel(f: float) -> float:
        return f / (200 / 3) if f < 1000 else 15 + np.log(f / 1000) / (np.log(6.4) / 27)

    mels = np.linspace(hz_to_mel(30), hz_to_mel(11000), 128 + 2)
    f_pts = np.where(mels < 15, mels * 200 / 3, 1000 * np.exp(np.log(6.4) / 27 * (mels - 15)))
    freqs = np.linspace(0, SR // 2, N_FFT // 2 + 1)
    slopes = f_pts[None, :] - freqs[:, None]
    down = -slopes[:, :-2] / np.diff(f_pts)[:-1]
    up = slopes[:, 2:] / np.diff(f_pts)[1:]
    return np.maximum(0, np.minimum(down, up)).astype(np.float32)


MEL = _mel_filterbank()  # (513 FFT bins, 128 bands)


def log_mel(y: np.ndarray) -> np.ndarray:
    """Mono audio at 44.1 kHz → (frames, 128): log1p(1000 · |STFT| @ mel), as LogMelSpect."""
    y = soxr.resample(y, SAMPLE_RATE, SR).astype(np.float32)
    n = 1 + len(y) // HOP  # frames centered on i * HOP, reflect-padded (torch.stft center=True)
    padded = np.pad(y, N_FFT // 2, mode="reflect")
    window = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)).astype(np.float32)
    out = np.empty((n, MEL.shape[1]), np.float32)
    for s in range(0, n, 4096):  # chunks bound memory
        idx = np.arange(N_FFT)[None, :] + HOP * np.arange(s, min(n, s + 4096))[:, None]
        mag = np.abs(np.fft.rfft(padded[idx] * window, axis=1)) / np.sqrt(N_FFT)
        out[s : s + len(idx)] = np.log1p(1000 * (mag.astype(np.float32) @ MEL))
    return out


def _dedup(frames: np.ndarray) -> np.ndarray:
    """Runs of adjacent peak frames become their mean frame (upstream deduplicate_peaks)."""
    out: list[float] = []
    count = 0
    for f in frames.tolist():
        if out and f - out[-1] <= 1:
            count += 1
            out[-1] += (f - out[-1]) / count
        else:
            out.append(float(f))
            count = 1
    return np.array(out)


def _peaks(logits: np.ndarray) -> np.ndarray:
    """Frames that are the maximum within ±3 frames (±60 ms) and above probability 0.5."""
    window_max = sliding_window_view(np.pad(logits, 3, constant_values=-np.inf), 7).max(axis=1)
    return _dedup(np.nonzero((logits == window_max) & (logits > 0))[0])


class BeatTracker:
    """Beat This! as ONNX, from `drumtx models download beat-this-final0`."""

    def __init__(self, path: Path) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.enable_cpu_mem_arena = False  # 0.5 GB less peak memory, for 8% more time
        self.session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])

    def logits(self, spect: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Beat and downbeat logits per frame, from overlapping 30 s chunks (keep_first)."""
        n = len(spect)
        starts = np.arange(-BORDER, n - BORDER, CHUNK - 2 * BORDER)
        if n > CHUNK - 2 * BORDER:
            starts[-1] = n - (CHUNK - BORDER)  # the last chunk ends at the end of the piece
        beat = np.full(n, -1000.0, np.float32)
        downbeat = np.full(n, -1000.0, np.float32)
        for start in starts[::-1].tolist():  # earlier chunks overwrite later ones
            pad = (max(0, -start), max(0, min(BORDER, start + CHUNK - n)))
            chunk = np.pad(spect[max(start, 0) : start + CHUNK], (pad, (0, 0)))
            b, d = (x[0, BORDER:-BORDER] for x in self.session.run(None, {"spect": chunk[None]}))
            beat[start + BORDER : start + BORDER + len(b)] = b
            downbeat[start + BORDER : start + BORDER + len(d)] = d
        return beat, downbeat

    def track(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Beat and downbeat times in seconds from the start of `y` (mono, 44.1 kHz)."""
        beat_logits, downbeat_logits = self.logits(log_mel(y))
        beats = _peaks(beat_logits) / FPS
        downbeats = _peaks(downbeat_logits) / FPS
        if len(beats):  # each downbeat moves to its nearest beat
            downbeats = np.unique(beats[np.abs(beats[None, :] - downbeats[:, None]).argmin(axis=1)])
        return beats, downbeats


def _apply_bpm(beats: np.ndarray, downbeats: np.ndarray, bpm: float) -> np.ndarray | None:
    """Beats at `bpm`: the tracked beats subdivided or thinned by a whole-number ratio, so tempo
    drift is kept. None if the tracked tempo is not near a whole-number ratio of `bpm`."""
    ratio = float(np.median(np.diff(beats))) * bpm / 60  # 2: the tracker went half tempo
    k = round(max(ratio, 1 / ratio))
    if abs(max(ratio, 1 / ratio) / k - 1) > 0.15:  # e.g. 3:2 is not a whole-number ratio
        return None
    if k == 1:
        return beats
    if ratio > 1:  # subdivide each interval into k beats
        steps = np.arange(k) / k
        inner = (beats[:-1, None] + np.diff(beats)[:, None] * steps[None, :]).ravel()
        return np.append(inner, beats[-1])
    # keep every k-th beat, starting at the phase that keeps the most downbeats
    on_beat = np.abs(beats[None, :] - downbeats[:, None]).argmin(axis=1) if len(downbeats) else []
    phase = max(range(k), key=lambda p: sum(i % k == p for i in on_beat))
    kept: np.ndarray = beats[phase::k]
    return kept


def tempo_map(
    beats: np.ndarray,
    downbeats: np.ndarray,
    beats_per_bar: int = 4,
    bpm: float | None = None,
    first_downbeat: float | None = None,
    time_signature_given: bool = False,
) -> TempoMap:
    """Number the beats into bars of `beats_per_bar`; bar 1 starts at the first downbeat.

    - Without `first_downbeat`, bar lines go where most tracked downbeats agree.
    - Beats before bar 1 form a pickup, measure 0. With `first_downbeat` more than one bar into
      the audio, earlier beats cannot be numbered (measures start at 0) and are left out.
    - `bpm` corrects half- and double-tempo tracking (and other whole-number ratios).
    """
    tempo_source: Literal["estimated", "user"] = "estimated"
    if bpm is not None and len(beats) > 1:
        fixed = _apply_bpm(beats, downbeats, bpm)
        if fixed is None:
            log.warning(
                "--bpm %g is not a whole-number multiple or fraction of the tracked tempo "
                "(about %.0f BPM); keeping the tracked beats.",
                bpm,
                60 / float(np.median(np.diff(beats))),
            )
        else:
            beats, tempo_source = fixed, "user"
    if first_downbeat is not None and len(beats):
        start = int(np.abs(beats - first_downbeat).argmin())
    elif len(downbeats) and len(beats):
        on_beat = np.abs(beats[None, :] - downbeats[:, None]).argmin(axis=1)
        votes = [int(np.sum(on_beat % beats_per_bar == p)) for p in range(beats_per_bar)]
        start = votes.index(max(votes))
    else:
        start = 0
    numbered = [
        Beat(round(float(t), 3), (i - start) // beats_per_bar + 1, (i - start) % beats_per_bar + 1)
        for i, t in enumerate(beats)
        if i - start >= -beats_per_bar
    ]
    return TempoMap(
        beats=tuple(numbered),
        time_signatures=(TimeSignature(1, beats_per_bar, 4),),
        tempo_source=tempo_source,
        time_signature_source="user" if time_signature_given else "default",
        first_downbeat_source="user" if first_downbeat is not None else "estimated",
    )
