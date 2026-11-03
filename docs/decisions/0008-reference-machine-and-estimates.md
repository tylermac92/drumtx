# 0008 — Reference machine and task estimates

- **Status:** Accepted, 2026-11-03
- **Task:** M0-8

## Reference machine

The performance targets in the Technical Design Document §11 (≤ 1× real time without separation, < 2 GB peak memory) are measured on your own laptop:

| | |
|---|---|
| Machine | Lenovo Legion Pro 5 |
| CPU | Intel Core i7-14700HX: 20 cores (8 performance, 12 efficiency), 28 threads |
| Memory | 32 GB |
| OS | Windows 11 |
| GPU | Not used for the targets. It is used only for timing `--separate --device cuda`. |

**How M6-1 measures it:**
- Plug the laptop into mains power and set Windows to its best-performance power mode.
- Download the models beforehand.
- Run `drumtx transcribe` with `--no-cache` on a 4-minute track and time it from start to exit.
- Record the median of three runs.

**Headroom.** This is a fast laptop, so the 1× target is easy to meet on it. The spikes measured about 0.8 s of detection (decision 0005) and about 2 s of beat tracking (decision 0006) per audio minute. That was on a 4-core cloud sandbox, which already runs about 20× faster than real time before decoding, quantizing and rendering. That margin supports the brief's promise of running on "an ordinary laptop CPU", so no second, slower machine is specified. If M6-1 finds the pipeline using more than about 0.25× real time on the reference machine, it also checks a 4-thread run, to stand in for a modest laptop.

## Estimates

**Unit:** focused days. A focused day is about 6 hours of your attention, including:
- reviewing pull requests;
- fixing CI;
- manual checks in MuseScore or a DAW;
- hand annotation.

Code is written with Claude Code, as in M0. Ranges run from "goes as planned" to "one significant surprise". Waiting time (downloads, CI queues) is excluded.

| Task | Days | Basis |
|---|---|---|
| M1-1 Audio ingest | 1–2 | FFmpeg fallback, size and duration limits, and decoding checks on 3 operating systems. |
| M1-2 Pipeline orchestration and cache | 1.5–2.5 | Cache keys, stage skipping, progress output. |
| M1-3 Baseline detector | 1–2 | The classical prototype in `spikes/m0-4/` already exists. |
| M1-4 Evaluation command | 1–2 | `mir_eval` does the metrics; MIDI and CSV references, JSON and Markdown output. |
| M1-5 Synthetic fixture generator | 1–2 | Drum sounds synthesized in code; matching across operating systems is the risk. |
| M1-6 Benchmark runner | 1.5–2.5 | Includes the target review and its decision record. |
| M1-7 Unquantized event outputs | 1–1.5 | The format exists (M0-7); adds the writers, `--force`, and CSV-hash protection. |
| M2-1 Obtain the model | 1.5–3 | The port exists (decision 0005); adds a conversion command, a one-time check against madmom features, and a model card. |
| M2-2 ONNX export and inference runtime | 1–2 | Chunking with overlap, and a fixture test at chunk boundaries. |
| M2-3 Peak picking and sensitivity presets | 1–2 | Threshold sweeps on the development set. |
| M2-4 Confidence and velocity | 1–2 | Calibration plus a reliability table. |
| M2-5 Model distribution | 1.5–2.5 | Registry, download, SHA-256 checks, offline mode, a test with networking off. |
| M2-6 Optional separation | 2–4 | Open-Unmix extra on PyTorch; installation across operating systems and the full-mix comparison are the risk. |
| M2-7 Model release evaluation | 0.5–1 | One test-set run and the write-up. |
| M3-1 Beat tracking and tempo map | 2–4 | NumPy mel features and postprocessing must match upstream within one frame (decision 0006). |
| M3-2 Quantizer | 2–3 | Grid choice, merges, residuals, property tests. |
| M3-3 Review flag computation | 1–1.5 | Thresholds and fixtures for four flag types. |
| M3-4 MIDI writer | 1–2 | Tempo event per beat; manual check in a DAW and in MuseScore. |
| M3-5 Instrument mapping configuration | 0.5–1 | The TOML file exists (M0-7); adds loading and error messages. |
| M3-6 Rhythm evaluation | 1–2 | Grid accuracy, benchmark columns, target decision. |
| M4-1 MusicXML writer core | 1.5–2.5 | Starts from the spike writer (decision 0007). |
| M4-2 Readability rules | 2–4 | Rest consolidation and durations are fiddly; ten outputs checked by hand. |
| M4-3 Uncertain-note marking | 0.5–1 | Color attributes, checked in MuseScore. |
| M4-4 Edge cases | 1–2 | Pickup, trailing partial measure, silence, dense passages. |
| M4-5 Compatibility testing | 1–2 | MuseScore command-line script and a CI job. |
| M5-1 Review report | 1–2 | Markdown report; timestamps spot-checked on 5 clips. |
| M5-2 `preview` command | 1–1.5 | Reuses the M1-5 drum sounds. |
| M5-3 `render` from edited events | 2–3 | CSV validation with row numbers, overrides, JSON rewrite rules. |
| M5-4 Tune flag thresholds | 1–2 | Needs measure-level error labels from the development set. |
| M5-5 Correction guide | 1–2 | Written while doing it on one of your own recordings. |
| M5-6 (Stretch) Event plot | 0.5–1 | matplotlib extra. |
| M6-1 Performance | 1–2 | Large headroom (see above); mostly measurement. |
| M6-2 Errors and messages | 1–2 | Audit and one test per exit-code path. |
| M6-3 Security review | 1.5–2.5 | Checklist, fuzz tests, `pip-audit`. |
| M6-4 Privacy verification | 0.5–1 | Offline full-pipeline CI test. |
| M6-5 `doctor` and cross-platform polish | 1–2 | Windows path issues; CI with and without FFmpeg. |
| M6-6 Documentation set | 1.5–3 | Includes a docs check that runs every command. |
| M7-1 Personal trial | 3–5 | 5–10 recordings, two of them also transcribed by hand for the timing comparison. |
| M7-2 Trial fixes and re-tuning | 3–6 | Unknown until the trial; the range is a budget. |
| M7-3 Release engineering | 0.5–1 | Changelog, checklist, wheel smoke test. |
| M7-4 Final evaluation and accuracy statement | 0.5–1 | One release-build test-set run and the write-up. |
| M7-5 v0.1.0 tag and post-MVP backlog | 0.5–0.5 | Tag, release notes, backlog. |

### Totals

| Milestone | Days |
|---|---|
| M1 | 8–14.5 |
| M2 | 8.5–16.5 |
| M3 | 7.5–13.5 |
| M4 | 6–11.5 |
| M5 | 6.5–11.5 |
| M6 | 6.5–12.5 |
| M7 | 7.5–13.5 |
| **M1–M7** | **50.5–93.5** |

That is roughly 10–19 weeks at five focused days a week. At one focused day a week, it is about one to two years.

### Not included

These are only needed if something goes wrong or you choose to do them:

- **Training our own detector:** 5–10 days, plus GPU or multi-day CPU time (decision 0005). Needed only if ADTOF falls short on your recordings in M2-1 or M7-1.
- **The PyTorch fallback for the beat tracker:** 1–2 days. Needed only if M3-1's one-frame match fails (decision 0006).
- **Full-mix tom annotation** (decision 0004, known gaps): 5–10 of your own songs per split, at 1–2 hours of annotation per minute of audio. For 3–4-minute songs that is roughly 5–25 days, the largest optional item. Without it, full-mix tom numbers stay below the stability minimum and are reported as unreliable. M7-2 can add some annotated trial clips, which covers part of this.

### Biggest uncertainties

M2-6 (separation install), M3-1 (matching upstream beats), M4-2 (readability) and M7-2 (trial fixes) have the widest ranges. Re-estimate after M1, when the real pace on this codebase is known.
