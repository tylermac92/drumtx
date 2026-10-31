"""M0-5 spike: score saved beat-tracker predictions against the corpus beat annotations.

python evaluate.py   # spike-venv; reads ~/drumtx-data/spike5/*.json
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import mir_eval
import numpy as np

DATA = Path.home() / "drumtx-data"
REPO = Path(__file__).resolve().parents[2]


def reference(clip_id: str) -> tuple[np.ndarray, np.ndarray, int]:
    rows = list(csv.DictReader((DATA / "corpus" / f"{clip_id}.beats.csv").open()))
    beats = np.array([float(r["time_s"]) for r in rows])
    downbeats = np.array([float(r["time_s"]) for r in rows if r["beat"] == "1"])
    return beats, downbeats, max(int(r["beat"]) for r in rows)


def meter_downbeats(beats: np.ndarray, first_downbeat: float, per_bar: int) -> np.ndarray:
    """Downbeats from a given first downbeat and meter (what --first-downbeat would supply)."""
    k = int(np.argmin(np.abs(beats - first_downbeat)))
    return beats[k % per_bar :: per_bar]


def failure(ref: np.ndarray, est: np.ndarray, beat_f: float, down_f: float) -> str:
    if len(est) < 2:
        return "no beats"
    ratio = np.median(np.diff(est)) / np.median(np.diff(ref))
    if 0.45 < ratio < 0.55:
        return "double tempo"
    if 1.8 < ratio < 2.2:
        return "half tempo"
    if not 0.9 < ratio < 1.1:
        return "other tempo ratio"
    if beat_f < 0.8:
        return "off-beat or unstable"
    if down_f < 0.5:
        return "bar offset"
    return "ok"


def group(row: dict[str, str]) -> str:
    return "E-GMD" if row["source"] == "E-GMD" else f"MDB {row['subset']}"


def main() -> None:
    meta = {r["clip_id"]: r for r in csv.DictReader((REPO / "eval" / "dev.csv").open())}
    for path in sorted((DATA / "spike5").glob("*.json")):
        preds = json.loads(path.read_text())
        scores: dict[str, list[tuple[float, float]]] = defaultdict(list)
        modes: Counter[str] = Counter()
        seconds = minutes = 0.0
        for clip, p in preds.items():
            ref, ref_down, per_bar = reference(clip)
            est = np.array(p["beats"])
            down = (
                np.array(p["downbeats"])
                if p["downbeats"]
                else meter_downbeats(est, ref_down[0], per_bar)
            )
            bf = mir_eval.beat.f_measure(ref, est)  # ±70 ms; no 5 s trimming (clips are short)
            df = mir_eval.beat.f_measure(ref_down, down)
            scores[group(meta[clip])].append((bf, df))
            modes[failure(ref, est, bf, df)] += 1
            seconds += p["seconds"]
            minutes += float(meta[clip]["duration_s"]) / 60
        print(f"== {path.stem}: {seconds / minutes:.2f} s per audio minute")
        for g, s in sorted(scores.items()):
            a = np.array(s)
            print(f" {g:16} n={len(a):2}  beat F {a[:, 0].mean():.3f}  down F {a[:, 1].mean():.3f}")
        print("  failure modes:", dict(modes.most_common()))


if __name__ == "__main__":
    main()
