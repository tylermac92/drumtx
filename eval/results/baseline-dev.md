# Benchmark: `baseline` on the dev set

- Commit: `e404a7240586a6a2aa38cb3f05ba1815bf940f37`
- Date: 2026-11-03
- Clips: 189 (107.4 minutes of audio)
- Detection runtime: 64.0 s (0.20 s per audio minute, all presets)

F-measure per class:

| Preset | Subset @ tolerance | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| strict | drum-only @ 50 ms | 0.71 | 0.58 | 0.66 | 0.17 | 0.20 |
| strict | drum-only @ 30 ms | 0.62 | 0.55 | 0.60 | 0.16 | 0.19 |
| strict | full-mix @ 50 ms | 0.43 | 0.45 | 0.77 | 0.01 | 0.13 |
| strict | full-mix @ 30 ms | 0.40 | 0.42 | 0.77 | 0.01 | 0.12 |
| strict | all @ 50 ms | 0.69 | 0.57 | 0.67 | 0.17 | 0.20 |
| strict | all @ 30 ms | 0.60 | 0.54 | 0.62 | 0.15 | 0.18 |
| balanced | drum-only @ 50 ms | 0.78 | 0.60 | 0.68 | 0.20 | 0.21 |
| balanced | drum-only @ 30 ms | 0.68 | 0.57 | 0.62 | 0.18 | 0.19 |
| balanced | full-mix @ 50 ms | 0.44 | 0.42 | 0.74 | 0.01 | 0.13 |
| balanced | full-mix @ 30 ms | 0.42 | 0.39 | 0.74 | 0.01 | 0.12 |
| balanced | all @ 50 ms | 0.75 | 0.58 | 0.68 | 0.18 | 0.20 |
| balanced | all @ 30 ms | 0.66 | 0.55 | 0.63 | 0.16 | 0.19 |
| sensitive | drum-only @ 50 ms | 0.71 | 0.60 | 0.67 | 0.20 | 0.21 |
| sensitive | drum-only @ 30 ms | 0.62 | 0.57 | 0.61 | 0.18 | 0.19 |
| sensitive | full-mix @ 50 ms | 0.32 | 0.39 | 0.70 | 0.01 | 0.13 |
| sensitive | full-mix @ 30 ms | 0.30 | 0.35 | 0.69 | 0.01 | 0.12 |
| sensitive | all @ 50 ms | 0.66 | 0.57 | 0.68 | 0.17 | 0.20 |
| sensitive | all @ 30 ms | 0.58 | 0.54 | 0.62 | 0.15 | 0.19 |
