"""Open every development-set transcription in MuseScore (M4-5; decision 0007 chose MuseScore).

    uv run python scripts/check_musescore.py [--data ~/drumtx-data] [--model adtof] [--out DIR]

For each clip of eval/dev.csv, `transcribe` writes the MusicXML (kept in OUT and reused on the next
run), and MuseScore's command line (`mscore3`, or --mscore) converts it to MIDI. A file passes when:
- MuseScore prints nothing but its progress lines and the benign `element already exists`. It exits
  0 and prints "success!" even for a broken file, so its messages are what count;
- the MIDI file it writes has one channel-10 note for each note of the score.

Clips under 2 s are too short to transcribe and have no output. Exit code 1 if any file fails.
"""

import argparse
import csv
import io
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import mido

from drumtx import pipeline
from drumtx.errors import InputError

ROOT = Path(__file__).resolve().parents[1]
# MuseScore's output lines that are not import problems (decision 0007).
BENIGN = re.compile(
    r"convert <.*>\.\.\.|\s*to <.*>|\.\.\. success!|instr '.*', tick .*: element already exists"
    r"|QStandardPaths: .*"
)


def problems(output: str) -> list[str]:
    """MuseScore's output lines that point to an import problem."""
    return [line for line in output.splitlines() if line.strip() and not BENIGN.fullmatch(line)]


def midi_problems(midi: bytes, score_notes: int) -> list[str]:
    """Problems with MuseScore's MIDI export of a score with `score_notes` notes."""
    on = [m for m in mido.MidiFile(file=io.BytesIO(midi)) if m.type == "note_on" and m.velocity]
    out = []
    if len(on) != score_notes:
        out.append(f"MIDI has {len(on)} notes, the score {score_notes}")
    if {m.channel for m in on} - {9}:
        out.append("MIDI notes outside channel 10")
    return out


def check(mscore: str, musicxml: Path) -> list[str]:
    midi = musicxml.with_suffix(".musescore.mid")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}  # no display needed
    run = subprocess.run(
        [mscore, "-o", str(midi), str(musicxml)],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    found = problems(run.stdout + run.stderr)
    if run.returncode or not midi.exists():
        return [*found, f"MuseScore exited {run.returncode} without a MIDI file"]
    return found + midi_problems(midi.read_bytes(), musicxml.read_bytes().count(b"<unpitched>"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--data", type=Path, default=Path.home() / "drumtx-data")
    p.add_argument("--model", default="adtof", help="detection model, as in `transcribe --model`")
    p.add_argument("--out", type=Path, default=Path("musescore-check"), help="transcriptions")
    p.add_argument("--mscore", default="mscore3", help="MuseScore command")
    args = p.parse_args()
    logging.basicConfig(level=logging.ERROR)

    rows = list(csv.DictReader((ROOT / "eval" / "dev.csv").open(encoding="utf-8")))
    failed, short = [], 0
    for i, r in enumerate(rows, start=1):
        audio = args.data / r["audio"]
        out_dir = args.out / r["clip_id"].replace("/", "__")
        musicxml = out_dir / f"{audio.stem}.musicxml"
        if not musicxml.exists():
            config = pipeline.Config(audio, out_dir, model=args.model, offline=True, force=True)
            try:
                pipeline.run(pipeline.RunContext.create(config))
            except InputError as e:
                if "at least" not in str(e):  # anything but "too short" is a failure
                    raise
                short += 1
                continue
        found = check(args.mscore, musicxml)
        print(f"[{i}/{len(rows)}] {'FAIL' if found else 'ok  '} {r['clip_id']}", flush=True)
        for line in found[:5]:
            print(f"        {line}")
        if found:
            failed.append(r["clip_id"])
    opened = len(rows) - short
    print(f"\n{opened - len(failed)} of {opened} MusicXML files open without import errors.")
    print(f"{short} clips are under 2 s and have no output.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
