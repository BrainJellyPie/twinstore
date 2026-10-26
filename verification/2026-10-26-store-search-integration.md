# Store search and import feedback after v0.8.2

Integrate five interface commits through `2f4efdf1`: home/online search
keyboard navigation, template-search focus, slow map-import feedback in six
languages, and deletion of a layout that has no floor yet.

The new online-search keyboard shortcut selected the first displayed store
button. A matching variant keeps its original store visible for context, so
searching for the variant focused the non-matching parent. An explicitly
collapsed group also stayed collapsed while filtering, hiding the match.
New cases exercise both an untouched group and a previously collapsed group,
including a copy of a copy. Both initially failed (four existing cases passed).

Only buttons matching the query now participate in Enter/ArrowDown selection.
Variant matches remain visible during filtering. Collapse controls return
when the query is cleared, retaining the existing saved expansion choices.
The parent remains visible and clickable for context.

All **73 tests in seven related frontend files** passed in 9.62 s, including
online identity, grouped search, home search, map imports, layout deletion,
model-wait feedback and empty-floor setup. TypeScript checking, ESLint on all
11 changed TypeScript files (zero errors/warnings), and the production build
passed (20.95 s; existing chunk/plugin warnings). Diff checking passed.

Backend code is unchanged from `ae2ec735`; previously verified backend tests
were not repeated for this UI-only integration. Released changelog text from
v0.8.2 onward is unchanged. These changes belong to Unreleased.
