# Keep mixed category/SKU experiments eligible for online transfer

Integrate the marketing branch through `0908df2f`: conditional price×sign
analysis offers, clearer kept-layout names/focus, localized control labels
without a control interval, and online-store ranking by carried product SKUs.

A new UI regression exposed an eligibility error. A tested variant can change
one missing SKU and also discount a category that the online store sells.
The SKU query correctly returns carries=0, but that does not describe the
category. The interface hid the store and prevented a valid partial transfer.
The initial focused UI suite had one failure and seven passes.

When category-wide changes are present, SKU counts now rank candidates without
excluding them. The existing server checks category/product applicability and
reports skipped changes. Pure SKU changes still exclude stores known to sell
none of their products; sign-only and currency checks are preserved.

The server regression creates an actual store fixture, observes carries=0
for its missing SKU, applies the mixed change and checks that the category is
discounted, the missing SKU is reported as skipped, and the original store is
unchanged. The UI regression carries that same kind of mixed variant through
the completion and skipped-change display.

Validation: **51 frontend tests in seven files** passed (7.29 s), and
**21 server/report tests** passed (4.95 s). Strict Pyright reported zero
errors/warnings; the backend app import passed. ESLint on nine changed
TypeScript files, TypeScript checking, diff checking and the production build
passed (20.19 s; existing chunk warning). Released changelog content from
v0.8.2 onward is unchanged. No local-model inference was needed for this
eligibility fix; the preceding CPU probe limitations remain documented.
