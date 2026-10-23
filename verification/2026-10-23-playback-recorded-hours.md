# Playback includes the complete recorded visit

The playback axis ended at the store's latest scheduled closing hour. A shopper
arriving just before closing could pay or leave later, but the final day's loop
stopped before those events and showed an incomplete revenue/customer count.
Legacy runs without a weekly schedule also offered only Monday, even when their
saved customers visited on another weekday.

`useStoreAssets` now accepts the saved customers when used by `PlaybackView`.
The shared time axis includes arrivals and every event's end time, and the day
picker includes recorded weekdays. Scheduled opening/closing hours remain store
metadata. Ready/running views that have no saved visits keep their existing
schedule-based bounds. The timeline is scanned once per memoized input change,
without spreading a large event list into `Math.max`.

Focused frontend verification:

- Original implementation: **6 failed, 7 passed in 1.16 seconds**. Cases cover
  ordinary closing, midnight, a two-hour overrun, final-event duration, earlier
  arrivals, missing weekdays and resetting the range when switching runs.
- A mounted playback-loop regression confirms the final day's purchase after
  midnight contributes revenue before the subsequent exit finishes playback.
- Related asset, playback, time-bar and currency checks: **67 passed in 4.53
  seconds**. TypeScript and ESLint on all changed files passed.
- Production Vite build passed in **17.00 seconds**, with chunk-size and Babel
  plugin-timing warnings.

The workspace's `pnpm` wrapper attempted to reinstall through a shared
`node_modules` symlink and refused that directory. The installed local Vitest,
TypeScript, ESLint and Vite executables were used directly; dependencies were not
reinstalled. No full frontend suite or backend suite was repeated.
