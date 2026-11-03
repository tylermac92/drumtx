# Benchmark: `adtof` on the dev set

- Commit: `9902c7a81896f38de87807bd64ef74af37184e82`
- Date: 2026-11-03
- Clips: 189 (107.4 minutes of audio)
- Detection runtime: 273.1 s (0.85 s per audio minute, all presets)

F-measure per class:

| Preset | Subset @ tolerance | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| strict | drum-only @ 50 ms | 0.76 | 0.76 | 0.68 | 0.61 | 0.75 |
| strict | drum-only @ 30 ms | 0.70 | 0.73 | 0.63 | 0.55 | 0.69 |
| strict | full-mix @ 50 ms | 0.85 | 0.73 | 0.89 | 0.25 | 0.83 |
| strict | full-mix @ 30 ms | 0.84 | 0.72 | 0.89 | 0.25 | 0.81 |
| strict | all @ 50 ms | 0.76 | 0.75 | 0.70 | 0.60 | 0.76 |
| strict | all @ 30 ms | 0.71 | 0.73 | 0.66 | 0.55 | 0.70 |
| balanced | drum-only @ 50 ms | 0.80 | 0.79 | 0.72 | 0.64 | 0.79 |
| balanced | drum-only @ 30 ms | 0.74 | 0.76 | 0.67 | 0.58 | 0.73 |
| balanced | full-mix @ 50 ms | 0.84 | 0.75 | 0.89 | 0.16 | 0.84 |
| balanced | full-mix @ 30 ms | 0.83 | 0.73 | 0.89 | 0.16 | 0.83 |
| balanced | all @ 50 ms | 0.81 | 0.79 | 0.74 | 0.63 | 0.79 |
| balanced | all @ 30 ms | 0.75 | 0.76 | 0.69 | 0.57 | 0.74 |
| sensitive | drum-only @ 50 ms | 0.82 | 0.74 | 0.73 | 0.60 | 0.79 |
| sensitive | drum-only @ 30 ms | 0.76 | 0.71 | 0.67 | 0.54 | 0.73 |
| sensitive | full-mix @ 50 ms | 0.74 | 0.72 | 0.79 | 0.09 | 0.82 |
| sensitive | full-mix @ 30 ms | 0.73 | 0.68 | 0.78 | 0.09 | 0.80 |
| sensitive | all @ 50 ms | 0.82 | 0.73 | 0.74 | 0.58 | 0.79 |
| sensitive | all @ 30 ms | 0.75 | 0.71 | 0.68 | 0.53 | 0.74 |
