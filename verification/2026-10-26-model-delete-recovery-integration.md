# Integrate model recovery and keep deletion navigation usable

Integrated the interface branch through
`4aa9e351905d61936d4986fe3a79954076c9af5d` onto main `bf262ab8`.
The six new changes offer model setup after unread package uploads, refresh
model-setup queries after API-key changes/tests, improve deletion confirmation
and focus for packages/studies/online stores, and leave a deleted study before
refreshing its list so its detail is not fetched again into a 404. The merge
of older main history in `01fc5fe1` is not counted as new implementation.

Integration review reproduced two missing deletion-focus cases: the replacement
entry was inside a folded mobile list, or no entry remained after deleting
the last store. The initial regression run failed two cases and passed the
existing desktop case. Deletion now opens the list before focusing a visible
replacement, falling back to the search field or New online store. Selection
and list-visibility changes participate in the focus effect.

A further functional boundary failed when seven stores became six after
deleting the only matching search result: the threshold hid the search box
while its filter still hid the remaining stores. One new regression failed
with the other three passing. An active query now keeps its search field,
so it can be edited or cleared without reloading or adding another store.
The test confirms that clearing the retained filter reveals the remaining
stores and does not resurrect the deleted one.

Final validation passed **76 tests in 10 files in 24.85 seconds**. Coverage
includes actual query-cache removal in the deletion component harness,
mobile hiding CSS, empty lists, retained filters, study detail invalidation,
product drafts/deletion, provider/model recovery, translations and marketing
navigation. These are jsdom/component checks; the mobile case uses hiding
CSS and does not claim a real-browser viewport measurement. ESLint passed
all eight changed TypeScript files without warnings. TypeScript and the
production build passed (30.26 seconds; existing chunk-size/plugin notices).

Backend code, the new separate local price-tag reader/probe, and the prior
custom store-type input fix are unchanged. Backend checks remain those of
the green parent, with 1,390 focused tests, strict Pyright and app import;
they were not repeated for this frontend-only integration. Changelog merging
retains both branches' Unreleased notes without duplicating the container-count
entry. The released v0.8.2 changelog tail is byte-identical to the tag.
