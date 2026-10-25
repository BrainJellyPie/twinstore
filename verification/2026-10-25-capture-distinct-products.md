# Preserve captured variants during automatic SKU matching

Automatic photo placement and shelf audits used loose SKU matching. A read
1500ml bottle could become the existing 500ml bottle; a generic name such as
Tea could match despite an additional captured brand and size. Matching
rewrote the captured name, brand, size and SKU, and could replace its estimated
price with the other product's price. This also occurred in saved child layouts.

The existing exact-name mode is now the default for both SKU matching and
adding photo racks. Thus replacement, addition and audits require the full
normalized display name, including brand and size. The batch workflow already
used this policy. Unknown products keep their captured identity and price.
Existing explicit loose-mode calls remain available; automatic application
paths do not opt into them. Known exact names still reuse their original SKU.

The pre-fix reproduction failed 28 checks and passed eight controls. After
the change, 185 focused capture/batch/API checks passed in 13.21 seconds;
the existing shelf-audit scenario separately passed in 1.70 seconds. Full-source
Pyright reports zero errors and warnings. Thirty-two tests use the real
LiteLLM/Instructor path with scripted HTTP in JSON/JSON Schema modes, USD/KRW,
read/estimated prices, full names and separate brand/size fields. They exercise
auditing, replacement, addition, unchanged sources and cached label reuse.
Four API cases verify saved child layouts preserve the distinct product's
SKU, full name and price. Existing ambiguity and exact-match controls pass.

No native vision inference, model weights or paid calls were used. These
checks test what happens to supplied model labels, not OCR accuracy. Existing
third-party LiteLLM logging cleanup warnings remain.
