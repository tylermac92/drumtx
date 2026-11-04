"""Compare drumtx.beats with the upstream `beat_this` package (M3-1, decision 0006).

    BEAT_THIS_PYTHON scripts/check_beats.py dump OUT.json      # env with beat-this 1.1.0, torch
    uv run python scripts/check_beats.py compare OUT.json

Both run the development rhythm subset (eval/dev.csv rows with beat annotations). `dump` saves the
upstream beats and downbeats (final0, minimal postprocessing); `compare` runs ours and counts the
beats and downbeats that are more than one frame (20 ms) from upstream's.
"""

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = Path.home() / "drumtx-data"
FRAME_S = 0.02


def clips() -> list[dict[str, str]]:
    rows = csv.DictReader((REPO / "eval" / "dev.csv").open())
    return [r for r in rows if r["beats"] == "1"]


def dump(out: str) -> None:
    from beat_this.inference import File2Beats

    f2b = File2Beats(checkpoint_path="final0", device="cpu", dbn=False)
    result = {}
    for r in clips():
        beats, downbeats = f2b(str(DATA / r["audio"]))
        result[r["clip_id"]] = {"beats": beats.tolist(), "downbeats": downbeats.tolist()}
        print(r["clip_id"], len(beats), flush=True)
    Path(out).write_text(json.dumps(result))


def compare(path: str) -> None:
    import numpy as np
    import soundfile as sf
    import soxr

    from drumtx import beats, models
    from drumtx.ingest import SAMPLE_RATE

    upstream = json.loads(Path(path).read_text())
    tracker = beats.BeatTracker(models.get_model("beat-this-final0", offline=False))
    off = {"beats": 0, "downbeats": 0}
    total = {"beats": 0, "downbeats": 0}
    worst = 0.0
    for r in clips():
        y, rate = sf.read(DATA / r["audio"], dtype="float32", always_2d=True)
        y = y.mean(axis=1)
        if rate != SAMPLE_RATE:
            y = soxr.resample(y, rate, SAMPLE_RATE)
        ours = dict(zip(("beats", "downbeats"), tracker.track(y), strict=True))
        for key in off:
            theirs = np.array(upstream[r["clip_id"]][key])
            mine = ours[key]
            total[key] += max(len(theirs), len(mine))
            if len(mine) != len(theirs):
                off[key] += abs(len(mine) - len(theirs))
                print(f"{r['clip_id']} {key}: {len(mine)} vs upstream {len(theirs)}")
                continue
            if len(mine):
                diff = np.abs(mine - theirs)
                worst = max(worst, float(diff.max()))
                off[key] += int(np.sum(diff > FRAME_S + 1e-9))
    print(f"{len(clips())} clips; largest difference {worst * 1000:.0f} ms")
    for key in off:
        print(f"{key}: {off[key]} of {total[key]} more than one frame from upstream")


if __name__ == "__main__":
    {"dump": dump, "compare": compare}[sys.argv[1]](sys.argv[2])
