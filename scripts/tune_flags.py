"""Tune the review flag thresholds on the development set (M5-4, decision 0013).

    uv run python scripts/tune_flags.py [--data DIR] [--cache FILE]

Each development clip is transcribed as `transcribe` does with the defaults: ADTOF `balanced`
detections, quantized on the tracked beats (the meter from the reference beats, as in
benchmark.py, else 4/4). In each measure, these hits are wrong:
- extra: a detected hit that matches no reference hit of its class within 50 ms;
- missed: a reference hit that matches no detected hit (a wrong class is one of each);
- misplaced: on clips with a reference score (E-GMD), a matched hit at another beat, grid or slot.
  The measure number is not compared: a wrong downbeat moves every bar, and is fixed once for the
  whole piece (`--first-downbeat`), not measure by measure.

A measure is *erroneous* when at least --min-wrong of its hits (matched, extra and missed) are
wrong. Nearly every measure has some wrong hit, mostly missed quiet notes (decision 0005), so
"any wrong hit" would make any flag look precise. Every combination of thresholds is scored by
the share of all measures flagged and the share of erroneous measures flagged. Prints Markdown
tables. Detections and beats are cached in --cache.
"""

import argparse
import csv
import itertools
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, get_args

import numpy as np
from benchmark import REPO, load, reference

from drumtx import beats, detect, models, pipeline, review
from drumtx import evaluate as ev
from drumtx.quantize import quantize
from drumtx.schema import CLASSES, MeasureFlag, QuantizedScore, event_from_json, event_to_json

CONFIDENCE = (0.0, 0.2, 0.3, 0.4, 0.5, 0.6)  # 0: the uncertain flag is off
RESIDUAL = (0.2, 0.25, 0.3, 0.35, 0.4, 0.45)
OFF_GRID_EVENTS = (0, 1, 2, 3, 4, 1000)  # 1000: off
TEMPO = (0.05, 0.08, 0.12, 0.2, 1000.0)  # 1000: off
ERRORS = ("extra", "missed", "misplaced")
OLD = review.Thresholds(0.5, 0.25, 1, 0.08)  # the M3-3 first estimates


@dataclass
class Measures:
    """One row per measure of every clip."""

    min_conf: np.ndarray  # lowest confidence of its hits; 1.0 when it has none
    off_grid: dict[float, np.ndarray]  # residual threshold -> number of hits beyond it
    tempo: np.ndarray  # |mean beat length / median - 1|
    merged: np.ndarray  # bool
    errors: dict[str, np.ndarray]  # error type -> number of wrong hits
    size: np.ndarray  # hits: matched, extra and missed


def transcribe(clips: list[dict[str, str]], data: Path, cache: Path) -> dict[str, Any]:
    done = json.loads(cache.read_text()) if cache.exists() else {}
    detector = detect.ModelDetector(models.get_model("adtof", offline=False))
    for r in clips:
        if r["clip_id"] not in done:
            audio = load(data / r["audio"], r["audio_sha256"])
            events = detector.detect(audio, "balanced")
            done[r["clip_id"]] = {
                "events": [event_to_json(e) for e in events],
                **pipeline.track_beats(audio, offline=False),
            }
            cache.write_text(json.dumps(done))
    return done


def clip_measures(
    r: dict[str, str], cached: dict[str, Any], data: Path
) -> tuple[QuantizedScore, dict[str, Any]]:
    """The unflagged score, and per measure (lo..hi) its features and errors."""
    base = data / "corpus" / r["clip_id"]
    per_bar = 4
    if r["beats"] == "1":
        per_bar = max(b for _, b in ev._read_beats(base.with_name(base.name + ".beats.csv")))
    tm = beats.tempo_map(
        np.array(cached["beats"]), np.array(cached["downbeats"]), per_bar,
        time_signature_given=True,
    )  # fmt: skip
    score = quantize([event_from_json(e) for e in cached["events"]], tm)
    placed = [(e, q) for e in score.events if (q := e.quantized)]
    lo = min([1, *(q.measure for _, q in placed)])
    hi = max([b.measure for b in tm.beats] + [q.measure for _, q in placed])
    starts = np.array([review.measure_times(tm, m)[0] for m in range(lo, hi + 1)])

    def at(t: float) -> int:
        return lo + max(0, int(np.searchsorted(starts, t, side="right")) - 1)

    n = hi - lo + 1
    errors = {k: np.zeros(n, int) for k in ERRORS}
    size = np.zeros(n, int)
    if r["score"] == "1":
        ref = ev.load_score(base.with_name(base.name + ".score.csv"))
    else:
        ref = ev.Track(reference(data, r["clip_id"]))
    for c in CLASSES:
        est = [(e, q) for e, q in placed if e.cls == c]
        pairs = dict(ev.match_events(ref.onsets[c], np.array([e.time_s for e, _ in est]), 0.05))
        matched = set(pairs.values())
        for j, (_, q) in enumerate(est):
            size[q.measure - lo] += 1
            if j not in matched:
                errors["extra"][q.measure - lo] += 1
        for i, t in enumerate(ref.onsets[c]):
            if i not in pairs:
                errors["missed"][min(at(t), hi) - lo] += 1
                size[min(at(t), hi) - lo] += 1
            elif ref.places and (want := ref.places[c][i]) is not None:
                q = est[pairs[i]][1]
                got = ev.place(q.measure, q.beat, q.grid, q.slot)
                if got is None or got[1:] != want[1:]:
                    errors["misplaced"][q.measure - lo] += 1

    min_conf = np.ones(n)
    fracs: list[list[float]] = [[] for _ in range(n)]
    merged = np.zeros(n, bool)
    for e, q in placed:
        min_conf[q.measure - lo] = min(min_conf[q.measure - lo], e.confidence)
        fracs[q.measure - lo].append(abs(q.residual_frac))
        merged[q.measure - lo] |= "merged" in e.flags
    tempo = np.zeros(n)
    times = np.array([b.time_s for b in tm.beats])
    if len(times) > 1:
        length = np.diff(times)
        median = float(np.median(length))
        for m in range(lo, hi + 1):
            mine = [d for b, d in zip(tm.beats, length, strict=False) if b.measure == m]
            if mine:
                tempo[m - lo] = abs(np.mean(mine) / median - 1)
    features = {
        "min_conf": min_conf,
        "off_grid": {x: np.array([sum(f > x for f in fs) for fs in fracs]) for x in RESIDUAL},
        "tempo": tempo,
        "merged": merged,
        "errors": errors,
        "size": size,
        "lo": lo,
    }
    return score, features


def flagged(m: Measures, th: review.Thresholds, use_merged: bool) -> np.ndarray:
    """The same rule as review.flag, on the precomputed features."""
    out = (m.min_conf < th.confidence) | (m.off_grid[th.residual_frac] > th.off_grid_events)
    out |= m.tempo > th.tempo
    return out | m.merged if use_merged else out


def erroneous(m: Measures, min_wrong: float) -> np.ndarray:
    wrong = np.sum([m.errors[k] for k in ERRORS], axis=0)
    out: np.ndarray = (wrong > 0) & (wrong >= min_wrong * np.maximum(m.size, 1))
    return out


def summary(flags: np.ndarray, m: Measures, wrong: np.ndarray) -> dict[str, float]:
    out = {
        "flagged": float(flags.mean()),
        "recall": float((flags & wrong).sum() / wrong.sum()),
        "precision": float((flags & wrong).sum() / max(1, flags.sum())),
    }
    for k in ERRORS:
        has = wrong & (m.errors[k] > 0)
        out[f"recall_{k}"] = float((flags & has).sum() / max(1, has.sum()))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--data", type=Path, default=Path.home() / "drumtx-data")
    p.add_argument("--cache", type=Path, default=Path.home() / "drumtx-data" / "flags-cache.json")
    p.add_argument("--min-wrong", type=float, default=0.5, help="share of a measure's hits")
    args = p.parse_args()
    clips = list(csv.DictReader((REPO / "eval" / "dev.csv").open()))
    done = transcribe(clips, args.data, args.cache)

    rows, sources = [], []
    for r in clips:
        cached = done[r["clip_id"]]
        if len(cached["beats"]) < 2:
            continue
        score, f = clip_measures(r, cached, args.data)
        # Self-check: the features give the flags review.flag gives, at the defaults.
        th = review.DEFAULT
        expect = {x.measure for x in review.flag(score, th).measure_flags} & set(
            range(f["lo"], f["lo"] + len(f["tempo"]))
        )
        one = Measures(
            f["min_conf"], f["off_grid"], f["tempo"], f["merged"], f["errors"], f["size"]
        )
        got = {f["lo"] + i for i in np.flatnonzero(flagged(one, th, True))}
        assert got == expect, (r["clip_id"], got ^ expect)
        rows.append(one)
        sources += [f"{r['source']}, {r['subset']}"] * len(one.tempo)
    m = Measures(
        np.concatenate([x.min_conf for x in rows]),
        {k: np.concatenate([x.off_grid[k] for x in rows]) for k in RESIDUAL},
        np.concatenate([x.tempo for x in rows]),
        np.concatenate([x.merged for x in rows]),
        {k: np.concatenate([x.errors[k] for x in rows]) for k in ERRORS},
        np.concatenate([x.size for x in rows]),
    )
    print(f"{len(rows)} clips, {len(m.tempo)} measures. Share erroneous, by --min-wrong:")
    for x in (0.0, 0.1, 0.25, 0.5):
        print(f"- {x:.0%}: {erroneous(m, x).mean():.0%}")
    wrong = erroneous(m, args.min_wrong)
    print(f"\nWith --min-wrong {args.min_wrong:.0%}:")

    def line(name: str, s: dict[str, float]) -> str:
        cells = [s["flagged"], s["recall"], s["precision"], *(s[f"recall_{k}"] for k in ERRORS)]
        return f"| {name} | " + " | ".join(f"{x:.0%}" for x in cells) + " |"

    header = (
        "| Thresholds | Measures flagged | Erroneous flagged | Flagged that are erroneous | "
        + " | ".join(f"{k.capitalize()} flagged" for k in ERRORS)
        + " |\n|---|---|---|---|---|---|---|"
    )
    off = review.Thresholds(0.0, 0.25, 1000, 1000.0)
    d = review.DEFAULT
    rows_ = [
        ("none (base rate)", np.ones_like(wrong)),
        ("uncertain < 0.5 alone", flagged(m, replace(off, confidence=0.5), False)),
        ("off-grid > 1 at 0.25 alone", flagged(m, replace(off, off_grid_events=1), False)),
        ("tempo > 8% alone", flagged(m, replace(off, tempo=0.08), False)),
        ("merged alone", flagged(m, off, True)),
        ("old defaults (M3-3): 0.5, 0.25, > 1, 0.08, merged", flagged(m, OLD, True)),
        (
            f"new defaults: {d.confidence}, {d.residual_frac}, > {d.off_grid_events}, "
            f"{d.tempo}, merged",
            flagged(m, d, True),
        ),
    ]
    print("\nEach flag alone, and the defaults:\n\n" + header)
    for name, flags in rows_:
        print(line(name, summary(flags, m, wrong)))

    print("\nBy source, with the new defaults:\n")
    print("| Source | Measures | Flagged | Erroneous | Erroneous flagged |\n|---|---|---|---|---|")
    labels, new = np.array(sources), flagged(m, d, True)
    for src in sorted(set(sources)):
        i = labels == src
        caught = (new & wrong)[i].sum() / max(1, wrong[i].sum())
        print(
            f"| {src} | {i.sum():,} | {new[i].mean():.0%} | {wrong[i].mean():.0%} | {caught:.0%} |"
        )

    results = []
    for c, r_, k, t, mg in itertools.product(
        CONFIDENCE, RESIDUAL, OFF_GRID_EVENTS, TEMPO, (True, False)
    ):
        th = review.Thresholds(c, r_, k, t)
        results.append((th, mg, summary(flagged(m, th, mg), m, wrong)))
    print("\nBest recall for each cap on the share of measures flagged:\n\n" + header)
    for cap in (0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5):
        th, mg, s = max(
            (x for x in results if x[2]["flagged"] <= cap), key=lambda x: x[2]["recall"]
        )
        name = (
            f"≤ {cap:.0%}: confidence {th.confidence}, residual {th.residual_frac}, "
            f"off-grid > {th.off_grid_events}, tempo {th.tempo}, merged {'on' if mg else 'off'}"
        )
        print(line(name, s))
    assert set(get_args(MeasureFlag)) == {"uncertain", "off_grid", "tempo", "merged"}


if __name__ == "__main__":
    main()
