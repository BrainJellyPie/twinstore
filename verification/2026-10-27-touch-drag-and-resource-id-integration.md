# Touch drag and resource ID integration

Integrated `claude/online-shopping-features-ji7y0f` at
`9bf5b58ee37f5907091f60111b4bb21ae7cfbde3` onto main
`58d9449e35b258521bc6a9b4354d35d5f5b05440`. This includes fixture dragging,
shopper focus handling, disabled-control explanations, model setup guidance
after command routing fails, and the shared 128-character resource ID limit.

## Reproduced and corrected during integration

Touch can deliver pointer-up and the following click to the originally pressed
cell. After a drag moved a fixture, that click selected its old empty cell; after
a refused drag, it cleared the overlap explanation. Two tests reproduced both
failures before the fix (2 failed, 8 passed in 4.01 seconds). The grid now consumes
that following pointer click. Fresh taps and keyboard activation still work.
Tests model the touch event sequence in jsdom; this is not a real-browser touch
smoke test.

The incoming ID limit was also tested against unchanged main: 11 failures and
1 pass in 4.52 seconds. Overlong filesystem names produced server errors; the
new validation rejects invalid names before file access. Additional boundary
checks cover 129, 255, and 256 characters alongside accepted 128-character IDs
and the branch's 300-character GET/POST cases.

## Verification

- Frontend: 90 tests across 8 affected suites passed in 9.91 seconds. TypeScript
  and changed-file ESLint passed. Vite built in 20.87 seconds with existing
  chunk/plugin timing warnings. jsdom emitted its navigation-not-implemented
  notice in the command palette test.
- Backend: 245 tests across 11 resource-ID and automatic layout/product API
  suites passed in 16.54 seconds. Strict Pyright reported 0 errors and 0
  warnings, and the server application import passed.

## Actual small-model automatic placement control

Qwen3.5-0.8B Q4_K_M, CPU only, five threads, llama.cpp b11878, context 8192,
native JSON Schema, temperature 0. A fresh application cache was used. Existing
server prompt-cache reuse was possible.

The `book-excluded` case asked an 8×6 bookstore to replace stationery with books
while retaining the existing book sections. Production selection and placement
passed in **11.06 seconds, 2 HTTP requests, 0 application cache hits**: 3 racks,
2 selected/placed SKU identities, 64 placements, no category mismatches. The
probe also checks complete unique assignments, SKU limits, immutable source
store, and preserved catalog identities and prices.

Evidence: `/workspace/scratch/starter-small-category-boundary/`
`book-excluded-json_schema-1793087210294568414`. This is a control for this case,
not a claim that all small-model output formats or semantics are reliable.
Receipt parsing is unchanged from main 461.

The published v0.8.2 tag and release artifacts are unchanged.
