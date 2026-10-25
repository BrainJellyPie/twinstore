"""Online-store API on the bundled sample project: templates, sites and variants, browsing, runs and replays."""

import time

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from store_emulator.domain.types import TokenUsage

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _wait(client: TestClient, run_id: str) -> dict:  # type: ignore[type-arg]
    for _ in range(300):
        view = client.get(f"/api/projects/{PID}/online/runs/{run_id}").json()
        if view["status"]["status"] in ("completed", "failed"):
            return view
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_templates_and_previews(client: TestClient) -> None:
    templates = client.get("/api/online/templates").json()
    assert len(templates) >= 40 and {"id", "name", "products", "photos", "highlights"} <= set(templates[0])
    png = client.get(f"/api/online/templates/{templates[0]['id']}/preview.png")
    assert png.status_code == 200 and png.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert client.get("/api/online/templates/nope/preview.png").status_code == 404
    assert client.get(f"/api/online/templates/{templates[0]['id']}/preview.png?currency=1x").status_code == 400


def test_site_lifecycle_and_browsing(client: TestClient) -> None:
    assert client.get(f"/api/projects/{PID}/online/sites").json() == []
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    assert site["name"] == "Threadline" and site["currency"] == "USD" and len(site["products"]) > 40
    sid = site["id"]
    assert client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "nope"}).status_code == 400

    edited = {**site, "name": "Threadline B", "options": {**site["options"], "welcome_popup": "none", "quick_add": True}}
    saved = client.put(f"/api/projects/{PID}/online/sites/{sid}", json=edited).json()
    assert saved["name"] == "Threadline B" and saved["options"]["quick_add"] and saved["created_at"] == site["created_at"]
    bad = {**edited, "products": [{**edited["products"][0], "category_id": "missing"}]}
    assert client.put(f"/api/projects/{PID}/online/sites/{sid}", json=bad).status_code == 422
    assert client.put(f"/api/projects/{PID}/online/sites/other", json=edited).status_code == 400

    variant = client.post(f"/api/projects/{PID}/online/sites/{sid}/copy",
                          json={"name": "No popup", "note": "popup off", "options": {**site["options"], "welcome_popup": "none"}}).json()
    assert variant["variant_of"] == sid and variant["options"]["welcome_popup"] == "none"
    listed = client.get(f"/api/projects/{PID}/online/sites").json()
    assert [s["id"] for s in listed] == [sid, variant["id"]] and listed[0]["products"] == len(site["products"])

    page = client.post(f"/api/projects/{PID}/online/sites/{sid}/browse", json={"device": "mobile"}).json()
    assert page["page"] == "home" and page["image"].startswith("data:image/png;base64,") and page["width"] < 500
    assert all(o["box"] is not None for o in page["options"])
    search = next(o for o in page["options"] if o["kind"] == "search")
    missing_query = client.post(f"/api/projects/{PID}/online/sites/{sid}/browse",
                                json={"state": page["state"], "option": search["number"]})
    assert missing_query.status_code == 400
    found = client.post(f"/api/projects/{PID}/online/sites/{sid}/browse",
                        json={"state": page["state"], "option": search["number"], "query": "sneakers"}).json()
    assert found["page"] == "search" and found["state"]["at"]["query"] == "sneakers"
    product = next(o for o in found["options"] if o["kind"] == "open_product")
    detail = client.post(f"/api/projects/{PID}/online/sites/{sid}/browse",
                         json={"state": found["state"], "option": product["number"]}).json()
    assert detail["page"] == "product" and any(o["kind"] == "add_to_cart" for o in detail["options"])
    assert client.post(f"/api/projects/{PID}/online/sites/{sid}/browse",
                       json={"state": found["state"], "option": 999}).status_code == 400
    leave = next(o for o in detail["options"] if o["kind"] == "leave")
    again = client.post(f"/api/projects/{PID}/online/sites/{sid}/browse",
                        json={"state": detail["state"], "option": leave["number"]}).json()
    assert again["page"] == "home" and again["state"]["history"] == [] and again["state"]["notice"]

    preview = client.get(f"/api/projects/{PID}/online/sites/{sid}/preview.png?device=mobile")
    assert preview.status_code == 200 and preview.content[:4] == b"\x89PNG"
    assert client.delete(f"/api/projects/{PID}/online/sites/{variant['id']}").status_code == 200
    assert client.get(f"/api/projects/{PID}/online/sites/{variant['id']}").status_code == 404


def test_site_from_the_projects_own_shelves(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "from_store", "name": "Sample online"}).json()
    assert site["template_id"] == "from_store" and site["name"] == "Sample online"
    assert site["products"] and all(p["sku"] for p in site["products"])
    page = client.post(f"/api/projects/{PID}/online/sites/{site['id']}/browse", json={}).json()
    assert page["options"]


def test_rule_run_compares_variants_on_the_same_shoppers(client: TestClient) -> None:
    a = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "electronics"}).json()
    b = client.post(f"/api/projects/{PID}/online/sites/{a['id']}/copy",
                    json={"options": {**a["options"], "page_load_ms": 7000, "service_fee": 500}}).json()
    status = client.post(f"/api/projects/{PID}/online/runs",
                         json={"site_ids": [a["id"], b["id"]], "shoppers": 24, "seed": 3}).json()
    assert status["total"] == 48 and status["site_names"] == [a["name"], b["name"]]
    view = _wait(client, status["run_id"])
    assert view["status"]["status"] == "completed", view["status"]["error"]
    result = view["result"]
    assert [v["sessions"] for v in result["variants"]] == [24, 24] and len(result["shoppers"]) == 24
    deltas = {d["metric"]: d for d in result["comparisons"][0]["deltas"]}
    assert deltas["conversion"]["n"] == 24 and deltas["conversion"]["diff"] <= 0
    assert result["variants"][0]["funnel"][0]["sessions"] == 24

    shopper = result["shoppers"][0]["id"]
    session = client.get(f"/api/projects/{PID}/online/runs/{status['run_id']}/sessions/1/{shopper}").json()
    assert session["site_id"] == b["id"] and session["session"]["steps"]
    png = client.get(f"/api/projects/{PID}/online/runs/{status['run_id']}/sessions/1/{shopper}/steps/0.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    assert client.get(f"/api/projects/{PID}/online/runs/{status['run_id']}/sessions/5/{shopper}").status_code == 404
    csv_text = client.get(f"/api/projects/{PID}/online/runs/{status['run_id']}/clickstream.csv").text
    assert csv_text.lstrip("﻿").startswith("variant,site,shopper") and len(csv_text.splitlines()) > 48

    runs = client.get(f"/api/projects/{PID}/online/runs").json()
    assert runs[0]["run_id"] == status["run_id"]
    assert client.delete(f"/api/projects/{PID}/online/runs/{status['run_id']}").status_code == 200
    assert client.get(f"/api/projects/{PID}/online/runs/{status['run_id']}").status_code == 404


def test_run_requests_are_validated(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "toy_store"}).json()
    base = f"/api/projects/{PID}/online/runs"
    assert client.post(base, json={"site_ids": [site["id"], site["id"]]}).status_code == 400
    assert client.post(base, json={"site_ids": ["missing"]}).status_code == 404
    assert client.post(base, json={"site_ids": [site["id"]], "missions": {"browse": 0}}).status_code == 400
    assert client.post(base, json={"site_ids": [site["id"]], "missions": {"browse": -1}}).status_code == 422
    assert client.post(base, json={"site_ids": ["../x"]}).status_code == 422
    assert client.get(f"/api/projects/{PID}/online/sites/bad.id").status_code == 400
    with_customers = client.post(base, json={"site_ids": [site["id"]], "shoppers": 6, "source": "project"}).json()
    view = _wait(client, with_customers["run_id"])
    assert view["status"]["status"] == "completed"
    assert all(s["persona_id"] for s in view["result"]["shoppers"])


class _FakeVision:
    def __init__(self) -> None:
        self.images = 0

    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str, user_prompt: str,
                                                      **_: object) -> T:
        raise AssertionError("a vision run must send the screenshot")

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str, **_: object,
    ) -> T:
        self.images += 1
        leave = next(line for line in user_prompt.splitlines() if "Close the tab" in line)
        return response_model.model_validate({"option": int(leave[1:leave.index("]")]), "thought": "Not for me."})

    def reset_usage(self) -> None:
        pass

    def get_usage(self) -> TokenUsage:
        return TokenUsage(requests=self.images)


def test_vision_run_uses_the_model(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from store_emulator.application import online

    fake = _FakeVision()
    monkeypatch.setattr(online, "ensure_resolvable", lambda _config: None)
    monkeypatch.setattr(online, "build_client", lambda *_args, **_kw: fake)
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "pharmacy"}).json()
    status = client.post(f"/api/projects/{PID}/online/runs",
                         json={"site_ids": [site["id"]], "shoppers": 3, "policy": "vlm", "model": "llamacpp:local"}).json()
    view = _wait(client, status["run_id"])
    assert view["status"]["status"] == "completed", view["status"]["error"]
    result = view["result"]
    assert result["policy"] == "vlm" and result["model"] == "llamacpp:local" and result["model_requests"] == 3
    assert result["variants"][0]["outcomes"] == {"bounced": 3} and fake.images == 3
    assert result["variants"][0]["clicks"] and all(0 <= c["x"] <= 1 and 0 <= c["y"] <= 1 for c in result["variants"][0]["clicks"])
