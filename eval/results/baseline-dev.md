# Benchmark: `baseline` on the dev set

- Commit: `993324599a966703c3522272b819a15fdaa70cdb`
- Date: 2026-11-05
- Clips: 189 (107.4 minutes of audio)
- Detection runtime: 43.5 s (0.14 s per audio minute, all presets)

F-measure per class:

| Preset | Subset @ tolerance | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| strict | drum-only @ 50 ms | 0.71 | 0.58 | 0.66 | 0.17 | 0.20 |
| strict | drum-only @ 30 ms | 0.62 | 0.55 | 0.60 | 0.16 | 0.19 |
| strict | full-mix @ 50 ms | 0.43 | 0.45 | 0.77 | 0.01 | 0.13 |
| strict | full-mix @ 30 ms | 0.40 | 0.42 | 0.77 | 0.01 | 0.12 |
| strict | all @ 50 ms | 0.69 | 0.57 | 0.67 | 0.17 | 0.20 |
| strict | all @ 30 ms | 0.60 | 0.54 | 0.62 | 0.15 | 0.18 |
| strict | E-GMD @ 50 ms | 0.67 | 0.60 | 0.60 | 0.21 | 0.25 |
| strict | E-GMD @ 30 ms | 0.55 | 0.57 | 0.52 | 0.20 | 0.23 |
| strict | IDMT-SMT-Drums @ 50 ms | 0.89 | 0.44 | 0.94 | 0.00 | 0.00 |
| strict | IDMT-SMT-Drums @ 30 ms | 0.88 | 0.43 | 0.94 | 0.00 | 0.00 |
| strict | MDB Drums @ 50 ms | 0.63 | 0.50 | 0.77 | 0.02 | 0.13 |
| strict | MDB Drums @ 30 ms | 0.62 | 0.48 | 0.76 | 0.02 | 0.13 |
| balanced | drum-only @ 50 ms | 0.78 | 0.60 | 0.68 | 0.20 | 0.21 |
| balanced | drum-only @ 30 ms | 0.68 | 0.57 | 0.62 | 0.18 | 0.19 |
| balanced | full-mix @ 50 ms | 0.44 | 0.42 | 0.74 | 0.01 | 0.13 |
| balanced | full-mix @ 30 ms | 0.42 | 0.39 | 0.74 | 0.01 | 0.12 |
| balanced | all @ 50 ms | 0.75 | 0.58 | 0.68 | 0.18 | 0.20 |
| balanced | all @ 30 ms | 0.66 | 0.55 | 0.63 | 0.16 | 0.19 |
| balanced | E-GMD @ 50 ms | 0.78 | 0.63 | 0.62 | 0.24 | 0.25 |
| balanced | E-GMD @ 30 ms | 0.66 | 0.59 | 0.55 | 0.22 | 0.23 |
| balanced | IDMT-SMT-Drums @ 50 ms | 0.85 | 0.43 | 0.93 | 0.00 | 0.00 |
| balanced | IDMT-SMT-Drums @ 30 ms | 0.84 | 0.42 | 0.93 | 0.00 | 0.00 |
| balanced | MDB Drums @ 50 ms | 0.56 | 0.49 | 0.74 | 0.01 | 0.13 |
| balanced | MDB Drums @ 30 ms | 0.54 | 0.47 | 0.73 | 0.01 | 0.13 |
| sensitive | drum-only @ 50 ms | 0.71 | 0.60 | 0.67 | 0.20 | 0.21 |
| sensitive | drum-only @ 30 ms | 0.62 | 0.57 | 0.61 | 0.18 | 0.19 |
| sensitive | full-mix @ 50 ms | 0.32 | 0.39 | 0.70 | 0.01 | 0.13 |
| sensitive | full-mix @ 30 ms | 0.30 | 0.35 | 0.69 | 0.01 | 0.12 |
| sensitive | all @ 50 ms | 0.66 | 0.57 | 0.68 | 0.17 | 0.20 |
| sensitive | all @ 30 ms | 0.58 | 0.54 | 0.62 | 0.15 | 0.19 |
| sensitive | E-GMD @ 50 ms | 0.74 | 0.63 | 0.63 | 0.25 | 0.25 |
| sensitive | E-GMD @ 30 ms | 0.62 | 0.60 | 0.56 | 0.22 | 0.23 |
| sensitive | IDMT-SMT-Drums @ 50 ms | 0.70 | 0.42 | 0.92 | 0.00 | 0.00 |
| sensitive | IDMT-SMT-Drums @ 30 ms | 0.69 | 0.41 | 0.92 | 0.00 | 0.00 |
| sensitive | MDB Drums @ 50 ms | 0.40 | 0.45 | 0.70 | 0.01 | 0.13 |
| sensitive | MDB Drums @ 30 ms | 0.39 | 0.44 | 0.69 | 0.01 | 0.13 |

Rhythm (`balanced` detections, tracked beats; beats and downbeats ±70 ms):

| Subset | Clips | Beat F | Downbeat F | Grid accuracy (hits) | Of hits found |
|---|---|---|---|---|---|
| drum-only | 55 | 0.98 | 0.87 | 0.49 (34099) | 0.69 |
| all | 67 | 0.98 | 0.87 | 0.49 (34099) | 0.69 |
| E-GMD | 43 | 0.99 | 0.84 | 0.49 (34099) | 0.69 |
| MDB Drums | 24 | 0.96 | 0.92 | – | – |
| full-mix | 12 | 0.93 | 0.86 | – | – |

Precision by confidence (`sensitive` detections, 50 ms):

| Class | Confidence | Detections | Precision |
|---|---|---|---|
| kick | 0.4–0.6 | 2724 | 0.20 |
| kick | 0.6–0.8 | 11522 | 0.50 |
| kick | 0.8–1.0 | 3045 | 0.94 |
| snare | 0.4–0.6 | 1787 | 0.29 |
| snare | 0.6–0.8 | 9488 | 0.34 |
| snare | 0.8–1.0 | 17761 | 0.51 |
| hihat | 0.4–0.6 | 1836 | 0.39 |
| hihat | 0.6–0.8 | 8490 | 0.42 |
| hihat | 0.8–1.0 | 16334 | 0.65 |
| tom | 0.4–0.6 | 2205 | 0.10 |
| tom | 0.6–0.8 | 14555 | 0.11 |
| tom | 0.8–1.0 | 11110 | 0.08 |
| cymbal | 0.4–0.6 | 1928 | 0.13 |
| cymbal | 0.6–0.8 | 10059 | 0.12 |
| cymbal | 0.8–1.0 | 14687 | 0.11 |
