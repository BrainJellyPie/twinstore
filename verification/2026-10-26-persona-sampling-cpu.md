# Separate customer-writer sampling settings in CPU probes

The customer generator passes `config.llm` into `assistive_client`; provider
resolution retains its sampling settings. `LLMConfig.temperature` defaults
to 1. The reusable local probe used temperature 0 for customer cases, a
useful deterministic stress setting but different from that default. Users
can configure other temperatures. Earlier references to the production
prompt describe its text, not equality of every application setting.

The probe now accepts `--temperature` from 0 to 2 and records the effective
value in `result.json`. Existing case defaults are preserved. Use
`--temperature 1` to exercise the default customer-writer sampling setting.
This changes the verification tool only: application prompts, schemas,
sampling settings, batch sizes and generated customer records are unchanged.

## Actual observations

All runs use Qwen3.5-2B Q4_K_M on llama.cpp b11878, five CPU threads, no GPU,
8,192-token context, reasoning disabled, seed 0 and a 4,096-token output
ceiling. The fixed twelve-person night-market fixture isolates the writer
from traffic estimation and uses the local batch sizes 5+5+2. The supplied
budget range is KRW 3,000–10,000. Each row completes three HTTP calls with
zero application cache hits; times are observations, not benchmarks.

| Production/candidate | Temperature | Mode | Time | Observed failure |
| --- | ---: | --- | ---: | --- |
| Budget fields first in the wire schema | 0 | Native schema | 102.04 s | All budgets fit, but one independently written profile is copied exactly |
| Copy applicable bounds; write other fields independently | 0 | JSON | 114.16 s | Two budgets outside the supplied range |
| Unchanged production prompt/schema | 1 | Native schema | 91.95 s | Six budgets outside the supplied range |
| Same copy-bounds candidate | 1 | Native schema | 90.47 s | Five budgets outside the supplied range |

The temperature-1 production run includes both bounds being exceeded and a
zero upper limit meaning unspecified, despite the supplied finite range.
The request trace confirms temperature 1 on the wire. Thus the budget
failure is also present with the default sampling temperature; it is not
explained solely by the deterministic stress setting.

Both candidates remain withheld. The schema-order candidate's first five
budgets were correct, but evaluating the complete cohort exposed repetition.
The copy-bounds candidate's previously successful small native-schema case
did not generalize to these controls. Its planned USD, unspecified-budget,
fractional EUR and JPY cases were not run after the first JSON failure; no
success is claimed for them. No records were clamped or deduplicated to make
the probes pass.

## Tool verification

Four invalid CLI values (`-1`, `nan`, `inf`, `2.01`) fail before inference.
A saved real-model coupon capture replays successfully under the unchanged
default temperature 0: zero HTTP calls and two cache hits. Its generated
fixture image is byte-identical to the original. Probe compilation and diff
checks pass. No application tests were rerun for this tool-only change;
main `873af611` remains the verified application baseline. Published v0.8.2
assets are unchanged.

Artifacts under `/workspace/scratch/cpu-vlm-probe-2b/`:

- `persona-budget-first/persona-nightmarket-local-batches-json_schema-1793036627621226620`.
- `persona-small-budget-controls/persona-nightmarket-local-batches-json-1793036878906599862`.
- `persona-default-temperature/persona-nightmarket-local-batches-json_schema-1793037128767461863`.
- `persona-small-default-temperature/persona-nightmarket-local-batches-json_schema-1793037394378142807`.
- `temperature-default-replay/`: saved-output check, not new inference.

CLI evidence: `/workspace/scratch/probe-temperature-cli-checks.json`.
Scratch runners: `probe-persona-budget-first.py` and `probe-persona-budget-fields.py`.
