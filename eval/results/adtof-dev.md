# Benchmark: `adtof` on the dev set

- Commit: `4a7556439c21b146106ae69cf708dcf231acfbf9`
- Date: 2026-11-03
- Clips: 189 (107.4 minutes of audio)
- Detection runtime: 242.9 s (0.75 s per audio minute, all presets)

F-measure per class:

| Preset | Subset @ tolerance | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| strict | drum-only @ 50 ms | 0.75 | 0.51 | 0.65 | 0.36 | 0.73 |
| strict | drum-only @ 30 ms | 0.69 | 0.48 | 0.61 | 0.32 | 0.67 |
| strict | full-mix @ 50 ms | 0.84 | 0.62 | 0.89 | 0.41 | 0.80 |
| strict | full-mix @ 30 ms | 0.83 | 0.62 | 0.88 | 0.41 | 0.79 |
| strict | all @ 50 ms | 0.76 | 0.52 | 0.68 | 0.36 | 0.73 |
| strict | all @ 30 ms | 0.70 | 0.50 | 0.64 | 0.33 | 0.68 |
| balanced | drum-only @ 50 ms | 0.80 | 0.62 | 0.71 | 0.64 | 0.78 |
| balanced | drum-only @ 30 ms | 0.74 | 0.59 | 0.65 | 0.57 | 0.73 |
| balanced | full-mix @ 50 ms | 0.84 | 0.66 | 0.89 | 0.22 | 0.84 |
| balanced | full-mix @ 30 ms | 0.83 | 0.65 | 0.89 | 0.22 | 0.82 |
| balanced | all @ 50 ms | 0.80 | 0.62 | 0.73 | 0.63 | 0.79 |
| balanced | all @ 30 ms | 0.75 | 0.60 | 0.68 | 0.57 | 0.73 |
| sensitive | drum-only @ 50 ms | 0.82 | 0.69 | 0.73 | 0.63 | 0.79 |
| sensitive | drum-only @ 30 ms | 0.76 | 0.66 | 0.67 | 0.57 | 0.73 |
| sensitive | full-mix @ 50 ms | 0.82 | 0.69 | 0.89 | 0.13 | 0.83 |
| sensitive | full-mix @ 30 ms | 0.81 | 0.69 | 0.88 | 0.13 | 0.81 |
| sensitive | all @ 50 ms | 0.82 | 0.69 | 0.75 | 0.62 | 0.79 |
| sensitive | all @ 30 ms | 0.76 | 0.66 | 0.69 | 0.56 | 0.74 |
