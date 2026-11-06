# DrumTx performance

- Machine: x86_64, 4 logical CPUs, Linux-6.18.44-fc-v242-x86_64-with-glibc2.39
- Python 3.12.3, commit 91d4309cd676657a010ff3c7e4623bccda9472ee+dirty, 2026-11-06
- `drumtx transcribe --no-cache`, 1 runs per file, median

| File | Audio | Separate | Wall time | Real-time factor | Peak memory | Stages |
|---|---|---|---|---|---|---|
| mix4min.wav | 4.0 min | yes | 77.1 s | 0.321 | 3,742 MB | Ingest 0.4 s, Separate 57.9 s, Detect 4.8 s, Track 11.4 s, Quantize 0.1 s, Render 0.1 s, Report 0.0 s |
| mix10min.wav | 10.0 min | yes | 144.1 s | 0.240 | 8,572 MB | Ingest 0.5 s, Separate 116.9 s, Detect 5.2 s, Track 19.1 s, Quantize 0.1 s, Render 0.3 s, Report 0.0 s |
