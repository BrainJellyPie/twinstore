# Preserve the displayed online preview after a failed transition

Changing number shuffling updated the preview's request seed before rendering
succeeded. If that request failed, the old numbered screenshot remained but its
next click used the new numbering scheme. A failed device switch similarly
changed the selected device and erased the current visit's click history.

Number seed, device and new-visit history now change only after a successful
response. Device, shuffle and restart controls are disabled during a request;
search submission also guards against a pending transition.

Before repair, four new regressions failed and three existing controls passed.
Coverage includes failed transitions in both shuffle directions, failed device
switching with an existing visit, and a deferred initial response followed by
attempted competing transitions. After repair, **23 focused frontend tests
passed in 3.84 seconds**, including the online designer controls. TypeScript and
changed-file ESLint passed without diagnostics. The production build passed in
17.67 seconds with existing bundle-size/plugin timing warnings. Backend checks
were not repeated for this frontend-only change.
