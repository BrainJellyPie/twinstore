# Keep late analysis reports from recreating deleted projects

POS fidelity and movement analysis read completed run inputs, computed their reports and wrote
output files without coordinating with project deletion. A deletion during computation or before
the write could therefore be followed by recreated run/project directories.

Both report commits now acquire the project tree lock, recheck the completed run and then save.
Computation stays outside the lock. Movement scoring returns the report to the application run
service, which performs its protected write using the same lifecycle boundary as POS fidelity.

Focused offline evidence:

- Calculation paused, write paused, deletion first and busy-project preservation, for both report
  types: **8 failed in 3.59s** before repair.
- Related lifecycle, API responsiveness and fidelity checks initially yielded **395 passed** and
  **3 failed in 4.86s**: the old movement API fixture created a run with no project metadata.
  The fixture now creates its owning project, matching valid application state.
- Final affected lifecycle/movement/API checks: **19 passed in 4.02s**.
- Changed simulation and movement modules strict Pyright: **0 errors**.

No full suite, real customer data, model calls, frontend or release changes.
