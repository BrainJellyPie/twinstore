"""Pure product grouping and partial edits; preserve positions and unedited fields."""
from store_emulator.domain.store import Store
from store_emulator.domain.product_edits import ProductEdit, ProductRow, ProductChange, ProductEditsPreview


def product_rows(store: Store) -> list[ProductRow]:
    rows: dict[str, ProductRow] = {}
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                row = rows.setdefault(item.sku, ProductRow(
                    sku=item.sku, names=[], prices=[], promos=[], placements=0, racks=[],
                ))
                row.placements += 1
                row.names.append(item.name)
                row.prices.append(item.price)
                row.promos.append(item.promo)
                row.racks.append(rack.rack_name or rack.id)
    for row in rows.values():
        row.names = list(dict.fromkeys(row.names))
        row.prices = list(dict.fromkeys(row.prices))
        row.promos = list(dict.fromkeys(row.promos))
        row.racks = list(dict.fromkeys(row.racks))
    return sorted(rows.values(), key=lambda row: (row.names[0].casefold(), row.sku))


def apply_product_edits(store: Store, edits: list[ProductEdit]) -> tuple[Store, ProductEditsPreview]:
    before = {row.sku: row for row in product_rows(store)}
    patches = {edit.sku: edit for edit in edits}
    if not patches.keys() <= before.keys():
        raise ValueError("A selected SKU is no longer in this layout; reload products")
    updated = store.model_copy(deep=True)
    counts: dict[str, int] = {}
    for rack in updated.racks:
        for slot in rack.slots:
            for item in slot.items:
                patch = patches.get(item.sku)
                if patch is None:
                    continue
                changed = False
                if patch.name is not None and patch.name != item.name:
                    item.name = patch.name
                    changed = True
                if patch.price is not None and patch.price != item.price:
                    item.price = patch.price
                    changed = True
                if patch.promo is not None and patch.promo != item.promo:
                    item.promo = patch.promo
                    changed = True
                if changed:
                    counts[item.sku] = counts.get(item.sku, 0) + 1
    after = {row.sku: row for row in product_rows(updated)}
    changes = [ProductChange(before=before[edit.sku], after=after[edit.sku], changed_placements=counts[edit.sku])
               for edit in edits if edit.sku in counts]
    return updated, ProductEditsPreview(changes=changes, changed_placements=sum(counts.values()))
