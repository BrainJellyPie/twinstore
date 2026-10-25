# Copy study names without splitting Unicode characters

Experiment and survey builders truncated copied names with JavaScript's UTF-16
`slice`, unlike the conjoint builder's existing code-point handling. A valid
80-character name consisting of 79 ASCII characters and one emoji became a
lone high surrogate on duplication. Pydantic rejects that value as invalid
Unicode before the study can be created.

Both builders now use the same code-point truncation as the conjoint builder.
A Node reproduction confirmed that the old copied name was not well formed,
while the new value is well formed and preserves the complete 80-character
input. The backend request model accepts the complete value and rejects the
split value. This is a small copy-flow correction, not a model inference change.

The existing experiment/survey draft and price round-trip suites pass: 69 tests
in 7.73 seconds. Full frontend TypeScript checking and ESLint for both changed
components finish successfully with no diagnostics. No new tests that duplicate
the slicing implementation were added, and no backend source or model behavior
changed.

The environment's `pnpm exec` first attempted dependency installation and stopped
on ignored dependency build scripts. Its automatic workspace-file edit was
restored. Checks then ran successfully using the installed local executables;
no build-script approval or repository dependency-policy change was required.
