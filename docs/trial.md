# Personal trial (M7-1)

The owner transcribes 5–10 of their own recordings, follows the [correction guide](correction-guide.md) on each, and logs what goes wrong. M7-2 fixes the issues from this page, and re-decides Q3 (whether `--separate` should be on by default) from the recording table.

**Done when:**
- Every issue is in the issue table with a severity.
- At least two tracks are timed: correcting the draft against transcribing by hand. The brief's correction-effort target is that correcting is faster.

**Privacy:** the recordings and their outputs stay outside the repo. This page holds only descriptions and numbers.

## Choosing recordings

Pick 5–10 recordings, across styles:
- **Feel:** straight rock or pop, swung or shuffled, a ballad, something fast, and one with fills or odd bars if you have it.
- **Sound:** some drum-only and some full mixes.
- **Separation:** run each full mix twice, once plainly and once with `--separate`, and note which draft needed less correcting. Q3 is decided from this.

## Each recording

1. **Transcribe:** `drumtx transcribe song.wav`.
2. **Keep the draft:** `mkdir drafts && cp song_drumtx/song.events.csv drafts/song.events.csv`, before you edit anything. `render` rewrites `events.json`, so this copy is the only record of the draft.
3. **Correct:** follow the correction guide until the score is right. Log every problem in the issue table as you go.
4. **Measure how much you changed:** `drumtx evaluate --pred drafts/song.events.csv --ref song_drumtx/song.events.csv`. Each FP is a hit you deleted and each FN is a hit you added, so the **all** row's F is how close the draft was. Record the ±50 ms F in the recording table.
5. **Keep the corrected `events.csv`** beside the audio, outside the repo. It is the hand annotation that M7-2 can add to the development set.

On the first recording, also add a row to the correction guide's "Walk-throughs" table (M5-5).

## Timing (at least two tracks)

The brief's measure is time to a finished score. For each timed track:
- Take two excerpts of the same length (30–60 s) from the same recording, of similar difficulty.
- **By hand:** transcribe one excerpt from the audio into MuseScore, with no draft.
- **Correcting:** time the other excerpt from `drumtx transcribe` to a corrected score in MuseScore, following the guide.
- Swap which excerpt is done by hand on the second track, so neither method always gets the harder excerpt.

Record the times in minutes, including listening and checking.

## Severity

| Severity | Meaning | Example |
|---|---|---|
| 1 | Blocks use: a crash, a wrong result the guide can't fix, lost or overwritten work, or a score MuseScore won't open | Every bar shifted, and `--first-downbeat` doesn't fix it |
| 2 | Costly: fixable with the guide's steps, but takes much longer than it should | Most snare ghost notes missing; tempo halved |
| 3 | Minor: cosmetic, or quick to fix | An awkward rest; a misleading message |

M7-2 closes every severity-1 issue.

## Recordings

| # | Recording (description only) | Style | Sound | `--separate` | Length | Draft F (±50 ms) | Flagged measures | Notes |
|---|---|---|---|---|---|---|---|---|
| | Not yet done | | | | | | | |

**Sound** is drum-only or full mix. For a full mix run twice, give one row per run.

## Timings

| Track # | Excerpt length | By hand (min) | Correcting (min) | Done first | Faster |
|---|---|---|---|---|---|
| | Not yet done | | | | |

## Issues

Ranked by severity, then by how often it came up.

| # | Severity | What happened | Recordings | Likely cause | Status |
|---|---|---|---|---|---|
| | | Not yet done | | | |

## Result

Not yet done. Once the trial is done, summarize here:
- whether correcting was faster on every timed track;
- the severity-1 issues;
- what the full-mix runs say about `--separate` (Q3).
