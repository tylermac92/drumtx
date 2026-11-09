# Troubleshooting

Start with:

```bash
drumtx doctor
```

It shows whether FFmpeg, the extras and the models are installed, and the command that adds anything missing.

## Error messages

Every error is one line starting with `Error:`, and the exit code says what kind it is (design §4): 2 for a problem with the input or the options, 3 for something missing, 4 for a processing failure. Run the command again with `-v` for more detail.

| Message (start) | Code | What to do |
|---|---|---|
| `Cannot decode song.xyz: not a supported audio file` | 2 | The file is damaged or isn't audio. Convert it to WAV or FLAC. |
| `Decoding .m4a needs FFmpeg` | 3 | Install FFmpeg, so that `ffmpeg` and `ffprobe` are on `PATH`, or convert the file to WAV. |
| `The audio is 12.5 minutes long; the limit is 10` | 2 | Transcribe part of it with `--start` and `--end`, or raise `--max-duration`. |
| `The audio is 1.20 s long; at least 2 s is needed` | 2 | The file or the excerpt is too short. |
| `… already exists in song_drumtx. Use --force to overwrite.` | 2 | Add `--force`, or choose another folder with `-o`. |
| `song.events.csv was edited after DrumTx wrote it` | 2 | Your edited CSV is safe: `transcribe` never overwrites it. Use `drumtx render` to apply it. To start over, rename or move it first. |
| `An output would overwrite song.mid itself` | 2 | The audio file has the name of an output. Rename it, or use `-o`. |
| `Model adtof is not installed, and --offline forbids downloading it` | 3 | While online, run `drumtx models download adtof` (and `beat-this-final0`), or drop `--offline`. |
| `… could not be downloaded from …` | 3 | Check the network or proxy, then try again. |
| `Converting this model needs uv` | 3 | Install [uv](https://docs.astral.sh/uv/), then download the model again. |
| `Converting the model failed` | 4 | The message ends with uv's own error. The conversion needs up to 1.5 GB of disk in uv's cache. |
| `… does not match its pinned SHA-256` | 4 | The model file is damaged or was changed. Run `drumtx models download <model>`. |
| `--separate needs the separation extra` / `--plot needs the plot extra` | 3 | Run the install command the message shows (`pipx inject drumtx …`). |
| `--device cuda: PyTorch sees no CUDA GPU` | 3 | Install a CUDA build of PyTorch, or leave out `--device cuda`. |
| `Out of memory` | 4 | Transcribe a shorter excerpt. `--separate` needs about 9 GB for 10 minutes (decision 0008). |
| `Cannot read or write <path>` | 2 | Check the path, the permissions and the free disk space, or choose another folder with `-o`. |
| `song.events.csv has 2 bad rows: line 5: …` | 2 | Fix those lines. A spreadsheet set to a language that writes `,` as the decimal point breaks the file: save with `.`. |
| `song.events.json is not a valid DrumTx events.json: $.events[3].class: …` | 2 | Fix the named field, or edit `events.csv` instead and run `drumtx render` on it. |
| `Unexpected error: …` | 1 | A bug in DrumTx. Run the command again with `-v`, and report it with that output and `drumtx doctor`'s. |
| `Interrupted.` | 130 | Ctrl-C. Files are replaced whole, so none is left half-written. |

## The score looks wrong

Fix the rhythm first, then the hits ([correction guide](correction-guide.md)). The report's summary shows the tempo, the first downbeat and the time signature that DrumTx used.

**Every bar is shifted, or bar 1 starts in the wrong place.** Find the time of the first downbeat, in seconds, in `events.csv` or by listening, and render again with it:

```bash
drumtx transcribe song.wav
```

```bash
drumtx render song_drumtx/song.events.json --first-downbeat 2.0
```

**The tempo is half or double the real one.** Transcribe again with the right tempo. The cached detection is reused, so it's quick:

```bash
drumtx transcribe song.wav --bpm 96 --force
```

**The meter isn't 4/4.** DrumTx doesn't detect it:

```bash
drumtx render song_drumtx/song.events.json --time-signature 3/4
```

**Too many extra notes, or too many missing ones.** Try another sensitivity: `strict` adds fewer extra notes and misses more; `sensitive` the opposite:

```bash
drumtx transcribe song.wav --sensitivity strict --force
```

**A full mix: toms in the wrong places, or extra notes everywhere.** Isolate the drums first. It needs the separation extra and takes about 13 s per minute of audio:

```bash
drumtx transcribe song.wav --separate --force
```

**Ghost notes are missing.** The detector often misses quiet notes (accuracy page). Add them as rows in `events.csv`, with a low velocity, and run `drumtx render`.

**The bar numbers are wrong after a long silence** (20 s or more). Transcribe the parts on each side separately:

```bash
drumtx transcribe song.wav --start 30 --end 75 -o song-verse
```

**A quarter of the bars are flagged.** That's expected: the flags point to bars where several hits are probably wrong (decision 0013). Bars that aren't flagged can be wrong too.

**Notes are on the wrong staff lines in MuseScore.** Change the staff position (`display`) or the MIDI note of a class with a mapping file (`--mapping`, [format](schema/events-v1.md)). Notation apps other than MuseScore aren't supported.

**File names show up as `ドラ…` in a Windows console.** That's how DrumTx prints characters the console's code page can't show, instead of failing. The files themselves are named correctly.

## Getting help

Run the failing command with `-v`. Note the output of `drumtx doctor`, then [open an issue](https://github.com/tylermac92/drumtx/issues).
