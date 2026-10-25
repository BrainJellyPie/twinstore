# Recover failed requests while playing a visit

A failed screenshot left the new animated player waiting on its loading message
forever. A failed playback-metadata request displayed an error without an action
to recover in place.

The player now reports screenshot failures and retries the current page with a
new image URL. The retry belongs to that page, leaving the step, speed and paused
state intact. Failed or incomplete requests cannot advance the phase timer.
Playback metadata also has a retry action. The image message is in all six UI
languages; retry uses the existing localized action label.

Both new regressions failed before repair while the two existing player tests
passed. Tests exercise repeated image failure, fresh retry URLs, pause/resume,
step preservation and metadata recovery. Nine focused player, side-by-side and
changed-shopper tests passed in 3.98 seconds. TypeScript and changed-file ESLint
passed; the production build passed in 18.48 seconds with the existing chunk
size/plugin timing warnings. This is a frontend-only change; backend checks
were not repeated.
