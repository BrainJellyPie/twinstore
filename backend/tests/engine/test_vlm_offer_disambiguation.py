"""A numbered shelf offer must survive ambiguous names and ensemble aggregation."""

import asyncio
import random

import pytest

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, TokenUsage, Weekday
from store_emulator.engine.llm_router import EnsembleLLMClient
from store_emulator.engine.perception import render_face
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import ShelfGlance, combine_votes, resolve


def offers(same_sku=True, names=("Tea", "Tea")):
    return Rack(id="offers", type="shelf", position=(3, 1), shape=[[1, 1]], slots=[
        Slot(block=block, face=Face.N, level=3, items=[SlotItem(
            sku="tea" if same_sku else f"tea-{block}", name=names[block], price=100 if block == 0 else 700)])
        for block in range(2)])


@pytest.mark.parametrize("same_sku", [False, True])
@pytest.mark.parametrize("shuffle_seed", [None, 3, 7])
def test_badge_disambiguates_identically_named_offers(same_sku, shuffle_seed):
    view = render_face(offers(same_sku), Face.N, width=256,
                       rng=random.Random(shuffle_seed) if shuffle_seed is not None else None)
    target = next(item for item in view.items if item.slot.block == 1)
    hit, how = resolve(view, ShelfGlance(product="Tea", number=target.mark, interest=10))
    assert hit == target and how == "number"


@pytest.mark.parametrize("number", [0, 999])
def test_ambiguous_names_do_not_guess_an_unidentified_sku(number):
    view = render_face(offers(False), Face.N, width=256)
    assert resolve(view, ShelfGlance(product="Tea", number=number)) == (None, "invalid")


def test_repeated_placements_of_one_sku_still_support_name_only_answers():
    view = render_face(offers(), Face.N, width=256)
    hit, how = resolve(view, ShelfGlance(product="Tea"))
    assert hit is not None and hit.item.sku == "tea" and how == "name"


def test_exact_printed_name_beats_a_different_product_with_the_same_words():
    view = render_face(offers(False, ("Potato chips crispy", "Crispy potato chips")), Face.N, width=256)
    target = next(item for item in view.items if item.slot.block == 1)
    other = next(item for item in view.items if item.slot.block == 0)
    hit, how = resolve(view, ShelfGlance(product="Crispy potato chips", number=other.mark))
    assert hit == target and how == "name"


@pytest.mark.parametrize("name", ["X", "茶", "1", "C++"])
def test_exact_short_or_punctuated_names_do_not_need_a_badge(name):
    view = render_face(offers(False, ("Other", name)), Face.N, width=256)
    target = next(item for item in view.items if item.slot.block == 1)
    assert resolve(view, ShelfGlance(product=name)) == (target, "name")


@pytest.mark.parametrize("names,said", [(("Green tea", "Black tea"), "tea"),
    (("a" * 60 + " small", "a" * 60 + " large"), "a" * 60)])
def test_ambiguous_fuzzy_or_truncated_names_use_the_badge(names, said):
    view = render_face(offers(False, names), Face.N, width=256)
    target = next(item for item in view.items if item.slot.block == 1)
    assert resolve(view, ShelfGlance(product=said, number=target.mark))[0] == target


@pytest.mark.parametrize("prefix", ["a" * 60, "a" * 59 + " "])
def test_clipped_product_name_cannot_impersonate_another_exact_name(prefix):
    view = render_face(offers(False, (prefix.strip(), prefix + "large")), Face.N, width=256)
    target = next(item for item in view.items if item.slot.block == 1)
    answer = ShelfGlance(product=target.item.name, number=target.mark, interest=10)
    assert resolve(view, answer)[0] == target


@pytest.mark.parametrize("named", [False, True])
def test_ensemble_keeps_the_voted_placement_of_a_repeated_sku(named):
    view = render_face(offers(), Face.N, width=256)
    target = next(item for item in view.items if item.slot.block == 1)
    combined, agreement = combine_votes(view, [(str(i), ShelfGlance(
        product="Tea" if named else "", number=target.mark, interest=10)) for i in range(3)])
    assert combined.number == target.mark and agreement == 1
    assert resolve(view, combined)[0] == target


class SelectedOffer:
    def __init__(self, number):
        self.number = number

    async def generate_structured_with_image_async(self, response_model, *args, **kwargs):
        return response_model.model_validate({"product": "Tea", "number": self.number, "interest": 10})

    def reset_usage(self):
        pass

    def get_usage(self):
        return TokenUsage()


@pytest.mark.parametrize("vote", [False, True])
@pytest.mark.parametrize("same_sku", [False, True])
def test_selected_offer_price_and_position_survive_complete_fake_vlm_purchase(vote, same_sku):
    rack = offers(same_sku)
    store = Store(id="s", name="Offers", type="shop", grid_size=(10, 10), racks=[rack,
        Rack(id="in", type="entrance", position=(0, 0), shape=[[1]]),
        Rack(id="out", type="exit", position=(9, 0), shape=[[1]]),
        Rack(id="till", type="counter", position=(8, 2), shape=[[1]])])
    view = render_face(rack, Face.N, width=256)
    target = next(item for item in view.items if item.slot.block == 1)
    provider = SelectedOffer(target.mark)
    if vote:
        provider = EnsembleLLMClient([(str(i), 1, SelectedOffer(target.mark)) for i in range(3)], mode="vote")
    config = SimulationConfig(budget_tolerance=None)
    config.engines.vlm_glance.plan_policy = "rule"
    config.engines.vlm_glance.glance_policy = "all"
    config.engines.vlm_glance.shuffle_marks = False
    config.engines.vlm_glance.buy_scale = 1
    config.engines.vlm_glance.weight_by_level = False
    config.engines.vlm_glance.image_width = 256
    engine = VLMGlanceEngine(provider, AStarPathFinder(), config)
    context = PerCustomerContext(store=store, persona=Persona(id="p", identity="shopper", age_group="30s",
        gender="Female", description="", intent="browse", purpose="browse"), day=Weekday.MON,
        arrival_hour=12, concurrent_visitors_in_hour=1, cue=BehaviorCue(), seed=7, behavior_patterns=[
            BehaviorPattern(id="purposeful", name="Browse", description="", grammar="",
                            browse_required_before_buy=False, max_products=2)])
    decision = asyncio.run(engine.decide_actions(context))
    result = execute_decision(store, "p", Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)
    assert len(result.purchases) == 1
    buy = result.purchases[0]
    assert (buy.product_sku, buy.price, buy.x, buy.y) == (target.item.sku, 700, 4, 0)
    assert (buy.product_block, buy.product_level) == (1, 3)
    assert result.total_spent == 700 and result.timeline[-1].action == Action.EXIT
