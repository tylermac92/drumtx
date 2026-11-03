"""M1-3: the baseline detector."""

import json
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from drumtx import detect
from drumtx.ingest import SAMPLE_RATE, AudioBuffer
from drumtx.schema import CLASSES, DrumClass, event_from_json, event_to_json
from drumtx.synth import drum_hit

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "src" / "drumtx" / "events-v1.schema.json").read_text("utf-8"))


def track(hits: list[tuple[float, DrumClass]], seconds: float = 4.0) -> np.ndarray:
    """Synthesized hits over a -60 dB noise floor."""
    y = np.random.default_rng(0).normal(0, 1e-3, round(seconds * SAMPLE_RATE)).astype(np.float32)
    for t, cls in hits:
        h = drum_hit(cls)
        i = round(t * SAMPLE_RATE)
        y[i : i + len(h)] += h[: len(y) - i]
    return y


@pytest.mark.parametrize("cls", CLASSES)
def test_isolated_hit_within_10_ms(cls: DrumClass) -> None:
    buf = AudioBuffer(track([(1.234, cls)])[:, None], start_s=5.0, source_duration_s=9.0)
    found = [e for e in detect.BaselineDetector().detect(buf) if e.cls == cls]
    # The first detection is the hit, in source-file time. The cymbal's noisy decay can
    # re-trigger later: a known weakness of the baseline (decision 0009).
    assert found and found[0].time_s == pytest.approx(6.234, abs=0.010)
    if cls != "cymbal":
        assert len(found) == 1


def test_simultaneous_and_repeated_hits() -> None:
    hits: list[tuple[float, DrumClass]] = [(0.5, "kick"), (0.5, "hihat"), (1.0, "snare")]
    hits += [(1.0, "hihat"), (1.5, "kick"), (1.5, "hihat"), (2.0, "snare"), (2.0, "hihat")]
    events = detect.BaselineDetector().detect(AudioBuffer(track(hits)[:, None], 0.0, 4.0))
    for t, cls in hits:
        assert any(e.cls == cls and abs(e.time_s - t) <= 0.010 for e in events), (t, cls)


def test_silence_has_no_events() -> None:
    quiet = AudioBuffer(track([])[:, None], 0.0, 4.0)
    assert detect.BaselineDetector().detect(quiet, "sensitive") == []


def test_events_are_schema_valid() -> None:
    buf = AudioBuffer(track([(0.5, "kick"), (1.0, "snare"), (1.5, "cymbal")])[:, None], 0, 4)
    events = detect.BaselineDetector().detect(buf)
    assert events == sorted(events, key=lambda e: e.time_s)
    item = Draft202012Validator(SCHEMA["properties"]["events"]["items"])
    for e in events:
        item.validate(event_to_json(e))
        assert event_from_json(event_to_json(e)) == e


def test_presets_order_detections() -> None:
    buf = AudioBuffer(track([(t / 4, "hihat") for t in range(1, 15)])[:, None], 0, 4)
    n = {p: len(detect.BaselineDetector().detect(buf, p)) for p in detect.PRESET_SCALE}
    assert n["strict"] <= n["balanced"] <= n["sensitive"]


def test_pick_peaks_merges_close_peaks() -> None:
    act = np.zeros(100)
    act[[10, 12, 50]] = 1.0  # 20 ms apart: one hit
    assert detect.pick_peaks(act, 0.5).tolist() == [10, 50]
