"""The event plot (M5-6): a PNG piano roll of the hits over time, flagged measures shaded.

Needs the `[plot]` extra (matplotlib), imported only for --plot. Drawn on a matplotlib `Figure`
directly, so no display or GUI backend is needed.
"""

from pathlib import Path

from drumtx.errors import MissingDependencyError, install_hint
from drumtx.review import measure_times
from drumtx.schema import CLASSES, QuantizedScore

SECONDS_PER_INCH = 4.0  # a 10-minute piece is 150 inches (15,000 pixels) wide
UNCERTAIN = "#E00000"  # as --mark-uncertain colors notes in the MusicXML


def check_installed() -> None:
    try:
        import matplotlib  # noqa: F401
    except ImportError as e:
        raise MissingDependencyError(
            f"--plot needs the plot extra ({e.name} is missing). Install it with:\n"
            f"  {install_hint('plot')}"
        ) from e


def write_plot(score: QuantizedScore, path: Path) -> Path:
    """One row per class; a tick per hit, red when uncertain; bar lines with measure numbers;
    flagged measures shaded and labeled with their flags."""
    check_installed()
    from matplotlib.figure import Figure
    from matplotlib.patches import Patch

    tm = score.tempo_map
    end = max([e.time_s for e in score.events] + [b.time_s for b in tm.beats] + [1.0]) + 0.5
    fig = Figure(figsize=(max(8.0, end / SECONDS_PER_INCH), 3.0), layout="constrained")
    ax = fig.add_subplot()
    if len(tm.beats) > 1:
        for b in tm.beats:
            if b.beat == 1:
                ax.axvline(b.time_s, color="0.75", linewidth=0.8, zorder=0)
                ax.text(b.time_s, len(CLASSES) - 0.4, f" {b.measure}", fontsize=7, color="0.4")
        for m in score.measure_flags:
            start, stop = measure_times(tm, m.measure)
            ax.axvspan(start, stop, color="orange", alpha=0.25, zorder=0, linewidth=0)
            ax.text(start, -0.9, " " + ", ".join(m.flags), fontsize=7, color="0.3")
    for row, cls in enumerate(CLASSES):
        hits = [e for e in score.events if e.cls == cls]
        colors = [UNCERTAIN if "uncertain" in e.flags else "black" for e in hits]
        ax.scatter([e.time_s for e in hits], [row] * len(hits), c=colors, marker="|", s=120)
    ax.set_yticks(range(len(CLASSES)), list(CLASSES))
    ax.set_ylim(-1.2, len(CLASSES))
    ax.set_xlim(0, end)
    ax.set_xlabel("seconds from the start of the file")
    fig.legend(  # outside the axes, so it never hides a hit or a measure number
        handles=[
            Patch(color="orange", alpha=0.25, label="flagged measure"),
            Patch(color=UNCERTAIN, label="uncertain hit"),
        ],
        loc="outside right upper",
        fontsize=7,
    )
    tmp = path.with_name(path.name + ".tmp")
    fig.savefig(tmp, dpi=100, format="png")
    tmp.replace(path)
    return path
