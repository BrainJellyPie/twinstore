# Korean receipt observations on the actual CPU model

Extend `local-receipt-probe.py` with `--language ko` and a KRW subtotal-only
fixture. Noto Sans Mono CJK KR renders Korean labels and product names without
missing glyphs; the normal and subtotal-only 512×520 images were inspected.
Amounts, quantity checks, matching, review and CSV still use the production
path. No model responses are mocked.

Qwen3.5-2B Q4_K_M with its F16 vision projector, llama.cpp b11878, five CPU
threads, zero GPU layers, 8192 context, 512 image tokens, reasoning disabled,
temperature/seed zero. Every run has a fresh application cache.

| Fixture | Mode | Seconds | Result |
| --- | --- | ---: | --- |
| Korean KRW purchase | Native JSON schema | 17.68 | Pass |
| Korean KRW subtotal only | Native JSON schema | 14.48 | Pass |
| Korean KRW purchase | JSON | 20.33 | Pass |
| Korean KRW subtotal only | JSON | 14.59 | Pass |

Four actual HTTP requests/attempts, zero application cache hits. Both products
(`녹차`, `생수`) match their store SKUs, preserving quantities 2 and 1 and paid
amounts 5000 and 1000 won. Dates/times, currency, review readiness and CSV
amounts also pass. Normal receipts return `합계 6000` as total evidence.

**The model still misreads subtotal-only receipts as having a final total.**
In both modes it returns `total_row="소계 6000"` and `total=6000`. The production
guard introduced in fix 456 correctly turns that total into `None` and keeps
the source row in notes. Purchased amounts remain available for review/CSV.
This demonstrates the guard on Korean evidence; it does not show that the
model itself learned the distinction or establish arbitrary-photo accuracy.
No production engine change was needed in this pass.

Artifacts under `/workspace/scratch/receipt-korean-cpu/`:

- `receipt-krw-ko-json_schema-1793083183838605359`
- `receipt-krw-subtotal-only-ko-json_schema-1793083237969325450`
- `receipt-krw-ko-json-1793083255040225566`
- `receipt-krw-subtotal-only-ko-json-1793083277924773479`

All four record production `vision_inputs.py` SHA-256
`b1821ce678ab463673cfd40e3cb364668f1247f31793c19c76333c9c52e7c15b`.

This pass also merges the single follow-up UI commit
`ab7fcef78b3a2e4b747fd53321b79cb620eac277`, adding status announcements for
empty layout/shopper/template searches. Three affected suites pass 28 tests
in 4.12s. TypeScript and changed-file ESLint are clean; Vite builds in 20.34s
with the existing large-chunk warning. The probe compiles, diff checks pass,
and backend validation remains inherited from fix 456 because backend source
is unchanged. Release v0.8.2 and older changelog bytes remain unchanged.
Frontend logs use `/workspace/scratch/ui-empty-search-`.
