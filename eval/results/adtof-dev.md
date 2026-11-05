# Benchmark: `adtof` on the dev set

- Commit: `0e38ba9189cea366d639e3d6f0fbc658e2b19e1c`
- Date: 2026-11-05
- Clips: 189 (107.4 minutes of audio)
- Detection runtime: 188.7 s (0.58 s per audio minute, all presets)

F-measure per class:

| Preset | Subset @ tolerance | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| strict | drum-only @ 50 ms | 0.76 | 0.76 | 0.68 | 0.61 | 0.75 |
| strict | drum-only @ 30 ms | 0.70 | 0.73 | 0.63 | 0.55 | 0.69 |
| strict | full-mix @ 50 ms | 0.85 | 0.73 | 0.89 | 0.25 | 0.83 |
| strict | full-mix @ 30 ms | 0.84 | 0.72 | 0.89 | 0.25 | 0.81 |
| strict | all @ 50 ms | 0.76 | 0.75 | 0.70 | 0.60 | 0.76 |
| strict | all @ 30 ms | 0.71 | 0.73 | 0.66 | 0.55 | 0.70 |
| strict | E-GMD @ 50 ms | 0.70 | 0.75 | 0.57 | 0.62 | 0.74 |
| strict | E-GMD @ 30 ms | 0.63 | 0.72 | 0.50 | 0.56 | 0.68 |
| strict | IDMT-SMT-Drums @ 50 ms | 0.98 | 0.84 | 0.95 | 0.00 | 0.00 |
| strict | IDMT-SMT-Drums @ 30 ms | 0.97 | 0.80 | 0.93 | 0.00 | 0.00 |
| strict | MDB Drums @ 50 ms | 0.90 | 0.74 | 0.89 | 0.23 | 0.84 |
| strict | MDB Drums @ 30 ms | 0.89 | 0.73 | 0.89 | 0.23 | 0.83 |
| balanced | drum-only @ 50 ms | 0.80 | 0.79 | 0.72 | 0.64 | 0.79 |
| balanced | drum-only @ 30 ms | 0.74 | 0.76 | 0.67 | 0.58 | 0.73 |
| balanced | full-mix @ 50 ms | 0.84 | 0.75 | 0.89 | 0.16 | 0.84 |
| balanced | full-mix @ 30 ms | 0.83 | 0.73 | 0.89 | 0.16 | 0.83 |
| balanced | all @ 50 ms | 0.81 | 0.79 | 0.74 | 0.63 | 0.79 |
| balanced | all @ 30 ms | 0.75 | 0.76 | 0.69 | 0.57 | 0.74 |
| balanced | E-GMD @ 50 ms | 0.76 | 0.80 | 0.64 | 0.67 | 0.78 |
| balanced | E-GMD @ 30 ms | 0.69 | 0.77 | 0.56 | 0.61 | 0.72 |
| balanced | IDMT-SMT-Drums @ 50 ms | 0.99 | 0.75 | 0.96 | 0.00 | 0.00 |
| balanced | IDMT-SMT-Drums @ 30 ms | 0.98 | 0.73 | 0.94 | 0.00 | 0.00 |
| balanced | MDB Drums @ 50 ms | 0.90 | 0.76 | 0.90 | 0.10 | 0.87 |
| balanced | MDB Drums @ 30 ms | 0.89 | 0.74 | 0.90 | 0.10 | 0.85 |
| sensitive | drum-only @ 50 ms | 0.82 | 0.74 | 0.73 | 0.60 | 0.79 |
| sensitive | drum-only @ 30 ms | 0.76 | 0.71 | 0.67 | 0.54 | 0.73 |
| sensitive | full-mix @ 50 ms | 0.74 | 0.72 | 0.79 | 0.09 | 0.82 |
| sensitive | full-mix @ 30 ms | 0.73 | 0.68 | 0.78 | 0.09 | 0.80 |
| sensitive | all @ 50 ms | 0.82 | 0.73 | 0.74 | 0.58 | 0.79 |
| sensitive | all @ 30 ms | 0.75 | 0.71 | 0.68 | 0.53 | 0.74 |
| sensitive | E-GMD @ 50 ms | 0.79 | 0.75 | 0.68 | 0.64 | 0.79 |
| sensitive | E-GMD @ 30 ms | 0.71 | 0.72 | 0.60 | 0.58 | 0.73 |
| sensitive | IDMT-SMT-Drums @ 50 ms | 0.98 | 0.62 | 0.93 | 0.00 | 0.00 |
| sensitive | IDMT-SMT-Drums @ 30 ms | 0.97 | 0.60 | 0.91 | 0.00 | 0.00 |
| sensitive | MDB Drums @ 50 ms | 0.81 | 0.74 | 0.79 | 0.07 | 0.84 |
| sensitive | MDB Drums @ 30 ms | 0.79 | 0.71 | 0.79 | 0.07 | 0.82 |

Rhythm (`balanced` detections, tracked beats; beats and downbeats ±70 ms):

| Subset | Clips | Beat F | Downbeat F | Grid accuracy (hits) | Of hits found |
|---|---|---|---|---|---|
| drum-only | 55 | 0.98 | 0.89 | 0.48 (34099) | 0.77 |
| all | 67 | 0.97 | 0.88 | 0.48 (34099) | 0.77 |
| E-GMD | 43 | 0.98 | 0.86 | 0.48 (34099) | 0.77 |
| MDB Drums | 24 | 0.96 | 0.92 | – | – |
| full-mix | 12 | 0.93 | 0.86 | – | – |

Precision by confidence (`sensitive` detections, 50 ms):

| Class | Confidence | Detections | Precision |
|---|---|---|---|
| kick | 0.0–0.2 | 1 | 0.00 |
| kick | 0.2–0.4 | 1292 | 0.32 |
| kick | 0.4–0.6 | 886 | 0.48 |
| kick | 0.6–0.8 | 951 | 0.66 |
| kick | 0.8–1.0 | 7415 | 0.95 |
| snare | 0.0–0.2 | 2152 | 0.11 |
| snare | 0.2–0.4 | 3321 | 0.26 |
| snare | 0.4–0.6 | 1795 | 0.54 |
| snare | 0.6–0.8 | 2357 | 0.80 |
| snare | 0.8–1.0 | 9535 | 0.93 |
| hihat | 0.0–0.2 | 630 | 0.23 |
| hihat | 0.2–0.4 | 3120 | 0.32 |
| hihat | 0.4–0.6 | 2031 | 0.45 |
| hihat | 0.6–0.8 | 2437 | 0.66 |
| hihat | 0.8–1.0 | 10291 | 0.93 |
| tom | 0.0–0.2 | 1503 | 0.16 |
| tom | 0.2–0.4 | 1770 | 0.28 |
| tom | 0.4–0.6 | 1289 | 0.48 |
| tom | 0.6–0.8 | 1438 | 0.72 |
| tom | 0.8–1.0 | 962 | 0.86 |
| cymbal | 0.2–0.4 | 242 | 0.33 |
| cymbal | 0.4–0.6 | 283 | 0.47 |
| cymbal | 0.6–0.8 | 346 | 0.75 |
| cymbal | 0.8–1.0 | 2417 | 0.94 |
