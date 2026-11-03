"""M0-5 spike: run one beat tracker over the spike clips and save its predictions.

    python track.py beat_this final0   # spike-venv (Python 3.12, PyTorch CPU)
    python track.py beat_this small0
    python track.py librosa            # spike-venv
    python track.py madmom             # madmom-venv (Python 3.9, madmom 0.16.1 from PyPI)

Writes ~/drumtx-data/spike5/<tracker>.json: {clip_id: {beats, downbeats, seconds}}.
Python 3.9-compatible on purpose (madmom 0.16.1 does not install on newer versions).
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

DATA = Path.home() / "drumtx-data"
REPO = Path(__file__).resolve().parents[2]


def clips() -> list[dict[str, str]]:
    """Development clips with beat annotations: all of MDB Drums, plus 10 E-GMD grooves."""
    rows = [r for r in csv.DictReader((REPO / "eval" / "dev.csv").open()) if r["beats"] == "1"]
    egmd = [r for r in rows if r["source"] == "E-GMD"]
    return [r for r in rows if r["source"] == "MDB Drums"] + egmd[:: max(1, len(egmd) // 10)][:10]


def beat_this(checkpoint: str):  # type: ignore[no-untyped-def]
    from beat_this.inference import File2Beats

    f2b = File2Beats(checkpoint_path=checkpoint, device="cpu", dbn=False)
    return lambda path: tuple(map(list, f2b(str(path))))


def madmom_tracker():  # type: ignore[no-untyped-def]
    from madmom.features.downbeats import DBNDownBeatTrackingProcessor, RNNDownBeatProcessor

    rnn = RNNDownBeatProcessor()
    dbn = DBNDownBeatTrackingProcessor(beats_per_bar=[3, 4], fps=100)

    def run(path):  # type: ignore[no-untyped-def]
        out = dbn(rnn(str(path)))
        return [float(t) for t, _ in out], [float(t) for t, n in out if n == 1]

    return run


def librosa_tracker():  # type: ignore[no-untyped-def]
    import librosa

    def run(path):  # type: ignore[no-untyped-def]
        y, sr = librosa.load(str(path), sr=22050)
        _, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
        return [float(t) for t in beats], []  # no downbeats; evaluate.py adds them from the meter

    return run


if __name__ == "__main__":
    name = sys.argv[1]
    if name == "beat_this":
        name, run = f"beat_this_{sys.argv[2]}", beat_this(sys.argv[2])
    else:
        run = {"madmom": madmom_tracker, "librosa": librosa_tracker}[name]()
    out = {}
    for r in clips():
        t0 = time.perf_counter()
        beats, downbeats = run(DATA / r["audio"])
        out[r["clip_id"]] = {
            "beats": beats,
            "downbeats": downbeats,
            "seconds": time.perf_counter() - t0,
        }
        print(r["clip_id"], len(beats), f"{out[r['clip_id']]['seconds']:.1f}s", flush=True)
    (DATA / "spike5").mkdir(exist_ok=True)
    (DATA / "spike5" / f"{name}.json").write_text(json.dumps(out))
