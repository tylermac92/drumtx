# Technical Design Document: DrumTx (working name)

## 1. Overview

DrumTx is a Python command-line tool and library. It turns an audio recording into editable drum notation through a staged pipeline:

**Ingest → Separate (optional) → Detect → Track → Quantize → Render → Report**

Each stage has a narrow interface and writes inspectable intermediate data. This serves three purposes:

- Algorithms can be swapped without touching the rest of the pipeline.
- Users can correct results at the event-list level and re-render without re-running detection.
- Evaluation can be done stage by stage.

The design assumes transcription will contain errors. Confidence values, review flags, audio preview, and re-rendering are first-class features, not afterthoughts.

### Terminology

| Term | Meaning |
|---|---|
| **Drum event** | One detected hit: time in seconds from the start of the source file (also when `--start` is used), instrument class, confidence (0–1), estimated velocity (1–127). |
| **Event list** | All drum events for a run, plus metadata. Stored as `<name>.events.json`, and as `<name>.events.csv` for editing. |
| **Tempo map** | Beat times, downbeat times, time signature, and where they came from (estimated or user-supplied). |
| **Quantized score** | The event list placed on a metrical grid (measure, beat, subdivision). |
| **Review report** | `<name>.report.md`: a run summary plus flagged measures to check. |
| **Instrument classes** | `kick`, `snare`, `hihat`, `tom`, `cymbal`. |
| **Sensitivity preset** | `strict`, `balanced`, or `sensitive`. Each preset is a set of per-class detection thresholds. |

## 2. Assumptions

These are planning assumptions, not user requirements. Each one is chosen to be conservative and replaceable.

| Area | MVP assumption | Rationale | How it stays adaptable |
|---|---|---|---|
| Language | Python 3.11+ (exact range pinned in M0) | The audio and ML ecosystem is mature (NumPy, librosa, PyTorch, ONNX Runtime, mir_eval). | Core logic sits behind a library API, so a later GUI or service can reuse it. |
| Operating systems | Linux, macOS, Windows | Musicians use all three. A CI matrix keeps them working. | No OS-specific code outside audio decoding and paths. |
| Distribution | `pipx install drumtx`; optional extras `drumtx[separation]` and `drumtx[plot]` | Keeps the default install small. Heavy dependencies are opt-in. | A Docker image or standalone binaries can come later. |
| User skill | Comfortable with a terminal and a notation editor or DAW | Matches a CLI-first product. | Library API and JSON outputs allow wrappers later. |
| Audio content | Recordings with an acoustic or electronic drum kit, mostly steady tempo, 60–200 BPM | This is the case current methods handle reasonably well. | Tempo and grid overrides cover edge cases. Limits are documented. |
| Meter | N/4 time signatures supplied by the user (default 4/4) | Automatic meter detection is unreliable. | The `TempoMap` structure already allows meter changes later. |
| Output | MusicXML + MIDI + JSON/CSV + Markdown report | MusicXML is the most widely imported editable notation format. MIDI covers DAWs. | Renderers are plug-ins on the quantized score. |
| Processing | Fully local; CPU by default; GPU optional for separation only (detection is CPU-only in the MVP) | Privacy, simplicity, and no hosting cost. GPU inference for detection would need the separate `onnxruntime-gpu` package. | Device selection is handled in one place. |

## 3. Supported inputs

| Format | MVP support | Mechanism |
|---|---|---|
| WAV, FLAC, AIFF | Yes | `soundfile` (bundles libsndfile) |
| MP3, OGG/Vorbis | Yes; to be confirmed in M1 | Recent `soundfile` releases bundle a libsndfile build with MP3 support. |
| M4A/AAC, others | Only if FFmpeg is on `PATH` | Decoded through an FFmpeg subprocess. A clear error is shown if FFmpeg is missing. |

**Normalization.** Audio is downmixed to mono (stereo is kept for the optional separation stage) and resampled to 44.1 kHz with float32 samples. Peak level is normalized for detection only; source files are never modified.

**Limits.**

- Default maximum duration is 10 minutes, adjustable with `--max-duration`.
- `--start` and `--end` select an excerpt. Event times, report timestamps, and preview alignment still use seconds from the start of the source file; the excerpt bounds are stored in `events.json`.
- Very short inputs (under 2 seconds) are rejected because beat tracking cannot work on them.
- Files larger than 2 GB are rejected before decoding (exit code 2).

**Recording types.** Results are expected to be best on isolated drum recordings, and worse on full mixes, live recordings, heavily processed or electronic kits, and lo-fi sources. The documentation and review report say this plainly.

## 4. CLI experience

The CLI is built with Typer, which is based on Click. Commands follow one verb per task.

```text
drumtx transcribe INPUT [options]    Full pipeline: audio → score, MIDI, events, report
drumtx render EVENTS [options]       Re-quantize and re-render from an (edited) events JSON/CSV
drumtx preview INPUT EVENTS [-o]     Mix the original audio with synthesized detected hits
drumtx evaluate --pred P --ref R     Accuracy of predictions against a reference (MIDI or CSV)
drumtx models list|download          Manage model files (for offline use)
drumtx doctor                        Check environment: Python, decoders, FFmpeg, extras, models
```

### Key `transcribe` options

| Option | Default | Purpose |
|---|---|---|
| `-o, --out-dir DIR` | `./<input-name>_drumtx/` | Where outputs go. |
| `--formats LIST` | `musicxml,midi,json,csv,report` | Which outputs to write. |
| `--separate / --no-separate` | off | Isolate drums first. Needs `drumtx[separation]`. Recommended for full mixes. |
| `--sensitivity` | `balanced` | `strict` misses more hits but adds fewer false ones; `sensitive` does the opposite. |
| `--bpm FLOAT` | estimated | Constrains the beat tracker to a tempo. |
| `--time-signature N/4` | `4/4` | Meter used for downbeats and barlines. |
| `--first-downbeat SEC` | estimated | Fixes the start of bar 1 when the estimate is wrong. |
| `--grid` | `auto` | `16th`, `triplet`, or `auto` (chosen per beat). |
| `--start SEC`, `--end SEC` | whole file | Transcribe an excerpt. |
| `--mark-uncertain` | off | Color low-confidence notes in the MusicXML. |
| `--midi-timing` | `quantized` | `quantized` (on grid, aligned to audio through the tempo map) or `performance` (raw times). |
| `--device` | `cpu` | `cpu` or `cuda`, for `--separate` only. Detection always runs on CPU in the MVP. |
| `--model ID` | registry default | Detection model. `baseline` selects the classical detector, which needs no download. |
| `--offline` | off | Never attempt a network access. Fails if the model is not installed. |
| `--force` | off | Overwrite existing outputs. Never overwrites an `events.csv` that was edited after it was written (detected by the hash stored in `events.json`); move or rename the edited file first. |
| `--no-cache` | off | Ignore cached stage outputs and recompute all stages. |
| `-v` / `-q` | — | More or less logging. |

### Key `render` options

`render` accepts `--formats`, `--grid`, `--mark-uncertain`, `--midi-timing`, and `--mapping`, plus two rhythm overrides that work on the stored beat times without the audio: `--first-downbeat SEC` and `--time-signature N/4`. With an override, the updated tempo map is saved to `events.json`. `render` overwrites the score, MIDI, and report it writes, and never modifies its input events file. A tempo fix (`--bpm`) needs the beat tracker, so it goes through `transcribe --force`, which reuses the cached detection.

### Example commands

```bash
# Isolated drum recording, defaults
drumtx transcribe drums_take3.wav

# Full mix: isolate drums, known tempo and meter, excerpt only
drumtx transcribe song.mp3 --separate --bpm 96 --time-signature 4/4 --start 30 --end 75

# Fix a wrong downbeat without re-running detection or touching the audio
drumtx render song_drumtx/song.events.json --first-downbeat 1.24

# Fix a wrong tempo estimate (beat tracking re-runs; cached detection is reused)
drumtx transcribe song.mp3 --separate --bpm 96 --force

# Listen to what was detected: original on the left channel, synthesized hits on the right
drumtx preview song.mp3 song_drumtx/song.events.json --split-stereo -o check.wav

# After fixing rows in the CSV, regenerate the score and MIDI
drumtx render song_drumtx/song.events.csv --formats musicxml,midi

# Measure accuracy against a hand-made reference
drumtx evaluate --pred song_drumtx/song.events.json --ref song_reference.mid --tolerance-ms 50
```

### Illustrative output

```text
$ drumtx transcribe groove.wav
[1/6] Ingest     groove.wav  3:12, 44.1 kHz stereo → mono
[2/6] Detect     1,842 events (kick 412, snare 386, hihat 911, tom 61, cymbal 72)
[3/6] Track      ~118 BPM (stable), 4/4, first downbeat at 0.48 s
[4/6] Quantize   grid auto: 92% of beats 16th, 8% triplet; 37 events >25% of a grid step off
[5/6] Render     groove.musicxml, groove.mid, groove.events.json, groove.events.csv
[6/6] Report     groove.report.md: 9 measures flagged for review
Note: automatic transcription contains errors. Check flagged measures first.
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success. Includes runs with warnings, such as "no drum events detected". |
| 2 | Usage or input error: bad option, unreadable or unsupported file, too long or too short, output exists without `--force`. |
| 3 | Missing dependency: FFmpeg, an optional extra, or a model while `--offline`. |
| 4 | Processing failure, such as model inference failing or a model file failing its SHA-256 check. |
| 1 | Unexpected internal error. Message points to `-v` and bug reporting. |

## 5. Output formats

### MVP outputs

| File | Format | Contents and notes |
|---|---|---|
| `<name>.musicxml` | MusicXML 4.0, uncompressed | One percussion part on a five-line staff. Voice 1 (stems up): hands (hi-hat, snare, tom, cymbal). Voice 2 (stems down): kick. One time signature and one tempo marking (median tempo). Grid of 16ths and 8th-note triplets, using `divisions = 12` per quarter note. Cymbal and hi-hat noteheads are x. |
| `<name>.mid` | Standard MIDI File type 1, channel 10, General MIDI drum notes | Tempo changes at every beat, so quantized notes line up with the original audio in a DAW. `--midi-timing performance` writes raw times instead. |
| `<name>.events.json` | Versioned JSON (`schema_version`), with a published JSON Schema | Source metadata (file name, SHA-256, duration, excerpt bounds), pipeline settings, model ID, tempo map, events with confidence, velocity, quantized position, and review flags, plus the SHA-256 of the `events.csv` as written. This is the authoritative intermediate format. |
| `<name>.events.csv` | CSV: `time_s,class,confidence,velocity` | The correction-friendly format. Edit it in any spreadsheet, then run `drumtx render`. Rows may be in any order. In rows added by hand, `confidence` and `velocity` may be left blank; they are read as 1.0 and 100. |
| `<name>.report.md` | Markdown | Settings, tempo summary, per-class counts, flagged measures with timestamps, known limitations. |
| `<name>.preview.wav` | WAV, from `drumtx preview` only | Original audio plus synthesized hits from bundled CC0 samples. |

### Default instrument mapping

The mapping is overridable with a TOML file passed as `--mapping`.

| Class | GM MIDI note | Staff position (treble-clef reference) | Notehead | Note |
|---|---|---|---|---|
| `kick` | 36 | F4 (bottom space) | normal | Voice 2 |
| `snare` | 38 | C5 (3rd space) | normal | |
| `hihat` | 42 (closed) | G5 (above staff) | x | Open/closed distinction is post-MVP. |
| `tom` | 47 | D5 | normal | One merged class. Specific toms are post-MVP. |
| `cymbal` | 49 (crash) | A5 (ledger line) | x | Crash and ride merged. Separation is post-MVP. |

Drum notation conventions vary between publishers. The mapping is documented in the report and is configurable.

### Later enhancements (not MVP)

- Compressed MusicXML (`.mxl`).
- PDF output, via MuseScore CLI or LilyPond.
- Guitar Pro or MuseScore-native files.
- Notation of articulations (accents, ghost notes, flams) and of tempo changes.
- Compound meters and odd groupings.
- Importing a corrected MIDI file back into the pipeline.

## 6. Architecture

```text
                ┌────────────── drumtx CLI (Typer) ───────────────┐
                │ transcribe | render | preview | evaluate | ...  │
                └──────────────────────┬──────────────────────────┘
                                       │ calls library API
┌──────────────────────────────────────▼───────────────────────────────────────┐
│ pipeline: RunContext, stage orchestration, cache (keyed by audio hash+params)│
├─────────┬───────────┬───────────┬──────────┬───────────┬──────────┬──────────┤
│ ingest  │ separate  │ detect    │ track    │ quantize  │ render   │ review   │
│ decode, │ (optional │ features, │ beats,   │ grid      │ musicxml,│ report,  │
│ resample│ extra)    │ model,    │ downbeats│ selection,│ midi,    │ flags,   │
│ trim    │           │ peak pick │ tempo map│ collisions│ json/csv │ preview  │
└─────────┴───────────┴───────────┴──────────┴───────────┴──────────┴──────────┘
  shared: models (registry, download, SHA-256 verify) · schema (events v1) ·
          mapping (TOML) · evaluate (mir_eval-based metrics)
```

### Components

| Component | Responsibility | Key interface |
|---|---|---|
| `ingest` | Decode, validate, downmix, resample, trim, enforce limits. | `load_audio(path, start, end) -> AudioBuffer` |
| `separate` | Optional drum-stem extraction. Imported lazily; clear error if the extra is not installed. | `Separator.isolate_drums(AudioBuffer) -> AudioBuffer` |
| `detect` | Log-mel features → per-class activation curves → peak picking → drum events. | `Detector.detect(AudioBuffer, preset) -> list[DrumEvent]`. Two implementations: `BaselineDetector` (classical, from M1) and `ModelDetector` (learned, from M2). |
| `track` | Beat and downbeat estimation, respecting user overrides. | `BeatTracker.track(AudioBuffer, hints) -> TempoMap` |
| `quantize` | Assign events to a metrical grid. Compute timing residuals and review flags. | `quantize(events, tempo_map, grid) -> QuantizedScore` |
| `render` | Write output files from a `QuantizedScore` and the event list. | `Renderer.write(score, path)` per format |
| `review` | Report generation, preview synthesis, flag thresholds. | `build_report(...)`, `synthesize_preview(...)` |
| `evaluate` | Onset-level and grid-level metrics against references. | `evaluate(pred, ref, tolerance) -> Metrics` |
| `models` | Model registry (ID, version, URL, SHA-256, license), download, cache directory, offline mode. | `get_model(id, offline) -> Path` |
| `pipeline` | Runs the stages and caches stage outputs. `render` reuses the cache or the events file. | `run(config) -> RunResult` |

## 7. Data flow

1. **Ingest.** The input file is decoded into an `AudioBuffer` (mono float32 at 44.1 kHz, plus stereo kept if separation is on). A SHA-256 hash of the source file becomes the cache key.
2. **Separate (optional).** The stereo mix goes in; a drum stem comes out, which replaces the mix for detection. Beat tracking still runs on the full mix, because other instruments help locate beats.
3. **Detect.**
   - Log-mel spectrogram: 10 ms hop, about 80–128 bands; finalized in M2.
   - The detector produces per-class activation curves at 100 frames per second.
   - Peak picking uses per-class thresholds from the sensitivity preset and a minimum gap between peaks of the same class (about 30 ms).
   - Output events carry time, class, confidence (the peak activation, calibrated), and velocity (mapped from activation or onset energy; approximate).
4. **Track.** The beat tracker estimates beats and downbeats, constrained by `--bpm`, `--time-signature`, and `--first-downbeat` when given. The resulting `TempoMap` records whether each value was estimated or user-supplied.
5. **Quantize.**
   - For each beat interval, events are converted to a phase (0–1).
   - Candidate grids are 4 subdivisions (16ths) and 3 subdivisions (8th-note triplets).
   - `auto` picks the grid with the lowest total snapping error, plus a penalty on triplets so that duple feel is preferred. Triplets require at least two events that fit them.
   - Collisions (same class, same slot) are merged, keeping the highest confidence. This merge is recorded in the event's flags rather than silently discarded.
   - Each event stores a residual: the distance in milliseconds from its snapped position, and that distance as a fraction of the grid step. The largest possible residual is half a step, which is 37.5 ms for 16ths at 200 BPM but 125 ms at 60 BPM, so flags use the fraction.
   - Positions are 1-based: `measure`, `beat`, and `slot` start at 1. A pickup measure before the first downbeat is measure 0.
   - Events before the first tracked beat or after the last one are placed by extending the nearest beat interval.
6. **Render.** MusicXML and MIDI are written from the quantized score. JSON and CSV are written from the full event list.
7. **Report.** Measures are flagged when:
   - they contain uncertain events (confidence below the review threshold);
   - they contain more than one event with a residual above 25% of the grid step;
   - the local tempo deviates more than 8% from the median;
   - a collision merge happened in them.

   The flag thresholds are configurable and tuned in M5.

`drumtx render` re-enters this flow at step 5, using a provided JSON or CSV file. An edited CSV has no tempo map, so `render` takes the tempo map from the sibling JSON file (`<name>.events.json`), adjusted by `--first-downbeat` or `--time-signature` when given.

### Example event (excerpt from `events.json`)

```json
{
  "id": 214, "time_s": 52.371, "class": "snare", "confidence": 0.58, "velocity": 71,
  "quantized": {"measure": 26, "beat": 2, "grid": "16th", "slot": 2, "residual_ms": 12.4, "residual_frac": 0.1},
  "flags": ["uncertain"]
}
```

## 8. Recommended technologies

Candidates marked "decide in M0" depend on the licensing and spike results.

| Need | Recommendation | Why | Alternatives / caveats |
|---|---|---|---|
| CLI | Typer | Type-hinted commands, generated help, testable through Click's `CliRunner`. | Click or argparse directly. |
| Audio input/output | `soundfile`; FFmpeg subprocess as fallback | Reliable lossless decoding with few dependencies. FFmpeg covers everything else. | `audioread`, PyAV |
| Resampling and features | librosa (or `soxr` for resampling) | Standard, well-documented spectrogram and onset tools. | torchaudio (adds a heavy dependency to the base install) |
| Drum detection model | A CRNN on log-mel features with 5 class outputs; trained in PyTorch, shipped as ONNX | Convolutional-recurrent models are a common, proven approach in automatic drum transcription (ADT) research. ONNX Runtime keeps inference CPU-friendly and avoids PyTorch in the base install. | **Decide in M0.** Options: (a) adopt a published pretrained ADT model, such as models released with the ADTOF work, if its license fits; (b) train our own on permissively licensed data, such as E-GMD; (c) use the classical baseline only. Verify every license. |
| Classical baseline | Spectral-flux onset detection plus frequency-band classification, or NMF with drum templates | No training data needed. Provides a regression floor and a fallback. | — |
| Beat and downbeat tracking | **Decide in M0** among: Beat This! (CPJKU), madmom, librosa | Beat This! is a recent neural beat and downbeat tracker. madmom is mature, but its model files carry non-commercial license terms. librosa tracks beats but not downbeats. | Each candidate conflicts with a base-install goal: Beat This! runs on PyTorch (needs an ONNX export, or goes in an extra); madmom's last PyPI release is old (verify it installs on Python 3.11+); librosa would need downbeats from `--first-downbeat` plus the meter. Verify license and maintenance status. Always support manual overrides. |
| Source separation (optional) | Demucs-family model behind the `[separation]` extra | Strong drum-stem quality. Isolating the heavy PyTorch dependency keeps the base install light. | Verify upstream maintenance status and weight licenses. Open-Unmix as an alternative. |
| MIDI | `mido` | Small, precise control over tempo events. | `pretty_midi` |
| MusicXML | A small purpose-built writer (stdlib `xml.etree` or `lxml`), validated against the MusicXML 4.0 XSD | Drum notation needs precise control of `<unpitched>`, instrument definitions, voices, noteheads, and beaming. **Confirm in M0 spike.** | music21 (supports percussion; evaluate whether its control over voicing and noteheads suffices) |
| Evaluation | `mir_eval` | Standard implementations of onset and beat metrics. | — |
| Testing and quality | pytest, Hypothesis, ruff, mypy, pip-audit | Property tests suit the quantizer; static checks catch errors cheaply. | — |
| Packaging and CI | `pyproject.toml` (hatchling), GitHub Actions matrix (Linux, macOS, Windows), PyPI trusted publishing | Minimal infrastructure. | — |

## 9. Quality assessment and correction workflow

Accuracy will vary by recording. The workflow lets users find errors quickly instead of assuming correctness.

1. **Read `report.md`.** It lists flagged measures with audio timestamps, the estimated tempo and its stability, per-class counts, and the settings used.
2. **Listen with `drumtx preview`.** Hearing synthesized hits against the original is the fastest way to spot misses, false hits, and wrong classes. The `--split-stereo` option plays the original on the left channel and the detected hits on the right.
3. **Fix rhythm problems with flags, not manual edits, and before editing hits.** A wrong downbeat, tempo, or meter garbles the whole score. `drumtx render --first-downbeat` or `--time-signature` fixes the bar position or meter in seconds. A wrong tempo needs `drumtx transcribe --bpm ... --force`, which reuses the cached detection; it refuses to overwrite an `events.csv` you have already edited.
4. **Fix hit-level errors** in either of two places:
   - in the notation editor or DAW, opening `.musicxml` or `.mid` directly; or
   - in `events.csv` (add, delete, or reclassify rows), followed by `drumtx render`.
   
   `--mark-uncertain` colors low-confidence notes in the score. Whether each notation app shows the color is verified in M4.
5. **Measure accuracy with `drumtx evaluate`** when a reference exists. This is for developers and for regression tracking.

The tool never claims a transcription is correct. Every report ends with a short limitations note.

## 10. Testing and evaluation

### Test levels

| Level | What | When |
|---|---|---|
| Unit | Ingest edge cases, peak picking, quantizer, mapping, writers, schema validation | Every commit |
| Property-based | Quantizer invariants: no event lost without a recorded merge; every event assigned to exactly one measure; idempotent re-quantization | Every commit |
| Golden files | MusicXML and MIDI output for fixed event lists. Diffs are reviewed when outputs change on purpose. | Every commit |
| Schema | MusicXML validated against the 4.0 XSD; `events.json` validated against its JSON Schema | Every commit |
| Synthetic end-to-end | MIDI patterns rendered to audio with CC0 samples (seeded; optional noise and backing) → `transcribe` → per-class F-measure above a fixture threshold; exact grid recovery at a known tempo | Every commit (short clips) |
| CLI | Commands, options, exit codes, messages through `CliRunner` | Every commit |
| Benchmark | Full development and test sets; per-class P/R/F, beat and downbeat F-measure, grid accuracy, runtime; compared against the last release | Nightly or manual; required before each release |
| Compatibility | Sample outputs opened in MuseScore (scripted conversion to PDF where MuseScore is available); manual checks in other apps chosen per open question Q4 | Nightly or manual; before each release |
| Cross-platform install | `pipx install` from the built wheel plus the `doctor` smoke test on 3 operating systems | Every commit to main; each release |
| Robustness | Corrupt, truncated, silent, very short, or very long files; unusual sample rates; non-ASCII paths | Every commit |

### Accuracy evaluation

- **Primary metric.** Per-class onset precision, recall, and F-measure with ±50 ms tolerance, using `mir_eval`. This is a common setting in ADT research. ±30 ms is also reported, since it is stricter.
- **Rhythm metrics.** Beat and downbeat F-measure. Grid accuracy, meaning the share of reference hits placed in the correct measure, beat, and slot, measured on clips with a reference score.
- **Data.**
  - A development set used for tuning, and a frozen held-out test set used only for release reports.
  - Each set is split into drum-only and full-mix subsets and stratified by style.
  - Annotations are of three kinds: onsets (CSV, same columns as `events.csv`) on every clip; beats and downbeats on every clip; and a reference score (onsets with `measure`, `beat`, `slot`) on a subset, for grid accuracy.
  - Candidate sources: public ADT datasets (for example ENST-Drums, MDB Drums, IDMT-SMT-Drums, E-GMD, ADTOF). Several carry research-only or non-commercial terms, so each needs a license check (M0-2). These are supplemented by a small set of recordings the team annotates itself, with permission.
- **Reporting.** Each model release ships a model card with per-class, per-subset results and known failure modes. Numbers are never quoted without saying which subset they come from.

## 11. Performance

| Item | Target | Approach |
|---|---|---|
| Runtime without separation | ≤ 1× real time on a reference laptop CPU (specified in M0) | ONNX Runtime CPU inference; vectorized features; chunked inference with overlap. |
| Runtime with separation | Measured and documented; expected to be several times slower on CPU | Optional `--device cuda`; caching so separation runs once per file. |
| Peak memory | < 2 GB for a 10-minute file without separation | Chunked processing; float32 throughout. |
| Re-runs | Quantize and render in seconds | Cache keyed by audio hash, stage, and parameters; `render` skips detection entirely. |
| Install size | Base install excludes PyTorch | Heavy dependencies only in `[separation]`. Model files downloaded once. |

## 12. Privacy and security

### Privacy

- All processing is local. There is no telemetry, analytics, or upload.
- The only network access is downloading a model, which happens on first use or through `drumtx models download`, and only from pinned URLs. `--offline` guarantees no network access. A CI test runs with networking disabled.
- Temporary files go in a private temp directory and are deleted on exit. The cache is stored inside the output directory and contains derived data only. `--no-cache` ignores and rebuilds it; deleting the folder removes it. A cached drum stem from separation can take hundreds of megabytes (about 200 MB for 10 minutes of float32 stereo).
- The JSON stores the source file name and hash, not the audio. The documentation notes that output folders may reveal file names.
- The documentation reminds users that they are responsible for having the rights to the audio they transcribe and to the resulting transcriptions.

### Security

- Input files are untrusted:
  - FFmpeg is invoked with argument lists, never through a shell.
  - Decoders and FFmpeg are kept current.
  - Duration and size limits are enforced before full decode where possible.
- Model files are verified by SHA-256 before loading. Formats that execute code on load (such as pickle) are not used; models ship as ONNX or safetensors.
- `transcribe` never overwrites existing files without `--force`, and never overwrites a hand-edited `events.csv`. `render` overwrites only the files it writes, never its input. Output paths are resolved and checked.
- `pip-audit` runs in CI. Dependencies are pinned in a lock file used by CI and release builds.

## 13. Key technical risks and trade-offs

| Risk / trade-off | Impact | Mitigation |
|---|---|---|
| Accuracy on full mixes is much lower than on drum-only audio | Users get noisy drafts | Optional separation; honest per-subset reporting; review tooling; `--sensitivity` presets. |
| Hi-hat vs. cymbal confusion; merged tom and cymbal classes | Wrong noteheads and classes | Five-class vocabulary for the MVP; classes flagged as lower-confidence; finer classes deferred. |
| Beat or downbeat errors (half/double tempo, bar offset) | Entire score shifted or garbled | User overrides; tempo-stability flags; fast re-runs from cache; report shows the estimated values prominently. |
| Rubato, tempo changes, swing | Off-grid events, wrong triplet choices | Per-beat grid selection; residual flags; one tempo marking in notation but a full tempo map in MIDI; swing handling is post-MVP. |
| Licensing of pretrained models and datasets | May block distribution or commercial use | License review in M0 before any adoption; recorded in a decision record; option to train only on permissive data. |
| Choosing separation vs. no separation by default | Quality vs. speed and install size | Off by default in MVP; documented recommendation for full mixes; revisit after beta (Q3). |
| Valid MusicXML that still reads poorly (voicing, beaming, rests) | Users must reformat | Notation readability rules (M4-2); review by a drummer; golden files. |
| Training data does not match user recordings | Benchmarks overstate quality | Mix of datasets plus self-annotated real-world clips; collect consented failure cases in beta. |
| Permissive licensing (Q1) leaves mostly electronic-kit, drum-only training data (for example E-GMD, CC BY 4.0) | Weak results on acoustic kits and full mixes | Decide Q1 knowing this cost; augment with backing-track mixing and self-recorded acoustic clips; report full-mix numbers separately. |
| Beat tracker choice pulls PyTorch or unmaintained code into the base install | Larger install or install failures | Install footprint and Python-version support are M0-5 selection criteria; ONNX export or an extra if needed. |
| Optional dependencies break across operating systems | Installation failures | Lightweight base install; `doctor` command; CI install matrix. |

## 14. Open questions

Each question has a working default used until it is resolved.

| # | Question | Why it matters | Working default |
|---|---|---|---|
| Q1 | Distribution and license model: open source (which license), free to use, any commercial intent? | Decides which models and datasets are allowed. | Permissive open source; avoid non-commercial components in the default install. |
| Q2 | Adopt a pretrained ADT model or train our own? | Largest effect on effort and accuracy. | Decided by M0-4 spike and M0-2 license review. |
| Q3 | Should `--separate` be on by default? | Quality vs. runtime and install size. | Off; revisit after beta data. |
| Q4 | Which notation apps must be officially supported? | Defines the compatibility test matrix. | MuseScore required; others best-effort. |
| Q5 | Primary input type expected from users: isolated drums or full mixes? | Tuning priorities and defaults. | Optimize for both; report separately. |
| Q6 | Is GPU support a requirement? | Test matrix and packaging complexity. | Separation only (`--device cuda`); detection is CPU-only. Untested beyond a smoke test. |
| Q7 | Where are model files hosted? | Release process and availability. | GitHub Releases assets with checksums. |
| Q8 | Is a Python library API part of the public contract for v0.1? | Stability promises. | Internal; only the CLI and `events.json` schema are stable. |

## 15. Post-MVP enhancements

- Open/closed hi-hat; specific toms (high, mid, floor); ride vs. crash; hi-hat pedal.
- Notation of articulations: ghost notes, accents, flams, rimshots.
- Swing detection and notation; compound meters; time-signature changes; tempo-change markings.
- PDF output; `.mxl`; MIDI import for correction round-trips.
- Batch processing of folders; config file.
- Fine-tuning on user-corrected data, with explicit consent.
- GUI or web front end built on the same library.
