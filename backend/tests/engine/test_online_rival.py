"""A rival shop: who tries it after leaving without buying, and what they look for there."""

from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import tries_rival
from store_emulator.engine.online.shoppers import at_rival, landing, sample_shoppers

_MIX = {"purchase": 1.0, "compare": 1.0, "gift": 1.0, "browse": 1.0}


def test_a_shopper_looks_for_the_same_thing_in_the_rival_catalog_or_does_not_go() -> None:
    home, rival = build_site("pet_store", site_id="home"), build_site("beauty", site_id="rival")
    shoppers = sample_shoppers(home, 60, seed=3, missions={**_MIX, "deal_hunt": 1.0}, mobile_share=0.5)
    went = [(s, there) for s in shoppers if (there := at_rival(rival, s)) is not None]
    assert 0 < len(went) < len(shoppers)
    assert all(at_rival(rival, s) is not None for s in shoppers if s.mission == "deal_hunt")
    for shopper, there in went:
        assert there.arrival == "search_engine" and there.id == shopper.id and there.goal == shopper.goal
        assert there.vision == shopper.vision and there.budget == shopper.budget
        if shopper.target_product:
            assert rival.product(there.target_product) is not None
        if shopper.target_category:
            assert rival.category(there.target_category) is not None
        assert rival.product(landing(rival, there).product_id) is not None
    # The same shop as the rival: everyone fits and looks for exactly the same thing.
    twin = build_site("pet_store", site_id="twin")
    assert [at_rival(twin, s) for s in shoppers] == [s.model_copy(update={"arrival": "search_engine"}) for s in shoppers]


def test_a_product_the_rival_also_sells_stays_the_target_under_the_rival_category() -> None:
    home, rival = build_site("grocery_delivery", site_id="home"), build_site("quick_commerce", site_id="rival")
    shopper = next(s for s in sample_shoppers(home, 80, seed=2, missions={"replenish": 1.0}, mobile_share=0.0)
                   if s.target_product and rival.product(s.target_product) is not None)
    there = at_rival(rival, shopper)
    product = rival.product(shopper.target_product)
    assert there is not None and product is not None and there.target_product == product.id and there.target_category == product.category_id
    assert landing(rival, there).product_id == product.id
    theirs = {c.name: c.id for c in rival.categories}
    ours = {c.id: c.name for c in home.categories}
    named = next(s for s in sample_shoppers(home, 80, seed=2, missions={"compare": 1.0}, mobile_share=0.0)
                 if ours[s.target_category] in theirs)
    renamed = at_rival(rival, named)
    assert renamed is not None and renamed.target_category == theirs[ours[named.target_category]]


def test_who_tries_the_rival_is_one_draw_per_shopper_led_by_their_mission() -> None:
    site = build_site("pet_store", site_id="home")
    buyers = sample_shoppers(site, 400, seed=5, missions={"purchase": 1.0}, mobile_share=0.5)
    browsers = sample_shoppers(site, 400, seed=5, missions={"browse": 1.0}, mobile_share=0.5)
    assert [tries_rival(s, 9) for s in buyers] == [tries_rival(s, 9) for s in buyers]
    share = sum(tries_rival(s, 9) for s in buyers) / len(buyers)
    assert 0.4 < share < 0.6 and sum(tries_rival(s, 9) for s in browsers) / len(browsers) < 0.2
    assert [tries_rival(s, 9) for s in buyers] != [tries_rival(s, 10) for s in buyers]
