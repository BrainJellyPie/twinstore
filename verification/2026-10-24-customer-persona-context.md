# Preserve customer evidence in the individual writer

Customer descriptions and supplemental/neighborhood summaries reached area and
traffic analysis, but the individual persona writer received only short category
labels and arrival specifications. Budget, preferences and other details absent
from those labels were lost. Identical labels and arrivals also gave the writer
the same cache key after the underlying evidence changed.

The writer now accepts optional source description and summary arguments and
adds nonempty values to each batch's user prompt. The common write path passes
them to full generation, the initial speed probe, and both children of the existing
bounded context/truncation recovery. Custom instructions remain separate, and no
labels, budgets or preferences are fabricated by application code. Direct callers
omitting the new optional values retain their prior prompt. There are no extra
inference calls; the source text adds input tokens to existing calls. An oversized
shared prefix still fails through the existing bounded recovery rather than being
silently truncated.

All 24 HTTP regressions failed before the patch. They exercise JSON and JSON-schema
modes, description-only/summary-only/both inputs, full/probe/context/truncated
workflows, and two revisions with identical area labels and traffic. Assertions
check changed budget/preference results, evidence in every child/probe request,
unchanged weekday/hour counts, ten distinct IDs without twins, and reuse only for
matching cached inputs. Context/truncation failures still have to be encountered
on a repeat before their successful child responses are retrieved from cache.

Focused persona, traffic, concurrency, recovery, grammar, optional-field and write
choice checks: 187 passed in 10.29 seconds, with one existing LiteLLM logging-cleanup
warning. Strict Pyright: zero errors. Responses were scripted through HTTP; no live
inference was used and actual model adherence to the evidence was not measured.
