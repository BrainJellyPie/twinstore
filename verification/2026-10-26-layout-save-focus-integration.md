# Shared layout focus after saving

Integrated `claude/online-shopping-features-ji7y0f` through `bb364577`
onto main `8c5d77bf`. The incoming change moves the saved-layout focus
handoff from the optimizer into the shared layout tabs, covering layouts
opened elsewhere and tab-strip remounts. Product bulk edits, shelf copies,
starter filling and library-photo drafts also focus their saved confirmations.

Both optimizer files conflicted because main had added protection against
delayed save responses after leaving the view. Resolution keeps that active
view/selection guard and its three regressions while adopting the incoming
shared focus behavior. Normal rule/vision saves still open the new layout;
their tests now assert selection rather than optimizer-local focus, which
is covered by the shared tab tests. No additional backend change is made.

Verification passes 167 frontend cases across seven relevant files in
13.57 seconds. TypeScript, ESLint of all nine changed TypeScript files,
production build and diff checks pass. Existing build chunk-size/Babel
timing notices remain. These are jsdom/type/build checks; no manual browser
or physical-device coverage is claimed. The unchanged backend inherits
1,355 focused cases and strict Pyright/boot from the prior application check.
No additional model inference is needed for this integration.

The Unreleased changelog preserves main's fixes. Released changelog text,
v0.8.2 tag and release assets are unchanged.
Logs: `/workspace/scratch/layout-save-focus-{tests,tsc,eslint,build}.log`.
