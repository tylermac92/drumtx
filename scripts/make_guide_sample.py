"""The example recording of the correction guide (docs/correction-guide.md, M5-5).

    uv run python scripts/make_guide_sample.py OUT_DIR

Writes groove.wav: 20 seconds of drums synthesized in code (decision 0003) at 96 BPM. A
two-beat fill (two snares, two toms) leads into six bars of groove with quiet ghost notes, and a
crash on the last downbeat. Bar 1 starts after the fill, at 3.5 s. Also writes groove.truth.csv,
the hits as an events.csv, to check a corrected transcription against.
"""

import argparse
from pathlib import Path

import soundfile as sf

from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import DrumClass
from drumtx.synth import render

BPM = 96
START_S = 1.0  # silence before the bar the fill starts in


def hits() -> list[tuple[float, DrumClass, int]]:
    """(time_s, class, velocity), sorted."""
    beats: list[tuple[float, DrumClass, int]] = [
        (0, "snare", 90), (0.5, "snare", 95), (1, "tom", 100), (1.5, "tom", 105)
    ]  # fmt: skip
    for bar in range(6):
        b = 2 + 4 * bar  # bar 1 starts two beats after the fill
        beats += [(b + e / 2, "hihat", 75 if e % 2 else 95) for e in range(8)]
        beats += [(b, "kick", 110), (b + 2, "kick", 105), (b + 2.5, "kick", 95)]
        beats += [(b + 1, "snare", 110), (b + 3, "snare", 112)]
        beats += [(b + 1.75, "snare", 25), (b + 3.75, "snare", 25)]  # ghost notes
    beats += [(26, "kick", 110), (26, "cymbal", 115)]
    return sorted((round(START_S + (b + 2) * 60 / BPM, 3), c, v) for b, c, v in beats)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("out_dir", type=Path)
    out = p.parse_args().out_dir
    out.mkdir(parents=True, exist_ok=True)
    h = hits()
    sf.write(out / "groove.wav", render(h, h[-1][0] + 2.0), SAMPLE_RATE, subtype="PCM_16")
    rows = "".join(f"{t:.3f},{c},1.0,{v}\n" for t, c, v in h)
    (out / "groove.truth.csv").write_text("time_s,class,confidence,velocity\n" + rows)
    print(out / "groove.wav")


if __name__ == "__main__":
    main()
