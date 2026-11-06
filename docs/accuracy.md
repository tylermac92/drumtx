# Accuracy and limitations

How well DrumTx finds drum hits with its default detector, the ADTOF model (`--model adtof`). These are the results of the one-time release evaluation (M2-7, 2026-11-04) on the frozen test set:
- **Test set:** 192 clips, 104 minutes. 181 are drum-only (E-GMD, IDMT-SMT-Drums, MDB Drums) and 11 are full mixes (MDB Drums); decision 0004.
- **Not tuned on:** the test set was not used for any tuning.

More detail, development-set results and how each number was produced are in the model card, `docs/models/adtof-frame-rnn.md`. The raw results are in `eval/results/adtof-test.json`.

The scores below are for **hit detection only**: the right instrument at the right time. Beats, bar lines and grid positions are in [Rhythm](#rhythm-development-set) at the end.

## How to read the numbers

- **Precision:** the share of detected hits that are real. Low precision means extra notes to delete.
- **Recall:** the share of real hits that were found. Low recall means missing notes to add.
- **F-measure:** both in one number; 1.0 is perfect.
- **Tolerance:** a detected hit counts if it is within 50 ms of the real one (30 ms for the stricter rows).

## Results at the default sensitivity (`balanced`)

Precision / recall / F-measure:

| Audio | Tolerance | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|---|
| Drums only | 50 ms | 0.87 / 0.75 / **0.81** | 0.74 / 0.68 / **0.71** | 0.83 / 0.70 / **0.76** | 0.68 / 0.67 / **0.68** | 0.86 / 0.85 / **0.85** |
| Drums only | 30 ms | 0.80 / 0.69 / **0.74** | 0.63 / 0.57 / **0.60** | 0.75 / 0.63 / **0.69** | 0.55 / 0.54 / **0.55** | 0.84 / 0.83 / **0.83** |
| Full mix | 50 ms | 0.77 / 0.93 / **0.84** | 0.63 / 0.84 / **0.72** | 0.81 / 0.72 / **0.76** | 0.40 / 0.57 / **0.47** | 0.80 / 0.92 / **0.85** |
| Full mix | 30 ms | 0.76 / 0.91 / **0.83** | 0.62 / 0.83 / **0.71** | 0.81 / 0.72 / **0.76** | 0.40 / 0.57 / **0.47** | 0.78 / 0.90 / **0.84** |
| All | 50 ms | 0.86 / 0.76 / **0.81** | 0.73 / 0.69 / **0.71** | 0.83 / 0.70 / **0.76** | 0.67 / 0.67 / **0.67** | 0.84 / 0.86 / **0.85** |
| All | 30 ms | 0.79 / 0.70 / **0.75** | 0.63 / 0.60 / **0.61** | 0.76 / 0.64 / **0.69** | 0.54 / 0.54 / **0.54** | 0.83 / 0.84 / **0.84** |

Against the project's targets (project brief; decision 0010):

| | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| Drums only: target / result | 0.85 / 0.81 ✗ | 0.85 / 0.71 ✗ | 0.75 / 0.76 ✓ | 0.60 / 0.68 ✓ | 0.60 / 0.85 ✓ |
| Full mix: target / result | 0.75 / 0.84 ✓ | 0.70 / 0.72 ✓ | 0.70 / 0.76 ✓ | not set / 0.47 | 0.50 / 0.85 ✓ |

The final check against these targets is M7-4.

## By kind of recording (`balanced`, 50 ms, F-measure)

| Source | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| E-GMD: human performances on electronic kits, with many quiet notes | 0.75 | 0.69 | 0.72 | 0.70 | 0.87 |
| MDB Drums: real recordings, drums only and full mixes | 0.91 | 0.77 | 0.78 | 0.50 | 0.85 |
| IDMT-SMT-Drums: real kits, simple patterns | 0.99 | 0.73 | 0.95 | — | — |

## Sensitivity presets (`--sensitivity`)

F-measure at 50 ms, drums only / full mix:

| Preset | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| `strict`: fewer extra notes, more missed ones | 0.76 / 0.85 | 0.69 / 0.76 | 0.73 / 0.77 | 0.59 / 0.53 | 0.84 / 0.85 |
| `balanced` (default) | 0.81 / 0.84 | 0.71 / 0.72 | 0.76 / 0.76 | 0.68 / 0.47 | 0.85 / 0.85 |
| `sensitive`: fewer missed notes, more extra ones | 0.76 / 0.76 | 0.67 / 0.64 | 0.76 / 0.71 | 0.64 / 0.39 | 0.83 / 0.81 |

On full mixes, `strict` is slightly better overall for snare and toms.

## Drum separation (`--separate`)

F-measure at 50 ms on the 11 full-mix test clips, at `balanced`:

| | Kick | Snare | Hi-hat | Tom | Cymbal |
|---|---|---|---|---|---|
| Without | 0.84 | 0.72 | **0.76** | 0.47 | **0.85** |
| With `--separate` | **0.90** | **0.79** | 0.74 | **0.51** | 0.82 |

Separation improves kick and snare on full mixes and costs a little hi-hat and cymbal. It also adds about 13 s of processing per minute of audio on a 4-core CPU and needs a lot of memory: about 9 GB for a 10-minute file (decision 0008). It needs the `[separation]` extra (`docs/models/umxl-drums.md`). It is off by default; try it on busy mixes.

## Confidence

Every hit has a confidence from 0 to 1. Higher confidence means a hit is more likely to be real.

On unseen audio, the middle range overstates it: about half of the hits between 0.6 and 0.8 are real for kick, snare and cymbal. Check notes below 0.8 first. Hits below 0.3 are flagged `uncertain` in `events.json`; with `--mark-uncertain` they are red in the MusicXML.

## Review flags

The report flags about a quarter of the measures on the development set. About four in ten of the measures where half the hits or more are wrong are flagged, and two in three flagged measures are such measures (decision 0013). Most of what flags miss is quiet notes that were never detected, so unflagged measures can be wrong too.

Velocity is only a rough loud/soft estimate.

## Known limitations

- **Quiet notes and ghost notes are often missed.** The model learned from rhythm-game charts, which leave them out. This is the main reason drum-only kick and snare fall short of their targets.
- **Snare has extra hits on real kits:** precision 0.58–0.68. The snare threshold was tuned to catch quiet notes.
- **Snare and tom timing is looser.** At 30 ms, their F-measure drops by 0.11–0.13; check the placement of fills.
- **Toms in full mixes are unreliable** (F 0.47, from only 75 test hits).
- **Five instrument classes only.** Toms are one class, crash and ride are one class, and open and closed hi-hat are one class.
- **Numbers come from public datasets.** Your own recordings may differ; the M7-1 trial measures that.

## Rhythm (development set)

How well DrumTx finds the beats and places hits on the grid (decision 0012; the test-set check is M7-4):

| | Drum-only | Full mix |
|---|---|---|
| Beats found (F-measure, ±70 ms) | 0.98 | 0.93 |
| Downbeats found (F-measure, ±70 ms) | 0.89 | 0.86 |
| Detected hits in the right bar, beat and slot | 0.77 | not measured |

- **Wrong bar lines** are the main rhythm error. In about one clip in seven, every bar is shifted by a whole bar or by a beat. If bar 1 looks wrong, pass `--first-downbeat` with the time of the first downbeat. If the tempo looks halved or doubled, pass `--bpm`.
- **Swing is written as straight 16ths.** A single swung 8th note in a beat stays on the 16th grid, not a triplet.
- **Long silences.** Breaks of up to about 8 s keep the right bar numbers after them. Around a 20 s silence, the beat tracker adds spurious beats, so the bars after it are numbered wrong. Transcribe the parts on either side separately with `--start` and `--end`.
- **The time signature is never detected.** Pass `--time-signature` for anything other than 4/4.
