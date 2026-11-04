"""Benchmark a detector on the evaluation corpus (M1-6, decision 0010).

    uv run python scripts/benchmark.py                          # development set
    uv run python scripts/benchmark.py --compare eval/results/baseline-dev.json
    uv run python scripts/benchmark.py --split test --release   # M2-7 and M7-4 only (decision 0004)
    uv run python scripts/benchmark.py --tune                   # best baseline thresholds
    uv run python scripts/benchmark.py --model adtof --compare eval/results/baseline-dev.json
    uv run python scripts/benchmark.py --model adtof --tune     # rewrites the model's presets
    python scripts/benchmark.py --model adtof --subset full-mix --separate  # needs the extra

Writes JSON and a Markdown table (default eval/results/<model>-<split>.json and .md) with the
commit, model ID, runtime, and P/R/F per preset, subset, tolerance and class. With --compare, every
F-measure that dropped by more than --margin is listed as a regression and the exit code is 1.
Reads the corpus from DATA (decision 0004); audio hashes are checked against the manifest.
"""

import argparse
import csv
import datetime
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import mir_eval
import numpy as np
import soundfile as sf
import soxr

from drumtx import detect, features, models
from drumtx.evaluate import match_counts, scores
from drumtx.ingest import SAMPLE_RATE, AudioBuffer
from drumtx.schema import CLASSES, DrumClass
from drumtx.separate import isolate_drums

REPO = Path(__file__).resolve().parents[1]
PRESETS: tuple[detect.Preset, ...] = ("strict", "balanced", "sensitive")
SUBSETS = ("drum-only", "full-mix", "all")
TOLERANCES = (0.05, 0.03)
# The learned model comes from the model directory, downloaded on first use (drumtx.models).
MODELS: dict[str, Callable[[Path], detect.Detector]] = {
    "baseline": lambda data: detect.BaselineDetector(),
    "adtof": lambda data: detect.ModelDetector(models.get_model("adtof", offline=False)),
}


def load(path: Path, sha256: str) -> AudioBuffer:
    """Like ingest.load_audio without its 2-second minimum (some corpus clips are shorter)."""
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        sys.exit(f"{path} does not match the manifest; rebuild the corpus (decision 0004).")
    y, rate = sf.read(path, dtype="float32", always_2d=True)
    if rate != SAMPLE_RATE:
        y = soxr.resample(y, rate, SAMPLE_RATE)
    return AudioBuffer(y, 0.0, len(y) / SAMPLE_RATE)


def reference(data: Path, clip_id: str, column: str = "time_s") -> dict[DrumClass, np.ndarray]:
    rows = list(csv.DictReader((data / "corpus" / f"{clip_id}.onsets.csv").open()))
    return {c: np.array([float(r[column]) for r in rows if r["class"] == c]) for c in CLASSES}


def rounded(counts: np.ndarray) -> dict[str, float | int]:
    return {k: round(v, 3) for k, v in scores(*(int(n) for n in counts)).items()}


def commit() -> str:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO
        ).stdout.strip()
        return head.stdout.strip() + ("+dirty" if dirty else "")
    except OSError:
        return "unknown"


def tune(buffers: dict[str, AudioBuffer], refs: dict[str, dict[DrumClass, np.ndarray]]) -> None:
    acts = {k: detect.baseline_activations(b.mono) for k, b in buffers.items()}
    for c in CLASSES:

        def f(t: float, c: DrumClass = c) -> float:
            peaks = {k: detect.pick_peaks(a[c], t) / detect.FPS for k, a in acts.items()}
            tot = np.sum([match_counts(refs[k][c], peaks[k], 0.05) for k in acts], axis=0)
            return float(scores(*(int(n) for n in tot))["f"])

        best = max(np.round(np.geomspace(0.005, 0.5, 41), 4), key=f)
        print(f"{c:7} best balanced threshold {best:.4f}  F {f(best):.3f}")


# Model preset tuning (M2-3): F-beta per preset, threshold grid, minimum-gap candidates.
BETA: dict[detect.Preset, float] = {"strict": 0.5, "balanced": 1.0, "sensitive": 2.0}
GRID = [float(t) for t in np.round(np.geomspace(0.01, 0.8, 39), 4)]
GAPS = (0.02, 0.03, 0.04, 0.05)
Counts = dict[tuple[float, str, float, str], np.ndarray]  # (gap, class, threshold, subset)


def f_beta(counts: np.ndarray, beta: float) -> float:
    tp, fp, fn = (int(n) for n in counts)
    b2 = beta * beta
    return (1 + b2) * tp / ((1 + b2) * tp + b2 * fn + fp) if tp else 0.0


def choose_presets(counts: Counts) -> dict[str, Any]:
    """Thresholds per preset and class, and one minimum gap, from dev-set counts.

    A threshold maximizes F-beta (0.5 for strict, 1 for balanced, 2 for sensitive), averaged over
    the drum-only and full-mix subsets so that neither dominates (decision 0004). Toms use
    drum-only alone: full-mix toms are too few to tune on (decision 0010). The gap maximizes the
    summed balanced scores; the smallest wins a tie.
    """

    def score(gap: float, c: str, t: float, beta: float) -> float:
        subsets = ("drum-only",) if c == "tom" else ("drum-only", "full-mix")
        return sum(f_beta(counts[(gap, c, t, s)], beta) for s in subsets) / len(subsets)

    gap = max(GAPS, key=lambda g: sum(max(score(g, c, t, 1) for t in GRID) for c in CLASSES))
    thresholds = {
        p: {c: max(GRID, key=lambda t: score(gap, c, t, b)) for c in detect.MODEL_ORDER}
        for p, b in BETA.items()
    }
    return {"min_gap_s": gap, "thresholds": thresholds}


def match_events(ref: np.ndarray, est: np.ndarray, tolerance_s: float) -> list[tuple[int, int]]:
    """(reference index, estimate index) pairs, as in match_counts."""
    return mir_eval.util.match_events(ref, est, tolerance_s) if len(ref) and len(est) else []


def fit_logistic(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """(b0, b1) maximizing the likelihood of labels y under sigmoid(b0 + b1 x): Newton's method."""
    xs = np.stack([np.ones_like(x), x], axis=1)
    w = np.zeros(2)
    for _ in range(100):
        p = 1 / (1 + np.exp(-xs @ w))
        hessian = (xs * (p * (1 - p))[:, None]).T @ xs + 1e-6 * np.eye(2)
        w += np.linalg.solve(hessian, xs.T @ (y - p))
    return float(w[0]), float(w[1])


def quantile_map(a: np.ndarray, v: np.ndarray) -> dict[str, list[float]]:
    """Matching quantiles of activations and reference velocities: a monotone mapping that keeps
    the reference's spread (a regression would squeeze velocities toward the mean)."""
    q = np.linspace(0, 1, 11)
    return {
        "activation": [round(float(x), 4) for x in np.quantile(a, q)],
        "velocity": [round(float(x), 1) for x in np.quantile(v, q)],
    }


def reliability(conf: np.ndarray, hit: np.ndarray) -> list[tuple[str, int, float]]:
    """(confidence bin, detections, precision) for bins 0–0.2, …, 0.8–1."""
    edges = np.linspace(0, 1, 6)
    idx = np.minimum(np.digitize(conf, edges) - 1, 4)
    return [
        (f"{edges[i]:.1f}–{edges[i + 1]:.1f}", int((idx == i).sum()), float(hit[idx == i].mean()))
        for i in range(5)
        if (idx == i).any()
    ]


def calibrate(
    acts: dict[str, dict[DrumClass, np.ndarray]],
    refs: dict[str, dict[DrumClass, np.ndarray]],
    velocities: dict[str, dict[DrumClass, np.ndarray]],
    presets: dict[str, Any],
) -> None:
    """Fit confidence and velocity per class from the `sensitive` detections (M2-4).

    Confidence: logistic regression of "matches a reference hit within 50 ms" on the activation's
    logit, over all clips. Velocity: quantile mapping on matched E-GMD hits, the only source with
    recorded velocities. Adds both to `presets` and prints the reliability table.
    """
    presets["confidence"], presets["velocity"] = {}, {}
    rows = []
    for c in detect.MODEL_ORDER:
        peak, hit, a_vel, v_vel = [], [], [], []
        for k, a in acts.items():
            frames = detect.pick_peaks(
                a[c], presets["thresholds"]["sensitive"][c], presets["min_gap_s"]
            )
            pairs = dict(match_events(refs[k][c], frames / detect.FPS, 0.05))
            matched = {j: i for i, j in pairs.items()}
            peak += a[c][frames].tolist()
            hit += [j in matched for j in range(len(frames))]
            if k in velocities:
                a_vel += [float(a[c][f]) for j, f in enumerate(frames) if j in matched]
                v_vel += [velocities[k][c][matched[j]] for j in range(len(frames)) if j in matched]
        x, y = detect.logit(np.array(peak)), np.array(hit, dtype=float)
        b0, b1 = fit_logistic(x, y)
        presets["confidence"][c] = [round(b0, 4), round(b1, 4)]
        presets["velocity"][c] = quantile_map(np.array(a_vel), np.array(v_vel))
        conf = 1 / (1 + np.exp(-(b0 + b1 * x)))
        rows += [(c, *row) for row in reliability(conf, y)]
    print("| Class | Confidence | Detections | Precision |\n|---|---|---|---|")
    print("\n".join(f"| {c} | {b} | {n} | {p:.2f} |" for c, b, n, p in rows))


def tune_model(
    detector: detect.ModelDetector,
    buffers: dict[str, AudioBuffer],
    refs: dict[str, dict[DrumClass, np.ndarray]],
    clips: list[dict[str, str]],
    data: Path,
) -> None:
    """Tune the model's presets on the development set and write them to its presets file."""
    acts = {k: detector.activations(features.spectrogram(b.mono)) for k, b in buffers.items()}
    subsets = {r["clip_id"]: r["subset"] for r in clips}
    counts: Counts = {}
    for gap in GAPS:
        for c in CLASSES:
            for t in GRID:
                for k, a in acts.items():
                    est = detect.pick_peaks(a[c], t, gap) / detect.FPS
                    key = (gap, c, t, subsets[k])
                    counts[key] = counts.get(key, 0) + np.array(match_counts(refs[k][c], est, 0.05))
    presets = choose_presets(counts)
    velocities = {
        r["clip_id"]: reference(data, r["clip_id"], "velocity")
        for r in clips
        if r["source"] == "E-GMD"
    }
    calibrate(acts, refs, velocities, presets)
    detect.MODEL_PRESETS_FILE.write_text(json.dumps(presets, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {detect.MODEL_PRESETS_FILE}:\n{json.dumps(presets, indent=2)}")


def compare(new: dict[str, Any], old: dict[str, Any], margin: float) -> list[str]:
    """Lines for every F-measure that moved by more than `margin`; regressions first."""
    worse, better = [], []
    for preset, tables in new["results"].items():
        for table, per_class in tables.items():
            for c, s in per_class.items():
                try:
                    before = old["results"][preset][table][c]["f"]
                except KeyError:
                    continue
                line = f"{preset:9} {table:22} {c:7} F {before:.3f} → {s['f']:.3f}"
                if s["f"] < before - margin:
                    worse.append("REGRESSION  " + line)
                elif s["f"] > before + margin:
                    better.append("improved    " + line)
    return worse + better


def markdown(result: dict[str, Any]) -> str:
    out = [
        f"# Benchmark: `{result['model']}` on the {result['split']} set",
        "",
        f"- Commit: `{result['commit']}`",
        f"- Date: {result['date']}",
        f"- Clips: {result['clips']} ({result['audio_minutes']:.1f} minutes of audio)",
        f"- Detection runtime: {result['runtime_s']:.1f} s "
        f"({result['s_per_audio_minute']:.2f} s per audio minute, all presets)",
        "",
        "F-measure per class:",
        "",
        "| Preset | Subset @ tolerance | " + " | ".join(CLASSES) + " |",
        "|---|---|" + "---|" * len(CLASSES),
    ]
    for preset, tables in result["results"].items():
        for table, per_class in tables.items():
            cells = " | ".join(f"{per_class[c]['f']:.2f}" for c in CLASSES)
            out.append(f"| {preset} | {table} | {cells} |")
    return "\n".join(out) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--data", type=Path, default=Path.home() / "drumtx-data")
    p.add_argument("--split", choices=("dev", "test"), default="dev")
    p.add_argument("--release", action="store_true", help="required to touch the test set")
    p.add_argument("--model", choices=sorted(MODELS), default="baseline")
    p.add_argument("--out", type=Path, help="results JSON; .md is written beside it")
    p.add_argument("--compare", type=Path, help="previous results JSON")
    p.add_argument("--margin", type=float, default=0.02, help="F-measure drop that counts")
    p.add_argument("--subset", choices=SUBSETS[:2], help="only these clips")
    p.add_argument(
        "--separate", action="store_true", help="isolate drums first (needs drumtx[separation])"
    )
    p.add_argument(
        "--tune",
        action="store_true",
        help="first tune thresholds on the dev set: printed for baseline, written for a model",
    )
    args = p.parse_args()
    if args.tune and (args.split != "dev" or args.subset or args.separate):
        sys.exit("Thresholds are tuned on the whole development set only (M2-3).")
    if args.split == "test" and not args.release:
        sys.exit("The test set is for release evaluation only (M2-7, M7-4); add --release.")

    clips = list(csv.DictReader((REPO / "eval" / f"{args.split}.csv").open()))
    clips = [r for r in clips if args.subset in (None, r["subset"])]
    buffers = {r["clip_id"]: load(args.data / r["audio"], r["audio_sha256"]) for r in clips}
    separation_s = 0.0
    if args.separate:
        start = time.perf_counter()
        buffers = {k: isolate_drums(b, offline=False, device="cpu") for k, b in buffers.items()}
        separation_s = time.perf_counter() - start
    refs = {r["clip_id"]: reference(args.data, r["clip_id"]) for r in clips}
    detector = MODELS[args.model](args.data)
    if args.tune and isinstance(detector, detect.ModelDetector):
        tune_model(detector, buffers, refs, clips, args.data)
        detector = MODELS[args.model](args.data)  # reload with the new presets
    elif args.tune:
        tune(buffers, refs)
    totals: dict[tuple[str, str, str, float, str], np.ndarray] = {}
    start = time.perf_counter()
    for preset in PRESETS:
        for r in clips:
            events = detector.detect(buffers[r["clip_id"]], preset)
            for c in CLASSES:
                est = np.array([e.time_s for e in events if e.cls == c])
                for tol in TOLERANCES:
                    counts = np.array(match_counts(refs[r["clip_id"]][c], est, tol))
                    for subset in (r["subset"], "all"):
                        key = (preset, subset, f"{round(tol * 1000)}", tol, c)
                        totals[key] = totals.get(key, 0) + counts
    runtime = time.perf_counter() - start
    minutes = sum(float(r["duration_s"]) for r in clips) / 60

    result: dict[str, Any] = {
        "model": args.model,
        "split": args.split,
        "commit": commit(),
        "date": datetime.date.today().isoformat(),
        "clips": len(clips),
        "audio_minutes": round(minutes, 2),
        "runtime_s": round(runtime, 1),
        "s_per_audio_minute": round(runtime / minutes / len(PRESETS), 3),
        "separate": args.separate,
        "separation_s_per_audio_minute": round(separation_s / minutes, 2),
        "results": {
            preset: {
                f"{subset} @ {ms} ms": {
                    c: rounded(totals[(preset, subset, ms, tol, c)]) for c in CLASSES
                }
                for subset in SUBSETS
                if subset in (args.subset or subset, "all")  # with --subset: it and "all"
                for tol in TOLERANCES
                for ms in [f"{round(tol * 1000)}"]
            }
            for preset in PRESETS
        },
    }
    name = "-".join([args.model, args.split, *[args.subset] * bool(args.subset)])
    name += "-separate" * args.separate
    out = args.out or REPO / "eval" / "results" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(args.compare.read_text()) if args.compare else None
    out.write_text(json.dumps(result, indent=2) + "\n")
    out.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
    print(markdown(result))
    if previous is not None:
        lines = compare(result, previous, args.margin)
        print(
            f"Compared with {args.compare} (commit {previous.get('commit', 'unknown')}),"
            f" margin {args.margin}:"
        )
        print("\n".join(lines) or "no changes beyond the margin")
        if any(line.startswith("REGRESSION") for line in lines):
            sys.exit(1)


if __name__ == "__main__":
    main()
