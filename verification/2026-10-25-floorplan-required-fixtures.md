# Do not import a missing fixture list as an empty store

The model-only floor-plan response gave `fixtures` an empty-list default. An
otherwise valid response containing only the outline and dimensions therefore
succeeded without a correction attempt. The application cached that incomplete
response and saved a layout with no stocked racks, in both explicit VLM and
automatic reading modes.

Make the fixture list required in the model response and state that requirement
in the prompt. Explicit `fixtures: []` still represents an empty plan. Domain
readings, classic recognition, optional labels/dimensions and geometry checks
retain their behavior. The changed schema also separates new cache entries from
the old optional-fixtures schema.

The 16 application/HTTP cases cover both JSON modes and both reader choices,
with corrected omissions, persistent omissions, corrupted cached responses and
explicit empty lists. They exercise real import persistence, saved `Store`
content, stocked-rack counts and cached rereads. Explicit VLM failure returns
502 without creating a layout; auto mode uses the existing classic reader on
a drawn plan and retains stocked racks. A separate check verifies requiredness
in the transmitted schema while preserving explicit empty plans.

Before the fix, 13 checks failed and four explicit-empty controls passed in
3.59 seconds. The focused import, persistence, metadata, geometry, aspect,
output-budget, access and checkout suite passed 290 tests in 14.42 seconds.
Full source Pyright reported zero errors and warnings. The 153 warnings were
existing LiteLLM async logging cleanup warnings. HTTP model replies were
scripted; no native inference, model downloads or paid APIs ran.
