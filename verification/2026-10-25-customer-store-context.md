# Ground customer generation in the owner's store details

The generation pipeline passed the address, customer profile, supplemental
evidence and neighborhood information, but omitted the saved store name, type
and description. Changing a cafe into a pharmacy while keeping the address and
customer description therefore produced identical requests and reused the same
cached responses in all three generation stages.

Include nonblank owner-provided store fields as a JSON object in the existing
runtime evidence passed to type analysis, hourly traffic and persona writing.
This preserves the original customer profile, instructions, uploaded-data
summary and neighborhood evidence. It does not overwrite the persisted upload
summary or invent missing facts for legacy metadata.

Before the change, 12 protocol tests reproduced the cross-store cache reuse;
three missing/null/blank metadata controls passed in 3.01 seconds. Both JSON
modes use the real application pipeline, LiteLLM, Instructor, HTTP adaptation
and disk cache with scripted responses. Changing each store field separately
must issue three fresh requests even when the model returns identical customer
labels. Repeating identical inputs reuses the cache. Every transmitted stage
must include the field, original instructions and other evidence; Korean text
and quoted descriptions remain intact. Persisted metadata keeps its original
upload summary and customer profile.

Focused store-context, preference, traffic, batching, estimate and neighborhood
tests passed all 147 checks in 10.08 seconds. Full source Pyright reported zero
errors and warnings. No native model, model downloads or paid requests ran;
these checks verify evidence delivery and cache separation, not the quality of
an actual model's demographic predictions.
