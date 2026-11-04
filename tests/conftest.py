"""Every test runs with networking disabled (M2-5) and with its own empty model directory."""

import socket
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise OSError("network access is disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setenv("DRUMTX_CACHE_DIR", str(tmp_path / "drumtx-cache"))
