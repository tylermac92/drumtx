# Benchmark: `adtof` on the test set

- Commit: `cd27133140efcdca584d017242092adb88316151`
- Date: 2026-11-04
- Clips: 11 (10.6 minutes of audio)
- Detection runtime: 20.6 s (0.65 s per audio minute, all presets)
- Separation (CPU): 13.0 s per audio minute

F-measure per class:

| Preset | Subset @ tolerance | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| strict | full-mix @ 50 ms | 0.89 | 0.81 | 0.76 | 0.51 | 0.80 |
| strict | full-mix @ 30 ms | 0.87 | 0.81 | 0.76 | 0.51 | 0.79 |
| strict | all @ 50 ms | 0.89 | 0.81 | 0.76 | 0.51 | 0.80 |
| strict | all @ 30 ms | 0.87 | 0.81 | 0.76 | 0.51 | 0.79 |
| strict | MDB Drums @ 50 ms | 0.89 | 0.81 | 0.76 | 0.51 | 0.80 |
| strict | MDB Drums @ 30 ms | 0.87 | 0.81 | 0.76 | 0.51 | 0.79 |
| balanced | full-mix @ 50 ms | 0.90 | 0.79 | 0.74 | 0.51 | 0.82 |
| balanced | full-mix @ 30 ms | 0.86 | 0.79 | 0.74 | 0.51 | 0.81 |
| balanced | all @ 50 ms | 0.90 | 0.79 | 0.74 | 0.51 | 0.82 |
| balanced | all @ 30 ms | 0.86 | 0.79 | 0.74 | 0.51 | 0.81 |
| balanced | MDB Drums @ 50 ms | 0.90 | 0.79 | 0.74 | 0.51 | 0.82 |
| balanced | MDB Drums @ 30 ms | 0.86 | 0.79 | 0.74 | 0.51 | 0.81 |
| sensitive | full-mix @ 50 ms | 0.85 | 0.73 | 0.74 | 0.47 | 0.81 |
| sensitive | full-mix @ 30 ms | 0.81 | 0.72 | 0.74 | 0.47 | 0.80 |
| sensitive | all @ 50 ms | 0.85 | 0.73 | 0.74 | 0.47 | 0.81 |
| sensitive | all @ 30 ms | 0.81 | 0.72 | 0.74 | 0.47 | 0.80 |
| sensitive | MDB Drums @ 50 ms | 0.85 | 0.73 | 0.74 | 0.47 | 0.81 |
| sensitive | MDB Drums @ 30 ms | 0.81 | 0.72 | 0.74 | 0.47 | 0.80 |

Precision by confidence (`sensitive` detections, 50 ms):

| Class | Confidence | Detections | Precision |
|---|---|---|---|
| kick | 0.2–0.4 | 74 | 0.09 |
| kick | 0.4–0.6 | 69 | 0.13 |
| kick | 0.6–0.8 | 64 | 0.38 |
| kick | 0.8–1.0 | 905 | 0.89 |
| snare | 0.0–0.2 | 130 | 0.07 |
| snare | 0.2–0.4 | 209 | 0.12 |
| snare | 0.4–0.6 | 129 | 0.19 |
| snare | 0.6–0.8 | 135 | 0.34 |
| snare | 0.8–1.0 | 1165 | 0.89 |
| hihat | 0.0–0.2 | 69 | 0.25 |
| hihat | 0.2–0.4 | 254 | 0.39 |
| hihat | 0.4–0.6 | 126 | 0.37 |
| hihat | 0.6–0.8 | 146 | 0.29 |
| hihat | 0.8–1.0 | 864 | 0.83 |
| tom | 0.0–0.2 | 24 | 0.00 |
| tom | 0.2–0.4 | 24 | 0.21 |
| tom | 0.4–0.6 | 20 | 0.25 |
| tom | 0.6–0.8 | 6 | 0.50 |
| tom | 0.8–1.0 | 33 | 0.91 |
| cymbal | 0.2–0.4 | 60 | 0.28 |
| cymbal | 0.4–0.6 | 91 | 0.41 |
| cymbal | 0.6–0.8 | 153 | 0.50 |
| cymbal | 0.8–1.0 | 607 | 0.89 |
