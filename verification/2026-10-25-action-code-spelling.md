# Preserve purchases written with a known offer-code variant

Model-written action codes such as `@p1` and a padded lowercase `@P1` variant
were accepted as strings but not decoded. The invalid-buy guards then removed
the intended planned or impulse purchase. This silently changed spending and
conversion rather than producing an obvious request error.

The offer decoder now resolves only unique known code spellings before its
existing placement, accessibility and exposure checks. Real store SKUs take
part in the identity/ambiguity check but are never rewritten. Generated codes
avoid both exact and case/space collisions with every real SKU, including ones
outside a later shortlist. This allows recovery without redirecting literal
SKUs such as `@p1` or ` @P1 ` to a different product. Both action prompts request
the exact capitalization and number of `@` characters.

The expanded real LiteLLM/Instructor HTTP tests cover JSON and JSON-schema,
planned and nearest routing, repeated cache reads, planned and impulse
purchases, adjacency and visibility exposure, and offers of the same SKU on
different levels, blocks or racks with different prices. Assertions include
the selected 700-unit offer, its two-unit 1400-unit checkout, product name,
single payment, exit, source immutability and out-of-stock lost revenue. The
impulse matrix also retains literal canonical-SKU responses and records their
purchase origin and quantity. Direct controls cover alias/real-SKU collisions,
shortlisted catalogs, ambiguous aliases and unknown identifiers without
normalizing arbitrary raw SKUs.

Before the repair, 80 HTTP cases reproduced lost purchases and 20 direct
collision/decoding cases failed. The initial baseline also had eight malformed
new control fixtures (missing required `nav`); correcting those fixtures made
all eight pass on the unchanged source. They are not production defects.
After the repair, the focused offer, exposure, code, reachability and cache
suites passed 407 checks in 12.98 seconds, with two known LiteLLM logging-cleanup
warnings. Full source Pyright reported zero errors and warnings. Provider
responses were scripted; no native model inference, downloads or paid calls
were used, and occurrence rates were not measured.
