"""M6-1: the performance script's own measurements (CI runs this on Linux, macOS and Windows)."""

import numpy as np
from perf import markdown, peak_bytes


def test_peak_bytes_grows_with_an_allocation() -> None:
    before = peak_bytes()
    assert 10 * 2**20 < before < 64 * 2**30  # a Python process: more than 10 MB, less than 64 GB
    block = np.ones((before + 200 * 2**20) // 8)  # more than the peak so far, touched
    assert peak_bytes() >= block.nbytes


def test_markdown_row() -> None:
    result = {
        "machine": {"processor": "x86_64", "cpus": 4, "platform": "Linux", "python": "3.13"},
        "commit": "abc",
        "date": "2026-11-06",
        "runs": 3,
        "files": [
            {
                "file": "a.wav",
                "audio_s": 240.0,
                "separate": False,
                "wall_s": 14.3,
                "realtime_factor": 0.0596,
                "stages_s": {"Detect": 2.5, "Track": 11.3},
                "peak_mb": 1237,
            }
        ],
    }
    row = "| a.wav | 4.0 min | no | 14.3 s | 0.060 | 1,237 MB | Detect 2.5 s, Track 11.3 s |"
    assert row in markdown(result)
