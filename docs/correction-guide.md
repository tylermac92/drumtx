# Correcting a transcription

DrumTx gets most hits right, never all of them. This guide takes one recording from a first transcription to a corrected score in this order:
1. Transcribe it.
2. Read the report.
3. Listen to the preview.
4. Fix the rhythm: bar lines, meter and tempo.
5. Fix the hits.
6. Render again.

**Fix the rhythm before any hit.** Every hit is placed relative to the bar lines, so moving bar 1 later would move everything you had already edited.

## The example

The commands below use `groove.wav`, a 20-second drum recording generated in code, so you can follow along. To make it, run this from a clone of the DrumTx repository:

```bash
uv run python scripts/make_guide_sample.py drumtx-guide
```

```bash
cd drumtx-guide
```

The groove is at 96 BPM in 4/4:
- **Fill:** two beats of fill (two snares, then two toms) before bar 1, which starts at 3.5 s.
- **Groove:** six bars of hi-hat, kick and snare, with quiet "ghost" snare notes on the last 16th of beats 2 and 4.
- **End:** a crash on the last downbeat.

`groove.truth.csv` lists every hit, so you can check your result at the end. With your own recording, the steps are the same; the times and the mistakes will differ.

Commands are shown as `drumtx`, as installed with `pipx`. In a clone that isn't installed, type `uv run drumtx` instead.

## 1. Transcribe

```bash
drumtx transcribe groove.wav
```

```text
[1/6] Ingest     groove.wav  0:20, mono
[2/6] Detect     93 events (kick 19, snare 24, hihat 49, tom 0, cymbal 1)
[3/6] Track      33 beats, about 97 BPM
[4/6] Quantize   grid auto: 0 of 26 beats in triplets, 0 merged
[5/6] Render     groove.events.json, groove.events.csv, groove.mid, groove.musicxml
[6/6] Report     groove.report.md: 1 measures flagged for review
```

Everything is in `groove_drumtx/`:
- **`groove.musicxml`:** the score.
- **`groove.mid`:** MIDI.
- **`groove.events.csv`:** the hits, one per row; this is the file you edit.
- **`groove.events.json`:** the hits with their positions, and the tempo map.
- **`groove.report.md`:** the review report.

## 2. Read the report

Open `groove_drumtx/groove.report.md`. Its summary:

```text
- **Source:** groove.wav, 0:20.50
- **Tempo:** about 97 BPM (estimated), stable: 97% of beats are within 8% of it
- **First downbeat** (measure 1): 0:01.00 (estimated)
- **Time signature:** 4/4 (default)
- **Flagged:** 1 of 8 measures need checking
```

Check these first, because they move every bar:
- **Tempo.** 97 BPM is right; the groove is at 96. Half or double the real tempo (48 or 192) would need `--bpm`, see step 4.
- **First downbeat.** 0:01.00 is wrong. The groove's first downbeat is at 3.5 s, after the fill. DrumTx put bar 1 one bar early, so every bar number is one too high.
- **Time signature.** 4/4 is right. DrumTx doesn't detect the meter; for 3/4 you'd use `--time-signature 3/4`.

Then the rest of the report:
- **Hits per class:** the table shows 0 toms, but the fill has two.
- **Flagged measures:** the report lists measure 0, from 0:00.00 to 0:01.00, flagged for "tempo 88 BPM". That is a beat tracked in the silence before the music, and it disappears when bar 1 moves. A flagged measure is a place to look, not proof of an error. Measures that aren't flagged can be wrong too.

The score in MuseScore (`groove.musicxml`). The fill sits in bar 1 after a half rest, with no toms:

![The first transcription](guide/1-transcribed.png)

## 3. Listen

```bash
drumtx preview groove.wav groove_drumtx/groove.events.json --split-stereo
```

```text
groove_drumtx/groove.preview.wav: 93 hits over groove.wav
```

Play `groove_drumtx/groove.preview.wav` with headphones. The original is on the left, and DrumTx's hits are on the right, played with simple synthesized drums. Follow the score as you listen:
- **The fill's toms are missing:** the right channel goes silent after the two snares.
- **Two ghost notes are missing:** on beat 2 of the first groove bar, and on beat 4 of the last groove bar before the crash. The other bars have them. In the score, compare each bar with its neighbours: the bars of a groove usually repeat.
- **An extra hi-hat:** one sounds with the final crash.

Write the problems down. Without `--split-stereo`, both are mixed in the middle, with the original quieter.

## 4. Fix the rhythm

A wrong bar line, meter or tempo garbles the whole score. Fix them with options, not by editing hits:

| Problem | Fix |
|---|---|
| Bar 1 starts in the wrong place | `drumtx render groove_drumtx/groove.events.json --first-downbeat SEC` |
| Wrong meter | `drumtx render groove_drumtx/groove.events.json --time-signature 3/4` |
| Half or double tempo | `drumtx transcribe groove.wav --bpm 96 --force`. It reuses the cached detection, so it's quick. It refuses once you have edited `events.csv`, which is one more reason to fix the rhythm first. |

`render` works without the audio file, and it never changes `events.csv`.

**Finding `SEC`:** in `groove.events.csv`, the first hits of the groove, a kick and a hi-hat, are at 3.490 s. Use the time of the first hit of the bar that should be bar 1, from the CSV or by listening. DrumTx moves bar 1 to the nearest beat.

```bash
drumtx render groove_drumtx/groove.events.json --first-downbeat 3.5
```

```text
Wrote groove.events.json, groove.mid, groove.musicxml, groove.report.md
```

The report now says `First downbeat (measure 1): 0:03.50 (user)` and `Flagged: 0 of 8 measures`. In the score, the fill is now a pickup before bar 1, and the second line starts at bar 5 instead of 6:

![Bar 1 moved to 3.5 s](guide/2-bar-1-moved.png)

The new bar 1 is kept in `events.json`, so later renders keep it too.

## 5. Fix the hits

You can fix hits in two places:
- **In `events.csv`, then `drumtx render`.** The MusicXML, MIDI and report stay in step with your fixes, and you can still change the bar lines or other options afterwards. This guide uses this route.
- **In MuseScore.** Open `groove.musicxml`, fix the notes, and save it as a MuseScore file. DrumTx doesn't read MuseScore files, so make these edits last.

`groove.events.csv` has one row per hit, in any order:

```text
time_s,class,confidence,velocity
2.240,snare,0.471,36
2.550,snare,0.752,49
3.490,kick,0.985,127
...
```

- **Classes:** `kick`, `snare`, `hihat`, `tom`, `cymbal`.
- **Reclassify** a hit by changing its class.
- **Delete** a hit by deleting its row.
- **Add** a hit with a new row. Leave `confidence` and `velocity` blank and they are read as 1.0 and 100; give a velocity (1–127) for a quiet note.
- **Times** are seconds from the start of the file, and they only need to be close. `render` snaps every hit to the nearest 16th or triplet. At 96 BPM a 16th is 0.156 s, so a time within about 0.07 s of the right one lands on the right note. Take times from the rows around the place you want.

If you use a spreadsheet, check that it saves with `.` as the decimal point and `,` between columns.

The fixes for the example:

| Problem | Edit | How the time was found |
|---|---|---|
| Missing toms in the fill | add `2.860,tom,,` and `3.170,tom,,` | The fill's snares are at 2.240 and 2.550, 0.31 s apart (an 8th note) |
| Missing ghost note, first groove bar | add `4.585,snare,,25` | The hi-hat on the "and" of beat 2 is at 4.430; one 16th later |
| Missing ghost note, last groove bar | add `18.335,snare,,25` | The hi-hat on the "and" of beat 4 is at 18.180; one 16th later |
| Extra hi-hat with the crash | delete the row `18.490,hihat,0.922,85` | |

Save the file, then:

```bash
drumtx render groove_drumtx/groove.events.csv
```

```text
Wrote groove.events.json, groove.mid, groove.musicxml, groove.report.md
```

`render` reads the tempo map, with bar 1 at 3.5 s, from `groove.events.json` next to the CSV. The score now has the toms in the pickup and every ghost note:

![The corrected score](guide/3-hits-fixed.png)

If a row has a mistake, such as a misspelled class or a time that isn't a number, `render` lists the bad rows by line number and changes nothing.

## 6. Check and render again

Listen again. The preview reads the edited CSV directly:

```bash
drumtx preview groove.wav groove_drumtx/groove.events.csv --split-stereo --force
```

You can render again as often as you like, for example:
- `--mark-uncertain` colors the remaining low-confidence notes red.
- `--grid 16th` stops DrumTx from choosing triplets.
- `--formats midi` writes the MIDI file only.

Every render rewrites the score, the MIDI file and the report. It never changes the CSV.

**For the example only,** compare your result with the truth:

```bash
drumtx evaluate --pred groove_drumtx/groove.events.json --ref groove.truth.csv
```

All 96 hits should match: precision, recall and F of 1.000 for every class.

**Starting over:** `drumtx transcribe ... --force` won't overwrite an `events.csv` you have edited. Rename or move it first.

## Checklist

1. `drumtx transcribe song.wav`
2. Read `song_drumtx/song.report.md`: tempo, first downbeat, time signature, then the flagged measures.
3. `drumtx preview song.wav song_drumtx/song.events.json --split-stereo`, and note what's wrong.
4. Fix the rhythm: `drumtx render song_drumtx/song.events.json --first-downbeat SEC` or `--time-signature N/4`, or `drumtx transcribe song.wav --bpm BPM --force`.
5. Fix the hits in `song_drumtx/song.events.csv`, then run `drumtx render song_drumtx/song.events.csv`.
6. Preview again, and finish in MuseScore if needed.

## Walk-throughs

Each time someone follows this guide end to end, using only its steps, add a row. If a command or its output no longer matches, fix the guide in the same change.

| Date | Recording | By | Result |
|---|---|---|---|
| 2026-11-06 | The generated example (`scripts/make_guide_sample.py`) | Claude Code, in a fresh folder | Every command and output as shown; the three screenshots come from this run (MuseScore 3.2.3, `mscore3 -T 10 -r 100`). All 96 hits match `groove.truth.csv`. |
| | One of the owner's own recordings | The owner | Not yet done |
