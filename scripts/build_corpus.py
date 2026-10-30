"""Build the evaluation corpus (M0-3, decision 0004) from datasets kept in DATA_DIR.

Writes annotation files to DATA_DIR/corpus/ (never committed) and the frozen
split manifests eval/dev.csv and eval/test.csv (committed). Usage:

    uv run python scripts/build_corpus.py ~/drumtx-data [--fetch-egmd]

--fetch-egmd downloads only the selected E-GMD clips from the 90 GB archive
using HTTP range requests.
"""

import argparse
import csv
import hashlib
import io
import math
import shutil
import urllib.request
import wave
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import mido

CLASSES = ("kick", "snare", "hihat", "tom", "cymbal")
EGMD_URL = "https://storage.googleapis.com/magentadata/datasets/e-gmd/v1.0.0/e-gmd-v1.0.0.zip"
# E-GMD (Roland TD-17) MIDI notes; follows the 5-class grouping used in ADTOF.
EGMD_NOTES = {
    **dict.fromkeys((36,), "kick"),
    **dict.fromkeys((37, 38, 40), "snare"),
    **dict.fromkeys((22, 26, 42, 44, 46), "hihat"),
    **dict.fromkeys((43, 45, 47, 48, 50, 58), "tom"),
    **dict.fromkeys((49, 51, 52, 53, 55, 57, 59), "cymbal"),
}
LABELS = {"KD": "kick", "SD": "snare", "HH": "hihat", "TT": "tom", "CY": "cymbal"}  # MDB, IDMT
# MIREX 2017 test split of MDB Drums; the other 12 tracks are the development split.
MDB_TEST = {
    "Beatles",
    "Country1",
    "FreeJazz",
    "Gospel",
    "Grunge",
    "Hendrix",
    "LatinJazz",
    "ModalJazz",
    "Punk",
    "SpeedMetal",
    "SwingJazz",
}
BEATS_PER_BAR = {"4-4": 4, "3-4": 3}  # other meters get onsets only
SCORE_TOL = 0.35  # max distance from the snapped slot, as a fraction of a grid step
MANIFEST_FIELDS = [
    "clip_id",
    "source",
    "license",
    "split",
    "subset",
    "style",
    "audio",
    "audio_sha256",
    "duration_s",
    "beats",
    "score",
    *CLASSES,
]

Onset = tuple[float, str, int]  # time_s, class, velocity
ScoreRow = tuple[Onset, int | None, int | None, str | None, int | None]


def egmd_onsets(midi: mido.MidiFile) -> list[Onset] | None:
    """Hits in seconds, or None if the kit uses a note outside the class map (e.g. tambourine)."""
    t, out = 0.0, []
    for msg in midi:
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            if msg.note not in EGMD_NOTES:
                return None
            out.append((t, EGMD_NOTES[msg.note], msg.velocity))
    return out


def grid_beats(bpm: float, beats_per_bar: int, duration: float) -> list[tuple[float, int]]:
    """Beat times from a constant tempo with bar 1 at time 0 (E-GMD is recorded to a click)."""
    step = 60 / bpm
    return [(i * step, i % beats_per_bar + 1) for i in range(math.floor(duration / step) + 1)]


def reference_score(onsets: list[Onset], bpm: float, beats_per_bar: int) -> list[ScoreRow]:
    """Place hits on the click grid: (onset, measure, beat, grid, slot), or None fields if unscored.

    Each beat takes the grid (16th or 8th-triplet) with the lower total snapping error; 16th on a
    tie or when every hit is on the beat. A hit further than SCORE_TOL of a grid step from its
    snapped position is left unscored.
    """
    steps = {"16th": 4, "triplet": 3}
    groups: dict[int, list[tuple[Onset, float]]] = {}
    for o in onsets:
        b = o[0] * bpm / 60
        groups.setdefault(math.floor(b + 1 / 8), []).append((o, b))  # 16th midpoint before beat
    out: list[ScoreRow] = []
    for hits in groups.values():
        err = {g: sum(abs(b - round(b * n) / n) * n for _, b in hits) for g, n in steps.items()}
        off_beat = any(round(b * 3) % 3 for _, b in hits)
        g = "triplet" if off_beat and err["triplet"] < err["16th"] else "16th"
        n = steps[g]
        for o, b in hits:
            s = round(b * n) / n
            if abs(b - s) * n > SCORE_TOL:
                out.append((o, None, None, None, None))
                continue
            beat = math.floor(s + 1e-9)
            slot = round((s - beat) * n) + 1
            out.append((o, beat // beats_per_bar + 1, beat % beats_per_bar + 1, g, slot))
    return out


def write_csv(path: Path, header: list[str], rows: Iterable[Iterable[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def onset_rows(onsets: list[Onset]) -> list[list[object]]:
    return [[f"{t:.6f}", c, "1.0", v] for t, c, v in sorted(onsets)]


class HttpFile(io.RawIOBase):
    """Read-only seekable view of a remote file, so zipfile can extract single members."""

    def __init__(self, url: str) -> None:
        self.url, self.pos = url, 0
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as r:
            self.size = int(r.headers["Content-Length"])

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = (0, self.pos, self.size)[whence] + offset
        return self.pos

    def readinto(self, b: bytearray | memoryview) -> int:  # type: ignore[override]
        if self.pos >= self.size or not len(b):
            return 0
        end = min(self.pos + len(b), self.size) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req) as r:
            data = r.read()
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return float(w.getnframes() / w.getframerate())


def build(data: Path, out: Path, fetch_egmd: bool) -> None:
    corpus = data / "corpus"
    rows: list[dict[str, object]] = []

    def add(
        clip_id: str,
        source: str,
        lic: str,
        split: str,
        subset: str,
        style: str,
        audio: Path,
        onsets: list[Onset],
        beats: list[tuple[float, int]] | None,
        score: list[ScoreRow] | None,
    ) -> None:
        write_csv(
            corpus / f"{clip_id}.onsets.csv",
            ["time_s", "class", "confidence", "velocity"],
            onset_rows(onsets),
        )
        if beats:
            write_csv(
                corpus / f"{clip_id}.beats.csv",
                ["time_s", "beat"],
                [[f"{t:.6f}", n] for t, n in beats],
            )
        if score:
            write_csv(
                corpus / f"{clip_id}.score.csv",
                ["time_s", "class", "confidence", "velocity", "measure", "beat", "grid", "slot"],
                # csv writes None (an unscored hit) as an empty field
                [
                    [f"{o[0]:.6f}", o[1], "1.0", o[2], m, b, g, s]
                    for o, m, b, g, s in sorted(score, key=lambda x: x[0])
                ],
            )
        n = Counter(c for _, c, _ in onsets)
        rows.append(
            {
                "clip_id": clip_id,
                "source": source,
                "license": lic,
                "split": split,
                "subset": subset,
                "style": style,
                "audio": audio.relative_to(data).as_posix(),
                "audio_sha256": sha256(audio),
                "duration_s": f"{wav_seconds(audio):.3f}",
                "beats": int(bool(beats)),
                "score": int(bool(score)),
                **{c: n[c] for c in CLASSES},
            }
        )

    # E-GMD: our dev = its validation split, our test = its test split (training uses its train
    # split). One kit per performance, rotating through the kits and skipping kits that remap
    # notes outside the class map.
    egmd = data / "e-gmd"
    meta = list(csv.DictReader((egmd / "e-gmd-v1.0.0.csv").open()))
    kits = sorted({r["kit_name"] for r in meta})
    midi_zip = zipfile.ZipFile(egmd / "e-gmd-v1.0.0-midi.zip")

    def read_midi(r: dict[str, str]) -> mido.MidiFile:
        return mido.MidiFile(file=io.BytesIO(midi_zip.read(f"e-gmd-v1.0.0/{r['midi_filename']}")))

    chosen: list[tuple[str, dict[str, str], list[Onset]]] = []
    for split, ours in (("validation", "dev"), ("test", "test")):
        by_id: dict[str, dict[str, dict[str, str]]] = {}
        for r in meta:
            if r["split"] == split:
                by_id.setdefault(r["id"], {})[r["kit_name"]] = r
        for i, pid in enumerate(sorted(by_id)):
            for j in range(len(kits)):
                row = by_id[pid].get(kits[(i + j) % len(kits)])
                if row and (onsets := egmd_onsets(read_midi(row))):
                    chosen.append((ours, row, onsets))
                    break
    if fetch_egmd:
        remote = zipfile.ZipFile(io.BufferedReader(HttpFile(EGMD_URL), 1 << 20))
        for _, r, _ in chosen:
            dest = egmd / "audio" / r["audio_filename"]
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                with (
                    remote.open(f"e-gmd-v1.0.0/{r['audio_filename']}") as src,
                    dest.open("wb") as f,
                ):
                    shutil.copyfileobj(src, f)
    for ours, r, onsets in chosen:
        # Rhythm annotations only for grooves in 4/4 or 3/4; fills are too short to track.
        bpb = BEATS_PER_BAR.get(r["time_signature"]) if r["beat_type"] == "beat" else None
        beats = grid_beats(float(r["bpm"]), bpb, float(r["duration"])) if bpb else None
        score = reference_score(onsets, float(r["bpm"]), bpb) if bpb else None
        clip_id = "egmd/" + r["audio_filename"].removesuffix(".wav").replace("/", "_")
        add(
            clip_id,
            "E-GMD",
            "CC BY 4.0",
            ours,
            "drum-only",
            r["style"],
            egmd / "audio" / r["audio_filename"],
            onsets,
            beats,
            score,
        )

    # MDB Drums: MIREX 2017 split; each track as a drum-only and a full-mix clip.
    mdb = data / "mdb-drums" / "MDBDrums" / "MDB Drums"
    for ann in sorted((mdb / "annotations" / "class").glob("*_class.txt")):
        track = ann.name.removeprefix("MusicDelta_").removesuffix("_class.txt")
        split = "test" if track in MDB_TEST else "dev"
        onsets = []
        for line in ann.read_text().splitlines():
            if line.split() and line.split()[1] in LABELS:  # "OT" (other) is dropped
                onsets.append((float(line.split()[0]), LABELS[line.split()[1]], 100))
        beat_file = mdb / "annotations" / "beats" / f"MusicDelta_{track}_MIX.beats"
        beats = [
            (float(t), int(n))
            for t, n in (ln.split() for ln in beat_file.read_text().splitlines() if ln.strip())
        ]
        for subset, folder, suffix in (
            ("drum-only", "drum_only", "Drum"),
            ("full-mix", "full_mix", "MIX"),
        ):
            add(
                f"mdb/{track}_{suffix}",
                "MDB Drums",
                "CC BY-NC-SA 4.0",
                split,
                subset,
                track,
                mdb / "audio" / folder / f"MusicDelta_{track}_{suffix}.wav",
                onsets,
                beats,
                None,
            )

    # IDMT-SMT-Drums (evaluation only): even loop numbers dev, odd test.
    idmt = data / "idmt-smt-drums"
    for xml in sorted((idmt / "annotation_xml").glob("*#MIX.xml")):
        name = xml.name.removesuffix(".xml")
        events = ET.parse(xml).getroot().iter("event")
        onsets = [
            (float(e.findtext("onsetSec", "")), LABELS[e.findtext("instrument", "")], 100)
            for e in events
        ]
        split = "dev" if int(name.split("_")[1].split("#")[0]) % 2 == 0 else "test"
        add(
            "idmt/" + name.replace("#", "_"),
            "IDMT-SMT-Drums",
            "CC BY-NC-ND 4.0",
            split,
            "drum-only",
            name.split("_")[0],
            idmt / "audio" / f"{name}.wav",
            onsets,
            None,
            None,
        )

    for split in ("dev", "test"):
        write_csv(
            out / f"{split}.csv",
            MANIFEST_FIELDS,
            [[r[k] for k in MANIFEST_FIELDS] for r in rows if r["split"] == split],
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("data", type=Path, help="dataset directory, e.g. ~/drumtx-data")
    p.add_argument("--out", type=Path, default=Path(__file__).parent.parent / "eval")
    p.add_argument("--fetch-egmd", action="store_true", help="download the selected E-GMD clips")
    a = p.parse_args()
    build(a.data.expanduser(), a.out, a.fetch_egmd)
