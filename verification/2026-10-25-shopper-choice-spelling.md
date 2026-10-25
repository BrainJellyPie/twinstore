# Preserve requested shopper groups despite model choice spelling

Known age, gender, purchase and sorting choices failed model validation when
their case or surrounding whitespace differed. The response-only TimedFilter
now recovers those spellings before its existing literal checks. The prompt
asks for exact labels. Unknown choices, changed internal spelling, wrong types
and explicit null groups remain errors. Explicit legacy filters stay strict.

The HTTP matrix covers all 18 choices in both structured-output modes through
real LiteLLM and Instructor with scripted responses. Twelve customer records
span every age/gender combination, purchases at two shelves, empty baskets,
impulse quantities and different visit/browse durations. Assertions compare
actual selected IDs and ordering against independently calculated expectations,
and check cache reuse and unchanged source records. The API regression also
retains exact criteria, unknown-shelf warnings and complete matching coverage.

Before the repair, 37 cases failed and 59 passed in 8.60 seconds. Focused
verification initially exposed six fixture failures because the test shelf had
no product slots and was therefore not a product rack; the fixture was corrected
to include both stocked shelves. The final new suite passed 89 checks in 2.90
seconds; the other focused range, clock, boundary and API suites had passed 273
checks. This is 362 distinct passing checks, without repeating those suites.
Full source Pyright reported zero errors and warnings. LiteLLM emitted known
logging-cleanup warnings. No native model inference, downloads, paid calls or
measurements of model error frequency were performed.
