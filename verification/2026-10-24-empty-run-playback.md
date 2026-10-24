# Empty completed runs retain working playback controls

The playback loop returned early for both an absent run (`null`) and a completed
run containing zero shoppers (`[]`). The latter still showed enabled playback
controls, but play never advanced the clock and skip-to-end never consumed its
seek request or marked the run finished.

Only `null` now suppresses playback. Empty runs use the existing clock, weekday,
seek, completion and reset paths with zero sales and no shopper frames.

Four regression cases failed before the change: play/finish and skip/reset,
each for one weekday and two nonconsecutive weekdays. The six playback test
files passed all 85 cases in 3.97 seconds, including existing populated runs,
midnight departures, dwell, queue positioning and metric checkpoints. The seven
directly affected metric cases were rerun after adjusting the test's last-item
lookup for the repository's TypeScript target and passed in 1.24 seconds.

Final TypeScript build and ESLint for the changed files passed. Vite production
build succeeded in 16.74 seconds with its existing large-chunk and plugin timing
warnings. No backend or model calls were needed.

```sh
./node_modules/.bin/vitest run src/features/playback
./node_modules/.bin/vitest run src/features/playback/__tests__/useSimulationLoopMetrics.test.ts
./node_modules/.bin/eslint src/features/playback/hooks/useSimulationLoop.ts src/features/playback/__tests__/useSimulationLoopMetrics.test.ts
./node_modules/.bin/tsc -b
./node_modules/.bin/vite build
```
