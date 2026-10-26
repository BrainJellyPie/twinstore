# Network recovery and optimizer result integration

Integrated `claude/online-shopping-features-ji7y0f` through `b924601e`,
preserving main `97f68d1c` and its discount-preview repair. Incoming commits
`1cc2a5d3` and `d17e1a9d` provide localized connection failures across API
modules; `d091a29a` adds retry to an unreadable online report; `b924601e`
focuses the completed optimizer verdict and labels short candidate histories.
The only merge conflict was the Unreleased changelog; both entries remain.
The released changelog tail, release tag and assets are unchanged.

Review found a boundary in the new `apiFetch` wrapper: a Request carrying
an AbortSignal cancelled with a custom reason was converted into a server
connection error, because the wrapper checked only `init.signal` or the
standard DOM AbortError. It now checks the effective signal inherited from
the Request too. An explicitly supplied signal, including null, still
overrides the Request's signal as fetch specifies. This is a wrapper-contract
regression; current API call sites generally pass URL strings and init signals.

The added cancellation regression fails on the incoming implementation,
while four other controls pass. Final verification passes 142 frontend cases
across 15 files in 12.46 seconds: API wrappers, affected marketing flows,
online report recovery, optimizer results and catalog ownership. TypeScript,
ESLint of all 35 changed TypeScript files, and production build pass. Build
takes 20.06 seconds and retains existing chunk-size/Babel timing notices.
These are jsdom/type/build checks, not a manual browser or device matrix.

Backend code is unchanged. The parent's 41 discount application tests,
strict Pyright/boot checks and actual one-request CPU A/B observation remain
applicable; no extra model inference was run for this UI/API integration.

Logs: `/workspace/scratch/network-cancel-before.log` and
`/workspace/scratch/network-recovery-{ui,tsc,eslint,build}.log`.
