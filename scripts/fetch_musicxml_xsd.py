"""Download the MusicXML 4.0 XSD, and the two schemas it imports, for the MusicXML tests (M4-1).
They are not kept in the repository (decision 0001). Usage:

    uv run python scripts/fetch_musicxml_xsd.py DIR
    DRUMTX_MUSICXML_XSD=DIR uv run pytest tests/test_musicxml.py
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/w3c/musicxml/v4.0/schema/"
SHA256 = {
    "musicxml.xsd": "bfe37ed25a9ec00e6f2591d53df260b84efe12aed209ba3ac0a76f9287665a99",
    "xml.xsd": "616a3077df5cfc954ac74a75abe9697b95eef7a85dbe09367d995a483e840eb5",
    "xlink.xsd": "6e601f8eeb41618b50e4c7f944dff754e57ea43b602755470dda24c9c2f6df92",
}


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, sha in SHA256.items():
        with urllib.request.urlopen(URL + name, timeout=60) as r:
            data = r.read()
        if hashlib.sha256(data).hexdigest() != sha:
            sys.exit(f"{name}: SHA-256 does not match")
        (out / name).write_bytes(data)
    print(f"MusicXML 4.0 XSD in {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
