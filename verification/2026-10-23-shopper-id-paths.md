# Carry encoded customer IDs through shopper detail routes

Customer storage accepts nonblank unique IDs and the frontend already URL-encodes them. An encoded
slash is decoded before server route matching, however, so the single-segment customer routes
returned 404 for saved IDs such as `고객/001` even though their runs and safe transcript storage worked.

Use the path converter for the customer portion of the five detail endpoints. Fixed journey,
interview and suggestions suffixes still select the action; the application receives the exact
customer identifier and retains its existing lookup and hashed transcript paths.

Focused evidence:

- Ten new end-to-end offline cases all failed before the change (4.61s). Cases cover leading,
  trailing and repeated slashes, Unicode, dot segments and strings matching endpoint suffixes.
- Each case checks journey, transcript, question, suggestions and reset, plus isolation from a
  second customer with the same trailing component and containment of the transcript file.
- After: **40 passed in 10.11s**, including existing Unicode/long-ID, legacy transcript and interview
  API checks. Strict Pyright on the changed route module: **0 errors**.

No live model calls, full suite, frontend or release changes. Project/run identifier validation and
rack preview routes are unchanged.
