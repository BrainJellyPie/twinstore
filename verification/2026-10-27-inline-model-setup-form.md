# Keep local-model setup from submitting an enclosing form

Integrate `claude/online-shopping-features-ji7y0f` at
`a7483e7ac4a2c6d0a0a75dff15958f238ddd080e`. Its three new commits offer
model setup after failed package reads, receipt reads, comparison explanations,
layout briefs, situation/area descriptions, shopper finding and vision synergy
when no model is configured. The existing setup controls now wrap in narrow
cards. The Unreleased changelog conflict retains both branches' entries.

Inspection found that the shared notice's native download/start button lacked
`type="button"`. Inside a form, clicking it both calls model startup and submits
the form, potentially retrying an LLM job while its model is still preparing.
This also affects existing uses such as the staff-script experiment form.
Two DOM behavior tests reproduce submission once per click, both before the
model is downloaded and after it is downloaded. Both fail before the fix
(3.98 seconds). Setting the button type prevents the form submission while
preserving one model-start call. The generic shared Button component is not
changed, so intended submit buttons keep their behavior.

Ten affected suites pass 130 tests in 13.16 seconds. Three suites had undefined
model-setup query mocks in their old non-setup error cases; they now default to
the typed configured-model fixture and override it for the explicit no-model
cases. Those 19 tests are rerun after the fixture change and pass in 4.86
seconds without query warnings. Final TypeScript compilation and changed-file
ESLint are clean. The production build passes in 20.96 seconds with existing
chunk-size and plugin-timing warnings. Production source does not change after
that build. Diff checks pass. Backend tests, Pyright and server boot are
inherited from integration 452, since this integration changes no backend code.
The v0.8.2 changelog and older entries are byte-identical; no tag or release
asset changes. Logs use `/workspace/scratch/ui-model-helper-form-`.
