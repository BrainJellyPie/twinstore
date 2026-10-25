# Online smart-search category and tag matches

Searching the built-in fashion store for `Apparel` or `Footwear` returned no
products despite catalogs of 8 and 12 products respectively. The online shopper
panel uses category names as search terms for browse, comparison and gift
missions, so this also produced false zero-result searches in model sessions.

Smart search awarded category/tag matches 0.6 points but required at least 1.0
to include a result. Its word-coverage gate now counts matched words separately
from ranking weights. Product names still rank above category/tag matches, and
at least half the query words must match. Exact-name and disabled search modes
keep their behavior.

Before repair: **47 failed, 24 passed in 0.99 seconds**. Coverage includes every
category in all 42 built-in templates, tags, case/whitespace, prefixes, Korean
and Japanese terms, multiword coverage, ranking, empty/unknown queries and
model-session search logs. After repair, these regressions and the existing
online engine/API checks passed: **103 tests in 18.86 seconds**. Full-source
Pyright: **0 errors, 0 warnings**. Model-session checks use scripted choices;
no paid or native model inference was used.
