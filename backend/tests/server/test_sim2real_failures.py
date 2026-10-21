"""Failed model calls must not become an apparent zero-agreement result."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import shelf_lab
from store_emulator.application.storage.io import write_json
from store_emulator.domain.capture import CaptureItem, CaptureResult
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.shelf_lab import GlanceAnswer


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    personas = [Persona(id=f"p{i}", identity="Shopper", age_group="20s", gender="Female",
                        description="Buys tea", intent="tea", purpose="tea") for i in range(2)]
    write_json(root / "personas.json", [p.model_dump(mode="json") for p in personas])
    write_json(root / "metadata.json", {"currency": "USD"})
    result = CaptureResult(image_size=(64, 64), currency="USD", items=[CaptureItem(
        id="i1", band=0, level=1, order=0, sku="tea", name="Tea", price=100, labeled=True,
    )])
    monkeypatch.setattr(shelf_lab, "_photo_and_result", lambda *_: (Image.new("RGB", (64, 64)), result))
    monkeypatch.setattr(shelf_lab, "capture_llm_config", Mock(return_value=LLMConfig(model="fake")))
    monkeypatch.setattr(shelf_lab, "LiteLLMClient", Mock())
    monkeypatch.setattr(shelf_lab.executor, "submit", Mock())
    from store_emulator.server.main import app
    return TestClient(app)


def finish(client):
    response = client.post("/api/projects/proj_test/captures/cap_test/sim2real", json={"personas": 2})
    assert response.status_code == 200, response.text
    shelf_lab.executor.submit.call_args.args[0]()
    return client.get(f"/api/projects/proj_test/captures/cap_test/lab/jobs/{response.json()['job_id']}").json()


@pytest.mark.parametrize("failures", ["all", "photos", "disjoint"])
def test_no_valid_pairs_cannot_be_reported_as_completed(client, monkeypatch, failures):
    async def panel(_llm, _views, personas, *, conditions, **_kwargs):
        return [GlanceAnswer(persona_id=p.id, condition=c, error="model unavailable" if (
            failures == "all" or failures == "photos" and c != "render"
            or failures == "disjoint" and ((i == 0) == (c == "render"))
        ) else "") for i, p in enumerate(personas) for c in conditions]
    monkeypatch.setattr(shelf_lab, "glance_panel", panel)
    view = finish(client)
    assert view["status"]["status"] == "failed", view
    assert view["sim2real"] is None
    assert "pair" in view["status"]["error"].lower()


def test_partial_failure_omits_empty_comparison_and_explains_errors(client, monkeypatch):
    async def panel(_llm, _views, personas, *, conditions, **_kwargs):
        return [GlanceAnswer(persona_id=p.id, condition=c, error="model unavailable" if c == "photo_raw" else "")
                for p in personas for c in conditions]
    monkeypatch.setattr(shelf_lab, "glance_panel", panel)
    view = finish(client)
    assert view["status"]["status"] == "completed", view
    assert [a["condition"] for a in view["sim2real"]["agreement"]] == ["photo"]
    assert any("fail" in note.lower() for note in view["sim2real"]["notes"])


@pytest.mark.parametrize("conditions", [[], ["render"]])
def test_photo_comparison_is_required_before_model_calls(client, conditions):
    response = client.post("/api/projects/proj_test/captures/cap_test/sim2real", json={"conditions": conditions})
    assert response.status_code == 422, response.text
    shelf_lab.capture_llm_config.assert_not_called()
    shelf_lab.executor.submit.assert_not_called()


@pytest.mark.parametrize("conditions", [["photo"], ["photo", "render", "photo"]])
def test_valid_no_pick_answers_are_compared_and_conditions_are_unique(client, monkeypatch, conditions):
    async def panel(_llm, _views, personas, *, conditions, **_kwargs):
        return [GlanceAnswer(persona_id=p.id, condition=c) for p in personas for c in conditions]
    monkeypatch.setattr(shelf_lab, "glance_panel", panel)
    response = client.post("/api/projects/proj_test/captures/cap_test/sim2real", json={"conditions": conditions})
    assert response.status_code == 200, response.text
    shelf_lab.executor.submit.call_args.args[0]()
    view = client.get(f"/api/projects/proj_test/captures/cap_test/lab/jobs/{response.json()['job_id']}").json()
    assert view["status"]["status"] == "completed", view
    report = view["sim2real"]
    assert len(report["conditions"]) == 2 and set(report["conditions"]) == {"render", "photo"}
    assert len(report["answers"]) == 4
    assert report["agreement"][0]["same_pick"] == 1
    assert report["agreement"][0]["pairs"] == 2
    assert all(s["none_rate"] == 1 and s["errors"] == 0 for s in report["stats"])
