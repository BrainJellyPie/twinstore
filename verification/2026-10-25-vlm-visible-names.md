# Keep local vision choices on the current shelf

Date: 2026-10-25. Based on main `fa89ea31`.

The actual Qwen3.5-0.8B Q4 CPU shopper reproduced a semantic failure in a
compact KRW store with a free offer. On a chart containing only sports drink
and vitamin water, it returned `product: "라이터"` (lighter), `number: 1`,
`interest: 9`. Lighter was in the persona's intended purchases, but not on that
shelf. Badge fallback accepted the answer as sports drink and the customer
executor bought that drink. `format_ok: true` alone concealed the mismatch.

The local JSON grammar now limits product names to the currently rendered
shelf's names, plus the empty no-name choice. Names use the existing 60-character
limit, with duplicates collapsed. Number constraints remain unchanged. This is
a wire constraint: older replies and providers without grammar enforcement
retain existing name/number resolution. Unnumbered raw photographs retain
free-text names for reading labels that differ from catalog names.

The same CPU fixture then named the visible `이온음료 600ml` (sports drink),
badge 4, with no missing targets or name mismatch. Both badges 1 and 4 show the
same product. A separate actual USD run also named visible products for both
shelves. These runs used production image rendering, VLM decisions and customer
execution, without mocked model replies or paid calls.

The fix does not establish accurate reasoning. The corrected Korean answer's
reason still misread the price as `#4,300원`; the image shows badge 4 at 3,000 won.
Entry plans also did not faithfully reproduce the persona's intended purchases.
These remain separate semantic limitations, not fixed results. Purchase counts
are recorded as execution evidence, not as a model-quality improvement.

Evidence under `/workspace/scratch/cpu-vlm-probe/`:

- `physical-KRW-1792963065280548075`: baseline, 3 calls, 24.01 seconds,
  off-shelf lighter resolved to sports drink; 3 executed units, 6,900 won.
- `physical-KRW-1792963117104861018`: visible-name grammar, 3 calls,
  6.90 seconds, both shelf names match; 2 executed units, 3,900 won.
- `physical-USD-1792963164811837349`: 3 calls, 22.44 seconds,
  `name_consistency_ok: true`; 2 executed units, $3.78.

The persistent server reuses prompt prefixes; these times are observations,
not a benchmark. Every run used a new application cache. Image files, request
bodies without credentials, replies, decisions and executed customers are saved.

The committed physical probe now checks name consistency separately from format
completion, so the baseline mismatch causes a nonzero exit. Reproduce with:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-physical-probe.py \
  --currency KRW --free --output /tmp/twinstore-local-probes
```

Nine selected wire/long-name regressions failed before the change. Coverage
includes real HTTP schema construction, sparse/empty badges, mixture/vote
routing, cache reuse, truncation recovery, long English/Korean/Japanese names
with shared prefixes, explicit no-choice answers and unnumbered photos.

Focused checks passed: 183 backend tests in 33.32 seconds, strict typing with
zero errors/warnings and backend boot. Mocked tests emitted 26 existing LiteLLM
logging-cleanup warnings. Frontend source was unchanged in this fix.
