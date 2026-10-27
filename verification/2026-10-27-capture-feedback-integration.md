# Integrate current photo-queue and progress feedback

Merge `claude/online-shopping-features-ji7y0f` at
`4dcf7e4743069a4f0ce1a03f2973ed597e721a41`. Four new non-merge commits
count products omitted from combined shelf photos while preserving the
full list, explain the model requirement before photo reading, announce
progress statuses, and use decimal-comma examples for Spanish/French.
New display strings include all six supported languages.

The only conflict is the Unreleased changelog; both sides' entries are
retained. No backend source changes are added by this integration. Existing
v0.8.2 notes and assets remain unchanged.

Four affected test files, including translation catalog ownership, pass
38 tests in 5.66 seconds. TypeScript compilation and changed-file ESLint
pass with no errors or warnings. Vite builds in 20.37 seconds, retaining
its chunk-size and plugin-timing warnings. Diff checks pass. Backend checks
are inherited from integration 447 (268 relevant tests, strict Pyright,
server import); the wider 995-test selection passed in integration 446.
Logs use `/workspace/scratch/ui-capture-feedback-`.

The ongoing CPU-model investigation continues with the impulse prompt's
missing product-face access coordinates, independently of this UI merge.
