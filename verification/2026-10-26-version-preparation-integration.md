# Integrate the next-version preparation branch

`claude/online-shopping-features-ji7y0f` advanced to
`29df4bd438abacfdeb01d46f094cae2b7bb34747`. Its only new commit after
the already integrated code changes is release preparation: the home
badge changes from `v0.8` to `v0.9`, and the accumulated changelog entries
are grouped under a `0.9.0` heading. No new application behavior is hidden
in the branch's older copies of main.

The merge retains this real branch ancestry. Its changelog conflict is
resolved by keeping the later customer-hour validation fix under
`Unreleased`, followed by the branch's version heading and existing notes.
The entire `0.8.2` section and all earlier release notes remain byte-identical.
The customer-hour validator and its tests are preserved.

This integration **does not publish a v0.9.0 release or create its tag**.
At inspection, the GitHub release endpoint returns 404 for v0.9.0 and
`git ls-remote` finds no v0.9.0 tag. The commit's release-preparation title
is not evidence of published assets. The completed v0.8.2 release remains
unchanged.

The three existing home/gallery/tile test files pass **55 tests in 3.64
seconds**. TypeScript passes. ESLint reports zero errors and the two
existing Fast Refresh warnings on unchanged helper exports. Vite builds
in 21.52 seconds with existing plugin-time/chunk-size notices. No new test
is added for the static version-text edit. Backend code is unchanged,
inheriting 415's 609 focused tests, 80 checks after prompt restoration,
strict Pyright and boot checks, together with its explicitly documented
CPU-model limitations. Diff and release-note preservation checks pass.

Logs: `/workspace/scratch/version-prep-{ui-tests,tsc,eslint,build}.log`.
