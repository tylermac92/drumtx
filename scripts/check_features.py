"""One-time check of drumtx.features against madmom (M2-1, docs/models/adtof-frame-rnn.md).

    MADMOM_PYTHON scripts/check_features.py dump OUT.npz AUDIO...    # env with madmom 0.16.1
    uv run python scripts/check_features.py compare OUT.npz MODEL.onnx

`dump` computes ADTOF's madmom features (adtof/io/mir.py, openMadmom) for each audio file.
`compare` computes ours for the same files and reports the largest difference, and how many ADTOF
onsets differ between the two feature sets (model run at the `balanced` preset).
"""

import sys
from typing import Any


def dump(out: str, paths: list[str]) -> None:  # runs in the old madmom env (Python 3.9)
    import numpy as np
    from madmom.audio.filters import LogarithmicFilterbank
    from madmom.audio.signal import FramedSignalProcessor, SignalProcessor
    from madmom.audio.spectrogram import LogarithmicFilteredSpectrogramProcessor
    from madmom.audio.stft import ShortTimeFourierTransformProcessor
    from madmom.processors import SequentialProcessor

    chain = SequentialProcessor(
        (
            SignalProcessor(num_channels=1, sample_rate=44100),
            FramedSignalProcessor(frame_size=2048, fps=100),
            ShortTimeFourierTransformProcessor(),
            LogarithmicFilteredSpectrogramProcessor(
                num_channels=1,
                sample_rate=44100,
                filterbank=LogarithmicFilterbank,
                frame_size=2048,
                fps=100,
                num_bands=12,
                fmin=20,
                fmax=20000,
                norm_filters=True,
            ),
        )
    )
    arrays: dict[str, Any] = {p: np.asarray(chain(p), dtype=np.float32) for p in paths}
    np.savez(out, **arrays)


def compare(npz: str, model: str) -> None:
    from pathlib import Path

    import numpy as np
    import soundfile as sf

    from drumtx import detect, features
    from drumtx.ingest import SAMPLE_RATE

    detector = detect.ModelDetector(Path(model))
    total = changed = 0
    for path, theirs in np.load(npz).items():
        y, rate = sf.read(path, dtype="float32", always_2d=True)
        assert rate == SAMPLE_RATE, (path, rate)
        ours = features.spectrogram(y.mean(axis=1))
        assert ours.shape == theirs.shape, (path, ours.shape, theirs.shape)
        a, b = (
            detect.to_events(
                detector.activations(x),
                detector.presets["thresholds"]["balanced"],
                0.0,
                detector.presets["min_gap_s"],
            )
            for x in (ours, theirs)
        )
        same = {(e.time_s, e.cls) for e in a} & {(e.time_s, e.cls) for e in b}
        total += max(len(a), len(b))
        changed += max(len(a), len(b)) - len(same)
        diff = float(np.abs(ours - theirs).max())
        print(
            f"{Path(path).name}: {len(ours)} frames; max diff {diff:.0e}, onsets {len(a)}/{len(b)}"
        )
    print(f"onsets that differ: {changed} of {total}")


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        dump(sys.argv[2], sys.argv[3:])
    else:
        compare(sys.argv[2], sys.argv[3])
