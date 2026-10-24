# Preserve directory identity when model category labels are clipped

The entry planner bounds category output to 30 characters for small local models.
After a longer directory label was clipped, exact category matching failed and
broad word matching could select unrelated shelves. With the same product name
on two shelves, the selected candidates included both the intended 700-unit offer
and an unrelated 100-unit offer. English labels sharing ordinary words and long
Korean/Chinese labels without spaces all reproduced the mismatch.

Category matching now recognizes a label at the schema's shared length limit as
potentially clipped and compares it with directory prefixes before word matching.
An unambiguous prefix preserves the intended shelf. Multiple matching prefixes
remain candidates, including a shorter exact label that could otherwise
impersonate the clipped name. This cannot recover distinctions absent from the
bounded response and does not claim to resolve them. Blank labels and shorter
partial labels retain their earlier behavior; product-only category fallback is
unchanged. No model call or output allowance was added.

Before repair, thirty cases failed and nine controls passed. Afterward, 163
focused planning, category, shelf-offer and ensemble-disambiguation checks passed
in 16.13 seconds. Nine additional strict-JSON and boundary cases brought the
unique total to 172; the final 48-case category file passed in 0.75 seconds.
Coverage includes full or grammar-bounded model strings, English/Korean/Chinese,
shared and different SKUs, rack order, multiple purchase seeds, actual purchase
price/revenue, exact 29/30-character labels, shared prefixes and blank input.
Strict Pyright reported zero errors. These are scripted/offline model and
simulation tests; no live inference or paid requests were used.
