# Bound repeated shape work in fixture face analysis

Blocked-face validation, starter-fill selection and rack access checks called
`valid_faces` separately for each block. That helper rebuilt the rotated shape
and complete block list each time, making these paths quadratic in fixture area.
The stateless face endpoint and full layout load perform the face scan directly,
so the repeated work could pause unrelated HTTP requests as well as the layout.
Starter fill also paid for repeated scans during its validation and selection.

The batch paths now reuse occupied-cell sets to reject internal faces. Starter
fill uses the already computed blocked-face set, including its internal-face
entries. Domain access helpers use their existing occupied-tile check instead
of rebuilding every block's face list. Passage and furniture roles, iteration
order, locked service faces and mutation-sensitive cache keys remain intact.

Before the change, 20 deterministic work-budget cases failed across four
rotations and five face/access operations. Fifteen geometry controls passed.
The budget counts complete shape enumerations rather than relying on a machine-
specific timeout. Afterward, 275 focused checks passed in 11.94 seconds. A final
preservation of side insertion order was checked with 156 of those tests in
0.70 seconds; these are not additional distinct tests. Strict Pyright on all
three changed modules reported zero errors.

An offline comparison captured 180 generated store layouts before the change
and replayed them afterward. Blocked-face records, starter faces/error messages,
access/service tiles and 10,800 face-acceptance queries matched exactly, including
rotations, holes, locked faces, overlaps, out-of-bounds cells and all fixture types.

Local rotated-square face-scan timings (seconds; illustrative, not a CI threshold):

| Side | Occupied blocks | Before | After |
| --- | ---: | ---: | ---: |
| 16 | 256 | 0.0090 | 0.0017 |
| 32 | 1,024 | 0.1171 | 0.0060 |
| 64 | 4,096 | 2.1275 | 0.0259 |
| 96 | 9,216 | 10.3031 | 0.0723 |

The 96-side fixture fits the existing 10,000 occupied-cell starter limit. The
measurement covers `list_blocked_faces`, not the complete HTTP request or render.
No model calls, new caches, dependencies or input limits were introduced.

```sh
uv run pytest -q tests/engine/test_large_fixture_faces.py tests/server/test_starter_fill_api.py tests/server/test_rack_geometry_validation.py tests/engine/routing/test_reachable_service_routes.py tests/engine/routing/test_checkout_targets.py tests/engine/test_product_move_displaced_access.py --tb=short
uv run pyright src/store_emulator/domain/rack.py src/store_emulator/engine/validation.py src/store_emulator/engine/starter_fill.py
```
