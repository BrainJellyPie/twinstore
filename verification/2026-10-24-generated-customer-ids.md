# Assign generated customer IDs in the harness

The persona prompt asked for an arbitrary ID, and `GeneratedPersona` required any
supplied ID to be a string of at most forty characters. The harness immediately
overwrote it with its own per-day/gender sequence. A local model returning numeric,
null, object, array or long IDs could therefore fail every batch and abort customer
generation even though all customer attributes were usable.

Remove ID from the generation schema and tell the model that ID, day and arrival
hour are assigned by the harness. Construct the stored Persona with the existing
deterministic ID, day and requested hour. The generated schema's existing handling
of extra fields ignores unsolicited IDs; customer attributes retain their existing
validation. The stored Persona schema and existing saved customers do not change.

Evidence (offline):

- Before: eight failures and three controls passing. Seven malformed ID cases
  aborted whole populations; the eighth check showed the unnecessary schema field.
- After: 162 focused checks passed in 3.93 seconds, covering mixed genders over
  multiple batches and weekdays, exact ID numbering, hourly visitor counts,
  missing-day protection, sample/probe budgets and generation concurrency.
- Strict Pyright on the changed production module reported zero errors;
  `git diff --check` passed. No live model calls were made.

This prevents failures caused by unused model-generated identifiers; it does not
relax validation of the customer attributes that simulations use.
