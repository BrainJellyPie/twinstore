# Keep neighborhood commits inside the project lifecycle

`save_town` checked only whether the project directory existed before taking a town-local lock.
Project deletion used a different lock, so a late write could recreate the deleted directory.
Synergy startup could also read the preceding neighborhood while a new one was being committed.

Take the existing project tree transaction before the town lock and its optimistic snapshot check.
The transaction rechecks project metadata after any pending deletion completes. Generation, map
downloads and image analysis still happen before this short commit boundary.

Evidence:

- Twelve new API cases failed on the previous implementation in 3.98 seconds. They cover both
  deletion orderings for save/generate/import/add/remove, a study behind a pending save, and a busy
  project lock. Imports use an offline fixture; studies do not call a model.
- All twelve passed after the fix, along with existing town conflict, synergy startup, numeric and
  structural validation checks: **64 passed** before the combined run was interrupted at **81.92s**.
  The next, preexisting rival-price test spent excessive time in catalog category matching; the
  interrupted test and later town API tests are not counted as passed. This performance issue is
  being investigated separately rather than waiting for a long verification run.
- Existing conflict fixtures now include project metadata, as a real project does.
- Strict Pyright on `application/town.py`: **0 errors**.

Separate discovery before this change exercised 120 complete rule-engine combinations (seed
1042391), 917 shoppers and 3,691 purchase lines in 6.728s. Free/tiny/high prices, bounded/unlimited
budgets, currencies, situations, promotions, stockouts, queues and routing options produced no
spend/quantity/checkout/offer inconsistencies. This was exploration, not a blanket correctness claim.

No full suite, frontend changes, paid model calls or release asset changes. This change protects the
neighborhood commit itself; it does not add a transaction around subsequent rival-comparison metadata.
