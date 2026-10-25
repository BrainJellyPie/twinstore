"""A marketing A/B variant, carried over to an online store, and an online variant's prices back to the store.

The marketing studio tests changes on the physical store's layout: a new price, a discount, a category's prices, a
new package. The same changes reach an online store through its products' SKUs (a store put online from a layout
keeps them), so one idea is tested in both channels on the same kind of shoppers. A move to another shelf height
becomes the product's place in the list: eye level and above leads its category (the "featured" order is the list's),
lower shelves end it. A shelf sign has no web counterpart and is reported as skipped rather than guessed; the other
way, an online variant's prices reach the layout's products with the same SKU, and its design, pictures and ads stay
online.
"""

from collections.abc import Mapping

from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.online import OnlineProduct, OnlineSite
from store_emulator.engine.marketing.variants import charm_price
from store_emulator.engine.prompting import display_price


def apply_store_changes(site: OnlineSite, changes: list[VariantChange], *, minor_per_major: int,
                        package_uris: Mapping[str, str] | None = None) -> tuple[list[OnlineProduct], list[str], list[str]]:
    """The store's products with the changes, what was applied (in words) and what was skipped and why. Prices are
    in the store's currency."""
    products = [p.model_copy() for p in site.products]
    by_sku = {p.sku: p for p in products if p.sku}

    def money(amount: int) -> str:
        return display_price(amount, site.currency)

    applied: list[str] = []
    skipped: list[str] = []
    first: list[OnlineProduct] = []
    last: list[OnlineProduct] = []
    for change in changes:
        if change.kind == "category_price":
            key = change.category.strip().casefold()
            ids = {c.id for c in site.categories if key and (key in c.name.casefold() or key == c.id.casefold())}
            inside = [p for p in products if p.category_id in ids]
            if change.percent is None or not inside:
                skipped.append(f"{change.category or 'category'}: no products in a matching category of this store")
                continue
            for p in inside:
                old = p.price
                new = max(0, round(old * (1 + change.percent / 100)))
                if change.charm:
                    charmed = charm_price(new, minor_per_major)
                    new = charm_price(new, minor_per_major, up=True) if change.percent > 0 and charmed <= old else charmed
                p.price = new
                p.list_price = p.list_price if p.list_price > new else 0  # a new everyday price
            applied.append(f"{change.category}: every price {change.percent:+g} %"
                           f"{' and ending in .99' if change.charm else ''} ({len(inside)} products)")
            continue
        if change.kind == "promo":
            skipped.append(f"{change.promo or 'sign'}: a shelf sign has no web counterpart; try a discount or a coupon")
            continue
        product = by_sku.get(change.sku)
        if product is None:
            skipped.append(f"{change.sku or 'product'}: no product with this SKU in this store")
            continue
        if change.kind == "move":
            if change.level is None:
                skipped.append(f"{product.name}: a move along the same shelf has no web counterpart")
                continue
            # Level 3 is eye level on a four-level rack; level 4 is above it, still in sight.
            up = change.level >= 3
            first[:] = [p for p in first if p is not product]
            last[:] = [p for p in last if p is not product]
            (first if up else last).append(product)
            applied.append(f"{product.name}: {'first' if up else 'last'} in its category, as on "
                           f"{'an eye-level' if up else 'a lower'} shelf"
                           f"{'' if site.options.default_sort == 'featured' else ' (shown with the Featured sort)'}")
            continue
        old = product.price
        if change.kind == "price":
            if change.price is None:
                skipped.append(f"{product.name}: no price given")
                continue
            product.price = change.price
            # Shoppers who remember the old price see it as the was-price; otherwise it is the new everyday price.
            reference = max(product.list_price, old) if change.keep_reference else product.list_price
            product.list_price = reference if reference > change.price else 0
            applied.append(f"{product.name}: price {money(old)} → {money(change.price)}")
        elif change.kind == "discount":
            if change.percent is None or change.percent >= 0:
                skipped.append(f"{product.name}: a discount needs a negative percentage")
                continue
            regular = product.list_price or old
            product.price = max(0, round(regular * (1 + change.percent / 100)))
            product.list_price = regular
            applied.append(f"{product.name}: {change.percent:g} % off, was {money(regular)}")
        else:  # package
            uri = (package_uris or {}).get(change.asset_id)
            if uri is None:
                skipped.append(f"{product.name}: product image {change.asset_id or '(none)'} not found")
                continue
            product.image_url = uri
            applied.append(f"{product.name}: new package picture")
    if first or last:
        moved = {id(p) for p in first + last}
        products = first + [p for p in products if id(p) not in moved] + last
    return products, applied, skipped


def price_changes(control: OnlineSite, variant: OnlineSite) -> tuple[list[VariantChange], list[str]]:
    """The variant's prices that differ from the control's, as layout changes matched by SKU, and what stays online.
    A product without a SKU is matched by its id only in a copy of the control: other stores reuse ids."""
    by_sku = {p.sku: p for p in control.products if p.sku}
    by_id = {p.id: p for p in control.products} if variant.variant_of == control.id else {}
    changes: list[VariantChange] = []
    skipped: list[str] = []
    for p in variant.products:
        old = by_sku.get(p.sku) if p.sku else by_id.get(p.id)
        if old is None:
            continue
        if old.price != p.price:
            if p.sku:
                changes.append(VariantChange(kind="price", sku=p.sku, price=p.price))
            else:
                skipped.append(f"{p.name}: no SKU, so no shelf product to match")
        if old.image_url != p.image_url:
            skipped.append(f"{p.name}: the new picture stays online")
    if variant.options != control.options:
        skipped.append("the page design, delivery and checkout options have no shelf counterpart")
    if variant.ads != control.ads:
        skipped.append("ads stay online")
    return changes, skipped
