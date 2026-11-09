# `drumtx`

Drum transcription from audio to editable notation.

**Usage**:

```console
$ drumtx [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--version`: Show the version and exit.
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `transcribe`: Full pipeline: audio to score, MIDI,...
* `evaluate`: Accuracy of predictions against a...
* `render`: Re-quantize and re-render from an (edited)...
* `preview`: Mix the original audio with synthesized...
* `doctor`: Check the environment: Python, decoders,...
* `models`: Manage model files (for offline use).

## `drumtx transcribe`

Full pipeline: audio to score, MIDI, events, and report.

**Usage**:

```console
$ drumtx transcribe [OPTIONS] {INPUT}
```

**Arguments**:

* `INPUT`: Audio file to transcribe.  [required]

**Options**:

* `-o, --out-dir <path>`: Output folder.  [default: (./&lt;input name&gt;_drumtx/)]
* `--start <float>`: Excerpt start, in seconds from the start of the file.
* `--end <float>`: Excerpt end, in seconds from the start of the file.
* `--max-duration <float>`: Longest audio accepted, in seconds.  [default: 600.0]
* `--sensitivity <strict|balanced|sensitive>`: strict misses more hits but adds fewer false ones; sensitive the opposite.  [default: balanced]
* `--bpm <float>`: Tempo, to fix half- or double-time beats.  [default: (estimated)]
* `--time-signature <str>`: Meter as N/4, e.g. 3/4.  [default: (4/4)]
* `--first-downbeat <float>`: Start of bar 1, in seconds from the start of the file.  [default: (estimated)]
* `--grid <auto|16th|triplet>`: Note grid: 16th, triplet, or auto (chosen per beat).  [default: auto]
* `--midi-timing <quantized|performance>`: MIDI notes on the grid (quantized) or at their detected times.  [default: quantized]
* `--mark-uncertain`: Color notes below the review confidence threshold in red.
* `--plot`: Also write &lt;name&gt;.plot.png: the hits over time, flagged measures shaded.
* `--mapping <path>`: Instrument mapping (TOML): MIDI notes and staff positions per class.  [default: (built-in mapping.toml)]
* `--model <str>`: Detection model (`drumtx models list`). baseline needs no download.  [default: adtof]
* `--offline`: Never access the network; fail if the model is missing.
* `--separate / --no-separate`: Isolate the drums first (recommended for full mixes). Needs drumtx[separation].  [default: no-separate]
* `--device <cpu|cuda>`: Where --separate runs: cpu, or cuda for an NVIDIA GPU.  [default: cpu]
* `--no-cache`: Ignore cached stage outputs and recompute.
* `--force`: Overwrite existing outputs, except an events.csv edited since it was written.
* `-v, --verbose`: More detail.
* `-q, --quiet`: Errors only.
* `--help`: Show this message and exit.

## `drumtx evaluate`

Accuracy of predictions against a reference (MIDI or CSV).

**Usage**:

```console
$ drumtx evaluate [OPTIONS]
```

**Options**:

* `--pred <path>`: Predicted events: events.json or events.csv.  [required]
* `--ref <path>`: Reference: MIDI (channel 10, General MIDI drums) or CSV.  [required]
* `--ref-beats <path>`: Reference beats CSV (time_s,beat), for beat metrics.
* `--ref-score <path>`: Reference score CSV (with measure,beat,grid,slot), for grid accuracy.
* `--tolerance-ms <float>`: Onset tolerance in ms; repeat for several.  [default: (50, 30)]
* `--out <path>`: Also write the results to OUT.json and OUT.md.
* `--help`: Show this message and exit.

## `drumtx render`

Re-quantize and re-render from an (edited) events JSON or CSV.

**Usage**:

```console
$ drumtx render [OPTIONS] {EVENTS}
```

**Arguments**:

* `EVENTS`: events.json, or an edited events.csv (beside its events.json).  [required]

**Options**:

* `--formats <str>`: Outputs to write, from musicxml, midi and report.  [default: musicxml,midi,report]
* `--time-signature <str>`: Meter as N/4, e.g. 3/4.  [default: (as stored)]
* `--first-downbeat <float>`: Start of bar 1, in seconds from the start of the file.  [default: (as stored)]
* `--grid <auto|16th|triplet>`: Note grid: 16th, triplet, or auto (chosen per beat).  [default: auto]
* `--midi-timing <quantized|performance>`: MIDI notes on the grid (quantized) or at their detected times.  [default: quantized]
* `--mark-uncertain`: Color notes below the review confidence threshold in red.
* `--plot`: Also write &lt;name&gt;.plot.png: the hits over time, flagged measures shaded.
* `--mapping <path>`: Instrument mapping (TOML): MIDI notes and staff positions per class.  [default: (built-in mapping.toml)]
* `-v, --verbose`: More detail.
* `-q, --quiet`: Errors only.
* `--help`: Show this message and exit.

## `drumtx preview`

Mix the original audio with synthesized detected hits.

**Usage**:

```console
$ drumtx preview [OPTIONS] {INPUT} {EVENTS}
```

**Arguments**:

* `INPUT`: The transcribed audio file.  [required]
* `EVENTS`: Its events.json or (edited) events.csv.  [required]

**Options**:

* `-o, --out <path>`: WAV file to write.  [default: (&lt;input name&gt;.preview.wav next to EVENTS)]
* `--split-stereo`: Original on the left channel, synthesized hits on the right.
* `--force`: Overwrite the WAV file.
* `-v, --verbose`: More detail.
* `-q, --quiet`: Errors only.
* `--help`: Show this message and exit.

## `drumtx doctor`

Check the environment: Python, decoders, FFmpeg, extras, models, device.

**Usage**:

```console
$ drumtx doctor [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `drumtx models`

Manage model files (for offline use).

**Usage**:

```console
$ drumtx models [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `list`: Available models and whether each is...
* `download`: Download (and verify) a model now, for...

### `drumtx models list`

Available models and whether each is installed.

**Usage**:

```console
$ drumtx models list [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

### `drumtx models download`

Download (and verify) a model now, for offline use.

**Usage**:

```console
$ drumtx models download [OPTIONS] [MODEL]
```

**Arguments**:

* `MODEL`: Model ID.  [default: adtof]

**Options**:

* `--help`: Show this message and exit.
