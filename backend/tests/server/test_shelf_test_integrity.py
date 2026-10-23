"""Shelf tests need comparable budgets, complete response pairs and stable evidence."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import marketing
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, setup_path
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ShelfChoice

PID = "proj_67916afd"
SID = "setup_7d6d"
BODY = {"setup_id": SID, "rack_id": "r_801fadeb", "target_sku": "A0017", "panel": 10,
        "changes": [{"kind": "promo", "sku": "A0017", "promo": "NEW"}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(marketing.executor, "submit", Mock())
    monkeypatch.setattr(marketing, "capture_llm_config", Mock(return_value=LLMConfig(model="fake")))
    monkeypatch.setattr(marketing, "LiteLLMClient", Mock())
    async def panel(_llm, personas, *_args, **_kwargs):
        return [ShelfChoice(respondent=p.id, age_group=str(p.age_group), gender=str(p.gender), arm=arm,
                            pick_sku="A0017", noticed=["A0017"]) for p in personas for arm in ("control", "test")]
    monkeypatch.setattr(marketing, "shelf_panel", AsyncMock(side_effect=panel))
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def finish(client):
    started = client.post(f"/api/projects/{PID}/shelf-tests", json=BODY)
    assert started.status_code == 200, started.text
    marketing.executor.submit.call_args.args[0]()
    url = f"/api/projects/{PID}/shelf-tests/{started.json()['job_id']}"
    return url, client.get(url).json()


@pytest.mark.parametrize("budget,store,status", [("KRW", None, 200), ("JPY", "JPY", 200), ("USD", "KRW", 422)])
def test_shelf_test_currency_matches_project_budgets(client, budget, store, status):
    path = metadata_path(PID)
    write_json(path, {**read_json(path), "currency": budget})
    path = setup_path(PID, SID)
    setup = read_json(path)
    setup["store"]["currency"] = store
    write_json(path, setup)
    response = client.post(f"/api/projects/{PID}/shelf-tests", json=BODY)
    assert response.status_code == status, response.text
    if status == 422:
        marketing.capture_llm_config.assert_not_called()
        marketing.executor.submit.assert_not_called()
    else:
        marketing.executor.submit.call_args.args[0]()
        view = client.get(f"/api/projects/{PID}/shelf-tests/{response.json()['job_id']}").json()
        assert view["status"] == "completed", view["error"]
        assert view["report"]["currency"] == budget
        assert marketing.shelf_panel.call_args.kwargs["currency"] == budget


@pytest.mark.parametrize("failures", ["all", "test_arm"])
def test_no_complete_pairs_cannot_be_reported_as_success(client, monkeypatch, failures):
    async def panel(_llm, personas, *_args, **_kwargs):
        return [ShelfChoice(respondent=p.id, age_group=str(p.age_group), gender=str(p.gender), arm=arm,
                            error="model unavailable" if failures == "all" or arm == "test" else "")
                for p in personas for arm in ("control", "test")]
    monkeypatch.setattr(marketing, "shelf_panel", panel)
    _, view = finish(client)
    assert view["status"] == "failed"
    assert view["report"] is None
    assert "pair" in view["error"].lower()


@pytest.mark.parametrize("failures", ["all", "test_arm"])
def test_nonexistent_model_badges_cannot_produce_a_completed_comparison(client, monkeypatch, failures):
    from store_emulator.engine.marketing.shelf_test import shelf_panel

    class InvalidBadges:
        calls = 0

        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            self.calls += 1
            invalid = failures == "all" or self.calls % 2 == 0
            return schema.model_validate({"pick": 999999 if invalid else 0, "noticed": []})

    monkeypatch.setattr(marketing, "shelf_panel", shelf_panel)
    monkeypatch.setattr(marketing, "LiteLLMClient", lambda config: InvalidBadges())
    _, view = finish(client)
    assert view["status"] == "failed" and view["report"] is None
    assert "pair" in view["error"].lower()


def test_partial_pairs_use_the_same_panel_for_every_report_metric(client, monkeypatch):
    async def panel(_llm, personas, *_args, **_kwargs):
        return [ShelfChoice(respondent=p.id, age_group=str(p.age_group), gender=str(p.gender), arm=arm,
                            pick_sku="A0017" if i == 0 else "",
                            error="model unavailable" if i > 0 and arm == "test" else "")
                for i, p in enumerate(personas) for arm in ("control", "test")]
    monkeypatch.setattr(marketing, "shelf_panel", panel)
    _, view = finish(client)
    assert view["status"] == "completed", view["error"]
    report = view["report"]
    assert report["respondents"] == 1
    assert report["errors"] == 9
    pick = next(row for row in report["picks"] if row["sku"] == "A0017")
    assert pick["control"] == pick["test"] == 1.0


@pytest.mark.parametrize("change", ["edit", "delete"])
def test_completed_shelf_images_survive_source_layout_changes(client, change):
    url, view = finish(client)
    assert view["status"] == "completed", view["error"]
    before = {arm: client.get(f"{url}/{arm}.png").content for arm in ("control", "test")}
    path = setup_path(PID, SID)
    if change == "delete":
        path.unlink()
    else:
        setup = read_json(path)
        for rack in setup["store"]["racks"]:
            for slot in rack["slots"]:
                for item in slot["items"]:
                    item["price"] = 999999
        write_json(path, setup)
    for arm, original in before.items():
        image = client.get(f"{url}/{arm}.png")
        assert image.status_code == 200
        assert image.content == original
    report = client.get(f"{url}/report.html")
    assert report.status_code == 200
    assert "data:image/png;base64," in report.text


@pytest.mark.parametrize("invalid", ["target", "face"])
def test_shelf_test_requires_target_on_visible_face(client, invalid):
    store = client.get(f"/api/projects/{PID}/setups/{SID}").json()["store"]
    rack = next(r for r in store["racks"] if r["id"] == BODY["rack_id"])
    target_faces = {s["face"] for s in rack["slots"] if any(i["sku"] == BODY["target_sku"] for i in s["items"])}
    face = next(f for f in "NSEW" if f not in target_faces)
    request = {**BODY, "face": face}
    if invalid == "target":
        request["target_sku"] = "missing_product"
    response = client.post(f"/api/projects/{PID}/shelf-tests", json=request)
    assert response.status_code == 400, response.text
    marketing.executor.submit.assert_not_called()
