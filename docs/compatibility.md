# Notation app compatibility (M4-5)

DrumTx writes uncompressed MusicXML 4.0. **MuseScore is the only supported notation app** (decision 0007, open question Q4). Every output is validated against the MusicXML 4.0 XSD in CI. This page records which apps have been checked and how.

## Results

| App | How it was checked | Result |
|---|---|---|
| MuseScore 3.2.3 (Ubuntu 24.04 package) | Automated: `scripts/check_musescore.py` on every development-set clip, nightly and on demand (the Benchmark workflow) | **159 of 159** files open without import errors (2026-11-05, default ADTOF detector); MIDI export matches the score note for note |
| MuseScore 3.2.3 | Visual: rendered scores for the M4-2 checklist (ten clips), M4-3 (red uncertain notes) and M4-4 (pickup numbering) | Notation, coloring and measure numbers as intended (`docs/notation-checklist.md`, decision 0007) |
| MuseScore 4 | Manual, by the owner: open `tests/golden/triplet.musicxml` and a file written with `--mark-uncertain` | Not yet checked; record the result below |
| Other apps (Dorico, Sibelius, Finale, Guitar Pro, Flat, …) | Not checked | Not supported (Q4). They may import the files, since the XSD check passes, but nothing has been verified. Colors from `--mark-uncertain` may be ignored. |

The development set has 189 clips. 30 of them are E-GMD clips under 2 s (29 of them fills), which `transcribe` refuses as too short, so they have no MusicXML. The 159 others are 87 E-GMD clips, 48 IDMT-SMT-Drums clips and 24 MDB Drums clips (12 drum-only, 12 full mix).

## How the automated check works

```bash
uv run python scripts/check_musescore.py --data ~/drumtx-data --out musescore-check
```

1. **Transcribe** each development-set clip with the default settings (`--model` picks the detector). Outputs are kept in `--out` and reused on the next run.
2. **Convert** each MusicXML file to MIDI with `mscore3 -o x.mid x.musicxml`, run with `QT_QPA_PLATFORM=offscreen`, so no display is needed.
3. **Read MuseScore's messages.** MuseScore's command line exits 0 and prints `... success!` even for a broken file: overfull measures, invalid elements and truncated files all "succeed". So a file passes only if MuseScore prints nothing but its progress lines and `element already exists`. That warning is benign: MuseScore 3 logs it whenever two notes start on the same tick (decision 0007).
4. **Compare the MIDI export:** it must have one channel-10 note for each note of the score.

The script exits 1 if any file fails. In CI it runs in the Benchmark workflow (`.github/workflows/benchmark.yml`), nightly and on demand, even when the benchmark itself reports a regression. It takes about 10 minutes for the development set on 4 cores.

## Manual checks

Add a row here for each manual check: app and version, date, file, and what you saw.

| App and version | Date | File | Result |
|---|---|---|---|
| | | | |
