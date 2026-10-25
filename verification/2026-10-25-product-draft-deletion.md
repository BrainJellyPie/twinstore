# Keep late product draft saves from recreating deleted projects

Product editing and automatic/manual starter filling checked project existence,
then created the layout directory and acquired a lock inside it before the final
protected save. Deletion between the check and either operation left a recreated
project directory even though the save subsequently returned 404.

Use each feature's existing project-wide save lock under the external setup-lock
directory and remove the eager layout-directory creation. Final receipt and draft
writes remain inside the project/source tree transaction; existing conflict and
idempotent retry behavior is retained.

Four concurrent HTTP regressions pause at path resolution and lock acquisition
for both features. All failed before repair in 3.56 seconds. After repair, 146
focused deletion, source-race, product-edit and starter-fill API tests passed in
17.59 seconds. Full-source Pyright reported zero errors and warnings; backend boot
passed. No real model service or frontend source changed.
