# Keep shelf grounding focused on coordinates

The grounding prompt asked for a short label beside every product box, but the
detector discarded those labels immediately. A null, overlong or nonstring label
on one otherwise valid box failed validation for the whole photograph, spent a
second request and fell back to classic detection without any of the valid model
boxes.

Remove the unused field from the response schema and request coordinates only.
Extra narration from non-enforcing providers is ignored like other unknown
fields. The later product-labeling stage remains responsible for names, brands,
sizes and prices. Required finite four-coordinate boxes, normalization,
refinement and the failure fallback are unchanged.

Before the change, 18 reproduction cases discarded the photo's detections;
18 omitted/blank/ordinary-name controls passed in 3.13 seconds. Scripted HTTP
responses through LiteLLM, Instructor and the cache cover both JSON modes and
bad labels at the first, middle and last of three valid boxes. All boxes must
keep their exact coordinates after one request, and a repeated call must use
the normalized coordinate-only cache entry. Existing nonfinite-coordinate tests
continue to require correction or uncached failure.

The focused grounding and capture tests passed 139 checks in 8.77 seconds.
One optional GroundingDINO test stayed skipped because it requires a roughly
700 MB model download; 36 existing LiteLLM async logging cleanup warnings were
emitted. Full source Pyright reported zero errors and warnings. No native model,
downloads or paid requests ran.
