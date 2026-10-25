"""A variant saves edited products and options together without changing its control."""

from copy import deepcopy

import pytest

from tests.server.test_online_api import PID, client


@pytest.mark.parametrize("kind", ["price", "stock", "name", "sponsored"])
def test_copy_saves_the_whole_product_draft_and_preserves_its_source(client, kind):
    source = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    products = deepcopy(source["products"])
    change = {"price": 777, "stock": 0, "name": "Changed item", "sponsored": ["sponsored"]}
    products[0]["badges" if kind == "sponsored" else kind] = change[kind]
    options = {**source["options"], "page_load_ms": 1200}
    response = client.post(f"/api/projects/{PID}/online/sites/{source['id']}/copy",
                           json={"name": "Changed variant", "note": "Draft edits", "options": options, "products": products})
    assert response.status_code == 200
    copied = response.json()
    assert copied["products"] == products and copied["options"] == options
    assert copied["variant_of"] == source["id"] and copied["name"] == "Changed variant"
    assert client.get(f"/api/projects/{PID}/online/sites/{copied['id']}").json() == copied
    assert client.get(f"/api/projects/{PID}/online/sites/{source['id']}").json() == source
    assert len(client.get(f"/api/projects/{PID}/online/sites").json()) == 2


@pytest.mark.parametrize("kind", ["empty", "empty_name", "negative_price", "duplicate_id", "unknown_category"])
def test_invalid_variant_product_draft_creates_no_partial_copy(client, kind):
    source = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    products = deepcopy(source["products"])
    if kind == "empty": products = []
    elif kind == "empty_name": products[0]["name"] = ""
    elif kind == "negative_price": products[0]["price"] = -1
    elif kind == "duplicate_id": products[1]["id"] = products[0]["id"]
    else: products[0]["category_id"] = "missing"
    before = client.get(f"/api/projects/{PID}/online/sites").json()
    response = client.post(f"/api/projects/{PID}/online/sites/{source['id']}/copy", json={"products": products})
    assert response.status_code == 422
    assert client.get(f"/api/projects/{PID}/online/sites").json() == before
    assert client.get(f"/api/projects/{PID}/online/sites/{source['id']}").json() == source


@pytest.mark.parametrize("body", [{}, {"products": None}])
def test_omitted_product_edits_keep_the_existing_copy_behavior(client, body):
    source = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    response = client.post(f"/api/projects/{PID}/online/sites/{source['id']}/copy", json=body)
    assert response.status_code == 200
    assert response.json()["products"] == source["products"]
