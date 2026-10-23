"""Visitor descriptions do not rescan the neighborhood for every copied shopper."""

import math
from types import SimpleNamespace

import pytest

from store_emulator.application import town as town_service
from store_emulator.domain.persona import Persona
from store_emulator.domain.town import Town, TownSpec, VenueCategory
from store_emulator.engine.town import generate_town, town_context_text
from store_emulator.engine.town import arrivals as arrival_engine


@pytest.mark.parametrize("days", [(1,), (1, 7)])
def test_repeated_visitors_share_building_and_competitor_lookups(monkeypatch, days):
    town = generate_town(TownSpec(size_m=400, seed=24102492))
    pool = [Persona(id=f"p{day}", day=day, identity="Visitor", age_group="20s", gender="Female",
                    description="A shopper.", intent="", purpose="snack") for day in days]
    lookups = []
    distances = []
    get_building = Town.get_building
    hypot = math.hypot

    def lookup(self, identifier):
        lookups.append(identifier)
        return get_building(self, identifier)

    def distance(*args):
        distances.append(1)
        return hypot(*args)

    with monkeypatch.context() as patch:
        patch.setattr(Town, "get_building", lookup)
        patch.setattr(arrival_engine, "math", SimpleNamespace(hypot=distance, floor=math.floor, inf=math.inf))
        people, arrivals = town_service.town_visitors(town, pool, seed=12, scale=2, scenario=None, store=None)
    origins = {a.origin_building_id for a in arrivals if not a.is_linked_trip and a.origin_building_id}
    rivals = sum(v.category == VenueCategory.CONVENIENCE and v.id != town.focal_venue_id for v in town.venues)
    assert len(people) > 10 * len(origins)
    assert len(lookups) <= len(origins)
    assert len(distances) <= len(origins) * rivals
    assert [p.description for p in people] == [f"A shopper. {town_context_text(a, town)}" for a in arrivals]
