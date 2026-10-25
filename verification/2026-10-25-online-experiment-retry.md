# Resume quick experiments after confirmed partial success

A quick comparison copied each selected experiment before starting its run. If a
later copy failed, or the local model was unavailable at run start, retrying
created the already confirmed variants again. Two successful copies followed by
a start failure caused four copies after one retry.

Successful copies now become selected stores immediately and their experiments
are removed from the pending picks. They remain visible even before the store
list refreshes, and merge into that list without duplicate rows. The current
request still uses its original store IDs plus its confirmed copies. The next
attempt creates only the remaining experiments. Store and experiment choices
are disabled while the request is pending. Users can deselect a retained copy
after a failure.

Four reproductions failed before repair. Five final regression tests cover a
failure before the first copy, between copies, and at run start; immediate
visibility, later list refresh, deselection and pending controls. Together with
model-selection and experiment definition checks, 19 distinct tests passed.
The final five-test rerun passed in 3.42 seconds after correcting a nullable API
fixture type. TypeScript, changed-file ESLint (zero warnings) and the production
build (17.62 seconds) passed. Backend code was unchanged.

This resumes confirmed successful responses within the current launcher. It
does not infer success from a network failure whose server-side outcome is
unknown, nor add server-side idempotency for an ambiguous request.
