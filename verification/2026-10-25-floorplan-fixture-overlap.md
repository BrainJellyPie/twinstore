# Reject phantom floor-plan fixtures before normalization

A finite, correctly shaped fixture box could be wholly outside the model's
own store outline. Clamping it to 0–1 collapsed it onto a wall, and the grid
builder's minimum-one-tile rule created a stocked rack there. Zero-area shelf
boxes had the same outcome; outside entrances and counters could also move
essential fixtures into a layout. The invalid model reading was cacheable.

Validate each fixture's intersection with the outline in the model-response
schema, before normalization and caching. Non-entrance fixtures need positive
width and height inside the store. Entrances may be lines or points, including
on its boundary, but cannot be disjoint. Reversed fixture corners and partial
overlap retain their existing normalization. The prompt states these rules.
The existing two-attempt correction budget and auto-reader fallback are unchanged.

Sixty failures were reproduced in 3.98 seconds through scripted HTTP responses:
both JSON modes, all six fixture kinds, outside sides/corners, boundary-only
contact, collapsed extents, corrected output, repeated failure and legacy
invalid cache entries. Five clipped-box and boundary-door controls passed.

Afterward, 157 focused geometry, reader, API and persistence checks passed in
9.56 seconds. Only corrected readings are cached; repeated invalid output
fails, while cached invalid readings trigger a fresh request. Pyright: zero
errors and warnings. The 26 pytest warnings are existing LiteLLM async logging
cleanup warnings. No native inference or model download was used.
