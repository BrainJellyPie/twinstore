# Integrate playback focus, slider values and accessible action names

Integrated `claude/online-shopping-features-ji7y0f` through
`01dbe1912e419ff472d30081d597b7a16a4ab981` into main
`bf6a08af87c18274ad668c05fdfa96c4100d7890`. The unique incoming changes restore
focus to playback after launching or opening a run, expose meaningful slider
values, identify shopper/variant actions, retain focus outlines in forced
colors, and omit scroll-linked report reveals with reduced motion.

The incoming focus helper stopped as soon as it found Play, even when the
button was disabled and could not take focus. `TimeBar` can render that
state while its time range is unavailable. Keep the existing bounded retry
until focus actually reaches the button; the five-second limit is unchanged.
A disabled-then-enabled regression failed before the fix. Controls cover a
button that appears later and one that stays unavailable beyond the limit.

Validation:

- 206 frontend tests in twelve affected playback, launcher, marketing,
  online-design and area files passed in 16.57 seconds.
- ESLint on all 25 changed TypeScript files: zero errors/warnings.
- TypeScript and Vite production build passed (21.02 seconds). Existing
  chunk-size/plugin-timing notices remain.
- CSS media guards were reviewed and included in the production build; no
  new cross-browser or screen-reader run is claimed for this integration.
- Diff checks pass. Backend files and the released v0.8.2 changelog section
  are unchanged, so backend checks were not repeated.

Logs: `/workspace/scratch/playback-focus-before.log` and
`playback-accessibility-integration-{tests,eslint,tsc,build}.log`.
