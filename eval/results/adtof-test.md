# Benchmark: `adtof` on the test set

- Commit: `23696ca77dbfca870fd4758507a34317b8aeff3f`
- Date: 2026-11-04
- Clips: 192 (104.0 minutes of audio)
- Detection runtime: 208.1 s (0.67 s per audio minute, all presets)

F-measure per class:

| Preset | Subset @ tolerance | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| strict | drum-only @ 50 ms | 0.76 | 0.69 | 0.73 | 0.59 | 0.84 |
| strict | drum-only @ 30 ms | 0.70 | 0.60 | 0.66 | 0.50 | 0.82 |
| strict | full-mix @ 50 ms | 0.85 | 0.76 | 0.77 | 0.53 | 0.85 |
| strict | full-mix @ 30 ms | 0.84 | 0.75 | 0.77 | 0.53 | 0.84 |
| strict | all @ 50 ms | 0.77 | 0.70 | 0.73 | 0.59 | 0.84 |
| strict | all @ 30 ms | 0.71 | 0.62 | 0.67 | 0.50 | 0.82 |
| strict | E-GMD @ 50 ms | 0.69 | 0.66 | 0.69 | 0.60 | 0.85 |
| strict | E-GMD @ 30 ms | 0.62 | 0.54 | 0.61 | 0.50 | 0.82 |
| strict | IDMT-SMT-Drums @ 50 ms | 0.97 | 0.82 | 0.94 | 0.00 | 0.00 |
| strict | IDMT-SMT-Drums @ 30 ms | 0.95 | 0.81 | 0.91 | 0.00 | 0.00 |
| strict | MDB Drums @ 50 ms | 0.90 | 0.80 | 0.78 | 0.54 | 0.85 |
| strict | MDB Drums @ 30 ms | 0.89 | 0.79 | 0.78 | 0.54 | 0.85 |
| balanced | drum-only @ 50 ms | 0.81 | 0.71 | 0.76 | 0.68 | 0.85 |
| balanced | drum-only @ 30 ms | 0.74 | 0.60 | 0.69 | 0.55 | 0.83 |
| balanced | full-mix @ 50 ms | 0.84 | 0.72 | 0.76 | 0.47 | 0.85 |
| balanced | full-mix @ 30 ms | 0.83 | 0.71 | 0.76 | 0.47 | 0.84 |
| balanced | all @ 50 ms | 0.81 | 0.71 | 0.76 | 0.67 | 0.85 |
| balanced | all @ 30 ms | 0.75 | 0.61 | 0.69 | 0.54 | 0.84 |
| balanced | E-GMD @ 50 ms | 0.75 | 0.69 | 0.72 | 0.70 | 0.87 |
| balanced | E-GMD @ 30 ms | 0.67 | 0.56 | 0.64 | 0.56 | 0.84 |
| balanced | IDMT-SMT-Drums @ 50 ms | 0.99 | 0.73 | 0.95 | 0.00 | 0.00 |
| balanced | IDMT-SMT-Drums @ 30 ms | 0.97 | 0.72 | 0.93 | 0.00 | 0.00 |
| balanced | MDB Drums @ 50 ms | 0.91 | 0.77 | 0.78 | 0.50 | 0.85 |
| balanced | MDB Drums @ 30 ms | 0.89 | 0.76 | 0.78 | 0.50 | 0.84 |
| sensitive | drum-only @ 50 ms | 0.76 | 0.67 | 0.76 | 0.64 | 0.83 |
| sensitive | drum-only @ 30 ms | 0.69 | 0.56 | 0.68 | 0.52 | 0.81 |
| sensitive | full-mix @ 50 ms | 0.76 | 0.64 | 0.71 | 0.39 | 0.81 |
| sensitive | full-mix @ 30 ms | 0.75 | 0.63 | 0.71 | 0.39 | 0.80 |
| sensitive | all @ 50 ms | 0.76 | 0.66 | 0.75 | 0.63 | 0.83 |
| sensitive | all @ 30 ms | 0.69 | 0.57 | 0.68 | 0.51 | 0.81 |
| sensitive | E-GMD @ 50 ms | 0.71 | 0.66 | 0.72 | 0.67 | 0.85 |
| sensitive | E-GMD @ 30 ms | 0.62 | 0.53 | 0.64 | 0.54 | 0.83 |
| sensitive | IDMT-SMT-Drums @ 50 ms | 0.98 | 0.59 | 0.94 | 0.00 | 0.00 |
| sensitive | IDMT-SMT-Drums @ 30 ms | 0.96 | 0.58 | 0.92 | 0.00 | 0.00 |
| sensitive | MDB Drums @ 50 ms | 0.84 | 0.70 | 0.73 | 0.41 | 0.82 |
| sensitive | MDB Drums @ 30 ms | 0.83 | 0.69 | 0.73 | 0.41 | 0.81 |

Precision by confidence (`sensitive` detections, 50 ms):

| Class | Confidence | Detections | Precision |
|---|---|---|---|
| kick | 0.0–0.2 | 1 | 0.00 |
| kick | 0.2–0.4 | 1650 | 0.12 |
| kick | 0.4–0.6 | 1225 | 0.28 |
| kick | 0.6–0.8 | 1415 | 0.52 |
| kick | 0.8–1.0 | 8517 | 0.88 |
| snare | 0.0–0.2 | 2023 | 0.13 |
| snare | 0.2–0.4 | 3434 | 0.21 |
| snare | 0.4–0.6 | 2105 | 0.33 |
| snare | 0.6–0.8 | 2167 | 0.58 |
| snare | 0.8–1.0 | 9310 | 0.87 |
| hihat | 0.0–0.2 | 423 | 0.33 |
| hihat | 0.2–0.4 | 1923 | 0.32 |
| hihat | 0.4–0.6 | 1621 | 0.38 |
| hihat | 0.6–0.8 | 2287 | 0.61 |
| hihat | 0.8–1.0 | 12042 | 0.87 |
| tom | 0.0–0.2 | 907 | 0.16 |
| tom | 0.2–0.4 | 911 | 0.31 |
| tom | 0.4–0.6 | 658 | 0.62 |
| tom | 0.6–0.8 | 812 | 0.87 |
| tom | 0.8–1.0 | 472 | 0.93 |
| cymbal | 0.2–0.4 | 322 | 0.20 |
| cymbal | 0.4–0.6 | 365 | 0.33 |
| cymbal | 0.6–0.8 | 531 | 0.49 |
| cymbal | 0.8–1.0 | 3823 | 0.90 |
