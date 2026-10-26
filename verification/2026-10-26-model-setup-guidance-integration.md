# Integrate localized model guidance without hiding selection diagnostics

Integrated `claude/online-shopping-features-ji7y0f` through
`c55ca3c5545321d20ef7e2dfa233e79f40260d64` into main
`a8e51543f145e45106d0dc454676c52c149ffcfa`. The branch localizes the setup
banner and the reason for an automatic local-model recommendation, adding
optional reason metadata while keeping the original English reason for
older clients.

Integration review found that manually overriding the recommended model
retained its automatic reason code: a forced 2B model could still be described
as the automatically chosen fast 0.8B model. GPU startup fallback similarly
lost the visible failure explanation when the frontend preferred the new
CPU reason code. Clear that automatic metadata on these two exceptional
paths so the existing diagnostic reason is displayed. Two regression tests
failed before the repair and pass afterward. Model choices and startup
behavior are unchanged.

The disabled-state setup guidance also offered a start/download that the
interface correctly did not allow. Both the API warning and the localized
banner now direct the user to settings to connect a provider or learn how to
enable the local model. Two banner regressions failed before the repair,
covering downloaded and not-yet-downloaded models. The new guidance has all
six language entries; the API warning remains English.

Validation:

- 51 backend tests in five relevant recommendation, setup and lifecycle files
  passed in 6.36 seconds; no model download or real startup was required for
  these metadata/UI changes.
- 88 frontend tests in five settings, banner and translation-catalog files
  passed in 4.47 seconds.
- Strict Pyright: zero errors/warnings. Application import/boot passed.
- ESLint on all eight changed TypeScript files: zero errors/warnings.
  TypeScript and production build passed (Vite 20.91 seconds, existing
  chunk-size/plugin-timing notices).
- Diff checks passed; the released v0.8.2 changelog section is unchanged.

Logs: `/workspace/scratch/model-setup-reason-before.log`,
`model-setup-disabled-before.log` and
`model-setup-integration-{backend,frontend,pyright,boot,eslint,tsc,build}.log`.
