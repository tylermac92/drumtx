"""Compare detection options on the M0-4 spike clips; prints per-class F-measure and runtime.

python run.py
"""

import time
from collections import defaultdict
from collections.abc import Callable

import numpy as np
import onnxruntime as ort
from common import (
    BAND_HZ,
    CLASSES,
    CLIPS,
    DATA,
    counts,
    f_measure,
    features,
    load_audio,
    manifest,
    peaks,
    reference,
)
from crnn import ADTOF_ONNX, ADTOF_ORDER, ADTOF_THRESHOLDS

TRAINED_ONNX = DATA / "models" / "spike" / "small_crnn_egmd.onnx"

# Classical baseline: positive spectral flux summed over one frequency band per class.
BANDS_HZ = {
    "kick": (30, 90),
    "tom": (100, 300),
    "snare": (1000, 4000),
    "cymbal": (4000, 8000),
    "hihat": (8000, 16000),
}


def classical_activations(x: np.ndarray) -> dict[str, np.ndarray]:
    flux = np.maximum(np.diff(x, axis=0, prepend=x[:1]), 0)
    out = {}
    for c, (lo, hi) in BANDS_HZ.items():
        a = flux[:, (BAND_HZ >= lo) & (BAND_HZ < hi)].sum(axis=1)
        out[c] = a / (np.percentile(a, 99.5) + 1e-9)  # per-clip normalisation
    return out


def onnx_activations(path, order) -> Callable[[np.ndarray], dict[str, np.ndarray]]:  # type: ignore[no-untyped-def]
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

    def run(x: np.ndarray) -> dict[str, np.ndarray]:
        y = session.run(None, {"x": x[None]})[0][0]
        return {c: y[:, i] for i, c in enumerate(order)}

    return run


def tune(acts: list[dict[str, np.ndarray]], refs: list[dict[str, np.ndarray]]) -> dict[str, float]:
    """Best threshold per class over all clips (optimistic: tuned on the clips it is scored on)."""
    best = {}
    for c in CLASSES:

        def f(t: float, c: str = c) -> float:
            tot = np.sum(
                [counts(r[c], peaks(a[c], t)) for a, r in zip(acts, refs, strict=True)], axis=0
            )
            return f_measure(*tot)

        best[c] = max(np.arange(0.05, 0.95, 0.025), key=f)
    return best


def main() -> None:
    meta = manifest()
    methods = {
        "classical": classical_activations,
        "adtof": onnx_activations(ADTOF_ONNX, ADTOF_ORDER),
    }
    if TRAINED_ONNX.exists():
        methods["trained"] = onnx_activations(TRAINED_ONNX, CLASSES)
    minutes = 0.0
    feat_s = 0.0
    acts: dict[str, list[dict[str, np.ndarray]]] = defaultdict(list)
    runtime: dict[str, float] = defaultdict(float)
    refs = []
    for clip in CLIPS:
        y = load_audio(DATA / meta[clip]["audio"])
        minutes += len(y) / 44100 / 60
        t0 = time.perf_counter()
        x = features(y)
        feat_s += time.perf_counter() - t0
        refs.append(reference(clip))
        for name, fn in methods.items():
            t0 = time.perf_counter()
            acts[name].append(fn(x))
            runtime[name] += time.perf_counter() - t0

    thresholds = {
        "classical": tune(acts["classical"], refs),
        "adtof": dict(zip(ADTOF_ORDER, ADTOF_THRESHOLDS, strict=True)),
        "trained": {c: 0.5 for c in CLASSES},
    }
    if TRAINED_ONNX.exists():
        thresholds["trained"] = {**thresholds["trained"], **_trained_thresholds()}
    print(f"{len(CLIPS)} clips, {minutes:.1f} min; features {feat_s / minutes:.2f} s/audio min\n")
    subsets: dict[str, list[int]] = {"drum-only": [], "full-mix": []}
    for i, clip in enumerate(CLIPS):
        subsets[meta[clip]["subset"]].append(i)
    for name in methods:
        print(f"== {name}: {runtime[name] / minutes:.2f} s per audio minute (after features)")
        for window in (0.05, 0.03):
            for subset, idx in subsets.items():
                row = []
                for c in CLASSES:
                    tot = np.sum(
                        [
                            counts(refs[i][c], peaks(acts[name][i][c], thresholds[name][c]), window)
                            for i in idx
                        ],
                        axis=0,
                    )
                    row.append(f"{c} {f_measure(*tot):.2f} (n={tot[0] + tot[2]})")
                print(f"  ±{window * 1000:.0f} ms {subset:9}: " + ", ".join(row))
        print("  thresholds:", {c: round(float(t), 3) for c, t in thresholds[name].items()})


def _trained_thresholds() -> dict[str, float]:
    import json

    return dict(json.loads((TRAINED_ONNX.with_suffix(".json")).read_text())["thresholds"])


if __name__ == "__main__":
    main()
