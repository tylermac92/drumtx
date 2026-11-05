"""The instrument mapping (Technical Design Document §5): per class, the MIDI note, staff position,
notehead and voice. `mapping.toml` next to this file is the default."""

import tomllib
from pathlib import Path
from typing import Any

DEFAULT = Path(__file__).with_name("mapping.toml")


def load(path: Path = DEFAULT) -> dict[str, dict[str, Any]]:
    # shortcut: no validation, default file only; M3-5 adds --mapping and checks every key
    return tomllib.loads(path.read_text(encoding="utf-8"))
