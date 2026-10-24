# Let complete receipt item lists reach review

Receipt transcription shared the storefront-rating limit of 1,500 output
tokens. Valid receipts with 30 indented or 60 compact item records exceed that
limit, making the model response fail before product matching and review.

Pass a 6,144-token ceiling only to receipt transcription. Storefront ratings
remain at 1,500, and the source capture configuration retains its 320-token
product-reading limit. Existing two-attempt retries, numeric validation,
currency conversion, review gates and cache isolation remain intact.

The existing Qwen3.5 tokenizer measured compact/indented JSON as follows:

| Items | English / USD | Korean / KRW |
| --- | --- | --- |
| 5 | 181 / 313 | 182 / 314 |
| 30 | 881 / 1,538 | 883 / 1,540 |
| 60 | 1,721 / 3,008 | 1,723 / 3,010 |

Tokenizer SHA-256: `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`.
This ceiling covers the measured examples; unusually long receipts and the
server's remaining context can still limit output.

Before the fix, 12 application/HTTP cases failed and 12 shorter-output controls
passed in 2.74 seconds. Both JSON modes use the real LiteLLM/Instructor stack
with scripted HTTP truncation based on measured response size and the actual
request cap. Checks cover every line, currency conversion, SKU matching,
review readiness, CSV values, cached rereads and the separate storefront cap.
These fixtures verify application behavior, not real-model transcription quality.

The focused suite produced 112 passes and seven test-double signature failures
in 5.30 seconds. Updating the shared fake to accept the new optional argument
made all 35 affected tests pass in 2.74 seconds: 119 distinct checks passed.
The 25 initial warnings were existing LiteLLM async logging cleanup warnings.
Full source Pyright reported zero errors and warnings. No native inference,
model downloads or paid requests ran.
