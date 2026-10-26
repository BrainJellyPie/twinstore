# Integrate current-day closing-time seeks

Integrate `claude/online-shopping-features-ji7y0f` through
`e75985e891b6c78050897ca09c9bd902e7b68d9c`, preserving real branch ancestry.
Previously every seek to closing time on an earlier day jumped to the final
day of the whole run. Finite seeks from the slider, keyboard or timeline now
stay on the selected day. The explicit skip button retains its existing
whole-run behavior through a separate playback-store action.

Review confirms that the internal skip marker remains in the transient
playback store; no API or persisted model value changes. Seeking an earlier
day to closing time keeps that day's accumulated sales and allows playback
to continue to the next available day. Whole-run skip preserves final totals,
including empty and nonconsecutive-day results. Existing backend fixes remain
unchanged. Changelog conflicts retain both branches' entries, and the entire
`0.8.2` section and older notes are byte-identical. No release or tag is created.

Eight playback and project-navigation files pass **125 tests in 5.02 seconds**.
TypeScript and changed-file ESLint pass with no lint warnings. Vite builds
successfully with existing plugin-time/chunk-size notices; diff checks pass.
Backend code inherits 425's 2,214 capture-price tests, strict Pyright/boot
checks and six fresh CPU price-tag cases, with their documented limits.

Logs and command timings: `/workspace/scratch/playback-day-seek-*`.
