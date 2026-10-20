"""Town / neighborhood generation and the multi-store demand model.

Typical use::

    town = generate_town(TownSpec(archetype=TownArchetype.RESIDENTIAL, seed=7))
    demand = estimate_demand(town, day_type="weekday")
    visitors, arrivals = plan_arrivals(pool, demand, town, seed=7, scale=0.2)
"""

from store_emulator.engine.town.arrivals import (
    counterfactual_arrival,
    plan_arrivals,
    town_context_text,
)
from store_emulator.engine.town.demand import (
    CategoryPrior,
    DemandParams,
    day_type_for,
    estimate_demand,
    purpose_label,
    synergy_analysis,
)
from store_emulator.engine.town.generator import (
    DEFAULT_OPEN_HOURS,
    auto_competitor_count,
    generate_town,
    place_venue,
    remove_venue,
)
from store_emulator.engine.town.osm import fetch_overpass, geocode, town_from_overpass

__all__ = [
    "DEFAULT_OPEN_HOURS",
    "CategoryPrior",
    "DemandParams",
    "auto_competitor_count",
    "counterfactual_arrival",
    "day_type_for",
    "estimate_demand",
    "fetch_overpass",
    "generate_town",
    "geocode",
    "place_venue",
    "plan_arrivals",
    "purpose_label",
    "remove_venue",
    "synergy_analysis",
    "town_context_text",
    "town_from_overpass",
]
