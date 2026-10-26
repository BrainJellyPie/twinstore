# Do not turn a container deposit into a product price

On main `f86efd4d`, actual Qwen3.5-2B Q4_K_M CPU recognition read the printed
`DEPOSIT $0.10` correctly. The returned numeric price was unknown, but capture
parsed the literal text as a ten-cent selling price and marked it exact.
This is a downstream interpretation failure after correct OCR, not an output
schema failure. The fixture is an explicitly drawn cola bottle and tag;
it is not a real shop photograph or a detector benchmark.

Price conversion now treats an English deposit amount immediately before or
after the number as insufficient selling-price evidence. Preserve the
recognized product and literal tag, use the existing estimated-price path,
and retain an existing matched product's price on placement. Explicit
deposit-inclusive selling prices, ordinary prices, coupons and sale labels
remain usable. The change does not rewrite prompts, recalculate a total,
change model request counts or retroactively alter stored captures.

Both the original fixture and its deposit-inclusive positive control were
visually inspected. Actual production-path runs used local separate-tag
recognition, llama.cpp b11878, five CPU threads, no GPU, 8,192-token context,
fresh application caches and zero cache hits. Each row made two HTTP calls.
Server prefix reuse was possible; timings are not a speed comparison.

| Run | Output mode | Time | Result |
| --- | --- | ---: | --- |
| Before: `DEPOSIT $0.10` | Native JSON schema | 14.14 s | Failure: ten cents marked exact |
| Before: `DEPOSIT INCLUDED $1.00` | Native JSON schema | 14.43 s | Control: 100 cents exact |
| After: `DEPOSIT $0.10` | Native JSON schema | 13.78 s | Estimated; original tag retained |
| After: `$0.10 DEPOSIT` | Native JSON schema | 12.98 s | Estimated; original tag retained |
| After: `DEPOSIT INCLUDED $1.00` | Native JSON schema | 13.73 s | 100 cents exact |
| After: `DEPOSIT $0.10` | Plain JSON | 17.58 s | Estimated; original tag retained |

The new regression file initially reported 26 failures and 13 passing sale
controls. All 39 cases pass after the fix, covering numeric-model guesses,
zero deposits, cent/decimal/full-width forms, included deposits, and actual
capture-to-layout placement for new and existing products. The source
layout and unrelated rack remain unchanged. This bounded English deposit
guard does not claim comprehensive recognition of deposit terminology in
every language.

Final focused validation: 1,250 backend tests passed, one optional detector
test skipped, in 7.67 seconds across ten capture/price files. The 39 warnings
were the existing LiteLLM asynchronous logging cleanup warning. Strict
Pyright reported zero errors and warnings; application import/boot,
compilation and diff checks passed. Frontend files are unchanged. Logs are
`/workspace/scratch/capture-deposit-{final-tests,pyright,boot}.log`.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `capture-deposit-before/capture-deposit-price-json_schema-1793027222100709888`
- `capture-deposit-included-control/capture-deposit-included-price-json_schema-1793027249086736623`
- `capture-deposit-final-capture-deposit-price-json_schema/capture-deposit-price-json_schema-1793027401498697286`
- `capture-deposit-final-capture-deposit-suffix-json_schema/capture-deposit-suffix-json_schema-1793027418199507693`
- `capture-deposit-final-capture-deposit-included-price-json_schema/capture-deposit-included-price-json_schema-1793027434020498482`
- `capture-deposit-final-capture-deposit-price-json/capture-deposit-price-json-1793027450702328942`
