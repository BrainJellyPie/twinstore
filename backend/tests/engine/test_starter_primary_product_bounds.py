"""Do not re-request a complete valid SKU subset just to enforce its count."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.starter_selection import CategorySelection, select_starter_products
from tests.engine.test_starter_selection import empty_store


KEYS = ['dairy', 'coffee_station']


class Model:
    def __init__(self, fault='', raw_skus=False):
        self.fault, self.raw_skus = fault, raw_skus
        self.calls = []

    async def generate_structured_async(self, schema, system, user, **kwargs):
        payload = json.loads(user)
        self.calls.append(payload)
        if issubclass(schema, CategorySelection):
            return schema.model_validate({'assignments': dict(zip(['r0', 'r1'], KEYS))})
        catalog = payload['categories']
        if 'choices' in schema.model_fields:
            return schema.model_validate({'choices': [next(iter(catalog.values()))[-1]['sku']]})
        selections = {key: [p['sku'] for p in catalog[key]] for key in KEYS}
        if self.raw_skus:
            selections = {key: [catalog_slot_item(p, 'USD').sku for p in CATALOG[key]] for key in KEYS}
        if self.fault == 'unknown_tail': selections[KEYS[0]].append('not_in_catalog')
        elif self.fault == 'duplicate_tail': selections[KEYS[0]].append(selections[KEYS[0]][0])
        elif self.fault == 'wrong_category_tail': selections[KEYS[0]].append(selections[KEYS[1]][0])
        return schema.model_validate({'selections': selections})


def select(model, limit=1, capacity=4):
    racks = [StarterRack(id=f'r{i}', name=key, type='shelf', available_slots=capacity) for i, key in enumerate(KEYS)]
    return select_starter_products(model, empty_store(), racks, 'One coherent starter assortment',
                                   allowed_categories=set(KEYS), product_limits=dict.fromkeys(KEYS, limit))


@pytest.mark.parametrize('raw_skus', [False, True])
@pytest.mark.parametrize('limit,capacity,kept', [(1, 4, 1), (3, 4, 3), (16, 1, 2)])
def test_primary_complete_valid_lists_keep_the_requested_subset_without_more_calls(raw_skus, limit, capacity, kept):
    model = Model(raw_skus=raw_skus)
    result = asyncio.run(select(model, limit, capacity))
    assert len(model.calls) == 2
    assert [(row.rack_id, row.category) for row in result] == [('r0', KEYS[0]), ('r1', KEYS[1])]
    for row in result:
        assert row.skus == [catalog_slot_item(p, 'USD').sku for p in CATALOG[row.category][:kept]]


@pytest.mark.parametrize('fault', ['unknown_tail', 'duplicate_tail', 'wrong_category_tail'])
def test_bad_tail_is_not_hidden_by_limiting_otherwise_valid_choices(fault):
    model = Model(fault)
    result = asyncio.run(select(model))
    assert len(model.calls) == 3
    assert list(model.calls[-1]['categories']) == [KEYS[0]]
    assert result[0].skus == [catalog_slot_item(CATALOG[KEYS[0]][-1], 'USD').sku]
    assert result[1].skus == [catalog_slot_item(CATALOG[KEYS[1]][0], 'USD').sku]


def test_cache_stores_and_reuses_the_bounded_primary_selection(tmp_path, monkeypatch):
    model = Model()
    client = LiteLLMClient(LLMConfig(model='openai/local', api_base='http://127.0.0.1:9/v1', cache_dir=str(tmp_path)))

    async def create(schema, messages, max_retries, seed, max_tokens):
        return await model.generate_structured_async(schema, messages[0]['content'], messages[1]['content']), SimpleNamespace(usage=None)

    monkeypatch.setattr(client, '_acreate', create)
    first = asyncio.run(select(client))
    assert len(model.calls) == 2
    assert asyncio.run(select(client)) == first and len(model.calls) == 2
    saved = [json.loads(path.read_text())['result'] for path in tmp_path.glob('*/*.json')]
    products = next(row for row in saved if any('skus' in g for g in row['groups']))
    assert all(len(group['skus']) == 1 for group in products['groups'])
    assert client.get_usage().cached_requests == 2
