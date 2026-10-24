# Movement map scale handles the maximum supported grid

Stores accept grids up to 256 tiles on each side. The movement report component
spread both complete maps into `Math.max`, passing up to 131,073 arguments and
throwing `RangeError: Maximum call stack size exceeded` before the report could
render. Reproductions using 256-by-256 and 256-by-255 maps failed before the fix;
the narrow 1-by-256 control passed.

The component now scans each row and value to calculate the same shared scale.
It does not allocate flattened or normalized copies or depend on a JavaScript
engine's argument-count limit. Visitor and occupancy normalization are unchanged.

## Evidence

- All five movement component cases passed, including existing full DOM checks
  for visitor and occupancy scales and upload/read ordering.
- Four related fidelity component cases also passed: nine checks in 2.42 seconds.
- The three large/narrow cases execute the report component with cached data,
  without mounting 131,072 SVG cell nodes just to reproduce a calculation crash.
  These are not browser rendering performance benchmarks.
- TypeScript build and ESLint for both changed files passed. Vite production
  build completed in 16.76 seconds with the existing chunk-size/plugin warnings.

```sh
./node_modules/.bin/vitest run src/features/runs/components/__tests__/MovementSection.test.tsx src/features/runs/components/__tests__/FidelitySection.test.tsx --reporter=dot
./node_modules/.bin/eslint src/features/runs/components/MovementSection.tsx src/features/runs/components/__tests__/MovementSection.test.tsx
./node_modules/.bin/tsc -b
./node_modules/.bin/vite build
```
