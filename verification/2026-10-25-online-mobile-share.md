# Preserve mobile-only and desktop-only online panels

The device sampler multiplied the requested mobile probability by an age factor.
At 100% mobile, older shoppers therefore still received desktop devices: a
500-person built-in panel with seed 8 contained 37 desktop shoppers.

Age factors now weight mobile-versus-desktop odds. This keeps the existing age
preference direction while preserving probabilities of zero and one and a
continuous transition between them. The random draw count is unchanged, so
changing the device mix does not resample missions, budgets or other traits.

Before repair: **5 regressions failed, 11 controls passed**. After repair:
**48 focused tests passed in 19.70 seconds**, including browser/session and
API controls. Tests cover every age group using project customers, both endpoint
shares, a 500-person generated panel, reproducibility, monotonic intermediate
shares, unchanged non-device traits, and age preferences in mixed panels.
Full-source Pyright reported zero errors or warnings and backend boot passed.
Mixed panels remain random samples, rather than exact device-count quotas.
No live inference was used.
