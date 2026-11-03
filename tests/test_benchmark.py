"""M1-6: the benchmark's regression comparison."""

from typing import Any

import pytest
from benchmark import compare, markdown


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
