# Execute only the online model configuration the user selected

The online launcher reused the model picker without its caller-side validation.
An empty ensemble or an unfilled single-model selection therefore sent null and
ran the server's default model. Invalid weights and text-only models selected
before switching to vision shoppers could also be submitted. The vision picker
offered shelf-voting mode even though the online policy always used one ensemble
member per shopper.

The launcher now validates catalog availability, explicit model identity,
vision capability, nonempty ensembles and finite positive weights before
starting. Loading/error messages use all six supported languages. Rules and an
explicit server-default selection remain available without a model catalog.
Online pickers offer only mixture mode; the API rejects unsupported vote mode
before client creation or job registration. Physical-store vision voting keeps
its existing option and behavior.

Before repair: **9 UI regressions failed, 2 controls passed**; **2 API vote
regressions failed, 2 mixture controls passed**. After repair, **42 distinct UI
tests** and **10 backend API tests** passed. Coverage includes delayed catalogs,
removed models, empty/zero/negative weights, text-to-vision policy changes,
correction and submission of valid choices, and physical-store vote selection.
Two UI checks were adjusted to await TanStack Query's observer notifications;
the final 11 online tests passed in 3.48 seconds. The API checks took 6.48 seconds.
Full-source Pyright, backend boot, TypeScript and changed-file ESLint passed.
Production build passed in 17.88 seconds with existing bundle/plugin warnings.
All model requests and job submissions were intercepted; no live inference ran.
