"""An ad lift needs a comparable store, not just matching local product IDs."""

import pytest

from store_emulator.domain.online import OrderLine, SessionResult
from store_emulator.engine.online.ads import ad_lifts, ad_rows
from store_emulator.engine.online.catalog import build_site
from tests.engine.test_online_ads import _ad, _site


@pytest.mark.parametrize("change", ["catalog", "price", "stock", "tagline", "category", "shipping", "coupon", "search", "currency", "shared_ad"])
def test_other_store_changes_cannot_be_attributed_to_the_new_ad(change):
    existing = _ad("home_tile", product="p020")
    control = _site(existing)
    variant = control.model_copy(update={"ads": [existing, _ad("hero_banner")]})
    if change == "catalog":
        other = build_site("beauty", site_id="other")
        variant = variant.model_copy(update={"products": other.products, "categories": other.categories})
    elif change in {"price", "stock"}:
        product = variant.products[0]
        replacement = product.model_copy(update={change: product.price + 1 if change == "price" else 0})
        variant = variant.model_copy(update={"products": [replacement, *variant.products[1:]]})
    elif change == "tagline":
        variant = variant.model_copy(update={"tagline": "Everything must go"})
    elif change == "category":
        variant = variant.model_copy(update={"categories": [variant.categories[0].model_copy(update={"name": "Special"}),
                                                             *variant.categories[1:]]})
    elif change == "currency":
        variant = variant.model_copy(update={"currency": "KRW"})
    elif change == "shared_ad":
        variant = variant.model_copy(update={"ads": [existing.model_copy(update={"headline": "A changed campaign"}), _ad("hero_banner")]})
    else:
        options = {"shipping": {"shipping_fee": control.options.shipping_fee + 1},
                   "coupon": {"coupon_percent": 40}, "search": {"search": "off"}}[change]
        variant = variant.model_copy(update={"options": variant.options.model_copy(update=options)})
    bought = SessionResult(shopper_id="s1", site_id=variant.id, outcome="purchased", steps=[], order_total=500,
                            order=[OrderLine(product_id="p010", name="Product", category_id="c1", quantity=1, price=500)])
    left = SessionResult(shopper_id="s1", site_id=control.id, outcome="left", steps=[])
    rows = ad_rows(variant, [bought])
    assert rows  # Observed campaign attribution remains available independently of causal comparisons.
    assert ad_lifts(control, [left], ad_rows(control, [left]), variant, [bought], rows) == []
    assert ad_lifts(variant, [bought], rows, control, [left], ad_rows(control, [left])) == []


@pytest.mark.parametrize("paused", [False, True])
def test_copied_store_metadata_and_unshown_campaigns_preserve_a_valid_control(paused):
    ad = _ad("hero_banner")
    control = _site(ad.model_copy(update={"active": False})) if paused else _site()
    variant = _site(ad).model_copy(update={"id": "variant", "name": "Campaign variant", "variant_of": control.id,
                                           "note": "Campaign only", "created_at": "later", "updated_at": "later"})
    lifts = ad_lifts(control, [], [], variant, [], ad_rows(variant, []))
    assert len(lifts) == 1 and lifts[0].ad_id == ad.id
