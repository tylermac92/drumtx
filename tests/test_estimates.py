"""M0-8: every M1–M7 task has an estimate in decision 0008, and the totals add up."""

import re
from collections import defaultdict
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
ESTIMATES = (DOCS / "decisions" / "0008-reference-machine-and-estimates.md").read_text("utf-8")
DAYS = r"([\d.]+)–([\d.]+)"


def test_every_task_has_an_estimate() -> None:
    tasks = re.findall(
        r"^\*\*(M[1-7]-\d+) ", (DOCS / "milestone-tasks.md").read_text("utf-8"), re.M
    )
    estimated = re.findall(rf"^\| (M[1-7]-\d+) .*?\| {DAYS} \|", ESTIMATES, re.M)
    assert tasks and [t for t, *_ in estimated] == tasks


def test_totals_add_up() -> None:
    sums: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for task, low, high in re.findall(rf"^\| (M[1-7])-\d+ .*?\| {DAYS} \|", ESTIMATES, re.M):
        for s in (task, "M1–M7"):
            sums[s][0] += float(low)
            sums[s][1] += float(high)
    totals = re.findall(rf"^\| \**(M[1-7](?:–M7)?)\** \| \**{DAYS}\** \|", ESTIMATES, re.M)
    assert len(totals) == 8
    for milestone, low, high in totals:
        assert sums[milestone] == [float(low), float(high)], milestone
