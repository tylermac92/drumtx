# Benchmark: `adtof` on the dev set

- Commit: `715c57cc80d3ba135b411c613737e3c1aabdb7b1`
- Date: 2026-11-04
- Clips: 12 (11.2 minutes of audio)
- Detection runtime: 29.3 s (0.88 s per audio minute, all presets)

F-measure per class:

| Preset | Subset @ tolerance | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| strict | full-mix @ 50 ms | 0.85 | 0.73 | 0.89 | 0.25 | 0.83 |
| strict | full-mix @ 30 ms | 0.84 | 0.72 | 0.89 | 0.25 | 0.81 |
| strict | all @ 50 ms | 0.85 | 0.73 | 0.89 | 0.25 | 0.83 |
| strict | all @ 30 ms | 0.84 | 0.72 | 0.89 | 0.25 | 0.81 |
| balanced | full-mix @ 50 ms | 0.84 | 0.75 | 0.89 | 0.16 | 0.84 |
| balanced | full-mix @ 30 ms | 0.83 | 0.73 | 0.89 | 0.16 | 0.83 |
| balanced | all @ 50 ms | 0.84 | 0.75 | 0.89 | 0.16 | 0.84 |
| balanced | all @ 30 ms | 0.83 | 0.73 | 0.89 | 0.16 | 0.83 |
| sensitive | full-mix @ 50 ms | 0.74 | 0.72 | 0.79 | 0.09 | 0.82 |
| sensitive | full-mix @ 30 ms | 0.73 | 0.68 | 0.78 | 0.09 | 0.80 |
| sensitive | all @ 50 ms | 0.74 | 0.72 | 0.79 | 0.09 | 0.82 |
| sensitive | all @ 30 ms | 0.73 | 0.68 | 0.78 | 0.09 | 0.80 |
