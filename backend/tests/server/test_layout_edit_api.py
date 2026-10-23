"""Layout edits written in words: drafted on the layout's own products and shelves, checked on a copy, kept as a new
layout only when the user saves them (fake model, no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"
SETUP = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Editor:
    def __init__(self, draft: dict[str, object]) -> None:
        self.draft = draft
        self.calls: list[tuple[str, str]] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.calls.append((system_prompt, user_prompt))
        return response_model.model_validate(self.draft)


def _store():
    from store_emulator.application.scenarios import (
        _store_for,  # pyright: ignore[reportPrivateUsage]
    )
    store = _store_for(PID, SETUP)
    assert store is not None
    return store


def _two_products():
    store = _store()
    seen: dict[str, tuple[str, str]] = {}
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                seen.setdefault(item.sku, (item.name, rack.rack_name))
    names = {}
    for sku, (name, rack) in seen.items():
        names.setdefault(name, []).append((sku, rack))
    unique = [(name, v[0][0], v[0][1]) for name, v in names.items() if len(v) == 1]
    return unique[0], unique[1], store


def test_instructions_become_checked_edits_and_a_new_layout(client, monkeypatch):
    from store_emulator.application import layout_edit
    (a_name, a_sku, _), (b_name, b_sku, b_rack), store = _two_products()
    fake = _Editor({"name": "Promo week", "summary": "A sign and a lower price.", "changes": [
        {"kind": "promo", "product": a_name, "promo": "SALE"},
        {"kind": "price", "product": b_name, "price": 0.99},
        {"kind": "move", "product": "Imaginary soda", "shelf": b_rack, "level": 3},
    ]})
    monkeypatch.setattr(layout_edit, "assistive_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit/draft", json={"text": "SALE sign on one, 99 cents for the other"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [c["kind"] for c in d["changes"]] == ["promo", "price"] and d["changes"][1]["price"] == 99
    assert len(d["applied"]) == 2 and any("Imaginary soda" in w for w in d["warnings"])
    assert "Instructions: SALE sign on one" in fake.calls[0][1]
    # Nothing was saved by drafting.
    before = {s["id"] for s in client.get(f"/api/projects/{PID}/setups").json()}
    saved = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit", json={"name": "Promo week", "changes": d["changes"], "source_sha256": d["source_sha256"], "request_id": "a" * 32})
    assert saved.status_code == 200, saved.text
    new = saved.json()
    assert new["id"] not in before and new["name"] == "Promo week" and len(new["applied"]) == 2
    project = client.get(f"/api/projects/{PID}").json()
    assert project["state"]["activeSetupId"] == new["id"]
    detail = client.get(f"/api/projects/{PID}/setups/{new['id']}").json()
    items = {i["sku"]: i for r in detail["store"]["racks"] for s in r["slots"] for i in s["items"]}
    assert items[a_sku]["promo"] == "SALE" and items[b_sku]["price"] == 99
    # The original layout is unchanged.
    original = {i.sku: i for r in store.racks for s in r.slots for i in s.items}
    assert _store().model_dump() == store.model_dump() and original[b_sku].price != 99


def test_edits_that_fit_nothing_are_refused(client, monkeypatch):
    from store_emulator.application import layout_edit
    monkeypatch.setattr(layout_edit, "assistive_client", lambda *a, **k: _Editor({"name": "x", "changes": [
        {"kind": "promo", "product": "Imaginary soda", "promo": "NEW"}]}))
    r = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit/draft", json={"text": "NEW sign on the imaginary soda"})
    assert r.status_code == 502 and "could not be drafted" in r.json()["detail"]
    package = client.post(f"/api/projects/{PID}/setups/{SETUP}/edit",
                          json=_save_body(changes=[{"kind": "package", "sku": "nothing", "asset_id": "pkg_x"}]))
    assert package.status_code == 422 and "only shown in tests" in package.json()["detail"]


def _save_body(**patch):
    from store_emulator.application.product_sources import read_product_source
    store, digest = read_product_source(PID, SETUP)
    sku = next(i.sku for r in store.product_racks for s in r.slots for i in s.items)
    return {'name': 'Reviewed edit', 'source_sha256': digest, 'request_id': 'a' * 32,
            'changes': [{'kind': 'promo', 'sku': sku, 'promo': 'NEW'}], **patch}


def _ids(client):
    return {s['id'] for s in client.get(f'/api/projects/{PID}/setups').json()}


@pytest.mark.parametrize('field', ['price', 'regular_price', 'currency', 'product_name', 'image', 'floor'])
def test_reviewed_edit_rejects_a_changed_source(client, field):
    from store_emulator.application.storage.io import write_json
    from store_emulator.application.storage.setups import read_setup, setup_path
    body = _save_body(); source = read_setup(PID, SETUP); before = _ids(client)
    store = source['store']; item = next(i for r in store['racks'] for s in r['slots'] for i in s['items'])
    if field == 'price': item['price'] += 1
    if field == 'regular_price': item['regular_price'] = item['price'] + 100
    if field == 'currency': store['currency'] = 'KRW'
    if field == 'product_name': item['name'] = 'A newer product name'
    if field == 'image': item['image_url'] = '/newer-image.png'
    if field == 'floor': store['name'] = 'A revised floor'
    write_json(setup_path(PID, SETUP), source)
    response = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=body)
    assert response.status_code == 409, response.text
    assert _ids(client) == before and read_setup(PID, SETUP) == source


def test_retried_save_returns_one_child_and_preserves_later_selection_and_edits(client):
    from store_emulator.application.setups import set_active_setup
    from store_emulator.application.storage.io import write_json
    from store_emulator.application.storage.setups import read_setup, setup_path
    body = _save_body(); before = _ids(client)
    first = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=body)
    assert first.status_code == 200, first.text
    child = first.json()['id']; saved = read_setup(PID, child); saved['name'] = 'Later manual name'
    write_json(setup_path(PID, child), saved); set_active_setup(PID, SETUP)
    replay = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=body)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert _ids(client) - before == {child}
    assert read_setup(PID, child) == saved
    assert client.get(f'/api/projects/{PID}').json()['state']['activeSetupId'] == SETUP


@pytest.mark.parametrize('patch', [{'name': 'Changed name'}, {'source_sha256': 'f' * 64},
                                  {'changes': [{'kind': 'promo', 'sku': 'different', 'promo': 'SALE'}]}])
def test_one_save_id_cannot_accept_changed_choices(client, patch):
    body = _save_body(); url = f'/api/projects/{PID}/setups/{SETUP}/edit'
    first = client.post(url, json=body); assert first.status_code == 200
    before = _ids(client)
    assert client.post(url, json={**body, **patch}).status_code == 409
    assert _ids(client) == before


def test_a_removed_child_is_not_resurrected_by_retry(client):
    from store_emulator.application.storage.setups import setup_path
    body = _save_body(); url = f'/api/projects/{PID}/setups/{SETUP}/edit'
    first = client.post(url, json=body); assert first.status_code == 200
    setup_path(PID, first.json()['id']).unlink(); before = _ids(client)
    assert client.post(url, json=body).status_code == 409
    assert _ids(client) == before


def test_completed_save_can_be_retried_after_source_removal(client):
    from store_emulator.application.storage.setups import setup_path
    body = _save_body(); url = f'/api/projects/{PID}/setups/{SETUP}/edit'
    first = client.post(url, json=body); assert first.status_code == 200
    setup_path(PID, SETUP).unlink()
    replay = client.post(url, json=body)
    assert replay.status_code == 200 and replay.json() == first.json()


def test_edited_child_preserves_building_floor_context(client):
    from store_emulator.application.storage.io import write_json
    from store_emulator.application.storage.setups import read_setup, setup_path
    source = read_setup(PID, SETUP)
    source['building'] = {'id': 'building_1', 'name': 'Mall', 'level': 2, 'label': 'Upper', 'floor_count': 2}
    write_json(setup_path(PID, SETUP), source)
    saved = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=_save_body())
    assert saved.status_code == 200, saved.text
    assert read_setup(PID, saved.json()['id']).get('building') == source['building']
    assert read_setup(PID, SETUP) == source


@pytest.mark.parametrize('price,status', [(0, 200), (9007199254740991, 200), (9007199254740992, 422), (10**100, 422)])
def test_saved_prices_remain_exactly_editable(client, price, status):
    body = _save_body(); sku = body['changes'][0]['sku']
    body['changes'] = [{'kind': 'price', 'sku': sku, 'price': price}]
    before = _ids(client)
    response = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=body)
    assert response.status_code == status, response.text
    if status != 200: assert _ids(client) == before
    else:
        from store_emulator.application.product_sources import read_product_source
        store, _ = read_product_source(PID, response.json()['id'])
        assert all(i.price == price for r in store.racks for s in r.slots for i in s.items if i.sku == sku)


def test_category_price_changes_cannot_create_uneditable_large_values(client):
    from store_emulator.application.storage.io import write_json
    from store_emulator.application.storage.setups import read_setup, setup_path
    source = read_setup(PID, SETUP)
    rack = next(r for r in source['store']['racks'] if any(s['items'] for s in r['slots']))
    rack['rack_name'] = 'Boundary category'; rack['slots'][0]['items'][0]['price'] = 9007199254740991
    write_json(setup_path(PID, SETUP), source)
    body = _save_body(changes=[{'kind': 'category_price', 'category': 'Boundary category', 'percent': 300}]); before = _ids(client)
    response = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=body)
    assert response.status_code == 422, response.text
    assert _ids(client) == before and read_setup(PID, SETUP) == source


def test_concurrent_retries_create_only_one_child(client):
    from concurrent.futures import ThreadPoolExecutor
    body = _save_body(); before = _ids(client); url = f'/api/projects/{PID}/setups/{SETUP}/edit'
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(url, json=body), range(8)))
    assert all(r.status_code in {200, 409} for r in results)
    accepted = [r.json()['id'] for r in results if r.status_code == 200]
    final = client.post(url, json=body); assert final.status_code == 200, final.text
    assert accepted and set(accepted) == {final.json()['id']}
    assert _ids(client) - before == {final.json()['id']}


@pytest.mark.parametrize('field,value', [('source_sha256', None), ('source_sha256', 'bad'),
                                        ('request_id', None), ('request_id', '../outside'), ('request_id', 'a' * 33)])
def test_save_requires_a_valid_review_snapshot_and_retry_identity(client, field, value):
    body = _save_body(); before = _ids(client)
    if value is None: body.pop(field)
    else: body[field] = value
    response = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=body)
    assert response.status_code == 422, response.text
    assert _ids(client) == before


def test_save_id_cannot_be_reused_for_a_different_source(client):
    body = _save_body(); first = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=body)
    assert first.status_code == 200
    before = _ids(client)
    response = client.post(f'/api/projects/{PID}/setups/setup_eaf5/edit', json=body)
    assert response.status_code == 409 and 'another source' in response.text
    assert _ids(client) == before


def test_interrupted_child_write_is_explicit_and_not_recreated_on_retry(client, monkeypatch):
    from store_emulator.application import layout_edit
    body = _save_body(); before = _ids(client); original = layout_edit.write_json
    def interrupted(path, data):
        if path.stem == 'setup_edit_' + body['request_id']:
            raise OSError('simulated disk failure')
        original(path, data)
    monkeypatch.setattr(layout_edit, 'write_json', interrupted)
    response = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=body)
    assert response.status_code == 500 and 'Retry the same request' in response.text
    monkeypatch.setattr(layout_edit, 'write_json', original)
    retry = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=body)
    assert retry.status_code == 409 and 'interrupted' in retry.text
    assert _ids(client) == before


def test_running_generation_and_corrupt_source_are_actionable(client, monkeypatch):
    from store_emulator.application import product_sources
    from store_emulator.application.storage.setups import setup_path
    body = _save_body(); before = _ids(client); url = f'/api/projects/{PID}/setups/{SETUP}/edit'
    monkeypatch.setattr(product_sources, 'find_active_generation', lambda *args: {'running': True})
    response = client.post(url, json=body)
    assert response.status_code == 409 and 'generation' in response.text
    assert _ids(client) == before
    monkeypatch.setattr(product_sources, 'find_active_generation', lambda *args: None)
    path = setup_path(PID, SETUP); path.write_text('{broken')
    response = client.post(url, json=body)
    assert response.status_code == 409 and 'unreadable' in response.text
    assert path.read_text() == '{broken'


def test_a_draft_keeps_the_snapshot_it_actually_read(client, monkeypatch):
    from store_emulator.application import layout_edit
    from store_emulator.application.product_sources import read_product_source
    from store_emulator.application.storage.io import write_json
    from store_emulator.application.storage.setups import read_setup, setup_path
    (name, _, _), _, _ = _two_products(); _, digest = read_product_source(PID, SETUP)
    class ConcurrentEditor(_Editor):
        async def generate_structured_async(self, response_model, system_prompt, user_prompt, **kwargs):
            source = read_setup(PID, SETUP); source['store']['name'] = 'Changed while the model was working'
            write_json(setup_path(PID, SETUP), source)
            return response_model.model_validate(self.draft)
    monkeypatch.setattr(layout_edit, 'assistive_client', lambda *a, **k: ConcurrentEditor({'name': 'Draft', 'changes': [{'kind': 'promo', 'product': name, 'promo': 'NEW'}]}))
    response = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit/draft', json={'text': 'Put a NEW sign on the tea'})
    assert response.status_code == 200, response.text
    draft = response.json(); assert draft['source_sha256'] == digest
    before = _ids(client)
    saved = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit', json=_save_body(source_sha256=draft['source_sha256'], changes=draft['changes']))
    assert saved.status_code == 409 and _ids(client) == before


@pytest.mark.parametrize('count', [6, 7, 12])
def test_drafting_accepts_all_twelve_supported_edit_instructions(client, monkeypatch, count):
    from store_emulator.application import layout_edit
    (name, _, _), _, _ = _two_products()
    fake = _Editor({'name': 'Several changes', 'changes': [{'kind': 'promo', 'product': name, 'promo': f'Sign {i}'} for i in range(count)]})
    monkeypatch.setattr(layout_edit, 'assistive_client', lambda *a, **k: fake)
    response = client.post(f'/api/projects/{PID}/setups/{SETUP}/edit/draft', json={'text': 'Apply these changes to the tea'})
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result['changes']) == count and len(result['applied']) == count


@pytest.mark.parametrize("configured", [False, True])
def test_saved_variant_keeps_operations_and_retry_preserves_later_settings(client, configured):
    from store_emulator.application.setups import run_operations, save_layout_operations
    from store_emulator.application.storage.setups import read_setup
    from store_emulator.domain.operations import OperationsConfig
    operations = OperationsConfig(stock_per_facing=1, backroom_per_product=0,
                                 daily_delivery=False, crew=2, till_schedule={"09": 0}) if configured else None
    save_layout_operations(PID, SETUP, operations)
    source = read_setup(PID, SETUP)
    body = _save_body()
    url = f"/api/projects/{PID}/setups/{SETUP}/edit"
    response = client.post(url, json=body)
    assert response.status_code == 200, response.text
    child = response.json()["id"]
    assert run_operations(PID, child, None, None) == operations
    assert run_operations(PID, child, None, False) is None
    assert read_setup(PID, SETUP) == source
    changed = OperationsConfig(stock_per_facing=99)
    save_layout_operations(PID, child, changed)
    assert client.post(url, json=body).json() == response.json()
    assert run_operations(PID, child, None, None) == changed
