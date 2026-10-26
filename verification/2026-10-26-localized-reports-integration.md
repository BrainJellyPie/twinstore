# Integrate localized comparison and journey displays

The six new commits on `claude/online-shopping-features-ji7y0f`, through
`1002d55c8644e7e1f840dd3a5f07a8d4f6175326`, are integrated with their real
ancestry. They name only the run with excluded customers in a one-sided
comparison note; translate journey-map steps and unnamed rack types; display
and search localized store-format names; give fidelity statistics readable
labels; and remove a leading separator from the Area map legend.

Review confirms that comparison values and note parameters remain unchanged,
custom rack names are preserved, and unknown format/type/metric identifiers
retain a fallback. Journey-map groups contain only browse/buy steps before
the new action-label lookup. All six language columns are supplied. Changelog
conflicts retain both branches' entries, including the latest package-size
and purchase-limit fixes. The `0.8.2` section and all older notes are
byte-identical to main before integration. No release or tag is created.

Focused verification:

- Ten layout-finder, comparison, fidelity, journey-map, rack-label and floor
  editor test files pass **103 tests in 10.08 seconds**. Two Area map/page
  files pass **47 tests in 4.04 seconds** after the final wording change.
- Five analysis/comparison backend files pass **75 tests in 5.29 seconds**,
  with 27 existing dependency/resource warnings.
- Strict Pyright reports zero errors or warnings; application import succeeds.
- TypeScript passes. Full frontend ESLint has zero errors and 20 warnings,
  all in files unchanged by this integration. Vite builds in 21.21 seconds
  with the existing plugin-time and chunk-size notices. Diff checks pass.

No model prompt or reader changes here. The six fresh CPU package-reading
cases from `2026-10-26-package-metric-size-cpu.md` remain the latest inference
evidence, with the limitations recorded there; UI integration is not a new
model-quality claim.

Logs and check timings: `/workspace/scratch/localized-reports-*`.
