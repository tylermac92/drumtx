"""The instrument mapping (Technical Design Document §5; M3-5): per class, the MusicXML name, MIDI
note, staff position, notehead and voice.

`mapping.toml` next to this file is the default. A file passed with `--mapping` has the same
tables; any class or key it leaves out keeps its default.
"""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from drumtx.errors import InputError
from drumtx.schema import CLASSES, DrumClass

DEFAULT = Path(__file__).with_name("mapping.toml")


@dataclass(frozen=True)
class Instrument:
    name: str
    midi_note: int  # 0–127, on channel 10
    display: str  # staff position as step and octave on a treble clef, such as "F4"
    notehead: Literal["normal", "x"]
    voice: Literal[1, 2]  # 1: stems up (hands); 2: stems down (feet)


Mapping = dict[DrumClass, Instrument]

# Each key's check, and what it must be.
CHECKS: dict[str, tuple[Any, str]] = {
    "name": (lambda v: isinstance(v, str) and v.strip() != "", "a non-empty string"),
    "midi_note": (
        lambda v: type(v) is int and 0 <= v <= 127,
        "a whole number from 0 to 127",
    ),
    "display": (
        lambda v: isinstance(v, str) and re.fullmatch(r"[A-G][0-9]", v) is not None,
        'a step and octave such as "F4"',
    ),
    "notehead": (lambda v: v in ("normal", "x"), '"normal" or "x"'),
    "voice": (lambda v: type(v) is int and v in (1, 2), "1 or 2"),
}


def _read(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"Cannot read the mapping {path}: {e}") from e
    except tomllib.TOMLDecodeError as e:
        raise InputError(f"The mapping {path} is not valid TOML: {e}") from e


def load(path: Path | None = None) -> Mapping:
    """The default mapping, with the tables of `path` over it. Every bad key is reported."""
    tables = _read(DEFAULT)
    if path is not None:
        errors = []
        for cls, table in _read(path).items():
            if cls not in CLASSES:
                errors.append(f"[{cls}] is not a class; the classes are {', '.join(CLASSES)}")
            elif not isinstance(table, dict):
                errors.append(f"{cls} must be a table, [{cls}]")
            else:
                for key, value in table.items():
                    if key not in CHECKS:
                        errors.append(
                            f"[{cls}] {key} is not a key; the keys are {', '.join(CHECKS)}"
                        )
                    elif not CHECKS[key][0](value):
                        errors.append(f"[{cls}] {key} must be {CHECKS[key][1]}, got {value!r}")
                tables[cls] = {**tables[cls], **table}
        if errors:
            raise InputError(f"The mapping {path} has errors:\n  " + "\n  ".join(errors))
    return {cls: Instrument(**tables[cls]) for cls in CLASSES}
