"""Synthesized drum sounds (decision 0003): deterministic, level set by velocity, in band."""

import numpy as np
import pytest

from drumtx.detect import BANDS_HZ
from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import CLASSES, DrumClass
from drumtx.synth import drum_hit


@pytest.mark.parametrize("cls", CLASSES)
def test_drum_hit(cls: DrumClass) -> None:
    hit = drum_hit(cls, velocity=64)
    assert hit.dtype == np.float32
    assert np.array_equal(hit, drum_hit(cls, velocity=64))
    assert float(np.abs(hit).max()) == pytest.approx(64 / 127, rel=1e-5)
    spectrum = np.abs(np.fft.rfft(hit)) ** 2
    freqs = np.fft.rfftfreq(len(hit), 1 / SAMPLE_RATE)
    lo, hi = BANDS_HZ[cls]
    assert spectrum[(freqs >= lo) & (freqs < hi)].sum() > 0.5 * spectrum.sum()
