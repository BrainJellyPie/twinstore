# Integrate studio navigation and preserve manually typed store types

Integrated `claude/online-shopping-features-ji7y0f` through
`1c35009c4d9cea432b7c393295010ae1c30f2ef5` onto main `af0834d8`:

- `4922033d`: Field pilots links to Staff scripts, with six-language copy.
- `595c6564`: Protocol editors receive focus after replacing their trigger.
- `f25569ef`: Narrow-screen studio content uses the page scroll area; wide
  screens retain independent panes.
- `1c35009c`: Initial/template store category ids display translated labels.

Review found an input regression in the category-label change. Typing the
custom name `cafeteria` passes through `cafe`, which was immediately replaced
by the translated category. Subsequent characters would append to that label.
Seven new regressions failed before the fix, while the original test passed.

The field now tracks whether its current controlled value was manually
entered. Typed text remains literal across locale changes, including text
equal to a category id. An external change from a later template selection
resets that editing state so preset ids display their translated labels.
The saved value and callback contract stay unchanged.

Validation passed **108 tests in seven files**, 16.56 seconds, covering the
six-language typing regression, template/locale changes, protocol focus,
field collection, routed draft lifetime and existing studio/store translations.
ESLint passed all nine changed TypeScript files with no warnings; TypeScript
passed. The production build passed in 23.09 seconds with existing chunk-size
and plugin-timing notices. Responsive CSS was reviewed and built; no real
mobile-browser rendering measurement is claimed by these jsdom tests.

Backend code is unchanged from the preceding green commit, which passed
1,430 focused tests, strict Pyright and app import. Those checks were not
repeated for this frontend-only integration. The explicit-container price
and catalog protections remain intact. The changelog conflict retains both
branches' Unreleased notes; the v0.8.2 released tail is byte-identical to its
tag. No release tag or asset was changed.
