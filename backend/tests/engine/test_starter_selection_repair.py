"""Incomplete model selections can be corrected without accepting partial assortments."""

import asyncio
import json
import random
from collections import Counter

import pytest

from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.starter_fill import fill_empty_racks, rack_choices
from store_emulator.engine.starter_selection import CategorySelection, select_starter_products
from tests.engine.test_starter_selection import empty_store


CATEGORY_FAULTS = ["missing_rack", "unknown_rack", "duplicate_rack", "duplicate_category", "unknown_category"]
PRODUCT_FAULTS = ["missing_products", "duplicate_product_category", "unknown_sku", "wrong_category_sku", "duplicate_sku", "over_limit"]


class RepairModel:
    def __init__(self, category_fault=None, product_fault=None, persistent=False):
        self.faults = {"category": category_fault, "product": product_fault}
        self.persistent = persistent
        self.calls = []
        self.counts = Counter()

    async def generate_structured_async(self, schema, system, user, **kwargs):
        payload = json.loads(user)
        if "choices" in schema.model_fields:
            self.counts["small"] += 1
            self.calls.append(("small", payload))
            count = schema.model_json_schema()["properties"]["choices"]["minItems"]
            if not self.persistent and isinstance(payload["categories"], dict):
                rows = next(iter(payload["categories"].values()))
                return schema.model_validate({"choices": [row["sku"] for row in rows[:count]]})
            return schema.model_validate({"choices": ["not_in_catalog"] * count})
        stage = "category" if issubclass(schema, CategorySelection) else "product"
        self.counts[stage] += 1
        self.calls.append((stage, payload))
        if stage == "category":
            keys = [row["id"] for row in payload["categories"]][:min(2, len(payload["racks"]))]
            groups = [{"category": key, "rack_ids": [r["id"] for i, r in enumerate(payload["racks"]) if i % len(keys) == k]}
                      for k, key in enumerate(keys)]
        else:
            groups = [{"category": key, "skus": [p["sku"] for p in rows[:payload["maximum_products_per_category"][key]]]}
                      for key, rows in payload["categories"].items()]
        fault = self.faults[stage] if self.persistent or self.counts[stage] == 1 else None
        if fault == "missing_rack":
            groups[0]["rack_ids"].pop()
            groups = [g for g in groups if g["rack_ids"]]
            if not groups:  # keep a schema-valid but semantically incomplete answer for a single rack
                groups = [{"category": keys[0], "rack_ids": ["omitted_original"]}]
        elif fault == "unknown_rack": groups[0]["rack_ids"][0] = "invented_rack"
        elif fault == "duplicate_rack":
            ids = groups[0]["rack_ids"]
            if len(ids) > 1: ids[-1] = ids[0]
            else: ids.append(ids[0])
        elif fault in {"duplicate_category", "duplicate_product_category"}:
            # A repeated category within the schema's bounds (at most one group per rack and category, 100 racks a
            # group): the second group takes the first one's category. With a single group the repeat goes into
            # its rack list instead, replacing its last rack so the list stays within its limit.
            if len(groups) > 1: groups[1]["category"] = groups[0]["category"]
            elif stage == "category":
                ids = groups[0]["rack_ids"]
                if len(ids) > 1: ids[-1] = ids[0]
                else: ids.append(ids[0])
            else:
                # One requested category allows only one product group, so a product of another category stands in
                # for the repeat and the answer still fails only the semantic check.
                key = next(key for key in CATALOG if key != groups[0]["category"])
                groups[0]["skus"] = [catalog_slot_item(CATALOG[key][0], "USD").sku]
        elif fault == "unknown_category": groups[0]["category"] = "not_in_catalog"
        elif fault == "missing_products": groups[0]["category"] = "not_requested"
        elif fault == "unknown_sku": groups[0]["skus"] = ["invented_sku"]
        elif fault == "wrong_category_sku":
            key = next(key for key in CATALOG if key != groups[0]["category"])
            groups[0]["skus"] = [catalog_slot_item(CATALOG[key][0], "USD").sku]
        elif fault == "duplicate_sku": groups[0]["skus"] *= 2
        elif fault == "over_limit": groups[0]["skus"] = [p["sku"] for p in payload["categories"][groups[0]["category"]][:2]]
        return schema.model_validate({"groups": groups})


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("fault", CATEGORY_FAULTS + PRODUCT_FAULTS)
def test_one_corrected_response_recovers_and_only_valid_products_are_placed(currency, fault):
    store = empty_store(currency)
    before = store.model_dump()
    model = RepairModel(fault if fault in CATEGORY_FAULTS else None, fault if fault in PRODUCT_FAULTS else None)
    chosen = asyncio.run(select_starter_products(model, store, rack_choices(store), "카페 🌿; no invented products",
                                                product_limits={key: 1 for key in CATALOG}))
    assert len(model.calls) == 3
    corrections = [payload for _, payload in model.calls if "correction" in payload]
    if fault in CATEGORY_FAULTS or fault == "duplicate_product_category":
        assert len(corrections) == 1 and corrections[0]["correction"]["error"]
        assert corrections[0]["correction"]["previous_response"]["groups"]
    else:
        assert not corrections and model.counts["small"] == 1
    result, report = fill_empty_racks(store, chosen, 2)
    assert {row.rack_id for row in chosen} == {"a", "b"}
    assert store.model_dump() == before and report.placements_added > 0
    for row in chosen:
        expected = {catalog_slot_item(p, currency).sku: catalog_slot_item(p, currency) for p in CATALOG[row.category]}
        assert len(row.skus) == 1
        rack = next(r for r in result.racks if r.id == row.rack_id)
        assert all(item == expected[item.sku] for slot in rack.slots for item in slot.items)


@pytest.mark.parametrize("fault", CATEGORY_FAULTS + PRODUCT_FAULTS)
def test_persistent_invalid_choices_stop_after_bounded_small_task_recovery(fault):
    store = empty_store()
    model = RepairModel(fault if fault in CATEGORY_FAULTS else None, fault if fault in PRODUCT_FAULTS else None, True)
    with pytest.raises(ValueError):
        asyncio.run(select_starter_products(model, store, rack_choices(store), "",
                                            product_limits={key: 1 for key in CATALOG}))
    stage = "category" if fault in CATEGORY_FAULTS else "product"
    assert model.counts[stage] == (2 if stage == "category" or fault == "duplicate_product_category" else 1)
    # This fake validates directly, without Instructor's retry loop. Each invalid small task now fails before caching.
    assert model.counts["small"] == (2 if stage == "category" else 1)
    assert not any(r.slots for r in store.racks)


def test_generated_boundary_combinations_preserve_coverage_exclusions_and_limits():
    rng = random.Random(261023)
    for index in range(48):
        store = empty_store(rng.choice(["USD", "KRW", "JPY"]))
        count = rng.choice([1, 2, 15, 16, 99, 100])
        racks = [StarterRack(id=f"section_{i}", name=f"진열대 {i} 🌿", type=rng.choice(["shelf", "fridge"]),
                             available_slots=rng.choice([1, 4, 16])) for i in range(count)]
        racks += [StarterRack(id="occupied", name="Keep existing", type="shelf", available_slots=8, reason="Occupied"),
                  StarterRack(id="blocked", name="Locked", type="fridge", available_slots=0)]
        allowed = set(rng.sample(sorted(CATALOG), rng.choice([1, 2, 8, 16])))
        per_slot = rng.randint(1, 4)
        category_fault = rng.choice(CATEGORY_FAULTS)
        product_fault = rng.choice(PRODUCT_FAULTS)
        model = RepairModel(category_fault, product_fault)
        chosen = asyncio.run(select_starter_products(model, store, racks, f"Boundary {index}",
            allowed_categories=allowed, product_limits={key: 1 for key in allowed}, products_per_slot=per_slot))
        assert Counter(row.rack_id for row in chosen) == Counter(f"section_{i}" for i in range(count))
        assert all(row.category in allowed and len(row.skus) == 1 for row in chosen)
        primary = next(payload for stage, payload in model.calls if stage == "product")
        partial = len(primary["categories"]) > 1 and product_fault != "duplicate_product_category"
        assert model.counts == ({"category": 2, "product": 1, "small": 1} if partial else {"category": 2, "product": 2})


@pytest.mark.parametrize("error", [TimeoutError("offline timeout"), ValueError("invalid provider configuration")])
def test_provider_errors_are_not_retried_as_invalid_selections(error):
    class Unavailable:
        calls = 0

        async def generate_structured_async(self, *args, **kwargs):
            self.calls += 1
            raise error

    model = Unavailable()
    store = empty_store()
    with pytest.raises(type(error), match=str(error)):
        asyncio.run(select_starter_products(model, store, rack_choices(store), ""))
    assert model.calls == 1


def test_cached_incomplete_answer_does_not_trap_retries(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from store_emulator.domain.config import LLMConfig
    from store_emulator.engine.llm_client import LiteLLMClient

    fake = RepairModel("missing_rack", "unknown_sku")
    client = LiteLLMClient(LLMConfig(model="openai/local", api_base="http://127.0.0.1:9/v1", cache_dir=str(tmp_path)))

    async def create(schema, messages, max_retries, seed, max_tokens):
        result = await fake.generate_structured_async(schema, messages[0]["content"], messages[1]["content"])
        return result, SimpleNamespace(usage=None)

    monkeypatch.setattr(client, "_acreate", create)
    store = empty_store()
    first = asyncio.run(select_starter_products(client, store, rack_choices(store), ""))
    assert len(fake.calls) == 4
    second = asyncio.run(select_starter_products(client, store, rack_choices(store), ""))
    assert second == first
    assert len(fake.calls) == 4  # invalid primary answers are revalidated; the good subset and its repair are reused
    assert client.get_usage().cached_requests == 4
