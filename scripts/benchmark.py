"""Benchmark a detector on the evaluation corpus (M1-6, decision 0010).

    uv run python scripts/benchmark.py                          # development set
    uv run python scripts/benchmark.py --compare eval/results/baseline-dev.json
    uv run python scripts/benchmark.py --split test --release   # M2-7 and M7-4 only (decision 0004)
    uv run python scripts/benchmark.py --tune                   # best baseline thresholds
    uv run python scripts/benchmark.py --model adtof --compare eval/results/baseline-dev.json

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

import numpy as np
import soundfile as sf
import soxr

from drumtx import detect
from drumtx.evaluate import match_counts, scores
from drumtx.ingest import SAMPLE_RATE, AudioBuffer
from drumtx.schema import CLASSES, DrumClass

REPO = Path(__file__).resolve().parents[1]
PRESETS: tuple[detect.Preset, ...] = ("strict", "balanced", "sensitive")
SUBSETS = ("drum-only", "full-mix", "all")
TOLERANCES = (0.05, 0.03)
# Model files are made by scripts/convert_adtof.py under DATA until M2-5 adds the model directory.
MODELS: dict[str, Callable[[Path], detect.Detector]] = {
    "baseline": lambda data: detect.BaselineDetector(),
    "adtof": lambda data: detect.ModelDetector(data / "models/adtof/frame_rnn_adtof_all_0.onnx"),
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


def reference(data: Path, clip_id: str) -> dict[DrumClass, np.ndarray]:
    rows = list(csv.DictReader((data / "corpus" / f"{clip_id}.onsets.csv").open()))
    return {c: np.array([float(r["time_s"]) for r in rows if r["class"] == c]) for c in CLASSES}


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
    p.add_argument("--tune", action="store_true", help="print the best baseline thresholds first")
    args = p.parse_args()
    if args.split == "test" and not args.release:
        sys.exit("The test set is for release evaluation only (M2-7, M7-4); add --release.")

    clips = list(csv.DictReader((REPO / "eval" / f"{args.split}.csv").open()))
    buffers = {r["clip_id"]: load(args.data / r["audio"], r["audio_sha256"]) for r in clips}
    refs = {r["clip_id"]: reference(args.data, r["clip_id"]) for r in clips}
    if args.tune:
        tune(buffers, refs)

    detector = MODELS[args.model](args.data)
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
        "results": {
            preset: {
                f"{subset} @ {ms} ms": {
                    c: rounded(totals[(preset, subset, ms, tol, c)]) for c in CLASSES
                }
                for subset in SUBSETS
                for tol in TOLERANCES
                for ms in [f"{round(tol * 1000)}"]
            }
            for preset in PRESETS
        },
    }
    out = args.out or REPO / "eval" / "results" / f"{args.model}-{args.split}.json"
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
