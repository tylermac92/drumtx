# Model card: Open-Unmix UMX-L drums (`umxl-drums`)

- **Status:** integrated in M2-6, 2026-11-04. Used only with `--separate`.
- **Chosen in:** decision 0003.

## What it is

The drums target of [Open-Unmix](https://github.com/sigsep/open-unmix-pytorch) UMX-L. It is a stereo BLSTM separation model trained on about 400 hours of multitrack audio. DrumTx keeps only the drum stem, as mono, and runs the detector on it instead of the mix. Beat tracking (M3) stays on the full mix.

| | |
|---|---|
| License | Weights CC BY-NC-SA 4.0 (Zenodo record 5069601); code MIT. Personal, non-commercial use only (decision 0001). |
| Upstream file | `https://zenodo.org/records/5069601/files/drums-69e0ebd4.pth` (113 MB), SHA-256 `69e0ebd402a0a0622ac9a887dfbc7fb7eb3b94f7fbdc1c843c26f1575104228a` |
| Loaded file | `umxl_drums.safetensors`, SHA-256 `8fc45a49f6d0b92221efd4a75bb68b4a65b655d0829d0374d5f7cc7d3fb83e52` |
| Settings | `openunmix.umxl`'s: 4096-point STFT, hop 1024, 16 kHz bandwidth, drums plus a residual target, one Wiener (EM) step |
| Runtime install | The `[separation]` extra: `openunmix`, `torch`, `torchaudio`, `safetensors` |

## Installing

Install the extra; without it, `--separate` exits with code 3 and prints the exact command for your install:

```bash
pipx inject drumtx "openunmix>=1.3,<1.4" "safetensors>=0.4" "torch>=2.4" "torchaudio>=2.4"
```

PyTorch from PyPI runs on the CPU on Windows and macOS. For `--device cuda`, install a CUDA build of PyTorch instead (<https://pytorch.org/get-started/locally/>); this is untested.

The weights download on first use, or with:

```bash
drumtx models download umxl-drums
```

Upstream publishes a PyTorch pickle, which DrumTx never loads at runtime (Technical Design Document §12). Downloading converts it once:
1. **Check the checkpoint:** its SHA-256 must match the pinned value.
2. **Read the tensors:** with PyTorch's tensors-only loader (`weights_only=True`), which does not run code from the file.
3. **Save as safetensors:** the three STFT entries that openunmix rebuilds itself are dropped.
4. **Check the result:** it must match the pinned SHA-256; two runs produced identical files. The `Model conversion` CI workflow repeats the conversion on Linux, macOS and Windows.

The runtime loads the safetensors file with strict key matching.

## Caching

The drum stem is a pipeline stage. It is cached in `<out-dir>/.drumtx-cache/` as `.npz`, mono float32: about 10 MB per audio minute. Changing the sensitivity, the model or later options reuses it. Only a new input, excerpt or separator recomputes it.

## Development-set results (M2-6)

The 12 full-mix development clips (MDB Drums, 11.2 minutes), ADTOF with its M2-3 presets, with and without `--separate`. Full results are in `eval/results/adtof-dev-full-mix.json` and `eval/results/adtof-dev-full-mix-separate.json`.

```bash
python scripts/benchmark.py --model adtof --subset full-mix
```

```bash
python scripts/benchmark.py --model adtof --subset full-mix --separate
```

F-measure at 50 ms, without → with separation:

| Preset | Kick | Snare | Hi-hat | Tom (15 hits) | Cymbal |
|---|---|---|---|---|---|
| `strict` | 0.85 → **0.89** | **0.73** → 0.69 | 0.89 → 0.89 | 0.25 → **0.72** | **0.83** → 0.74 |
| `balanced` | 0.84 → **0.90** | **0.75** → 0.70 | **0.89** → 0.86 | 0.16 → **0.56** | **0.84** → 0.78 |
| `sensitive` | 0.74 → **0.82** | 0.72 → 0.73 | **0.79** → 0.77 | 0.09 → **0.41** | 0.82 → 0.81 |

**What changes (at `balanced`):**
- **Kick and toms improve.** Precision rises (kick 0.78 → 0.93, tom 0.09 → 0.42), because bass and other low instruments no longer trigger false hits.
- **Snare and cymbal get worse.** Recall falls (snare 0.78 → 0.62, cymbal 0.83 → 0.71): the separator removes part of their energy.
- **ADTOF already handles mixes well.** It was trained on real music, not on isolated drums, which is why the gain is smaller than for a drums-only detector.
- **Caveats:**
  - only 12 clips, all from one source;
  - the thresholds were tuned on unseparated audio;
  - the tom numbers rest on 15 hits.

**Runtime:**
- **Separation:** 11.8 s per audio minute on the 4-core sandbox CPU (about 0.2× real time), on top of detection. M6-1 measured 12–15 s per audio minute again with `scripts/perf.py`, and peak memory of 3.7 GB for a 4-minute file and 8.6 GB for a 10-minute file, since the whole piece is separated at once (decision 0008). The reference machine and `--device cuda` are not measured yet.
- **Memory:** the whole excerpt is processed at once, so memory grows with its length.

**Recommendation:** keep `--separate` off by default (Q3). Try it on full mixes where the kick or toms are buried, and compare. Revisit after the M7-1 trial with your own recordings, and consider tuning thresholds for separated stems if it becomes the default.
