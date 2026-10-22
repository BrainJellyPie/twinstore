"""Exact SKU assignment; names, prices, order and geometry remain unchanged."""
from store_emulator.domain.library_photos import PhotoChange, PhotoPreview, PhotoProduct
from store_emulator.domain.store import Store


def products(store: Store) -> list[PhotoProduct]:
    rows: dict[str, PhotoProduct] = {}
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                row = rows.setdefault(item.sku, PhotoProduct(sku=item.sku, names=[], image_urls=[], placements=0))
                if item.name not in row.names:
                    row.names.append(item.name)
                if item.image_url and item.image_url not in row.image_urls:
                    row.image_urls.append(item.image_url)
                row.placements += 1
    return list(rows.values())


def assign(store: Store, photos: dict[str, tuple[str, str]], replace: bool) -> tuple[Store, PhotoPreview]:
    rows = {p.sku: p for p in products(store)}
    changes: list[PhotoChange] = []
    for sku, (name, url) in photos.items():
        row = rows.get(sku)
        if row is None:
            raise ValueError(f"Product no longer exists: {sku}")
        if row.image_urls and not replace:
            raise ValueError(f"{sku} already has an image. Allow replacement or remove this choice")
        changes.append(PhotoChange(**row.model_dump(), asset_name=name, image_url=url))
    result = store.model_copy(deep=True)
    for rack in result.racks:
        for slot in rack.slots:
            for item in slot.items:
                if item.sku in photos:
                    item.image_url = photos[item.sku][1]
    return result, PhotoPreview(changes=changes, changed_placements=sum(c.placements for c in changes))
