"""Every test runs with networking disabled (M2-5), with its own empty model directory, and with a
stand-in beat tracker (M3-1): beats every 0.5 s, downbeats every 2 s. A test marked
`real_tracker` gets the real one, which needs the beat-this-final0 model."""

import socket
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from drumtx import pipeline
from drumtx.ingest import AudioBuffer


def fake_track(audio: AudioBuffer, offline: bool) -> dict[str, list[float]]:
    beats = audio.start_s + np.arange(0, audio.duration_s, 0.5)
    return {"beats": beats.round(3).tolist(), "downbeats": beats[::4].round(3).tolist()}


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, request: Any) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise OSError("network access is disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setenv("DRUMTX_CACHE_DIR", str(tmp_path / "drumtx-cache"))
    if "real_tracker" not in request.keywords:
        monkeypatch.setattr(pipeline, "track_beats", fake_track)
