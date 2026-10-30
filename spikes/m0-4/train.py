"""Train the CRNN from scratch on part of E-GMD's train split, on CPU, within a time budget.

python train.py fetch 300     # download ~300 train performances (one kit each)
python train.py train 30      # train for 30 minutes, tune thresholds, export ONNX + JSON
"""

import csv
import io
import json
import random
import sys
import time
import zipfile

import numpy as np
import torch
from common import CLASSES, DATA, FPS, REPO, counts, f_measure, features, load_audio, peaks
from crnn import CRNN, export_onnx

sys.path.insert(0, str(REPO / "scripts"))
import build_corpus as bc  # noqa: E402

EGMD = DATA / "e-gmd"
CACHE = DATA / "spike-cache"
OUT = DATA / "models" / "spike" / "small_crnn_egmd.onnx"


def fetch(n: int) -> None:
    meta = [r for r in csv.DictReader((EGMD / "e-gmd-v1.0.0.csv").open()) if r["split"] == "train"]
    kits = sorted({r["kit_name"] for r in meta})
    by_id: dict[str, dict[str, dict[str, str]]] = {}
    for r in meta:
        by_id.setdefault(r["id"], {})[r["kit_name"]] = r
    midi_zip = zipfile.ZipFile(EGMD / "e-gmd-v1.0.0-midi.zip")
    remote = zipfile.ZipFile(io.BufferedReader(bc.HttpFile(bc.EGMD_URL), 1 << 20))
    ids = sorted(by_id)
    CACHE.mkdir(parents=True, exist_ok=True)
    for i, pid in enumerate(ids[:: max(1, len(ids) // n)][:n]):
        for j in range(len(kits)):
            r = by_id[pid].get(kits[(i + j) % len(kits)])
            midi = r and bc.mido.MidiFile(
                file=io.BytesIO(midi_zip.read(f"e-gmd-v1.0.0/{r['midi_filename']}"))
            )
            if r and (onsets := bc.egmd_onsets(midi)):
                break
        else:
            continue
        audio = load_audio(io.BytesIO(remote.read(f"e-gmd-v1.0.0/{r['audio_filename']}")))
        y = np.zeros((int(np.ceil(len(audio) / 441)), len(CLASSES)), np.float32)
        for t, c, _ in onsets:
            f = round(t * FPS)
            for d, v in ((0, 1.0), (-1, 0.5), (1, 0.5)):  # one frame of label "radiation"
                if 0 <= f + d < len(y):
                    y[f + d, CLASSES.index(c)] = max(y[f + d, CLASSES.index(c)], v)
        np.savez(CACHE / f"train_{i:04d}.npz", x=features(audio), y=y)
    print("cached", len(list(CACHE.glob("train_*.npz"))), "clips")


def train(minutes: float) -> None:
    torch.manual_seed(0)
    random.seed(0)
    torch.set_num_threads(4)
    files = sorted(CACHE.glob("train_*.npz"))
    held = files[::10]  # 10% for threshold tuning
    data = [np.load(f) for f in files if f not in held]
    data = [(d["x"], d["y"]) for d in data if len(d["x"]) > 50]
    total_min = sum(len(x) for x, _ in data) / FPS / 60
    print(f"training on {len(data)} clips, {total_min:.0f} min of audio")
    model = CRNN()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    seq, batch, step, t0 = 400, 16, 0, time.time()
    weights = [len(x) for x, _ in data]
    while time.time() - t0 < minutes * 60:
        xs, ys = [], []
        for x, y in random.choices(data, weights=weights, k=batch):
            s = random.randrange(max(1, len(x) - seq))
            xp, yp = np.zeros((seq, x.shape[1]), np.float32), np.zeros((seq, 5), np.float32)
            xp[: len(x[s : s + seq])], yp[: len(y[s : s + seq])] = x[s : s + seq], y[s : s + seq]
            xs.append(xp)
            ys.append(yp)
        model.train()
        loss = torch.nn.functional.binary_cross_entropy(
            model(torch.from_numpy(np.stack(xs))), torch.from_numpy(np.stack(ys))
        )
        opt.zero_grad()
        loss.backward()
        opt.step()
        step += 1
        if step % 100 == 0:
            print(
                f"step {step} loss {loss.item():.4f} {(time.time() - t0) / 60:.1f} min", flush=True
            )
    model.eval()
    thresholds = {}
    with torch.no_grad():
        acts = [model(torch.from_numpy(np.load(f)["x"][None]))[0].numpy() for f in held]
    refs = [np.load(f)["y"] for f in held]
    for i, c in enumerate(CLASSES):

        def f(t: float, i: int = i) -> float:
            tot = np.sum(
                [
                    counts(np.nonzero(r[:, i] == 1)[0] / FPS, peaks(a[:, i], t))
                    for a, r in zip(acts, refs, strict=True)
                ],
                axis=0,
            )
            return f_measure(*tot)

        thresholds[c] = float(max(np.arange(0.1, 0.9, 0.025), key=f))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    export_onnx(model, OUT)
    OUT.with_suffix(".json").write_text(
        json.dumps(
            {
                "steps": step,
                "minutes": minutes,
                "train_clips": len(data),
                "train_audio_min": total_min,
                "thresholds": thresholds,
            },
            indent=1,
        )
    )
    print("thresholds", thresholds, "steps", step)


if __name__ == "__main__":
    {"fetch": lambda a: fetch(int(a)), "train": lambda a: train(float(a))}[sys.argv[1]](sys.argv[2])
