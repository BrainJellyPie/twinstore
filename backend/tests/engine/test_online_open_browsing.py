"""A whole-shop browsing goal must not retain an invisible category restriction."""
import pytest

from store_emulator.engine.online import shoppers as gen
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import relevance


@pytest.mark.parametrize('seed', [4, 17, 91])
def test_whole_shop_goal_clears_only_its_category_and_search_targets(monkeypatch, seed):
    site = build_site('fashion', site_id='source')
    monkeypatch.setattr(gen, '_OPEN_BROWSING', 0.0)
    focused = gen.sample_shoppers(site, 32, seed=seed, missions={'browse': 1}, mobile_share=.5)
    monkeypatch.setattr(gen, '_OPEN_BROWSING', 1.0)
    broad = gen.sample_shoppers(site, 32, seed=seed, missions={'browse': 1}, mobile_share=.5)
    for before, after in zip(focused, broad, strict=True):
        assert before.target_category and before.target_terms
        assert not after.target_category and not after.target_terms and not after.target_product
        assert after.model_copy(update={field: getattr(before, field) for field in ['goal', 'target_category', 'target_terms']}) == before
        assert {relevance(after, product, site) for product in site.products} == {.45}
        assert {relevance(before, product, site) for product in site.products} == {.45, 1.0}


def test_whole_shop_browser_can_enter_a_rival_without_the_old_arbitrary_category():
    site = build_site('fashion', site_id='source')
    shopper = gen.sample_shoppers(site, 1, seed=4, missions={'browse': 1}, mobile_share=0)[0]
    assert 'the shop' in shopper.goal
    rival = site.model_copy(deep=True, update={'id': 'rival',
        'categories': [c for c in site.categories if c.id != 'apparel'],
        'products': [p for p in site.products if p.category_id != 'apparel']})
    moved = gen.at_rival(rival, shopper, site)
    assert moved == shopper.model_copy(update={'arrival': 'search_engine'})
    assert gen.landing(rival, moved).product_id in {p.id for p in rival.products}
    focused = shopper.model_copy(update={'target_category': 'apparel', 'target_terms': ['apparel'],
                                         'goal': 'Browse apparel only'})
    assert gen.at_rival(rival, focused, site) is None


@pytest.mark.parametrize('mission', ['purchase', 'compare', 'gift', 'replenish', 'deal_hunt'])
def test_other_missions_are_independent_of_the_open_browsing_mix(monkeypatch, mission):
    site = build_site('fashion', site_id='source')
    monkeypatch.setattr(gen, '_OPEN_BROWSING', 0.0)
    before = gen.sample_shoppers(site, 20, seed=4, missions={mission: 1}, mobile_share=.5)
    monkeypatch.setattr(gen, '_OPEN_BROWSING', 1.0)
    assert gen.sample_shoppers(site, 20, seed=4, missions={mission: 1}, mobile_share=.5) == before
