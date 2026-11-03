"""Accuracy of predicted events against a reference (Technical Design Document §10).

Onsets are matched per class with mir_eval (each reference hit matches at most one predicted hit of
the same class within the tolerance). Beats and downbeats use mir_eval's beat F-measure (±70 ms).
"""

import json
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mido
import mir_eval
import numpy as np

from drumtx.errors import InputError
from drumtx.schema import CLASSES, DrumClass, DrumEvent, event_from_json, read_events_csv

DEFAULT_TOLERANCES_MS = (50.0, 30.0)
DRUM_CHANNEL = 9  # MIDI channel 10, counted from 0
# General MIDI drum notes, plus the Roland e-kit notes used by E-GMD (22, 26, 58).
GM_DRUM_NOTES: dict[int, DrumClass] = {
    **dict.fromkeys((35, 36), "kick"),
    **dict.fromkeys((37, 38, 40), "snare"),
    **dict.fromkeys((22, 26, 42, 44, 46), "hihat"),
    **dict.fromkeys((41, 43, 45, 47, 48, 50, 58), "tom"),
    **dict.fromkeys((49, 51, 52, 53, 55, 57, 59), "cymbal"),
}


@dataclass
class Track:
    """Hits per class, optional beats as (time, position in bar), and what could not be scored."""

    onsets: dict[DrumClass, np.ndarray]
    beats: list[tuple[float, int]] | None = None
    unknown_notes: Counter[int] = field(default_factory=Counter)
    other_channel_notes: int = 0


def _from_events(events: list[DrumEvent]) -> dict[DrumClass, np.ndarray]:
    return {c: np.array(sorted(e.time_s for e in events if e.cls == c)) for c in CLASSES}


def load_prediction(path: Path) -> Track:
    """An events.json (with its tempo map's beats) or an events.csv."""
    if path.suffix.lower() == ".csv":
        return Track(_from_events(read_events_csv(path)))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        events = [event_from_json(e) for e in doc["events"]]
        beats = [(float(b["time_s"]), int(b["beat"])) for b in doc["tempo_map"]["beats"]]
    except OSError as e:
        raise InputError(f"Cannot read {path}: {e.strerror}") from e
    except (ValueError, KeyError, TypeError) as e:
        raise InputError(f"{path.name} is not a DrumTx events.json file ({e!r}).") from e
    return Track(_from_events(events), beats or None)


def load_reference(path: Path, beats_path: Path | None = None) -> Track:
    """A MIDI file (channel 10, General MIDI drum notes) or a CSV like events.csv."""
    if path.suffix.lower() in (".mid", ".midi"):
        track = _read_midi(path)
    else:
        track = Track(_from_events(read_events_csv(path)))
    if beats_path is not None:
        track.beats = _read_beats(beats_path)
    return track


def _read_midi(path: Path) -> Track:
    try:
        midi = mido.MidiFile(path)
        hits: dict[DrumClass, list[float]] = {c: [] for c in CLASSES}
        unknown: Counter[int] = Counter()
        other = 0
        now = 0.0
        for msg in midi:  # message times are seconds since the previous message
            now += msg.time
            if msg.type != "note_on" or msg.velocity == 0:
                continue
            if msg.channel != DRUM_CHANNEL:
                other += 1
            elif msg.note in GM_DRUM_NOTES:
                hits[GM_DRUM_NOTES[msg.note]].append(now)
            else:
                unknown[msg.note] += 1
    except (OSError, EOFError, ValueError, KeyError) as e:
        raise InputError(f"Cannot read MIDI file {path.name}: {e}") from e
    return Track({c: np.array(t) for c, t in hits.items()}, None, unknown, other)


def _read_beats(path: Path) -> list[tuple[float, int]]:
    """time_s,beat rows; beat is the position in the bar and 1 marks a downbeat (decision 0004)."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        if lines[0].strip() != "time_s,beat":
            raise ValueError("the header must be time_s,beat")
        beats = []
        for line in lines[1:]:
            if line.strip():
                t, b = line.split(",")
                beats.append((float(t), int(b)))
        return beats
    except (OSError, IndexError, ValueError) as e:
        raise InputError(f"Cannot read beats file {path.name}: {e}") from e


def scores(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    """Counts with precision, recall and F-measure. Empty denominators score 0."""
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "p": tp / (tp + fp) if tp + fp else 0.0,
        "r": tp / (tp + fn) if tp + fn else 0.0,
        "f": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0,
    }


def match_counts(ref: np.ndarray, est: np.ndarray, tolerance_s: float) -> tuple[int, int, int]:
    """(true positives, false positives, false negatives) with one-to-one matching."""
    tp = len(mir_eval.util.match_events(ref, est, tolerance_s)) if len(ref) and len(est) else 0
    return tp, len(est) - tp, len(ref) - tp


def evaluate(
    pred: Track, ref: Track, tolerances_ms: tuple[float, ...] = DEFAULT_TOLERANCES_MS
) -> dict[str, Any]:
    onsets = []
    for tol in tolerances_ms:
        per_class = {c: match_counts(ref.onsets[c], pred.onsets[c], tol / 1000) for c in CLASSES}
        total = tuple(int(n) for n in np.sum(list(per_class.values()), axis=0))
        onsets.append(
            {
                "tolerance_ms": tol,
                "classes": {c: scores(*n) for c, n in per_class.items()},
                "all": scores(*total),
            }
        )
    beats = None
    if ref.beats is not None:
        est = pred.beats or []
        with warnings.catch_warnings():  # mir_eval warns about empty beat lists
            warnings.simplefilter("ignore")
            beats = {
                "pred_has_beats": bool(est),
                "beat_f": mir_eval.beat.f_measure(_times(ref.beats), _times(est)),
                "downbeat_f": mir_eval.beat.f_measure(
                    _times(ref.beats, downbeats=True), _times(est, downbeats=True)
                ),
            }
    return {
        "onsets": onsets,
        "beats": beats,
        "not_scored": {
            "unknown_midi_notes": {str(n): k for n, k in sorted(ref.unknown_notes.items())},
            "notes_not_on_channel_10": ref.other_channel_notes,
        },
    }


def _times(beats: list[tuple[float, int]], downbeats: bool = False) -> np.ndarray:
    return np.array([t for t, b in beats if b == 1 or not downbeats])


def markdown(result: dict[str, Any], pred: Path, ref: Path) -> str:
    out = ["# DrumTx evaluation", "", f"- Prediction: `{pred.name}`", f"- Reference: `{ref.name}`"]
    for block in result["onsets"]:
        out += ["", f"## Onsets, ±{block['tolerance_ms']:g} ms", ""]
        out += [
            "| Class | Precision | Recall | F | TP | FP | FN |",
            "|---|---|---|---|---|---|---|",
        ]
        for name, s in [*block["classes"].items(), ("**all**", block["all"])]:
            prf = (
                f"{s['p']:.3f} | {s['r']:.3f} | {s['f']:.3f}"
                if s["tp"] + s["fp"] + s["fn"]
                else "– | – | –"  # no hits on either side
            )
            out.append(f"| {name} | {prf} | {s['tp']} | {s['fp']} | {s['fn']} |")
    if result["beats"] is not None:
        b = result["beats"]
        out += ["", "## Beats, ±70 ms", "", f"- Beat F: {b['beat_f']:.3f}"]
        out.append(f"- Downbeat F: {b['downbeat_f']:.3f}")
        if not b["pred_has_beats"]:
            out.append("- The prediction has no beats (no tempo map), so both scores are 0.")
    skipped = result["not_scored"]
    if skipped["unknown_midi_notes"] or skipped["notes_not_on_channel_10"]:
        out += ["", "## Not scored", ""]
        for note, n in skipped["unknown_midi_notes"].items():
            out.append(f"- MIDI note {note}: {n} hits (not a DrumTx class)")
        if skipped["notes_not_on_channel_10"]:
            n = skipped["notes_not_on_channel_10"]
            out.append(f"- {n} notes on channels other than 10 (not drums)")
    return "\n".join(out) + "\n"
