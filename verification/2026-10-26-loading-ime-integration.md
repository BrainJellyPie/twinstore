# Store loading, IME input and complete chat characters

Integrated `claude/online-shopping-features-ji7y0f` through `dbf2ed7c`
onto main `51b5edaa`. Incoming changes show the localized loading view while
a store, unseen layout or previous run loads, and keep Safari's legacy IME
composition Enter (`keyCode=229`) from submitting half-written design requests.

Review also found the design textarea truncated UTF-16 code units, unlike
the command palette and Python API's 1,200-codepoint limit. At 1,199 Korean
characters followed by an emoji, it retained a lone surrogate; emoji-only
input was cut to 600 characters. The textarea now counts complete Unicode
codepoints. Three regressions check the displayed text and outgoing request:
Korean/emoji boundary, 1,200 emoji and ordinary text. Two fail against the
incoming implementation and all three pass after repair. This establishes
outgoing text integrity, not a reproduced backend exception.

Verification passes 138 distinct frontend cases: the five integration files
passed 135 in 13.39 seconds, then the changed SiteDesigner file passed all
43 cases (including three new regressions) in 11.49 seconds. Final TypeScript,
ESLint of all four changed TypeScript files and production build pass; the
build took 20.52 seconds. Three existing route fast-refresh warnings and
existing build timing/chunk-size notices remain. No manual browser/device
coverage or extra model inference is claimed. The unchanged backend inherits
1,468 focused cases plus strict Pyright and boot from the preceding fix.

The changelog merge preserves both Unreleased sections. Released text,
v0.8.2 tag and release assets remain unchanged.
Logs: `/workspace/scratch/loading-ime-tests.log`,
`/workspace/scratch/chat-unicode-{before,final}.log`, and
`/workspace/scratch/loading-ime-final-{tsc,eslint,build}.log`.
