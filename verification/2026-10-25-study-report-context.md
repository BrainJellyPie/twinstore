# Keep study caveats when repeated quotations fill the report budget

A survey produced by the real report builder, with four stimuli, all seven
questions and 48 valid 240-character explanations, serialized to 17,315
characters without respondent rows. The 16,000-character commentary cap cut
inside its duplicate verbatim quotations: the supplied JSON was invalid and
the final interpretation notes were absent. Those same explanations already
travel separately into theme coding.

When a report exceeds the cap, compact_report now omits the redundant verbatims
before applying the existing size limit. The reproduced report becomes 7,581
characters while preserving every aggregate, price curve, preference, segment
and note. Small reports retain their quotations, including cases too small for
theme coding. Source reports and caller exclusion sets are unchanged. This
does not redesign the existing cap for oversized non-verbatim report content.

Tests use real survey aggregation in USD and KRW, with short/long explanations
and one failed respondent. Scripted HTTP cases in both output modes exercise
real LiteLLM/Instructor, application report loading, all 48 coded explanations,
commentary validation, saved reading and cache reuse. The saved quantitative
report remains byte-for-byte unchanged.

Four initial long-report checks reproduced lost JSON/caveats; two initial
short-report expectations were refined to retain existing quotation behavior.
The final focused report, summary, theme-recovery, grammar and API suites passed
69 checks in 5.48 seconds, with 27 known LiteLLM logging-cleanup warnings. Full
source Pyright reported zero errors and warnings. No native model inference,
model download, paid call or model error-frequency measurement was performed.
