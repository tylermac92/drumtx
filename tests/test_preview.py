"""M5-2: `drumtx preview` mixes the original audio with the events synthesized in place."""

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from typer.testing import CliRunner

from drumtx.cli import app
from drumtx.ingest import SAMPLE_RATE
from drumtx.schema import DrumClass
from drumtx.synth import ORIGINAL_GAIN, drum_hit, render

runner = CliRunner()
HITS: list[tuple[float, DrumClass, int]] = [
    (0.503, "kick", 100),
    (1.011, "snare", 90),
    (1.498, "hihat", 70),
    (2.007, "tom", 110),
    (2.75, "cymbal", 100),
]


def write_events_csv(path: Path) -> Path:
    rows = [f"{t},{cls},0.9,{v}" for t, cls, v in HITS]
    path.write_text("time_s,class,confidence,velocity\n" + "\n".join(rows) + "\n")
    return path


def preview(*args: str) -> tuple[int, str]:
    result = runner.invoke(app, ["preview", *args, "-q"])
    return result.exit_code, result.stderr


@pytest.mark.parametrize("rate", [SAMPLE_RATE, 48000])
def test_hits_are_in_place_at_the_source_length(tmp_path: Path, rate: int) -> None:
    wav = tmp_path / "in.wav"
    original = 0.5 * np.sin(2 * np.pi * 220 * np.arange(4 * rate) / rate)
    sf.write(wav, original, rate)
    events = write_events_csv(tmp_path / "in.events.csv")
    assert preview(str(wav), str(events), "--split-stereo") == (0, "")
    out, out_rate = sf.read(tmp_path / "in.preview.wav")
    assert out_rate == SAMPLE_RATE and out.shape == (4 * SAMPLE_RATE, 2)
    assert np.abs(out[:, 0]).max() == pytest.approx(0.5 * ORIGINAL_GAIN, abs=1e-3)
    for t, cls, v in HITS:  # where each synthesized hit best matches the right channel
        hit = drum_hit(cls, v)[: SAMPLE_RATE // 10]
        lo = round((t - 0.05) * SAMPLE_RATE)
        corr = np.correlate(out[lo : lo + SAMPLE_RATE // 10 + len(hit), 1], hit, "valid")
        found = (lo + int(np.argmax(corr))) / SAMPLE_RATE
        assert found == pytest.approx(t, abs=0.010), cls


def test_from_json_and_csv_with_overwrite_protection(tmp_path: Path) -> None:
    wav, out = tmp_path / "in.wav", tmp_path / "out"
    sf.write(wav, render(HITS, 4.0), SAMPLE_RATE)
    args = ["transcribe", str(wav), "-o", str(out), "-q", "--model", "baseline"]
    assert runner.invoke(app, args).exit_code == 0
    for events in ("in.events.json", "in.events.csv"):
        target = tmp_path / f"{events}.wav"
        assert preview(str(wav), str(out / events), "-o", str(target)) == (0, "")
        data, _ = sf.read(target, always_2d=True)
        assert data.shape == (4 * SAMPLE_RATE, 1)
        assert np.abs(data).max() > ORIGINAL_GAIN  # the hits are there, louder than the original
    code, err = preview(str(wav), str(out / "in.events.csv"), "-o", str(target))
    assert code == 2 and "already exists" in err
    assert preview(str(wav), str(out / "in.events.csv"), "-o", str(target), "--force")[0] == 0


def test_bad_events(tmp_path: Path) -> None:
    wav = tmp_path / "in.wav"
    sf.write(wav, render(HITS, 4.0), SAMPLE_RATE)
    doc = json.loads(
        (Path(__file__).parents[1] / "docs/schema/examples/groove.events.json").read_text()
    )
    doc["events"][3]["class"] = "gong"
    bad = tmp_path / "bad.events.json"
    bad.write_text(json.dumps(doc))
    code, err = preview(str(wav), str(bad))
    assert code == 2 and "not a valid DrumTx events.json: $.events[3].class: 'gong'" in err
    code, err = preview(str(wav), str(tmp_path / "missing.csv"))
    assert code == 2 and "Cannot read" in err
