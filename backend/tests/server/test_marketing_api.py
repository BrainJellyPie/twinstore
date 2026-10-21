"""Marketing studio through the API: the product library, a rule-engine A/B test and a concept test answered by a
fake vision model (no network)."""

import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image
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


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _wait(client, path: str) -> dict:
    for _ in range(1200):
        view = client.get(path).json()
        if view["status"] in ("completed", "failed"):
            assert view["status"] == "completed", view["error"]
            return view
        time.sleep(0.1)
    raise AssertionError(f"{path} did not finish")


def _upload(client, name: str, **form: str) -> dict:
    files = {"image": (f"{name}.png", _png(synth_package(name)), "image/png")}
    res = client.post(f"/api/projects/{PID}/lab/packages", files=files, data={"name": name, **form})
    assert res.status_code == 200, res.text
    return res.json()


def test_product_library(client):
    a = _upload(client, "Volt Cola", brand="Volt", sku="A0001")
    b = _upload(client, "Fizzo Lime")
    assert a["name"] == "Volt Cola" and a["brand"] == "Volt" and a["sku"] == "A0001"
    assert [p["asset_id"] for p in client.get(f"/api/projects/{PID}/lab/packages").json()] == [b["asset_id"], a["asset_id"]]
    patched = client.patch(f"/api/projects/{PID}/lab/packages/{b['asset_id']}", json={"sku": "A0002", "name": "Fizzo Lime 500ml"})
    assert patched.status_code == 200 and patched.json()["sku"] == "A0002" and patched.json()["name"] == "Fizzo Lime 500ml"
    assert client.delete(f"/api/projects/{PID}/lab/packages/{a['asset_id']}").status_code == 204
    assert client.get(f"/api/projects/{PID}/lab/packages/{a['asset_id']}").status_code == 404


def test_rule_ab_test(client, monkeypatch):
    body = {
        "setup_id": SETUP, "panel": 60, "focus_skus": ["A0017"],
        "variants": [
            {"name": "Half price", "changes": [{"kind": "discount", "sku": "A0017", "percent": -50}]},
            {"name": "Eye level", "changes": [{"kind": "move", "sku": "A0017", "rack_id": "r_b5cf7836", "level": 3}]},
        ],
    }
    started = client.post(f"/api/projects/{PID}/experiments", json=body)
    assert started.status_code == 200, started.text
    eid = started.json()["job_id"]
    view = _wait(client, f"/api/projects/{PID}/experiments/{eid}")
    report = view["report"]
    assert view["request"]["variants"][0]["changes"][0]["percent"] == -50 and view["request"]["panel"] == 60
    assert report["panel_size"] == 60 and [v["name"] for v in report["variants"]] == ["Half price", "Eye level"]
    assert all(v["applied"] and v["vs_control"] and v["focus"] for v in report["variants"])
    assert any("100 shoppers" in n for n in report["notes"])
    assert [j["job_id"] for j in client.get(f"/api/projects/{PID}/experiments").json()] == [eid]
    assert client.get(f"/api/projects/{PID}/marketing").json()["currency"] == report["currency"]

    html = client.get(f"/api/projects/{PID}/experiments/{eid}/report.html")
    assert html.status_code == 200 and html.headers["content-type"].startswith("text/html")
    assert "Half price" in html.text and "<svg" in html.text and "Method and caveats" in html.text
    md = client.get(f"/api/projects/{PID}/experiments/{eid}/report.md").text
    assert md.startswith("# ") and "## Results" in md and "| Arm |" in md
    assert "attachment" in client.get(f"/api/projects/{PID}/experiments/{eid}/report.html?download=1").headers["content-disposition"]

    class _Writer:
        async def generate_structured_async(self, response_model, system_prompt, user_prompt, *, max_retries=1, seed=None):  # noqa: ANN001
            assert "## Results" in user_prompt
            return response_model.model_validate({"summary": "Half price moved units.", "interpretation": "Price matters.", "next_steps": "Test -30 %."})

    from store_emulator.application import marketing
    monkeypatch.setattr(marketing, "build_client", lambda *a, **k: _Writer())
    note = client.post(f"/api/projects/{PID}/experiments/{eid}/narrative", json={"model": "openai/gpt-4o-mini"})
    assert note.status_code == 200 and note.json()["model"] == "openai/gpt-4o-mini"
    assert "Half price moved units." in client.get(f"/api/projects/{PID}/experiments/{eid}/report.html").text
    assert "Commentary (model-written)" in client.get(f"/api/projects/{PID}/experiments/{eid}/report.md").text
    assert client.delete(f"/api/projects/{PID}/experiments/{eid}/narrative").status_code == 204
    assert "Half price moved units." not in client.get(f"/api/projects/{PID}/experiments/{eid}/report.html").text

    nothing = {"setup_id": SETUP, "variants": [{"name": "Ghost", "changes": [{"kind": "promo", "sku": "NOPE"}]}]}
    assert client.post(f"/api/projects/{PID}/experiments", json=nothing).status_code == 400
    pkg = _upload(client, "Leafy Tea")
    packaged = {"setup_id": SETUP, "variants": [{"name": "New pack", "changes": [{"kind": "package", "sku": "A0017", "asset_id": pkg["asset_id"]}]}]}
    assert "vision" in client.post(f"/api/projects/{PID}/experiments", json=packaged).json()["detail"]
    assert client.delete(f"/api/projects/{PID}/experiments/{eid}").status_code == 204
    assert client.get(f"/api/projects/{PID}/experiments/{eid}").status_code == 404


class _FakeVLM:
    def __init__(self, config: object) -> None:
        self.n = 0

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        self.n += 1
        a = 4 if self.n % 3 else 2
        return response_model.model_validate({
            "purchase_intent_A": a, "purchase_intent_B": 6 - a, "appeal_A": 4, "appeal_B": 3,
            "too_cheap": 0.8, "cheap": 1.4, "expensive": 2.4, "too_expensive": 3.2,
            "preferred": "A" if a == 4 else "B", "why": "looks fresh",
        })


def test_concept_test_with_fake_vision_model(client, monkeypatch):
    from store_emulator.application import marketing
    monkeypatch.setattr(marketing, "LiteLLMClient", _FakeVLM)
    a, b = _upload(client, "Leafy Tea"), _upload(client, "Clara Water")
    body = {
        "stimuli": [a["asset_id"], b["asset_id"]], "stimulus_names": ["Leafy", "Clara"],
        "questions": ["purchase_intent", "appeal", "price_vw", "preference", "open"],
        "panel": 12, "model": "openai/gpt-4o-mini", "reference_price": 199,
    }
    started = client.post(f"/api/projects/{PID}/surveys", json=body)
    assert started.status_code == 200, started.text
    sid = started.json()["job_id"]
    report = _wait(client, f"/api/projects/{PID}/surveys/{sid}")["report"]
    assert report["respondents"] == 12 and report["errors"] == 0
    assert {(s["question"], s["stimulus"]) for s in report["scales"]} == {
        ("purchase_intent", 0), ("purchase_intent", 1), ("appeal", 0), ("appeal", 1)}
    assert report["price"]["n"] == 12 and report["preference"][0]["name"] == "Leafy"
    assert report["segments"] and report["verbatims"][0] == "looks fresh"
    assert client.get(f"/api/projects/{PID}/surveys/{sid}/board.jpg").content[:2] == b"\xff\xd8"
    csv = client.get(f"/api/projects/{PID}/surveys/{sid}/export.csv").text.splitlines()
    assert csv[0].startswith("respondent,age_group,gender,purchase_intent_A") and len(csv) == 13
    page = client.get(f"/api/projects/{PID}/surveys/{sid}/report.html").text
    assert "Concept test report" in page and "data:image/jpeg;base64," in page and "Price range for Leafy" in page and "<svg" in page
    quota = {**body, "age_groups": ["70s"]}
    assert client.post(f"/api/projects/{PID}/surveys", json=quota).status_code == 400


class _ShelfVLM:
    def __init__(self, config: object) -> None:
        pass

    async def generate_structured_with_image_async(self, response_model, system_prompt, user_prompt, image_url, *, max_retries=1, seed=None, route=None):  # noqa: ANN001
        assert image_url.startswith("data:image/png;base64,") and "badge" in system_prompt
        return response_model.model_validate({"noticed": [1, 2], "pick": 1, "why": "It stood out."})


def test_shelf_test_with_fake_vision_model(client, monkeypatch):
    from store_emulator.application import marketing
    monkeypatch.setattr(marketing, "LiteLLMClient", _ShelfVLM)
    pkg = _upload(client, "Leafy Tea")
    body = {"setup_id": SETUP, "rack_id": "r_801fadeb", "target_sku": "A0017", "panel": 12, "model": "openai/gpt-4o-mini",
            "changes": [{"kind": "package", "sku": "A0017", "asset_id": pkg["asset_id"]}, {"kind": "promo", "sku": "A0017", "promo": "NEW"}]}
    started = client.post(f"/api/projects/{PID}/shelf-tests", json=body)
    assert started.status_code == 200, started.text
    tid = started.json()["job_id"]
    view = _wait(client, f"/api/projects/{PID}/shelf-tests/{tid}")
    r = view["report"]
    assert r["respondents"] == 12 and r["errors"] == 0 and r["target_name"].startswith("Arizona")
    assert [c["metric"] for c in r["comparisons"]] == ["pick", "noticed", "noticed_first"]
    assert len(r["choices"]) == 24 and {c["arm"] for c in r["choices"]} == {"control", "test"}
    assert abs(sum(p["control"] for p in r["picks"]) - 1) < 1e-6 or len(r["picks"]) == 8
    assert view["request"]["target_sku"] == "A0017"
    for arm in ("control", "test"):
        img = client.get(f"/api/projects/{PID}/shelf-tests/{tid}/{arm}.png")
        assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    page = client.get(f"/api/projects/{PID}/shelf-tests/{tid}/report.html").text
    assert "Shelf test report" in page and page.count("data:image/png;base64,") == 2 and "<svg" in page
    prev = client.post(f"/api/projects/{PID}/shelf-tests/preview", json={k: body[k] for k in ("setup_id", "rack_id", "target_sku", "changes")}).json()
    assert prev["control"].startswith("data:image/png;base64,") and prev["control"] != prev["test"] and len(prev["applied"]) == 2
    bad = {**body, "changes": [{"kind": "promo", "sku": "NOPE"}]}
    assert client.post(f"/api/projects/{PID}/shelf-tests", json=bad).status_code == 400
    assert client.delete(f"/api/projects/{PID}/shelf-tests/{tid}").status_code == 204
