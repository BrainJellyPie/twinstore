# Integrate in-page focus and cover optional report sections

Merge feature branch `b56195e0eb4a1fc4b38de9766f4065eca6217820` onto main
`1f486bd8`. Incoming work includes `5e8cb793` (scroll only the layout strip),
`c3675b19` (move focus with in-page jumps) and `b56195e0` (language-picker
outline in forced colors). Layout auto-scrolling now adjusts the strip's
scroll position without calling `scrollIntoView` on its selected tab.
The home-store jump, dashboard results teaser and online report navigation
focus their destination after scrolling.

Review found three missed targets: optional advertising, competitor and
survey results remained ordinary nonfocusable divs. Their links scrolled,
but `.focus()` did nothing, leaving the next keyboard step at the navigation
bar. Three populated-report regressions fail on the incoming implementation
(three failed, nine passed). The targets now use `tabIndex=-1`, matching the
other report sections without adding stops to ordinary Tab navigation.
All three regressions pass after the repair.

Validation: 132 tests pass across seven relevant frontend suites in 13.65
seconds. These cover the optional section targets, root navigation, home
gallery, layout tabs, dashboard results and localization. TypeScript passes;
lint on the nine changed TypeScript files has zero errors and the same two
existing route fast-refresh warnings previously recorded for the home route.
The production build passes in 20.64 seconds with the existing chunk-size
and Babel timing notices.
The three failed regressions were reproduced with valid typed advertising
data; an initial scratch fixture using a nonexistent placement code was
corrected before collecting that baseline.

The focus/scroll assertions run in jsdom. The forced-colors outline was
reviewed statically and compiled; no new Windows/browser matrix is claimed.
Backend code is unchanged from the preceding A/B schema fix, whose 447
focused tests, strict Pyright and boot check remain the backend evidence.
Only the changelog conflicted; both Unreleased change sets are retained and
the released v0.8.2 changelog tail is unchanged. No release tag was moved.

Logs: `/workspace/scratch/page-jump-optional-before.log` and
`page-jump-focus-{tests,tsc,eslint,build}.log`.
