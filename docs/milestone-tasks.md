# Milestone Task List: DrumTx MVP (v0.1)

## How to use this list

- **Milestones** M0–M7 are sequenced. Some milestones can overlap where the dependencies allow it:
  - M3 can start once M1-7 exists, using the baseline detector.
  - M4 can start once the M3-2 quantizer interface is stable.
- **No dates are given**, because no timeline was specified. The team should size the tasks during M0.
- **Task IDs** (for example M2-3) are referenced in dependency notes. Open questions Q1–Q8 refer to the Technical Design Document.

### Definition of done (applies to every task)

- Code reviewed and merged.
- Tests added and passing in CI on Linux, macOS, and Windows.
- User-facing behavior documented.
- No new lint or type errors.
- Any decision recorded in `docs/decisions/` when one was made.

## M0 — Foundations and feasibility

**Goal:** Set up the project skeleton and resolve the decisions that most affect scope: model approach, beat tracker, MusicXML approach, licensing, and evaluation data.

**M0-1 — Repository, packaging, and CLI stub**
- *Description:* Create a `src/` layout, `pyproject.toml`, and a Typer entry point with stub commands (`transcribe`, `render`, `preview`, `evaluate`, `models`, `doctor`). Set up ruff, mypy, pytest, and a lock file.
- *Acceptance criteria:*
  - `pipx install .` works on all three operating systems.
  - `drumtx --help` and `drumtx --version` work.
  - The CI matrix (3 operating systems × supported Python versions) runs lint, type checks, and tests on every pull request.

**M0-2 — License and component review**
- *Description:* List candidate detection models, beat trackers, separation models, datasets, and drum samples, each with its license and usage terms. Recommend components given Q1.
- *Acceptance criteria:*
  - A decision record contains a table of components, licenses, and verdicts (allowed / allowed as optional extra / excluded).
  - Every non-commercial or unclear item is flagged.
- *Dependencies:* Q1 must be resolved, or the working default accepted.

**M0-3 — Evaluation corpus and annotation format**
- *Description:* Define the reference annotation format (CSV, same columns as `events.csv`). Assemble a development set and a held-out test set, each with drum-only and full-mix subsets, from allowed sources plus self-recorded or permitted clips.
- *Acceptance criteria:*
  - A manifest lists every clip with its source, license, subset, and split.
  - Splits are frozen and hashed.
  - A written rule says the test set is used only for release evaluation.
  - Each subset contains enough clips to give stable per-class numbers; the team sets the count and records the rationale.
- *Dependencies:* M0-2.

**M0-4 — Spike: drum detection approach**
- *Description:* On 5–10 development clips, compare three options: a classical prototype, a candidate pretrained model (if its license allows), and a small trained-model prototype or a training-effort estimate.
- *Acceptance criteria:*
  - A written comparison covers per-class F-measure, runtime, install footprint, and license.
  - A recommendation resolves Q2.
- *Dependencies:* M0-2, M0-3.

**M0-5 — Spike: beat and downbeat tracking**
- *Description:* Compare candidate trackers on development clips with beat annotations.
- *Acceptance criteria:*
  - Beat and downbeat F-measure, failure modes (half or double tempo, bar offset), runtime, and license are documented.
  - One tracker is selected, along with a fallback.
- *Dependencies:* M0-2, M0-3.

**M0-6 — Spike: MusicXML percussion output**
- *Description:* Write a hand-built two-bar groove (kick, snare, hi-hat, one triplet beat) twice: once with music21 and once with a minimal custom writer.
- *Acceptance criteria:*
  - Both files are checked in MuseScore (plus any apps chosen under Q4) for staff positions, x noteheads, two voices, beaming, and a triplet.
  - A decision record names the chosen approach.
  - The sample file is committed as a future golden file.

**M0-7 — Data contracts**
- *Description:* Define the `DrumEvent`, `TempoMap`, and `QuantizedScore` types; the `events.json` schema v1 (published as JSON Schema); the CSV format; the class vocabulary; and the default instrument mapping in TOML.
- *Acceptance criteria:*
  - The JSON Schema file and example files validate in tests.
  - The mapping table matches the Technical Design Document §5.
  - The schema documentation is written.

**M0-8 — Reference hardware and initial estimates**
- *Description:* Specify the reference machine used for performance targets. Size the M1–M7 tasks.
- *Acceptance criteria:*
  - The reference machine specification is recorded.
  - Every task has an estimate.
  - Risks raised by the spikes are added to the risk register in the Technical Design Document.

## M1 — Ingest, baseline detection, and evaluation harness

**Goal:** Make `transcribe` produce an unquantized event list end to end with a classical detector, and measure it.

**M1-1 — Audio ingest**
- *Description:* Decode with `soundfile`, falling back to FFmpeg. Downmix, resample to 44.1 kHz, apply `--start` and `--end`, and enforce duration limits.
- *Acceptance criteria:*
  - WAV, FLAC, and MP3 test files decode on all operating systems.
  - A missing FFmpeg for M4A gives exit code 3 and an install hint.
  - Corrupt or unsupported files give exit code 2 and a clear message.
  - Files over 10 minutes are rejected unless `--max-duration` is set.
  - Non-ASCII paths work.
- *Dependencies:* M0-1.

**M1-2 — Pipeline orchestration and cache**
- *Description:* Add a `RunContext`, stage execution, a cache keyed by audio SHA-256, stage, and parameters, progress output, and `-v`/`-q`.
- *Acceptance criteria:*
  - Re-running with only quantize options changed skips Ingest and Detect, as shown in a test.
  - `--no-cache` forces recomputation.
  - The cache stays inside the output directory.
- *Dependencies:* M0-7, M1-1.

**M1-3 — Baseline detector**
- *Description:* Implement `BaselineDetector`: spectral-flux onsets plus band-energy (or NMF) classification for all five classes.
- *Acceptance criteria:*
  - Emits schema-valid events.
  - Per-class development-set results are recorded as the regression floor.
  - Isolated synthetic hits are detected within ±10 ms.
- *Dependencies:* M0-4, M1-1.

**M1-4 — Evaluation command**
- *Description:* Implement `drumtx evaluate` using `mir_eval` onset metrics. Accept a reference as MIDI (GM drum mapping) or CSV. Make the tolerance configurable. Write JSON and Markdown output.
- *Acceptance criteria:*
  - Results on hand-computed fixtures match expectations exactly.
  - Per-class and overall P/R/F are reported at 50 ms and 30 ms.
  - Unknown MIDI notes are reported, not silently dropped.
- *Dependencies:* M0-7.

**M1-5 — Synthetic fixture generator**
- *Description:* A seeded script renders MIDI drum patterns to audio using CC0 samples, with optional noise and backing tracks.
- *Acceptance criteria:*
  - Output is deterministic (identical hashes across runs and operating systems within tolerance).
  - Fixtures cover straight 16ths, triplets, and simultaneous hits.
  - The fixtures are used in an end-to-end test that runs in under 60 seconds in CI.
- *Dependencies:* M0-2 (sample licenses).

**M1-6 — Benchmark runner**
- *Description:* One command runs a detector over the development set or (in release mode) the test set, and writes a results table and runtime.
- *Acceptance criteria:*
  - Results include the commit and model ID.
  - A comparison against the previous results file highlights per-class regressions above a configurable margin.
  - It runs as a manual or nightly CI job.
- *Dependencies:* M1-3, M1-4, M0-3.

**M1-7 — Unquantized event outputs**
- *Description:* `transcribe` writes `events.json` and `events.csv` (detection only, empty tempo map).
- *Acceptance criteria:*
  - Outputs are schema-valid.
  - Existing files are not overwritten without `--force`.
  - Exit codes match the Technical Design Document §4.
- *Dependencies:* M1-2, M1-3.

## M2 — Learned detection and optional separation

**Goal:** Replace the baseline with a learned detector that measurably beats it, and add optional drum isolation.

**M2-1 — Obtain the model (per Q2)**
- *Description:* Either integrate the chosen pretrained model, or build a reproducible training pipeline (config, data loaders, augmentation, CRNN with five outputs) and train on allowed data.
- *Acceptance criteria:*
  - The model beats the M1 baseline in per-class F-measure on the development set for kick, snare, and hi-hat.
  - Training, or conversion of the pretrained model, is reproducible from a documented command.
  - A model card exists.
- *Dependencies:* M0-4, M1-6.

**M2-2 — ONNX export and inference runtime**
- *Description:* Export to ONNX. Implement `ModelDetector` with chunked inference and overlap-add.
- *Acceptance criteria:*
  - Activations from ONNX match the training framework within a set tolerance (for example a maximum absolute difference of 1e-4).
  - Chunk boundaries cause no duplicate or missed peaks (fixture test).
  - Memory stays bounded on a 10-minute file.
- *Dependencies:* M2-1.

**M2-3 — Peak picking and sensitivity presets**
- *Description:* Tune per-class thresholds and minimum gaps on the development set only, for `strict`, `balanced`, and `sensitive`.
- *Acceptance criteria:*
  - Thresholds are stored alongside the model.
  - On the development set, `strict` has higher precision and `sensitive` higher recall than `balanced` for each core class.
  - The presets are documented.
- *Dependencies:* M2-2.

**M2-4 — Confidence and velocity**
- *Description:* Calibrate confidence values. Map activation or onset energy to velocity.
- *Acceptance criteria:*
  - Confidence is in [0, 1], and higher-confidence bins have higher precision on the development set (reliability table in the model card).
  - Velocity is in 1–127 and increases with activation.
  - The documentation states that velocity is approximate.
- *Dependencies:* M2-2.

**M2-5 — Model distribution**
- *Description:* Model registry with ID, version, URL, SHA-256, and license. Download on first use into a per-user cache directory. Implement `drumtx models list|download` and `--offline`.
- *Acceptance criteria:*
  - A tampered or corrupted file is rejected with a clear error.
  - `--offline` works with a pre-downloaded model and fails with exit code 3 when the model is absent.
  - A CI test with networking disabled passes.
  - Only ONNX or safetensors formats are loaded.
- *Dependencies:* M2-2; Q7.

**M2-6 — Optional separation**
- *Description:* Add the `[separation]` extra and the `--separate` flag, with lazy import and device selection. Beat tracking stays on the full mix.
- *Acceptance criteria:*
  - Without the extra, the error message gives the exact `pipx inject` or `pip` command (exit code 3).
  - On the full-mix development subset, results with and without separation are reported, along with runtime.
  - The separated stem is cached.
- *Dependencies:* M1-2, M0-2.

**M2-7 — Model release evaluation**
- *Description:* Run the frozen test set once for the candidate model.
- *Acceptance criteria:*
  - The model card contains per-class, per-subset P/R/F at 50 ms and 30 ms, plus known failure modes.
  - Results are copied into `docs/accuracy.md`.
- *Dependencies:* M2-3, M2-6.

## M3 — Tempo, quantization, and MIDI

**Goal:** Place events on a metrical grid and produce MIDI that lines up with the source audio.

**M3-1 — Beat tracking and tempo map**
- *Description:* Integrate the beat tracker chosen in M0-5. Build the `TempoMap`. Honor `--bpm`, `--time-signature` (N/4), and `--first-downbeat`.
- *Acceptance criteria:*
  - The tempo map is stored in `events.json`, with each value marked as estimated or user-supplied.
  - Overrides demonstrably change the result (tests).
  - Half-time and double-time results can be corrected through `--bpm` (test).
- *Dependencies:* M0-5, M1-2.

**M3-2 — Quantizer**
- *Description:* Per-beat grid selection (16th / triplet / auto, with a penalty on triplets), slot assignment, collision merging with recorded flags, and residuals.
- *Acceptance criteria:*
  - Property tests pass: every event is assigned to exactly one measure; merges are recorded; re-quantization is idempotent.
  - Synthetic straight and triplet grooves at known tempo are quantized 100% correctly.
  - Residuals are within 1 ms of the computed value in tests.
- *Dependencies:* M3-1, M0-7.

**M3-3 — Review flag computation**
- *Description:* Flag uncertain events, measures with large residuals, tempo deviation, and merges, using configurable thresholds.
- *Acceptance criteria:*
  - Flags appear in `events.json` per event and per measure.
  - The thresholds are documented.
  - Fixture tests cover each flag type.
- *Dependencies:* M3-2, M2-4.

**M3-4 — MIDI writer**
- *Description:* Type 1 Standard MIDI File, channel 10, with notes from the mapping. Tempo events at each beat for `--midi-timing quantized`; raw times for `performance`.
- *Acceptance criteria:*
  - Converting ticks back to seconds puts quantized notes within ±5 ms of their beat-grid times.
  - The file opens in at least one DAW and in MuseScore, lined up with the audio (manual check, recorded).
  - Golden-file tests pass.
- *Dependencies:* M3-2, M3-5.

**M3-5 — Instrument mapping configuration**
- *Description:* Load the default TOML mapping and accept a user-supplied file through `--mapping`.
- *Acceptance criteria:*
  - A custom mapping changes MIDI notes and staff positions.
  - Invalid files produce errors naming the bad key (exit code 2).
- *Dependencies:* M0-7.

## M4 — MusicXML notation output

**Goal:** Produce valid, readable drum notation that opens cleanly in the target notation apps.

**M4-1 — MusicXML writer core**
- *Description:* Percussion part with an instrument list, `divisions = 12`, measures, time signature, a single tempo marking (median tempo), two voices, rests, and noteheads per the mapping.
- *Acceptance criteria:*
  - Every output validates against the MusicXML 4.0 XSD in CI.
  - Golden files exist for straight, triplet, and empty-measure cases.
- *Dependencies:* M0-6, M3-2, M3-5.

**M4-2 — Readability rules**
- *Description:* Beam groups per beat, rest consolidation, triplet brackets, stem direction per voice, and note durations that extend to the next hit within the beat.
- *Acceptance criteria:*
  - A written checklist is agreed with a drummer reviewer.
  - Ten varied outputs from the development set pass the checklist in MuseScore.
  - Remaining issues are logged.
- *Dependencies:* M4-1.

**M4-3 — Uncertain-note marking**
- *Description:* With `--mark-uncertain`, color notes below the review threshold.
- *Acceptance criteria:*
  - Colored notes appear in MuseScore, or the documentation states which apps ignore color.
  - Without the flag, no color attributes are written.
- *Dependencies:* M4-1, M3-3.

**M4-4 — Edge cases**
- *Description:* Handle audio before the first downbeat (pad a leading measure with rests), a trailing partial measure, long silences, and very dense passages.
- *Acceptance criteria:*
  - Each case has a fixture test producing schema-valid, sensible output.
  - Measure numbers in the score match measure numbers in the report.
- *Dependencies:* M4-1.

**M4-5 — Compatibility testing**
- *Description:* A script opens or converts corpus outputs with the MuseScore command line where available; apps chosen under Q4 are checked manually.
- *Acceptance criteria:*
  - 100% of development-set outputs open without import errors in MuseScore.
  - Results for other apps are recorded in `docs/compatibility.md`.
  - A nightly or manual CI job exists.
- *Dependencies:* M4-2; Q4.

## M5 — Review and correction workflow

**Goal:** Give users a fast, reliable way to find and fix transcription errors.

**M5-1 — Review report**
- *Description:* `report.md` with the run settings, model ID, tempo summary (and stability), per-class counts, flagged measures with audio timestamps and reasons, a "suggested next steps" section (override flags, preview), and a limitations note.
- *Acceptance criteria:*
  - Generated on every `transcribe` and `render` run.
  - Flagged measure timestamps match the audio (spot-checked on 5 clips).
  - Readable as plain text and as rendered Markdown.
- *Dependencies:* M3-3.

**M5-2 — `preview` command**
- *Description:* Mix the original audio (reduced in level) with hits synthesized from bundled CC0 samples per class. Option `--split-stereo`.
- *Acceptance criteria:*
  - Synthesized hits are within ±10 ms of event times (fixture test).
  - Output is a WAV file at the source length.
  - Works from either JSON or CSV events.
- *Dependencies:* M1-7, M0-2.

**M5-3 — `render` from edited events**
- *Description:* Load JSON or CSV (with the tempo map from the sibling JSON file or from flags), validate, re-quantize, and re-render the selected formats.
- *Acceptance criteria:*
  - Adding, deleting, or reclassifying CSV rows is reflected in the MusicXML and MIDI (end-to-end test).
  - Validation errors list the row numbers.
  - Detection does not run.
- *Dependencies:* M3-2, M4-1, M3-4.

**M5-4 — Tune flag thresholds**
- *Description:* Using the development set, tune the review thresholds so flagged measures capture a large share of actual errors without flagging most of the piece.
- *Acceptance criteria:*
  - A documented trade-off table shows the share of erroneous measures flagged against the share of all measures flagged.
  - Default thresholds are chosen and recorded.
- *Dependencies:* M5-1, M2-7.

**M5-5 — Correction guide**
- *Description:* A tutorial covering: read the report → preview → fix tempo and downbeat with flags → fix hits in MuseScore or CSV → re-render. Uses a sample file the project can share.
- *Acceptance criteria:*
  - A team member who has not used the tool completes the guide on the sample without help.
  - Screenshots and commands are current.
- *Dependencies:* M5-1–M5-3.

**M5-6 — (Stretch) Event plot**
- *Description:* With the `[plot]` extra, `--plot` writes a PNG piano roll of events over time with flagged regions shaded.
- *Acceptance criteria:*
  - Works when the extra is installed.
  - Without the extra, exit code 3 with an install hint.
- *Dependencies:* M3-3.

## M6 — Hardening, performance, security, and documentation

**Goal:** Make the tool dependable to install and run, and fully documented.

**M6-1 — Performance**
- *Description:* Profile the pipeline. Optimize to the Technical Design Document §11 targets.
- *Acceptance criteria:*
  - A 4-minute track without separation runs at ≤ 1× real time on the reference machine.
  - Peak memory is < 2 GB on a 10-minute file.
  - Runtime with separation is measured and documented.
  - Benchmark results are stored.
- *Dependencies:* M2-6, M4-1.

**M6-2 — Errors and messages**
- *Description:* Audit every failure path for an actionable message and the correct exit code.
- *Acceptance criteria:*
  - The exit-code table in the documentation matches tests.
  - Each code path has at least one test.
  - No tracebacks appear without `-v`, except for exit code 1.
- *Dependencies:* M1–M5.

**M6-3 — Security review**
- *Description:* Verify that subprocesses never use a shell, model loading is safe, output paths are checked, temp files are cleaned up, and input limits hold. Add `pip-audit` to CI.
- *Acceptance criteria:*
  - A security checklist is completed and committed.
  - Fuzz tests with corrupt or truncated files cause no crashes beyond exit codes 2 or 4.
  - `pip-audit` reports no known high-severity issues at release time.
- *Dependencies:* M1-1, M2-5.

**M6-4 — Privacy verification**
- *Description:* Confirm there is no network access except model download, and no telemetry.
- *Acceptance criteria:*
  - A full-pipeline CI test runs with networking blocked and `--offline`.
  - The privacy section of the documentation is written.
- *Dependencies:* M2-5.

**M6-5 — `doctor` and cross-platform polish**
- *Description:* `doctor` reports the Python version, decoders, FFmpeg, extras, models, and device. Handle Windows path quirks.
- *Acceptance criteria:*
  - `doctor` output is correct in CI on all three operating systems, both with and without FFmpeg and the extras.
  - Install from the wheel plus a smoke test passes on all three operating systems.
- *Dependencies:* M0-1.

**M6-6 — Documentation set**
- *Description:* README (what it does and does not do), install guide, quickstart, CLI reference (generated from Typer), output formats and schema, accuracy and limitations (from M2-7), correction guide (M5-5), troubleshooting, and contributing guide.
- *Acceptance criteria:*
  - Every documented command is tested by a docs check that runs it.
  - The limitations page states expected accuracy differences between drum-only and full-mix audio.
  - The documentation is reviewed by someone outside the core team.
- *Dependencies:* M5-5, M2-7.

## M7 — Beta and v0.1 release

**Goal:** Validate with real users, fix the most important problems, and ship v0.1 with an honest accuracy statement.

**M7-1 — Private beta**
- *Description:* Recruit about 5–10 testers, a mix of musicians and developers. Provide a pre-release build, a feedback template, a short survey on correction effort compared with manual transcription, and an opt-in way to share failure cases (audio shared only with explicit permission).
- *Acceptance criteria:*
  - Feedback is collected from all active testers.
  - Issues are triaged by severity.
  - Survey results are summarized against the success measure in the brief.
- *Dependencies:* M6.

**M7-2 — Beta fixes and re-tuning**
- *Description:* Fix top-priority issues. Re-tune presets and flag thresholds using only the development set, plus consented beta clips added to the development set.
- *Acceptance criteria:*
  - All severity-1 issues are closed.
  - The benchmark shows no regressions on the development set.
  - The test set remains untouched until M7-4.
- *Dependencies:* M7-1.

**M7-3 — Release engineering**
- *Description:* Semantic versioning, changelog, PyPI publishing through CI trusted publishing, model artifacts with checksums at the Q7 location, and a release checklist.
- *Acceptance criteria:*
  - A dry-run release to TestPyPI installs and passes the smoke test on all three operating systems.
  - Model checksums in the registry match the hosted files.
  - The checklist is committed.
- *Dependencies:* M2-5, M6-5.

**M7-4 — Final evaluation and accuracy statement**
- *Description:* Run the frozen test set with the release build and update the model card and `docs/accuracy.md`.
- *Acceptance criteria:*
  - Published numbers come from the release build.
  - The subsets and tolerances are stated.
  - Known failure modes are listed.
  - Comparison with the brief's provisional targets is reported honestly, including any misses.
- *Dependencies:* M7-2.

**M7-5 — v0.1.0 release and post-release plan**
- *Description:* Publish, announce with the limitations clearly stated, and set up issue templates for bug reports and transcription-quality reports.
- *Acceptance criteria:*
  - The package is installable from PyPI.
  - Release notes link to the accuracy and limitations pages.
  - A triage owner and cadence are agreed.
  - A post-MVP backlog is created from the Technical Design Document §15 and beta feedback.
- *Dependencies:* M7-3, M7-4.

## Dependency summary

```text
M0 ──► M1 ──► M2 ──► M3 ──► M4 ──► M5 ──► M6 ──► M7
             │        ▲      ▲
             └────────┘      │   M3 may start on the baseline detector after M1-7
                    M3-2 ────┘   M4 may start once the quantizer interface is stable
```

## Post-MVP backlog (seed)

- Open/closed hi-hat, specific toms, ride vs. crash, hi-hat pedal.
- Notation of ghost notes, accents, and flams.
- Swing handling; compound and changing meters; tempo-change markings.
- PDF and `.mxl` export; MIDI import for correction round-trips.
- Batch mode; config file; Docker image or standalone binaries.
- Opt-in fine-tuning from corrected transcriptions.
- GUI or web front end on the library API.
