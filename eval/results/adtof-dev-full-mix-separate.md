# Benchmark: `adtof` on the dev set

- Commit: `715c57cc80d3ba135b411c613737e3c1aabdb7b1+dirty`
- Date: 2026-11-04
- Clips: 12 (11.2 minutes of audio)
- Detection runtime: 19.3 s (0.57 s per audio minute, all presets)
- Separation (CPU): 11.8 s per audio minute

F-measure per class:

| Preset | Subset @ tolerance | kick | snare | hihat | tom | cymbal |
|---|---|---|---|---|---|---|
| strict | full-mix @ 50 ms | 0.89 | 0.69 | 0.89 | 0.72 | 0.74 |
| strict | full-mix @ 30 ms | 0.88 | 0.69 | 0.88 | 0.72 | 0.72 |
| strict | all @ 50 ms | 0.89 | 0.69 | 0.89 | 0.72 | 0.74 |
| strict | all @ 30 ms | 0.88 | 0.69 | 0.88 | 0.72 | 0.72 |
| balanced | full-mix @ 50 ms | 0.90 | 0.70 | 0.86 | 0.56 | 0.78 |
| balanced | full-mix @ 30 ms | 0.88 | 0.69 | 0.85 | 0.56 | 0.76 |
| balanced | all @ 50 ms | 0.90 | 0.70 | 0.86 | 0.56 | 0.78 |
| balanced | all @ 30 ms | 0.88 | 0.69 | 0.85 | 0.56 | 0.76 |
| sensitive | full-mix @ 50 ms | 0.82 | 0.73 | 0.77 | 0.41 | 0.81 |
| sensitive | full-mix @ 30 ms | 0.80 | 0.70 | 0.76 | 0.41 | 0.79 |
| sensitive | all @ 50 ms | 0.82 | 0.73 | 0.77 | 0.41 | 0.81 |
| sensitive | all @ 30 ms | 0.80 | 0.70 | 0.76 | 0.41 | 0.79 |
