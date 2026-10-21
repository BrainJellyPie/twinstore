# Shelf Lab

Controlled experiments on photographed shelves. Shelf Lab works on a **shelf capture** (a photo the
capture pipeline has turned into a planogram) and adds three instruments:

| Instrument | What it does | Ground truth |
| :--- | :--- | :--- |
| **Counterfactual edits** | Change one thing on the real photo: swap two products, empty a run (stock-out), put a new package on the shelf, change a price tag, hang a promotion sign, extend a product over its neighbour | The boxes of rewritten pixels (pixels outside them are untouched, tested) and the planogram the edited photo shows |
| **Sim2real** | The same personas, cues and per-call seeds glance at the photo and at the simulator's render of the same planogram (and at the untouched photo, a set-of-mark ablation) | Paired answers per persona: same-pick rate with a Wilson interval, interest correlation, shelf-level share |
| **Compliance audit** | Field photo against a layout's reference face: missing, unexpected, misplaced, facings, tag price, empty stretches; compliance score | Paired rule-based simulations price the whole deviation and each stock-out per day, with intervals |

In the app: **Capture → Shelf Lab** tab. Click products on the photo to choose them, queue edits into a
recipe, render the counterfactual; the photo becomes a before/after slider with the changed pixels
available as a mask.

## API

```
POST   /api/projects/{pid}/lab/packages                    upload a package image (PNG with alpha, or a photo on a plain background)
POST   /api/projects/{pid}/captures/{cid}/edits            {"edits": [PhotoEdit, …]} → EditedShelf
GET    /api/projects/{pid}/captures/{cid}/edits/{eid}/image | /mask
POST   /api/projects/{pid}/captures/{cid}/sim2real         {"personas": 24, "conditions": ["render","photo","photo_raw"], "edit_id": ""}
POST   /api/projects/{pid}/captures/{cid}/audit            {"setup_id": "…", "rack_id": "…", "panel": 300}
GET    /api/projects/{pid}/captures/{cid}/lab/jobs/{jid}   status + report
```

## Benchmark and lever experiments (command line)

```bash
cd backend
# rendered shelves from every store template, three photo degradations, every edit kind
uv run python -m store_emulator.lab_cli bench --out bench/ --per-template 6 --per-kind 2
# or a project's real captures
uv run python -m store_emulator.lab_cli bench --out bench_real/ --captures .data/proj_67916afd/captures
# one persona panel on each original and its counterfactual, any vision model
uv run python -m store_emulator.lab_cli levers --bench bench/ --model gemini:gemini-3.8-flash --personas 24 --out levers.jsonl
```

`bench` writes `index.jsonl` plus, per shelf, `original.png`, `planogram.json` and for every
counterfactual `<cf>.png`, `<cf>_mask.png`, `<cf>.json` (the edit, its changed boxes and the edited
planogram). `levers` prints, per edit kind, the mean change in the share of shoppers picking the edited
product with a bootstrap interval, and how many shoppers changed their pick at all.

Code: `backend/src/store_emulator/engine/shelf_lab/` (edits, sim2real, audit, bench, levers),
`application/shelf_lab.py`, `server/routes/shelf_lab.py`, `frontend/src/features/capture/ShelfLab.tsx`.
