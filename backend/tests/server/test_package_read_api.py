"""A product image read by a vision model: printed name and brand replace the file-name guess, and an exact product
of the layout is linked (fake model, no network)."""

import io

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from store_emulator.engine.shelf_lab.edits import synth_package

PID = "proj_67916afd"
SETUP = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _upload(client, name: str) -> dict:
    buf = io.BytesIO()
    synth_package(name).save(buf, format="PNG")
    res = client.post(f"/api/projects/{PID}/lab/packages", files={"image": ("IMG_2041.png", buf.getvalue(), "image/png")},
                      data={"name": "IMG 2041"})
    assert res.status_code == 200, res.text
    return res.json()


def _reader(reading: dict[str, object], seen: list[str]):
    class _VLM:
        def __init__(self, config: object) -> None:
            self.model = "fake-vision"

        async def generate_structured_with_image_async[T: BaseModel](
            self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
            *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
        ) -> T:
            assert image_url.startswith("data:image/jpeg;base64,")
            seen.append(user_prompt)
            return response_model.model_validate(reading)
    return _VLM


def test_reading_a_pack_names_it_and_links_the_layout_product(client, monkeypatch):
    from store_emulator.application import shelf_lab
    store = client.get(f"/api/projects/{PID}/setups/{SETUP}").json()["store"]
    item = next(i for r in store["racks"] for s in r.get("slots", []) for i in s["items"])
    seen: list[str] = []
    monkeypatch.setattr(shelf_lab, "LiteLLMClient", _reader(
        {"name": "Green Tea 500 ml", "brand": "Leafy", "size": "500 ml", "category": "Tea",
         "shelf_product": item["name"].upper(), "confidence": 0.9}, seen))
    monkeypatch.setattr(shelf_lab, "capture_llm_config", lambda config, model: config.engines.vlm_glance.llm)
    asset = _upload(client, "Leafy Tea")
    r = client.post(f"/api/projects/{PID}/lab/packages/{asset['asset_id']}/read", json={"setup_id": SETUP})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["asset"]["name"] == "Green Tea 500 ml" and body["asset"]["brand"] == "Leafy"
    assert body["linked"] and body["asset"]["sku"] == item["sku"] and body["reading"]["shelf_product"] == item["name"]
    assert item["name"] in seen[0]
    listed = client.get(f"/api/projects/{PID}/lab/packages").json()
    assert next(a for a in listed if a["asset_id"] == asset["asset_id"])["name"] == "Green Tea 500 ml"


def test_an_unknown_product_is_not_linked_and_failures_change_nothing(client, monkeypatch):
    from store_emulator.application import shelf_lab
    seen: list[str] = []
    monkeypatch.setattr(shelf_lab, "LiteLLMClient", _reader({"name": "Mystery Soda", "brand": "", "shelf_product": "Nope 1L"}, seen))
    monkeypatch.setattr(shelf_lab, "capture_llm_config", lambda config, model: config.engines.vlm_glance.llm)
    asset = _upload(client, "Mystery")
    body = client.post(f"/api/projects/{PID}/lab/packages/{asset['asset_id']}/read", json={}).json()
    assert body["asset"]["name"] == "Mystery Soda" and not body["linked"] and body["asset"]["sku"] == ""
    assert "Store products: none given" in seen[0]

    class _Broken:
        def __init__(self, config: object) -> None:
            self.model = "x"

        async def generate_structured_with_image_async(self, *a, **k):
            raise RuntimeError("AuthenticationError: invalid api key")

    monkeypatch.setattr(shelf_lab, "LiteLLMClient", _Broken)
    other = _upload(client, "Other")
    r = client.post(f"/api/projects/{PID}/lab/packages/{other['asset_id']}/read", json={})
    assert r.status_code == 502 and "rejected the API key" in r.json()["detail"]
    listed = client.get(f"/api/projects/{PID}/lab/packages").json()
    assert next(a for a in listed if a["asset_id"] == other["asset_id"])["name"] == "IMG 2041"


@pytest.mark.parametrize("missing", ["name", "brand", "size", "category", "shelf_product", "all"])
def test_partial_pack_reading_preserves_known_fields_and_never_invents_a_product_link(client, monkeypatch, missing):
    from store_emulator.application import shelf_lab

    store = client.get(f"/api/projects/{PID}/setups/{SETUP}").json()["store"]
    item = next(i for r in store["racks"] for s in r.get("slots", []) for i in s["items"])
    reading = {"name": "Green Tea 500 ml", "brand": "Leafy", "size": "500 ml", "category": "Tea",
               "shelf_product": item["name"], "confidence": 0.9}
    fields = ["name", "brand", "size", "category", "shelf_product"] if missing == "all" else [missing]
    for field in fields:
        reading[field] = None
    monkeypatch.setattr(shelf_lab, "LiteLLMClient", _reader(reading, []))
    monkeypatch.setattr(shelf_lab, "capture_llm_config", lambda config, model: config.engines.vlm_glance.llm)
    asset = _upload(client, "Leafy Tea")
    response = client.post(f"/api/projects/{PID}/lab/packages/{asset['asset_id']}/read", json={"setup_id": SETUP})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["asset"]["name"] == (asset["name"] if "name" in fields else "Green Tea 500 ml")
    assert body["asset"]["brand"] == (asset["brand"] if "brand" in fields else "Leafy")
    assert all(body["reading"][field] == "" for field in fields)
    assert body["reading"]["confidence"] == 0.9
    linked = "shelf_product" not in fields
    assert body["linked"] == linked and body["asset"]["sku"] == (item["sku"] if linked else "")
    listed = client.get(f"/api/projects/{PID}/lab/packages").json()
    assert next(a for a in listed if a["asset_id"] == asset["asset_id"]) == body["asset"]


@pytest.mark.parametrize("word", ["Tea", "녹차"])
@pytest.mark.parametrize("collision", [False, True])
def test_bounded_product_name_links_only_an_unambiguous_full_product(client, monkeypatch, word, collision):
    from store_emulator.application import shelf_lab
    from store_emulator.domain.rack import SlotItem
    from tests.engine.test_rival_comparison_boundaries import pair

    prefix = (word * 120)[:120]
    full = prefix + " 500 ml"
    store, _ = pair(our_name=full)
    if collision:
        store.racks[0].slots[0].items.append(SlotItem(sku="different", name=prefix, price=100))
    monkeypatch.setattr(shelf_lab, "_load_store", lambda *args: store)
    monkeypatch.setattr(shelf_lab, "LiteLLMClient", _reader({"name": "Read Tea", "shelf_product": prefix}, []))
    monkeypatch.setattr(shelf_lab, "capture_llm_config", lambda config, model: config.engines.vlm_glance.llm)
    asset = _upload(client, "Tea")
    response = client.post(f"/api/projects/{PID}/lab/packages/{asset['asset_id']}/read", json={"setup_id": SETUP})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["linked"] is (not collision)
    assert body["asset"]["sku"] == ("" if collision else "tea")
    assert body["reading"]["shelf_product"] == ("" if collision else full)
    assert body["asset"]["name"] == "Read Tea"
    listed = client.get(f"/api/projects/{PID}/lab/packages").json()
    assert next(a for a in listed if a["asset_id"] == asset["asset_id"]) == body["asset"]
