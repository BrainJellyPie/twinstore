# Bound local traffic output to explicit opening slots

2026-10-26, based on main `42fd22df`. Qwen3.5-2B Q4_K_M on CPU,
llama.cpp b11878, five threads, 8192-token context, temperature/seed zero,
thinking disabled. All CPU observations used real loopback model calls and
fresh application caches. Timing is observational; server prefix reuse can
change it. Artifacts below are under `/workspace/scratch/cpu-vlm-probe-2b/`.

The new traffic-stage probe supplies four customer-type labels, a 24-hour
schedule and observed counts of exactly one visitor in each hour. It calls
production `analyze_daily_traffic`; it does not claim to run the upstream
area-profile or downstream individual writers.

Before the change:

- `traffic-24h-json_schema-1792997543971485139`: one HTTP call, 27.68 s.
  All 24 slots were present, but every observed count became zero.
- `traffic-last-hour-json_schema-1792997574770880017`: one call, 5.32 s.
  The 23–24 single-slot control retained one visitor and a valid type.
- `traffic-24h-json-1792997582813624990`: a real request timed out after
  180.26 s. There were zero **completed** HTTP responses, not zero attempts;
  client usage counted one attempted request. The response body was unavailable.
- A separate bounded diagnostic, `traffic-bounded/traffic-24h-json-1792998071302162257`,
  used one attempt and a 1200-token output ceiling. It returned HTTP 200 after
  57.522 s with `finish_reason=length`: the unfinished array contained 54
  `visitor_count` keys, all zero, instead of ending after 24 rows. This is not
  a recovered body from the earlier timeout.

`traffic_response_model` now asks for a finite object whose numbered keys are
exactly the opening slots. The decoder validates key coverage, restores numeric
slot order, and assigns clock hours. Missing/extra keys, schema echoes and mixed
numbered entries/explicit clocks fail rather than being silently discarded.
Retry feedback identifies missing and unknown keys, including an accidentally
added closing boundary. Existing explicit-hour and positional arrays remain
accepted for older providers and canonical caches; cached output remains a list
of validated rows with hours. Existing identity, count, duplicate-clock and
out-of-hours checks remain in place.

The wire schema references one registered row definition instead of repeating
all customer-type choices for every hour. The initial inline prototype used
5735 input tokens in JSON mode. The shared-definition prototype used 2005; the
final prompt adds a small instance example. The test also checks 24 slots with
16 near-limit labels without expanding the serialized schema past 6000
characters. No visitor count is replaced in order to pass a probe.

Actual final structured-output results, each one HTTP call with zero application
cache hits:

| Artifact under `traffic-final/` | Seconds | Result |
| --- | ---: | --- |
| `traffic-24h-json_schema-1792998743848793198` | 23.08 | All 24 observed one-visitor slots and their types retained |
| `traffic-last-hour-json_schema-1792998770173915015` | 5.03 | 23–24 keeps one visitor |
| `traffic-last-hour-zero-json_schema-1792998778200534222` | 1.85 | Explicit zero visitors remains zero |
| `traffic-24h-varied-json_schema-1792998782898290804` | 39.80 | Six hours each of 0, 2, 5 and 1 visitors retained, total 48 |

Plain JSON remains weaker. The first instance-example candidate returned keys
0 through 24 three times and failed after 110 s
(`traffic-final/traffic-24h-json-1792998630863881640`). With precise unknown-key
feedback, `traffic-key-feedback/traffic-24h-json-1792998922171225861` completed
valid keys 0–23 after two calls, 66.52 s. It still changed the supplied counts
to zero, so the semantic probe deliberately **fails**. This fixes neither that
counting error nor every possible local-model failure. The earlier full-inline
and shared-definition prototypes also retained wrong zero counts; their
results are in `traffic-keyed-bounded/` and `traffic-keyed-shared/`.

The full production customer pipeline was then run, including a newly generated
area profile, traffic and individuals:
`persona-24h-json_schema-1792999170602403161`. Three real calls took 62.42 s.
The estimate and final population both contain exactly 24 visitors, one in each
hour. The requested two-person sample produces two written profiles and 22
explicitly marked twins. Both written customers invent positive KRW budgets
(2000–5000 and 1500–3000) absent from the source. The complete quality probe
therefore **fails**, despite correct slot counts and completed generation. The
budget issue remains open; this change does not overwrite model budgets.

The probe now persists a sanitized request before waiting and reports attempted
calls separately from completed responses. A refused-loopback connection control
(`/workspace/scratch/probe-request-failure/pack-label-json_schema-1792999438939437960`) records two attempts, zero completed responses and the
request that previously would have been lost. Image bytes stay in `image.png`;
request logs contain an image placeholder and no authorization headers/key.
This control does not invoke a model. Probe compilation passed.

Twenty-five new regressions cover both JSON modes, reversed keys, 0–1/23–24/
9–18/0–24 windows, canonical caches, invalid or mixed entries, shared schema
size and schema isolation. Before the implementation, 17 failed and eight
passed. Afterward all 25 pass (15 existing LiteLLM logging-worker warnings).

Integration includes `1005085e` (broader online browsing-goal wording) and
`95bd1d5c`, including its two predecessor commits (wrapped floor thought bubbles,
opaque labels and two-line shopper facts). No conflicts occurred. Frontend
validation passes 67 selected cases, changed-file ESLint, TypeScript and the
production Vite build (21.23 s). Known Vite chunk-size/plugin-timing warnings
remain. Strict backend Pyright reports zero errors/warnings and the server boots.
The first Pyright command was launched outside the backend configuration
folder and could not resolve two installed dependencies; the configured
backend-directory command passed.

The 21-file affected backend selection initially passed 459 cases and failed
26 in 34.66 s. These failures came from two offline fixtures that decoded the
first JSON object in a system prompt; they now encountered the new instance
example rather than Instructor's appended schema. The fixtures now read the
SDK schema section. All 84 cases in those two files pass on rerun (11.96 s),
so all 485 distinct selected cases have passing results. The initial selection
emitted 29 LiteLLM cleanup warnings and the rerun 12. No full repository test
suite was run or claimed. The new schema tests are part of that 485-case count.
