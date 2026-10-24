# Bounded recovery for intent input-context rejection

Even with compact offer records, urban and campus templates have stage-two
system prompts above the managed local server's effective 8K context per slot.
Eight HTTP regressions reproduced the failed visit before this change.

After a terminal typed input-context rejection, the engine now asks for candidate
codes from the full offer table, using the same persona, behavior pattern, situation
and budget. The candidate limit is the larger of four and the pattern's purchase
limit. A request-local grammar and validator reject unknown codes; repeated valid
codes are deduplicated, and an empty selection is valid. Candidate selection allows
two structured attempts. The focused intent request then has one attempt, with no
recursive recovery if either child still fails. Catalogs too small to shrink skip
this recovery. The terminal exception, including original HTTP status, determines
eligibility; an earlier context error cannot override a later validation failure.

The focused prompt explicitly identifies its candidate scope. It retains all
original rack metadata and access information, while showing placements only for
selected offers. Original record codes decode to canonical SKUs, and the schema
fingerprint retains the hidden SKU mapping. The store and inventory are unchanged;
routing and subsequent impulse exposure use the full store. The decision trace
records selected codes and SKUs. This changes model context and potentially its
choices; it is not evidence of statistically identical live-model preferences.

Offline Qwen tokenizer measurements of production system prompts:

| Template | Full intent | Full-table selection | Focused intent (first four offers) |
| --- | ---: | ---: | ---: |
| compact_cvs | 5,723 | 1,926 | 1,748 |
| urban_cvs | 9,337 | 3,585 | 2,252 |
| campus_cvs | 9,848 | 2,884 | 2,549 |

These exclude customer text, chat templates, response-schema overhead and output.
Very large catalogs, long custom input or many racks can still exceed context;
the bounded recovery then reports the failure. Repeated identical visits reuse
successful selection/focused/impulse results, but still submit the initial full
intent request because provider rejection is not cached.

Focused verification: 293 tests passed in 5.89 seconds, including 33 new cases;
strict Pyright reported zero errors. New coverage uses real OpenAI/LiteLLM/Instructor
HTTP parsing in JSON and JSON_SCHEMA modes, both route orderings, correction of an
unknown code, canonical purchase revenue, cache reuse, unchanged stores, HTTP
403/429, unrelated 400 errors, generated context-looking text, output truncation,
exhausted selection attempts, focused failure, terminal-attempt precedence, small
catalogs, empty selections, duplicate codes and custom purchase limits above four.
Eight existing LiteLLM logging-cleanup warnings occurred. All inference was scripted;
no live model, paid provider or model-weight download was used.
