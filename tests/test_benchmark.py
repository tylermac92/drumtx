"""M1-6 to M2-4: the benchmark's regression comparison, preset tuning and calibration."""

from typing import Any

import numpy as np
import pytest
from benchmark import (
    GAPS,
    GRID,
    Counts,
    choose_presets,
    compare,
    f_beta,
    fit_logistic,
    markdown,
    quantile_map,
    reliability,
)

from drumtx.schema import CLASSES


def result(f: float, commit: str = "abc") -> dict[str, Any]:
    scores = {"tp": 1, "fp": 0, "fn": 0, "p": 1.0, "r": 1.0, "f": f}
    return {"results": {"balanced": {"all @ 50 ms": {"kick": scores, "snare": dict(scores)}}}}


@pytest.mark.parametrize(
    ("before", "after", "first"),
    [(0.80, 0.77, "REGRESSION"), (0.80, 0.79, None), (0.80, 0.83, "improved"), (0.80, 0.82, None)],
)
def test_compare_margin(before: float, after: float, first: str | None) -> None:
    lines = compare(result(after), result(before), margin=0.02)
    if first is None:
        assert lines == []
    else:
        assert len(lines) == 2 and all(line.startswith(first) for line in lines)
        assert f"F {before:.3f} → {after:.3f}" in lines[0]


def test_compare_skips_new_entries() -> None:
    new = result(0.5)
    new["results"]["strict"] = new["results"]["balanced"]  # not in the old file
    assert len(compare(new, result(0.9), margin=0.02)) == 2  # only the shared preset


def test_markdown() -> None:
    r = {
        "model": "baseline", "split": "dev", "commit": "abc", "date": "2026-11-03", "clips": 1,
        "audio_minutes": 2.0, "runtime_s": 3.0, "s_per_audio_minute": 0.5,
        "results": {"balanced": {"all @ 50 ms": {
            c: {"f": 0.5} for c in ("kick", "snare", "hihat", "tom", "cymbal")
        }}},
    }  # fmt: skip
    assert "| balanced | all @ 50 ms | 0.50 | 0.50 | 0.50 | 0.50 | 0.50 |" in markdown(r)


def test_f_beta() -> None:
    assert f_beta(np.array([5, 5, 5]), 1.0) == pytest.approx(0.5)
    assert f_beta(np.array([8, 2, 8]), 0.5) > f_beta(np.array([8, 2, 8]), 2.0)  # precise
    assert f_beta(np.array([0, 3, 4]), 1.0) == 0.0


def test_choose_presets_orders_thresholds() -> None:
    """Higher thresholds trade recall for precision; strict picks higher ones than sensitive."""

    def counts(t: float) -> np.ndarray:
        tp = round(100 * (1 - t))
        return np.array([tp, max(0, round(300 * (0.6 - t))), 100 - tp])

    table: Counts = {
        (g, c, t, s): counts(t) for g in GAPS for c in CLASSES for t in GRID
        for s in ("drum-only", "full-mix")
    }  # fmt: skip
    for t in GRID:  # full-mix toms favor the top threshold, but toms tune on drum-only alone
        table[(0.02, "tom", t, "full-mix")] = np.array([int(t == GRID[-1]), 0, 1])
    presets = choose_presets(table)
    assert presets["min_gap_s"] == 0.02  # all gaps tie
    th = presets["thresholds"]
    for c in CLASSES:
        assert th["strict"][c] > th["balanced"][c] > th["sensitive"][c]
    assert th["balanced"]["tom"] == th["balanced"]["kick"]


def test_fit_logistic_recovers_parameters() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(0, 2, 20000)
    y = (rng.random(len(x)) < 1 / (1 + np.exp(-(0.5 + 1.5 * x)))).astype(float)
    b0, b1 = fit_logistic(x, y)
    assert b0 == pytest.approx(0.5, abs=0.1) and b1 == pytest.approx(1.5, abs=0.1)


def test_quantile_map_is_monotone() -> None:
    rng = np.random.default_rng(1)
    m = quantile_map(rng.random(500), rng.integers(1, 128, 500).astype(float))
    assert len(m["activation"]) == len(m["velocity"]) == 11
    assert np.all(np.diff(m["activation"]) >= 0) and np.all(np.diff(m["velocity"]) >= 0)


def test_reliability_bins() -> None:
    conf = np.array([0.1, 0.15, 0.5, 0.9, 1.0])
    hit = np.array([0.0, 1.0, 1.0, 1.0, 1.0])
    assert reliability(conf, hit) == [("0.0–0.2", 2, 0.5), ("0.4–0.6", 1, 1.0), ("0.8–1.0", 2, 1.0)]


def test_compare_rhythm() -> None:
    def with_rhythm(beat_f: float, grid: float, hits: int = 10) -> dict[str, Any]:
        r = result(0.8)
        rhythm = {"beat_f": beat_f, "downbeat_f": 0.5, "grid_accuracy": grid, "grid_hits": hits}
        r["rhythm"] = {"all": rhythm}
        return r

    lines = compare(with_rhythm(0.70, 0.90), with_rhythm(0.80, 0.80), margin=0.02)
    assert lines[0].startswith("REGRESSION") and "beat_f" in lines[0]
    assert lines[1].startswith("improved") and "grid_accuracy" in lines[1]
    # A subset without reference scores has no grid accuracy to compare.
    assert compare(with_rhythm(0.8, 0.0, hits=0), with_rhythm(0.8, 0.8), margin=0.02) == []


def test_markdown_rhythm() -> None:
    r = {
        "model": "adtof", "split": "dev", "commit": "abc", "date": "2026-11-05", "clips": 1,
        "audio_minutes": 2.0, "runtime_s": 3.0, "s_per_audio_minute": 0.5, "results": {},
        "rhythm": {"drum-only": {
            "clips": 3, "beat_f": 0.9, "downbeat_f": 0.75, "grid_hits": 120,
            "grid_accuracy": 0.6, "grid_accuracy_matched": 0.8,
        }},
    }  # fmt: skip
    assert "| drum-only | 3 | 0.90 | 0.75 | 0.60 (120) | 0.80 |" in markdown(r)
