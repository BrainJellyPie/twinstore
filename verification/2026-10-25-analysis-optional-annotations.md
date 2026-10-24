# Preserve valid analytical answers with absent annotations

Optional null journey-step references, figures, follow-up questions or comparison
detail rejected a valid answer. The affected paths were shopper interviews,
questions about a completed run, and explanations comparing two runs.

Normalize those null annotations to their existing omitted-field defaults:
empty lists for references/questions and empty strings for optional comparison
detail. Prompts request those representations. Required answer/summary text,
non-null field types, length bounds and evidence filtering remain unchanged.
No citation or narrative is invented.

Sixteen failures were reproduced through real HTTP parsing in both JSON modes;
33 omitted/valid annotations and strict-validation controls passed in 4.24
seconds. Tests use an executed purchase journey, preserve exact answer text,
filter unsupported figures and journey references, and check cached response
values. Required null, blank and malformed answers remain errors.

Afterward, 94 focused interview, personal-context and run-analysis API checks
passed in 9.12 seconds. Pyright reported zero errors and warnings. The 28 pytest
warnings are existing async logging cleanup warnings. No real model inference
or model download was used.
