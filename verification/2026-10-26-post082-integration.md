# Changes prepared after the v0.8.2 cutoff

The v0.8.2 candidate remains `2a0959fa`. This separate integration combines
three actual-CPU-model fixes with the interface branch through `9960b3c6`:

- Reference tags (`WAS`, `MSRP`, `RRP`) do not become current selling prices.
- Explicit printed zero prices survive capture and replacement of paid offers.
- Multipack quantities constrain package-to-catalog links for multiplication
  and recognized count wording.

The corresponding before/after model observations and limitations are in
`2026-10-26-capture-reference-price-cpu.md`,
`2026-10-26-capture-free-price-cpu.md` and
`2026-10-26-package-count-cpu.md`. The fresh 198-rack automatic-stocking
observation is recorded in `2026-10-26-hypermarket-native-fresh-cpu.md`.

The later interface work adds translated file fields, model-setup recovery
links, clearer rack/run labels, one-based coordinates in optimizer notes,
visible tab/chart focus and layout fixes for operating costs and image-less
products. These changes are under **Unreleased**. The entire v0.8.2 and
earlier changelog text is preserved exactly from `2a0959fa`.

Focused validation, without repeating the release's full backend suite:

- Capture price/currency/boundary checks: **1,002 passed**, 3.42 s.
- All package-reader checks after both count guards: **152 passed**, 4.29 s.
- Integrated optimizer/validation checks: **75 passed**, 24.39 s.
- Affected frontend flows: **118 passed in eight files**, 14.59 s.
- Strict backend Pyright: zero errors/warnings; app import passed.
- ESLint for 20 changed frontend files and TypeScript checking passed.
- Production frontend build passed in 20.39 s with existing chunk-size and
  plugin-time warnings. Diff/probe compilation checks passed.

The capture/package implementations did not conflict with the later branch;
the new optimizer/validation checks cover its backend changes. The previous
39/14 LiteLLM cleanup warnings in the focused capture/package runs remain
documented. This integration is held outside v0.8.2 until release publication
has been verified.
