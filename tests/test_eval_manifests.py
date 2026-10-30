import hashlib
from pathlib import Path

import pytest

# Frozen in decision 0004. Change only through a new decision record.
FROZEN = {
    "dev.csv": "0b18c0cbf9442693330c6bf537218299e22bd80947f173728a0d204b837be1b8",
    "test.csv": "0f00ce72a2a7c96809e182274c172f4a76d7aa358cb2ecc6f3d00c06cb407bc3",
}


@pytest.mark.parametrize("name", FROZEN)
def test_split_manifest_is_frozen(name: str) -> None:
    path = Path(__file__).parent.parent / "eval" / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == FROZEN[name]
