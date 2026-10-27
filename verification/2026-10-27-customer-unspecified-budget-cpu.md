# Preserve unspecified customer budgets

The actual Qwen3.5-2B Q4_K_M CPU writer returned three customers with
`budget_min_major: ""` and `budget_max_major: "0"` for a profile explicitly
without a spending budget. The first response had the requested customer
types and valid narratives. Rejecting the empty amounts triggered a second
request that invented nonzero budgets for all three customers.

The parser now maps blank major amounts to the existing zero sentinel only
when both supplied amounts are blanks or valid zero representations. Both
major fields must still be present; a blank paired with a nonzero, malformed,
boolean or null amount is rejected. Mixed major/stored fields remain invalid.
The canonical cache and persisted customer values retain integer `0, 0`.
The production prompts and transmitted schema are unchanged. This does not
infer bounds from prose, clamp valid amounts, or rewrite earlier generated
customers or cached nonzero budgets.

## Actual CPU evidence

Six fresh probes made seven HTTP requests to llama.cpp b11878 on port 8082,
five CPU threads, no GPU, 8,192 context, reasoning disabled. No response was
mocked or replayed, and all application cache-hit counts were zero. The four
customer-writer runs used temperature **1**, matching the production default;
the two traffic-stage probes used temperature **0**.

| Probe | Mode | Time | HTTP calls | Result |
| --- | --- | ---: | ---: | --- |
| Quoted CSV visitor counts, before | JSON | 10.50 s | 1 | Preserved 2 visitors at 09:00 and 0 at 10:00 |
| A single identity containing a comma, before | JSON | 7.20 s | 1 | Preserved the complete label and both hourly counts |
| Three requested customers, before | JSON Schema | 24.31 s | 1 | Types/counts/unspecified budgets correct; narrative caveat below |
| Three requested customers, before | JSON | 66.67 s | 2 | Blank first response rejected; retry invented budgets |
| Three requested customers, after | JSON | 25.04 s | 1 | Accepted original blank/zero pairs as unspecified budgets |
| Three requested customers, after | JSON Schema | 19.60 s | 1 | Same type/count/budget result; narrative caveat remains |

For **both modes**, the complete first request and first response content
were exactly equal between the before/after runs. The JSON difference is
therefore attributable to accepting the original unspecified-budget form:
the correction request is avoided. The different first-request runtimes
are not evidence of an inference-speed improvement.

These are focused stage checks, not a full wizard or simulation run. The
traffic evidence is a synthetic CSV-export summary, not an uploaded file.
The writer fixture supplies three same-hour requests: nurse, nurse, student;
its oracle checks the actual request rows, customer count, identities,
categories, budgets and basic text properties. Passing these checks is not
a general semantic-quality pass. Manual inspection of the unchanged native
response found `age_group: "30s"` beside a description saying "late 20s".
The fix does not address that contradiction or other previously documented
local-model narrative and budget-inference limitations.

Reproduction uses `verification/local-model-probe.py` with the new
`traffic-quoted-counts`, `traffic-identity-comma` and `persona-mixed-types`
cases. Use `--endpoint http://127.0.0.1:8082/v1`, the table's output mode,
and `--temperature 1` for the persona case. Local raw request/response,
input and result artifacts are in:

- `/workspace/scratch/traffic-evidence-baseline/`
- `/workspace/scratch/persona-mixed-types-baseline/`
- `/workspace/scratch/customer-blank-budget-final/`

The JSON reproduction pair ends in `1793063449057491654` before and
`1793063715586447716` after; the native pair ends in `1793063409416804108`
and `1793063779075634844`. The summary and exact-equality checks are in
`customer-blank-budget-summary.json` and
`customer-blank-budget-reproduction.json` under the same scratch directory.

## Focused verification

The new regression test reproduced **49 failures and 24 passes** before
the fix (4.75 s). It exercises both structured-output modes and four
currencies, verifies that normalization prevents a second invented answer,
and checks canonical caching, unchanged inputs and rejection of partial or
malformed amounts. The first repaired budget-focused run passed **136**
tests in 3.97 s. These mocked transport tests are separate from the actual
CPU calls above.

The final related run passed **529 tests across 16 files** in 26.05 s,
covering budgets, hourly labels, batch identity/grammar, truncation/context
recovery, optional fields and traffic forms. Its 29 warnings came from
dependency deprecations/resource cleanup. Strict backend Pyright returned
zero errors and warnings; backend import smoke, probe compilation and
diff checks passed.

No frontend production files changed; the preceding integration's UI
checks apply. The v0.8.2 changelog section is byte-for-byte unchanged.
