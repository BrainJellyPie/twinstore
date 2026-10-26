# Follow-up customer budget boundaries on the actual CPU model

2026-10-26, from main `56c36e3e`. Qwen3.5-0.8B Q4_K_M, CPU only,
five threads, llama.cpp b11878, 8192-token context, temperature 0 and seed 0.
All calls use fresh application caches; server prefix reuse makes elapsed times
observations rather than independent benchmarks. The production customer
pipeline runs directly, with no mocked model replies.

| Input | Artifact directory | Calls | Seconds | Result |
| --- | --- | ---: | ---: | --- |
| Korean KRW with thousands commas, 3,000–10,000 won | `persona-neighborhood-json_schema-1792974836317484802` | 3 | 30.46 | Correct 3000–10000 stored won; diagnostic fails identical written customers |
| Spanish USD, $3–$10 | `persona-us-json_schema-1792974931250783037` | 3 | 22.51 | Correct 300–1000 cents and snacks/drinks preferences; current diagnostics pass |
| French EUR with decimal commas, €2,50–€7,75 | `persona-fractional-json_schema-1792975057093111973` | 3 | 26.96 | Model emits `"2.50"`/`"7.75"`, stored as 250/775; diagnostic fails identical written customers |

The final Spanish schema includes required preferences. Its earlier candidate
without that requirement returned explicit zero amounts. This repeat passes,
but a single deterministic case does not establish general multilingual budget
accuracy. The new `persona-fractional` case is retained in the reusable probe.

Manual review of the French fractional case also finds the identity “un petit
café” (a small café), rather than a type of person, and the French goal
“acheter du café” despite the English-output instruction. Valid amounts and
well-formed JSON do not resolve those semantic errors. The duplicate diagnostic
keeps this case failed; the Latin-letter heuristic alone cannot recognize the
wrong language or nonhuman identity.

A scratch variant advertises `customer_types` and `visit_goals`, accepting the
old field names as validation aliases. The actual run
`persona-fractional-people-keys-json_schema-1792975192870987049` completes in
three calls and 23.48 seconds. Its types are now people (passersby, tourists,
students), but labels remain French, its goal pool collapses to “acheter”, an
unrelated “lunettes” keyword appears, and both written customers are identical.
That variant is withheld; no production profile aliases or parsing rules change
in this iteration. The diagnostic remains failed.

This integration includes `53ac253f`: shrinkable mobile grid columns, compact
conjoint attribute controls, narrower shelf-test inputs, vertical store quick
links, and smaller side-panel tabs. The changelog wording is narrowed to the
changed layouts rather than claiming every possible phone layout is fixed.

Verification: 149 frontend cases in eight affected suites pass (53.22 seconds),
followed by TypeScript, lint of the changed frontend files and a production build
(20.78 seconds). The usual chunk-size and Babel-plugin timing warnings remain.
The test process was observed while it was busy, then completed normally; it
was neither terminated nor rerun. No backend application source changes in this
iteration, so the previous strict-typing and backend checks were not repeated.
