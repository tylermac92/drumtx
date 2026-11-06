# DrumTx performance

- Machine: x86_64, 4 logical CPUs, Linux-6.18.44-fc-v242-x86_64-with-glibc2.39
- Python 3.11.17, commit 91d4309cd676657a010ff3c7e4623bccda9472ee+dirty, 2026-11-06
- `drumtx transcribe --no-cache`, 3 runs per file, median

| File | Audio | Separate | Wall time | Real-time factor | Peak memory | Stages |
|---|---|---|---|---|---|---|
| mix4min.wav | 4.0 min | no | 14.3 s | 0.060 | 1,237 MB | Ingest 0.1 s, Detect 2.5 s, Track 11.3 s, Quantize 0.0 s, Render 0.1 s, Report 0.0 s |
| mix10min.wav | 10.0 min | no | 27.7 s | 0.046 | 1,398 MB | Ingest 0.2 s, Detect 5.8 s, Track 21.1 s, Quantize 0.1 s, Render 0.3 s, Report 0.0 s |
