# Preserve shopper identifiers in paired experiment evidence

The experiment worker retained minimal outcomes for factorial review using a
schema that treated customer identifiers as file resource identifiers. Supported
customer labels containing Unicode, whitespace or punctuation were rejected, as
were scenario/neighborhood clone IDs containing `~`. The worker intentionally
kept the main A/B report successful but discarded the paired snapshot, making a
new experiment's factorial source unavailable with a legacy-source explanation.

Customer labels now remain exact strings in paired evidence. Nonblank, unique,
panel-member checks remain enforced, and actual experiment/setup resource IDs
retain their path-safe validation. Labels are neither trimmed nor normalized.
Existing CSV formula escaping remains unchanged.

Evidence:

- 14 API regressions failed before the fix; four ASCII/numeric/long-ID controls
  already passed. The matrix includes Unicode composition, emoji, spaces,
  generated clone suffixes, path-like strings, quotes/newlines and formula-like IDs.
- 84 focused API and engine checks passed in 5.61 seconds. They verify retained
  source availability, exact labels, paired contrast estimates, CSV round trips,
  distinct labels, blank/missing/foreign identities and existing snapshot guards.
- Strict Pyright on the changed domain module: zero errors.
- No live model calls or full-suite rerun. No UI text changed.

```sh
uv run pytest -q tests/server/test_factorial_customer_identifiers.py tests/server/test_factorial_api.py tests/engine/test_factorial.py --tb=short
uv run pyright src/store_emulator/domain/factorial.py
```

This affects future captures and supported saved snapshots. Evidence discarded by
an earlier run cannot be reconstructed from aggregate reports; rerun that study.
