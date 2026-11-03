"""Score BaselineDetector on the development set and record the regression floor (M1-3).

    uv run python scripts/eval_baseline.py          # writes eval/results/baseline-dev.json
    uv run python scripts/eval_baseline.py --tune   # first prints the best `balanced` thresholds

Reads the corpus from ~/drumtx-data (decision 0004). Superseded by the benchmark runner (M1-6).
"""

import argparse
import csv
import json
from pathlib import Path

import mir_eval
import numpy as np
import soundfile as sf
import soxr

from drumtx import detect
from drumtx.ingest import SAMPLE_RATE, AudioBuffer
from drumtx.schema import CLASSES, DrumClass

DATA = Path.home() / "drumtx-data"
REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "eval" / "results" / "baseline-dev.json"
TOLERANCES = (0.05, 0.03)


def load(path: Path) -> AudioBuffer:
    """Like ingest.load_audio, but without its 2-second minimum: some corpus clips are shorter."""
    y, rate = sf.read(path, dtype="float32", always_2d=True)
    if rate != SAMPLE_RATE:
        y = soxr.resample(y, rate, SAMPLE_RATE)
    return AudioBuffer(y, 0.0, len(y) / SAMPLE_RATE)


def reference(clip_id: str) -> dict[str, np.ndarray]:
    rows = list(csv.DictReader((DATA / "corpus" / f"{clip_id}.onsets.csv").open()))
    return {c: np.array([float(r["time_s"]) for r in rows if r["class"] == c]) for c in CLASSES}


def counts(ref: np.ndarray, est: np.ndarray, tol: float) -> np.ndarray:
    tp = len(mir_eval.util.match_events(ref, est, tol)) if len(ref) and len(est) else 0
    return np.array([tp, len(est) - tp, len(ref) - tp])


def scores(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    p, r = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "p": round(p, 3),
        "r": round(r, 3),
        "f": round(2 * tp / max(2 * tp + fp + fn, 1), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tune", action="store_true")
    args = parser.parse_args()
    clips = list(csv.DictReader((REPO / "eval" / "dev.csv").open()))
    buffers = {r["clip_id"]: load(DATA / r["audio"]) for r in clips}
    refs = {r["clip_id"]: reference(r["clip_id"]) for r in clips}

    if args.tune:
        acts = {k: detect.baseline_activations(b.mono) for k, b in buffers.items()}
        for c in CLASSES:

            def f(t: float, c: DrumClass = c) -> float:
                tot = np.sum(
                    [
                        counts(refs[k][c], detect.pick_peaks(a[c], t) / detect.FPS, 0.05)
                        for k, a in acts.items()
                    ],
                    axis=0,
                )
                return float(scores(*(int(v) for v in tot))["f"])

            grid = np.round(np.geomspace(0.005, 0.5, 41), 4)
            best = max(grid, key=f)
            print(f"{c:7} best balanced threshold {best:.4f}  F {f(best):.3f}")

    result: dict[str, object] = {
        "detector": "baseline",
        "split": "dev",
        "thresholds": detect.THRESHOLDS,
        "results": {},
    }
    detector = detect.BaselineDetector()
    presets: tuple[detect.Preset, ...] = ("strict", "balanced", "sensitive")
    for preset in presets:
        tot: dict[tuple[str, float, str], np.ndarray] = {}  # (subset, tolerance, class)
        for r in clips:
            events = detector.detect(buffers[r["clip_id"]], preset)
            for c in CLASSES:
                est = np.array([e.time_s for e in events if e.cls == c])
                for tol in TOLERANCES:
                    for subset in (r["subset"], "all"):
                        key = (subset, tol, c)
                        tot[key] = tot.get(key, 0) + counts(refs[r["clip_id"]][c], est, tol)
        result["results"][preset] = {  # type: ignore[index]
            f"{subset} @ {round(tol * 1000)} ms": {
                c: scores(*(int(v) for v in tot[(subset, tol, c)])) for c in CLASSES
            }
            for subset in ("drum-only", "full-mix", "all")
            for tol in TOLERANCES
        }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    for name, table in result["results"]["balanced"].items():  # type: ignore[index]
        print(f"balanced {name:22}", "  ".join(f"{c} {s['f']:.2f}" for c, s in table.items()))


if __name__ == "__main__":
    main()
