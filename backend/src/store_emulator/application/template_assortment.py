"""Stock an unsaved generated floor from the catalog before creating any project files."""
import asyncio
from collections import defaultdict

from store_emulator.application.errors import AppError, model_failure
from store_emulator.application.providers import assistive_client
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.layout_options import TemplateLayoutRequest
from store_emulator.domain.rack import RackType
from store_emulator.domain.starter_fill import RackFill, StarterRack
from store_emulator.domain.store import Store
from store_emulator.engine.layout_gen.catalog import CATALOG, category_label
from store_emulator.engine.starter_fill import fill_empty_racks, rack_choices
from store_emulator.engine.starter_selection import select_starter_products


def select_initial_assortment(config: SimulationConfig, store: Store, layout: TemplateLayoutRequest,
                              description: str) -> tuple[Store, list[RackFill]]:
    empty = store.model_copy(deep=True)
    for rack in empty.racks:
        if rack.type in {RackType.SHELF, RackType.FRIDGE}:
            rack.slots = []
    by_id = {rack.id: rack for rack in empty.racks}
    groups: dict[tuple[str, str, str], list[StarterRack]] = defaultdict(list[StarterRack])
    try:
        for choice in rack_choices(empty):
            if not choice.reason and choice.available_slots:
                rack = by_id[choice.id]
                groups[(rack.rack_desc, choice.type, rack.design_variant)].append(choice)
        grouped: list[StarterRack] = []
        members: dict[str, list[str]] = {}
        for index, choices in enumerate(groups.values()):
            key = f"section_{index}"
            members[key] = [choice.id for choice in choices]
            grouped.append(choices[0].model_copy(update={"id": key,
                "name": f"{choices[0].name} ({len(choices)} racks)",
                "available_slots": sum(c.available_slots for c in choices)}))
        if not grouped:
            raise ValueError("No accessible shelves are available for automatic products. Use format defaults or add shelves.")
        limits = {key: layout.category_product_limits.get(key, layout.products_per_category or 16) for key in CATALOG}
        llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 5000})
        llm = assistive_client("", llm_config)
        chosen = asyncio.run(select_starter_products(llm, empty, grouped,
            f"Store description: {description[:2000]}\nAssortment and design requirements: {layout.requirements}",
            allowed_categories=set(CATALOG) - set(layout.excluded_categories), product_limits=limits,
            category_limit=len(grouped)))
        assignments = [RackFill(rack_id=rid, category=row.category, skus=row.skus) for row in chosen for rid in members[row.rack_id]]
        stocked, _ = fill_empty_racks(empty, assignments, 2)
        stocked_racks = {rack.id: rack for rack in stocked.racks}
        for row in assignments:
            stocked_racks[row.rack_id].rack_desc = row.category
            stocked_racks[row.rack_id].rack_name = category_label(row.category, store.currency or "USD")
        return stocked, assignments
    except Exception as exc:
        raise AppError(model_failure(exc, "Automatic starter products could not be selected")
                       + " Return to Store details and turn off automatic products to use format defaults.", 502) from exc
