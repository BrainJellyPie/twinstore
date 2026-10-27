# Integrate model connection and shelf feedback

Merge `claude/online-shopping-features-ji7y0f` at
`eacece17ab85eea0e8154febdc305d2d6ce28b80`. Seven new non-merge commits
announce model connection results, name racks in copy and starter selection
controls, count additional off-grid fixtures, improve photo checkbox spacing,
and explain missing inputs in concept and staff-script experiments. New
strings cover all six supported languages. The source branch also removes
its earlier changelog conflict markers; none remain in the integrated tree.

Integration corrects the staff-script button's `aria-describedby` condition:
it refers to the missing-input explanation only while that paragraph exists.
Other disabled states no longer refer to a nonexistent element.

Nine affected test files pass 114 tests in 12.91 seconds. TypeScript compilation
and changed-file ESLint pass with no errors or warnings. Vite builds in
20.76 seconds with existing chunk-size and plugin-timing warnings. Diff
checks pass. Backend validation is inherited from integration 449 (328
relevant tests, strict Pyright, server import); integration 450 changed only
probe diagnostics. The v0.8.2 changelog section and all older entries are
byte-for-byte unchanged. No release assets or tags change.
Logs use `/workspace/scratch/ui-model-shelf-feedback-`.

Separately, a fresh CPU Qwen3.5-2B Q4_K_M starter-product control on current
backend code passes in JSON mode: the Korean neighborhood-store example
assigns all 12 empty racks exactly once and preserves selected catalog
identities and prices (10 distinct SKUs). It completes two real HTTP calls
in 66.77 seconds with no application cache hits. This single successful
case does not establish that arbitrary shopper price constraints work.
Evidence: `/workspace/scratch/starter-loop-latest/compact-json-1793078101419670608`.
