# Product-library empty-name recovery

Integrated `claude/online-shopping-features-ji7y0f` through `d6e3e933`
onto main `f9948fcc`. Blurring an empty or whitespace-only package name
restores its saved value without submitting an empty update. This keeps
the displayed name consistent with the existing server-side required name.
Both Unreleased changelog entries are retained; released notes are unchanged.

The four affected/adjacent product-library files pass 44 frontend tests in
3.64 seconds, including the incoming empty-name case, unfinished edits,
late acknowledgments, project changes, save failure/retry, uploaded pack
reading and product linking. TypeScript and lint of both changed TypeScript
files report no errors/warnings. Production build passes in 20.92 seconds
with existing chunk-size and Babel-timing notices. Diff checks pass.
No additional application change was needed in this integration.

Backend application/test code is byte-identical to the parent; its 582
focused customer tests and strict Pyright/boot are inherited, not rerun.
The preceding CPU customer-writer checks retain their documented budget
and narrative limitations. No new CPU inference or manual browser/device
coverage is claimed for this small UI change. The v0.8.2 release is unchanged.

Logs: `/workspace/scratch/pack-name-{tests,tsc,eslint,build}.log`.
