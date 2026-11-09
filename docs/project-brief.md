# Project Brief: DrumTx (working name)

*Command-line drum transcription from audio to editable notation*

## Problem

Writing out drum parts by ear is slow and needs skill. A few minutes of music can take a trained drummer an hour or more. Most automatic tools focus on pitched instruments, or they produce raw MIDI that still needs heavy cleanup before it reads as drum notation. Drum transcription is hard for several reasons:

- Drums overlap with other instruments and with each other.
- Tempo drifts in human performances.
- Cymbals and hi-hats sound alike.
- Quiet or ghosted hits are easy to miss.

## Intended user

The author only: a musician comfortable running a few terminal commands and editing notation in a desktop app such as MuseScore. DrumTx is a personal, non-commercial tool and is not distributed (decision 0001).

## Product concept

A local, offline-capable CLI takes an audio file and produces four things:

1. A **drum score** in MusicXML, for editing in notation software.
2. A **drum MIDI file**, for DAWs.
3. A **drum event list** (JSON and CSV) with per-hit timestamps and confidence values.
4. A **review report** that points users to the passages most likely to be wrong.

The output is treated as a **first draft to be corrected**, not a finished transcription. The tool helps users find and fix errors quickly.

## Goals

1. Produce a usable first-draft drum transcription that takes less effort to correct than transcribing from scratch.
2. Make results easy to inspect and correct:
   - Confidence values and flagged measures.
   - Audio preview of the detected hits.
   - Re-rendering from an edited event list.
3. Measure and record accuracy honestly, per instrument class and per recording type.
4. Run locally on an ordinary laptop CPU, with no account or upload required.

## Non-goals (MVP)

- Perfect or publication-ready notation without human review.
- Pitched instruments, or full-band transcription.
- Real-time or live transcription.
- GUI, web service, or mobile app.
- Fine articulation: flams, drags, rimshots, cross-sticks, open/closed hi-hat, ghost-note notation.
- Specific tom identification (high, mid, floor), and specific cymbal identification (crash vs. ride).
- Automatic time-signature detection and compound meters (6/8, 12/8).
- 32nd notes and 16th-note triplets (sextuplets). Such passages are snapped to the nearest supported grid, and timing flags usually point to them.

## MVP scope

| Area | MVP decision |
|---|---|
| Platforms | Python package for Linux, macOS, and Windows, installed with `pipx` from a local clone. |
| Input | WAV, FLAC, and AIFF natively; MP3 and OGG via the audio library; other formats when FFmpeg is installed. Mono or stereo, up to 10 minutes by default. |
| Instrument classes | Five: `kick`, `snare`, `hihat`, `tom`, `cymbal`. |
| Drum isolation | Optional (`--separate`) for full mixes. |
| Rhythm | Beat and downbeat tracking, with user overrides (`--bpm`, `--time-signature`, `--first-downbeat`). |
| Quantization | Per-beat grid of 16ths or 8th-note triplets. Meters of the form N/4. |
| Outputs | MusicXML (single percussion staff), General MIDI drum file, events JSON and CSV, Markdown review report. |
| Review tools | `preview` (audio check), `render` (re-render after edits), `evaluate` (accuracy against a reference). |

## Key success measures

The onset targets were reviewed after the baseline was measured (M1-6, decision 0010), which also added targets for tom, cymbal, and full-mix audio. The rhythm targets were set in M3-6 from the first rhythm benchmark (decision 0012).

| Measure | Target |
|---|---|
| Per-class onset F-measure on a held-out test set, ±50 ms tolerance | Reported separately for drum-only and full-mix audio. Drum-only: ≥ 0.85 for kick and snare, ≥ 0.75 for hi-hat, ≥ 0.60 for tom and cymbal. Full mix: ≥ 0.75 for kick, ≥ 0.70 for snare and hi-hat, ≥ 0.50 for cymbal; tom is reported without a target (too few test hits). |
| Downbeat F-measure on the test set, ±70 ms | ≥ 0.85, for drum-only and for full-mix audio. |
| Grid accuracy on the test set: share of the reference score's hits that DrumTx detected and placed in the correct measure, beat and slot | ≥ 0.75 on drum-only audio. The share over all reference hits, missed ones included, is reported without a target. |
| Notation validity | 100% of generated MusicXML validates against the MusicXML 4.0 schema and opens in MuseScore without errors on the development set during work (M4-5) and on the test set at release (M7-4). |
| Runtime | ≤ 1× real time on a reference laptop CPU without separation (the reference machine is in decision 0008). |
| Correction effort | On your own recordings, a draft can be corrected to a score that sounds right in the browser editor, with no CSV or notation editing. The time per track is recorded on at least two tracks (M7-1b). Reworded after M7-1: the original target (faster than transcribing by hand) assumed hand-transcription experience. |
| Installation | Clean install and smoke test pass on all three operating systems in CI. |

## Major risks

1. **Accuracy on full mixes.** Results will be noticeably worse than on isolated drums, and separation adds cost and artifacts.
2. **Rhythm errors.** Tempo, downbeat, or grid errors can shift or garble a whole score even when individual hits are detected correctly.
3. **Licensing.** Non-commercial terms are fine for personal use (decision 0001), but some datasets are research-only or forbid redistribution, and sharing the project later would mean replacing those parts.
4. **Notation readability.** A valid MusicXML file is not the same as readable drum notation.

## Planning assumptions

- Python stack. Personal, non-commercial, and not distributed (decision 0001).
- One developer: the author.
- No fixed deadline. Work is sequenced as milestones M0–M7 (see the Milestone Task List).
- Unresolved decisions are listed as open questions in the Technical Design Document.
