# Personal trial (M7-1)

The owner transcribes 5–10 of their own recordings, listens to each draft, and logs what sounds wrong. This is a listening trial: no corrections and no timing. Fixing a draft by editing `events.csv` turned out too hard without transcription experience (issue 1 below), so correcting and its timing move to the browser editor (M7-1b).

M7-2 fixes the issues from this page, and re-decides Q3 (whether `--separate` should be on by default) from the recording table.

**Done when:** every recording has a row and a rating, and every issue is in the issue table with a severity.

**Privacy:** the recordings and their outputs stay outside the repo. This page holds only descriptions and ratings.

## Choosing recordings

Pick 5–10 recordings, across styles:
- **Feel:** straight rock or pop, swung or shuffled, a ballad, something fast, and one with fills or odd bars if you have it.
- **Sound:** some drum-only and some full mixes.
- **Separation:** run each full mix twice, once plainly and once with `--separate`, and note which draft sounds closer. Q3 is decided from this.

## Each recording

1. **Transcribe:** `drumtx transcribe song.wav`. For a full mix, also `drumtx transcribe song.wav --separate -o song_separated`.
2. **Read the report** (`song_drumtx/song.report.md`): is the tempo about right, or half or double? Is the time signature right? Note how many measures are flagged.
3. **Listen:** `drumtx preview song.wav song_drumtx/song.events.json --split-stereo`, then play `song_drumtx/song.preview.wav` with headphones. Your recording is on the left and DrumTx's hits are on the right. You don't need to write notation: just note what sounds wrong and roughly when (the time in the player is enough). For example:
   - hits on the right that aren't in the recording, or hits in the recording with silence on the right;
   - the wrong drum, such as a tom played as a snare;
   - the right channel drifting ahead of or behind the recording.
4. **Rate the draft:**
   - **Usable:** a few wrong or missing hits; the groove is recognizable.
   - **Needs work:** many wrong hits, or one part (such as the hi-hat) mostly wrong, but the timing holds.
   - **Unusable:** the timing is wrong (drifting, half or double tempo), or most hits are wrong.
5. **Optional:** open `song_drumtx/song.musicxml` in MuseScore and note anything that reads badly.

On a full mix, do steps 2–4 for both runs, and say which sounded closer.

## Severity

| Severity | Meaning | Example |
|---|---|---|
| 1 | Blocks use: a crash, lost or overwritten work, a score MuseScore won't open, or a draft that can't be fixed with the tools you have | Fixing hits needs CSV editing you can't do |
| 2 | Costly: a draft that would take much longer to fix than it should | Most snare ghost notes missing; tempo halved |
| 3 | Minor: cosmetic, or quick to fix | An awkward rest; a misleading message |

M7-2 closes every severity-1 issue.

## Recordings

| # | Recording (description only) | Style | Sound | `--separate` | Length | Tempo right? | Flagged measures | Rating | What sounded wrong |
|---|---|---|---|---|---|---|---|---|---|
| | Not yet done | | | | | | | | |

**Sound** is drum-only or full mix. For a full mix, give one row per run.

## Issues

Ranked by severity, then by how often it came up.

| # | Severity | What happened | Recordings | Likely cause | Status |
|---|---|---|---|---|---|
| 1 | 1 | Fixing hits means editing `events.csv` by hand: finding the time of each hit and typing rows. Without transcription experience this was too hard to finish on the owner's first recording. | The first one tried | Correcting assumes you can find fixes by ear and enter them as numbers | Planned: the browser editor (M7-1b) |

## Result

Not yet done. Once the trial is done, summarize here:
- how many drafts were usable, needed work, or were unusable, for drum-only and for full mixes;
- the severity-1 issues;
- what the full-mix runs say about `--separate` (Q3).
