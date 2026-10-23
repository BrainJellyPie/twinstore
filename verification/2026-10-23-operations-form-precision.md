# Operational settings survive the form without deliberate rounding

The shared run/operations form rounded saved patience to tenths of a minute
and refill thresholds to whole percentages. An untouched 31.25-second setting
therefore replayed and saved as 30 seconds, while a 12.5% refill point became
13%. A valid server-side 10-second patience value could not be replayed because
the form required at least 30 seconds.

The form now converts units without that rounding, accepts the server's
10–7,200-second patience range and fractional refill percentages, and uses
matching native input bounds. Blank, non-finite and out-of-range inputs remain
invalid. Validation guidance was updated in English, Korean, Chinese, Japanese,
Spanish and French. This applies to both new runs and the operations lab.

Focused verification:

- Before the fix: **2 failed**, 2.94 seconds, demonstrating rejected saved
  patience and changed replay values.
- Run/shared-store and operations-lab checks: **142 passed**, 6.23 seconds.
  Coverage includes minimum/maximum values, fractional seconds and thresholds,
  native browser validity, replay/save payloads, existing run submission and
  all six locale controls. Numeric round trips are checked within normal
  floating-point precision.
- TypeScript: **passed**.
- Production Vite build: **passed**, 16.71 seconds; existing large-chunk and
  Babel-plugin timing warnings remain.
- Changed-file ESLint: **zero errors/warnings**.

Backend source is unchanged. No live models or real project data were used;
full suites were not repeated under the user's focused-validation policy.
