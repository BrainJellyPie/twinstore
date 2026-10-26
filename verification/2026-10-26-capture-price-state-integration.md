# Integrate capture price errors and reverted estimates

Integrate `claude/online-shopping-features-ji7y0f` through
`c58af9113b9098ce52f19c430bd0405d2797423f`. Its only new behavior commit,
`7058267d`, connects invalid price fields to their error message in capture
review and Shelf Lab. Restoring the exact original price text also restores
its estimated status, so an undone edit does not leave an artificial dirty
state. API payload identifiers and price parsing remain unchanged.

The branch had also merged an older main. The actual merge changes only the
two capture components, their two test files, and the changelog; current
backend and verification files are byte-identical to main. Resolve the two
changelog conflicts by adding the new capture note once and preserving main's
existing provider-label and reversed-multipack notes. The `0.8.2` section and
all earlier notes remain unchanged. Real branch ancestry is retained; no tag
or release is created.

Three focused capture currency, Shelf Lab and unsaved-edit test files pass
**12 tests in 4.77 seconds**. TypeScript and changed-file ESLint pass with no
lint warnings. Vite builds in 21.21 seconds with existing plugin-time and
chunk-size notices; diff checks pass. Backend code inherits 423's 338 package
engine/API tests, strict Pyright/boot checks, and six fresh CPU package-link
cases, including their documented metadata limitations.

Logs and command timings: `/workspace/scratch/capture-price-state-*`.
