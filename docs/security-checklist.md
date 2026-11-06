# Security checklist (M6-3)

DrumTx reads files it didn't write: audio, `events.json` and `events.csv` files that people edit and pass around, mapping files, and model files from the internet. This checklist records what was checked, how, and what was changed. Design §12 has the rules. `tests/test_security.py` automates what can be automated.

- **Reviewed:** 2026-11-06, at the commit of the M6-3 pull request.
- **Status:** ✅ checked and holds; ⚠️ known limit, accepted.

## Subprocesses

| | Check | How it was verified |
|---|---|---|
| ✅ | No subprocess goes through a shell. The three calls are `ffprobe`, `ffmpeg` (`ingest.py`) and `uv` (model conversion, `models.py`), each with an argument list. | Read every call. `test_no_shell_and_no_code_loading` fails on `shell=True`, `os.system` or `os.popen` anywhere in the package. |
| ✅ | **Fixed:** FFmpeg opens only a local file. The input is now `-protocol_whitelist file -i file:<absolute path>`. Before, the bare path was passed: a relative name starting with `-` was read by `ffprobe` as an option, and a name like `http:x.m4a` as a URL. The whitelist also stops a playlist inside the file (`.m3u8`, concat) from opening anything but local files, so audio never causes network access. | `test_ffmpeg_input_is_a_local_file`, `test_ffmpeg_reads_odd_names`, `test_playlists_cannot_reach_the_network` |

## Models and caches

| | Check | How it was verified |
|---|---|---|
| ✅ | Models come only from the pinned HTTPS URLs in `models.REGISTRY`. Every downloaded source file and every converted model is checked against a pinned SHA-256, and the installed file is checked again on **every** load (`models.get_model`). | Read `models.py`; `test_models.py` covers a modified file (exit 4). |
| ✅ | Only ONNX and safetensors files are loaded (`models.LOADABLE`). No pickle, `eval` or `exec` at runtime. | `test_no_shell_and_no_code_loading` scans the package for pickle, `allow_pickle=True`, `yaml.load`, `marshal`, `eval` and `exec`. |
| ✅ | Checkpoints in PyTorch format are converted once, in a throwaway environment (`uv run --isolated --no-project`), after their SHA-256 has been checked. The one `torch.load` uses `weights_only=True`, which reads tensors and does not run code. | Same scan: every `torch.load` must say `weights_only=True`. |
| ✅ | The stage cache in `<out>/.drumtx-cache/` holds JSON and `.npz` read with `allow_pickle=False`: data only, so a cache from someone else's output folder can't run code. | Read `pipeline.py`. |

## Untrusted inputs

| | Check | How it was verified |
|---|---|---|
| ✅ | Audio: files over 2 GB are refused before decoding, and the duration (and any `--start`/`--end` excerpt) is checked from the header before the full decode. FFmpeg decodes at most the selected span (`-t`). | `test_ingest.py`: size cap, limits and excerpts. |
| ✅ | **Fixed:** `events.json` is validated against its JSON Schema (`events-v1.schema.json`) wherever it is read: `render`, `preview` and `evaluate`. Before, a wrong type or an extreme value deep in the file ended in an unexpected error (exit 1). The schema now bounds every time to one day (86,400 s), measure numbers to 1,000,000 and beats per bar to 16, so grid arithmetic stays finite. `NaN` and `Infinity`, which Python's JSON reader accepts, are refused. jsonschema became a runtime dependency for this. | `test_fuzz_events_json`, `test_python_reads_nan_but_events_json_does_not`, `test_schema_limits_match_the_code` |
| ✅ | `events.csv`: every row is checked, and errors give line numbers. **Fixed:** times are now bounded to one day too, so `1e300` is an input error, not an overflow. | `test_fuzz_events_csv`, `test_errors.py` |
| ✅ | Mapping files: unknown classes and keys, and every value, are checked before use. | `test_mapping.py`, `test_fuzz_bytes` |
| ✅ | CLI options: `--bpm` 20–400, `--time-signature` N/4 with N from 1 to 16, `--first-downbeat` ≥ 0, `--tolerance-ms` > 0, `--formats` from a fixed list. | `test_beats.py`, `test_rerender.py`, `test_errors.py` |
| ⚠️ | A crafted audio header (thousands of channels, an extreme sample rate) can still make decoding allocate a lot of memory. That ends with exit 4 (out of memory) or, at worst, the operating system stopping the process. Nothing is written in either case. | Accepted: real recordings don't do this, and the input is your own. |
| ⚠️ | `events.csv` and `events.json` have no size limit; they are read into memory. | Accepted: they are your own files, and a 10-minute piece has a few thousand rows. |

## Output paths

| | Check | How it was verified |
|---|---|---|
| ✅ | `transcribe` never overwrites outputs without `--force`, and never an `events.csv` edited since it was written. `render` never writes `events.csv`. | `test_render.py`, `test_rerender.py` |
| ✅ | **Fixed:** no output may be the input itself, even with `--force`. Before, a WAV file named `song.mid` would have been replaced by the MIDI output, and `preview -o` could name the source audio or the events file. Paths are compared after resolving them. | `test_outputs_never_overwrite_the_source`, `test_preview_never_overwrites_an_input` |
| ✅ | Output names are the input's name plus a fixed suffix, written into the output folder: they can't leave it. Each file is written to a temporary file and then renamed over the target, so a symbolic link at an output path is replaced, not followed. | Read `render.py`. |

## Temporary files

| | Check | How it was verified |
|---|---|---|
| ✅ | **Fixed:** every output and cache file goes through one helper, `render.write_atomic`, which removes its temporary file on any failure, Ctrl-C included, and leaves the old file as it was. Before, four copies of this code could leave a `.tmp` file behind. The preview WAV and the plot PNG are now built in memory. | `test_atomic_write_cleans_up` |
| ✅ | Model downloads and conversions happen in a `TemporaryDirectory` inside the model folder, removed on exit, success or not. | Read `models.py`. |

## Fuzzing

`tests/test_security.py` damages valid files and runs the commands on them. The only outcomes allowed are exit 0 (the damage was harmless), 2 or 4, with no traceback:
- audio in WAV, FLAC, OGG and M4A (through FFmpeg): truncated, or with bytes overwritten in the header or anywhere, 15 cases each;
- `events.json` with a field replaced by a wrong type or an extreme value, run through `render`, `preview` and `evaluate` (60 cases);
- `events.csv` rows with odd times, classes and numbers (60 cases);
- byte damage to `events.json`, `events.csv` and a mapping together (30 cases).

Before writing these, a larger exploratory run took 600 damaged audio files, 1,000 runs on damaged `events.json` files and 1,200 runs on damaged CSV and mapping files. Audio, CSV and mapping files already ended with exit 0 or 2. `events.json` did not: wrong types and extreme values ended in exit 1 in 25 distinct ways. Schema validation fixed all of them.

## Dependencies

| | Check | How it was verified |
|---|---|---|
| ✅ | Every dependency is pinned in `uv.lock`, which CI uses (`uv sync --locked`). | `ci.yml` |
| ✅ | `pip-audit` runs in CI (the `audit` job) on every runtime dependency in the lock file, both extras included. It fails on any known vulnerability, not only high-severity ones. On 2026-11-06: **no known vulnerabilities**. | `uvx pip-audit==2.9.0 -r <uv export --all-extras --no-dev> --disable-pip` |
| ⚠️ | The decoders are third-party C code reading untrusted files: libsndfile (bundled with `soundfile`, pinned in the lock file) and FFmpeg (from your system). | Keep them updated: `uv lock --upgrade-package soundfile`, and your system's FFmpeg package. |

## Related

- **Exit codes and messages:** M6-2, `tests/test_errors.py`.
- **Network access and telemetry:** M6-4 (privacy).
