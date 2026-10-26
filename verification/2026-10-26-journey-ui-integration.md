# Integrate page and control naming; contain journey-picture focus

Integrated `claude/online-shopping-features-ji7y0f` through
`3858f29847878625e40bde13ca32f9f1d6533604` into main
`20590ba505a2e86e5f5b6cd99a73eea35b0c9514`. The incoming changes name pages,
provider controls and capture-row actions, add names to studio/area fields,
improve English journey steps, and restore focus after leaving a shopper's
journey. Earlier backend work carried by the branch's merge commit was
already on main. The final integration has no backend changes.

The incoming picture overlay moved focus to Close and declared itself modal,
but did not contain focus. Forward/backward Tab were not prevented at its
only control, and a background action could receive focus. Three added
regressions failed on that implementation; its original open/close test
passed. Use the existing shared Radix dialog for the enlarged picture, with
its portal, keyboard containment, background isolation and return-focus
handling. Keep the caption, image, explicit modal role and localized Close
control. Image clicks keep the picture open; Escape and Close restore focus
to its opener.

Validation:

- 76 frontend tests in 12 relevant files passed in 12.15 seconds: picture
  focus and dismissal, shopper navigation, shared return focus, provider
  settings, capture currency/actions, page titles, shortcut sheet, area,
  shelf prices, survey/conjoint and home navigation.
- TypeScript build passed; Vite production build passed in 21.41 seconds.
  Existing chunk-size/plugin-timing notices remain.
- ESLint on all 19 changed TypeScript files: zero errors, three pre-existing
  route Fast Refresh warnings. Running ESLint on the same route at the parent
  commit reproduced those three warnings.
- Diff checks pass. The released changelog from v0.8.2 onward is byte-for-byte
  unchanged. Unchanged backend checks were not repeated.

Logs are `/workspace/scratch/journey-modal-before.log` and
`journey-ui-integration-{tests,eslint,tsc,build}.log`.
