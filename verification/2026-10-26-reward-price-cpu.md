# Reward amounts must not become shelf prices

On main `63012e3b`, Qwen3.5-2B correctly read `EARN $1.00` and returned a
null selling price. The capture converter nevertheless parsed that amount
as an exact 100-cent product price. The Korean tag `1,000원 적립` reproduced
the same failure: correct text, null model price, then an exact 1,000-won
product price. These amounts describe benefits, not the product's price.

The existing non-selling-label guard now recognizes earned/reward/store
credit amounts and Korean 적립/적립금/적립액. It preserves the printed text,
uses the normal estimated fallback and prevents a matched product's current
price from being replaced by the reward amount. Explicit `Rewards price`
or `적립금 적용가` labels remain usable selling prices. The fix changes
conversion; prompts and response formats are unchanged.

## Actual CPU observations

Qwen3.5-2B Q4_K_M on llama.cpp b11878, five CPU threads, no GPU,
8,192-token context and reasoning disabled. Every listed case used a fresh
application cache and two HTTP requests: product recognition and a separate
tag read. Synthetic images were visually inspected. Known fixture geometry
isolates recognition and production `build_items` conversion; this is not
a detector benchmark or a real-shelf accuracy estimate.

| Case | Mode | Seconds | Result |
| --- | --- | ---: | --- |
| EARN $1.00 baseline | Native schema | 14.62 | Failed: exact 100 cents |
| 1,000원 적립 baseline | Native schema | 14.69 | Failed: exact 1,000 won |
| EARN $1.00 repaired | Native schema | 4.08 | Estimated, 229 cents |
| EARN $1.00 repaired | JSON | 18.13 | Estimated, 189 cents |
| $1.00 REWARD repaired | Native schema | 13.22 | Estimated, 229 cents |
| 1,000원 적립 repaired | Native schema | 4.08 | Estimated, 3,100 won |
| REWARDS PRICE $1.00 control | Native schema | 15.68 | Exact 100 cents retained |

Fallback amounts can differ with the model's product/category interpretation;
they are estimates, not a recovery of the photographed item's actual price.
The native server can reuse prompt prefixes, so durations are observations,
not comparative performance measurements. The reusable probe contains the
four new tags and retains existing price/coupon/free/unit-rate controls.

## Regression verification

Before the English guard, the expanded savings regression file has 44 failing
and 173 passing cases. Before adding the Korean guard, the expanded file
has nine Korean failures and 219 passing cases. The initial attempt to
select Korean tests using `-k` selected none because pytest escaped their
IDs; the full file was run instead and supplied those failure counts.

Final focused verification passes 1,355 cases across nine capture files in
4.08 seconds. Coverage includes numeric model guesses, currencies and fullwidth
text, zero reward values, positive conditional selling prices, unrelated
products, source-store immutability, and placement with/without a known SKU.
Sixteen existing LiteLLM cleanup warnings remain. Strict Pyright/boot and
probe compilation pass. Frontend is unchanged; the parent's 142 UI checks,
TypeScript/lint and production build are inherited, not rerun.

## Evidence

Under `/workspace/scratch/cpu-vlm-probe-2b/`:

- English baseline: `reward-baseline/capture-reward-price-json_schema-1793038574172460401`.
- Korean baseline: `reward-korean-baseline/capture-reward-krw-json_schema-1793038753794252188`.
- Five passing result records under `reward-final/`, timestamps
  `1793038654238246508` through `1793038789926567439`.

Logs: `/workspace/scratch/reward-price-{baseline,before,korean-before,tests,pyright,boot}.log`,
`/workspace/scratch/reward-final-cpu.log` and
`/workspace/scratch/reward-korean-{baseline,final}.log`.
The v0.8.2 release remains unchanged; this fix is Unreleased on main.
