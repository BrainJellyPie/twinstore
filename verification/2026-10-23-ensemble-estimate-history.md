# Ensemble history must identify the models behind the labels

Run manifests display ensemble member names and rounded weights. Two different
model groups can therefore share a manifest label. The estimator matched that
label alone and reused the old group's request count, tokens and elapsed time,
even after a user changed the actual models while retaining their aliases.

Ensemble measurements now also read the existing saved `input/config.json` and
compare the ensemble mode, ordered model references and exact weights. Missing,
malformed or incompatible inputs are skipped. The newest compatible older run
can still supply a measurement; otherwise the ordinary engine defaults apply.
Single-model legacy histories retain their existing behavior. This change does
not freeze mutable provider endpoint settings or claim exact future costs.

Focused offline verification:

- Original-code reproduction: **18 failed, 2 passed in 2.35 seconds**, covering
  text/vision engines, one/both model substitutions behind identical aliases,
  weights that share a rounded display label, unreadable/missing saved identity
  and valid matching history.
- Added two cases retaining an older compatible measurement behind a newer
  incompatible one. New cases plus existing history/ensemble tests:
  **95 passed in 3.64 seconds**.
- Strict Pyright for `application/run_estimate.py`: **0 errors**.

No provider calls, full suite or frontend build were needed.
