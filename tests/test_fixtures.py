"""M1-5: the synthetic fixture generator, and an end-to-end run over its fixtures."""

import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

import make_fixtures as mf
import numpy as np
import pytest

from drumtx import evaluate as ev
from drumtx import pipeline
from drumtx.schema import CLASSES

NOISY = {"noise_db": -40.0, "backing": True}
# Audio rounded to 16-bit steps (make_fixtures.pcm_sha256). If one changes, the fixtures changed.
HASHES = {
    ("straight16", False): "32f9446868f68bc4061e2ef26207248439b330276aaacbd2f589a73a84bfa91a",
    ("triplets", False): "37d3b117c2b1459c52d1260717fa30ad34554d342f3b0ce351e1438cf32787b3",
    ("simultaneous", False): "05bad2f612f24080ccb2a424bc61ebf35bed9c75781a7409fd5c1c02d2a067b4",
    ("straight16", True): "55d501f7082d3e65f651ca3b2b83abf88296165dd87ad247d6c9368fdf79e612",
    ("triplets", True): "0e4ffc696a0f73cfc38e2e2e00a96e49125ea991506d392f4a53412a88d83081",
    ("simultaneous", True): "053e30be59c9f2b72b7b2ffdc6e5ed70869c2d870748882c35592a7b532f009f",
}
VARIANTS = [(p, noisy) for p in mf.PATTERNS for noisy in (False, True)]
IDS = [f"{p.name}-{'noisy' if noisy else 'clean'}" for p, noisy in VARIANTS]


@pytest.mark.parametrize(("pattern", "noisy"), VARIANTS, ids=IDS)
def test_deterministic(pattern: mf.Pattern, noisy: bool) -> None:
    kw = NOISY if noisy else {}
    assert mf.pcm_sha256(mf.audio(pattern, **kw)) == HASHES[(pattern.name, noisy)]  # type: ignore[arg-type]


def test_seed_changes_output() -> None:
    p = mf.PATTERNS[0]
    assert mf.timed_hits(p, 0) != mf.timed_hits(p, 1)
    assert [t for t, _, _ in mf.timed_hits(p, 0)] == [t for t, _, _ in mf.timed_hits(p, 1)]


def test_coverage() -> None:
    by_name = {p.name: p for p in mf.PATTERNS}
    straight = {b % 1 for b, _ in by_name["straight16"].hits}
    assert straight == {Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)}
    assert {b % 1 for b, _ in by_name["triplets"].hits} == {
        Fraction(0),
        Fraction(1, 3),
        Fraction(2, 3),
    }
    per_instant = Counter(b for b, _ in by_name["simultaneous"].hits)
    assert max(per_instant.values()) == 3 and min(per_instant.values()) >= 2
    assert {c for p in mf.PATTERNS for _, c in p.hits} == set(CLASSES)


def test_files_agree(tmp_path: Path) -> None:
    """The MIDI reference, the onset CSV and the hit list describe the same hits."""
    p = next(p for p in mf.PATTERNS if p.name == "triplets")
    mf.write(p, tmp_path)
    midi = ev.load_reference(tmp_path / "triplets.mid")
    csv = ev.load_reference(tmp_path / "triplets.onsets.csv")
    hits = mf.timed_hits(p)
    for c in CLASSES:
        want = sorted(t for t, cls, _ in hits if cls == c)
        # MIDI stores 90 BPM as 666,667 µs per beat: 0.5 ppm off, a few µs over the pattern.
        np.testing.assert_allclose(midi.onsets[c], want, atol=1e-5)
        np.testing.assert_allclose(csv.onsets[c], want, atol=1e-6)
    assert hits[2][1] == "hihat"  # the first triplet
    assert hits[2][0] == pytest.approx((1 + 1 / 3) * 60 / 90)


@pytest.mark.parametrize(("pattern", "noisy"), VARIANTS, ids=IDS)
def test_end_to_end(tmp_path: Path, pattern: mf.Pattern, noisy: bool) -> None:
    """Transcribe each fixture and score it against its MIDI reference.

    Every hit must be found within 50 ms. False positives are not checked: the baseline's band
    bleed produces many (decision 0009), and the benchmark (M1-6) tracks precision.
    """
    start = time.perf_counter()
    wav = mf.write(pattern, tmp_path, **(NOISY if noisy else {}))  # type: ignore[arg-type]
    config = pipeline.Config(input=wav, out_dir=tmp_path / "out", model="baseline")
    events = pipeline.run(pipeline.RunContext.create(config))["detect"]
    pred = ev.Track({c: np.array([e.time_s for e in events if e.cls == c]) for c in CLASSES})
    result = ev.evaluate(pred, ev.load_reference(tmp_path / f"{pattern.name}.mid"), (50,))
    for c, s in result["onsets"][0]["classes"].items():
        assert s["fn"] == 0, (c, s)
    assert time.perf_counter() - start < 10
