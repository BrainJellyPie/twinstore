"""A situation described in words becomes a custom scenario; promotions and stock-outs are checked against the
layout's products (fake model, no network)."""

import copy

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


class _Writer:
    def __init__(self, draft: dict[str, object]) -> None:
        self.draft = draft
        self.prompts: list[str] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.prompts.append(user_prompt)
        return response_model.model_validate(self.draft)


DRAFT = {
    "name": "Rainy match night", "weather": "rain", "temperature_c": 14, "day_type": "weekday", "only_days": [5],
    "crowding": "busy", "events": [{"kind": "sports_match", "intensity": 0.8, "start_hour": 18, "end_hour": 18}],
    "promotions": [{"target": "Pepsi", "kind": "1+1", "label": "1+1"}, {"target": "Zorblax", "kind": "discount"}],
    "stockouts": ["Firewood", "Snickers", "Snickers"], "notes": "Fans stop by before kick-off.",
}


def test_a_description_becomes_a_checked_scenario_with_its_effects(client, monkeypatch):
    from store_emulator.application import scenarios
    fake = _Writer(DRAFT)
    monkeypatch.setattr(scenarios, "assistive_client", lambda *a, **k: fake)
    text = "Rainy Friday, the game at the stadium tonight, 1+1 on Pepsi, out of Snickers"
    r = client.post("/api/scenarios/describe", json={"text": text, "project_id": PID, "setup_id": SETUP})
    assert r.status_code == 200, r.text
    body = r.json()
    s = body["scenario"]
    assert s["id"] == "custom" and s["name"] == "Rainy match night" and s["description"] == text
    assert s["weather"] == "rain" and s["only_days"] == [5] and s["crowding"] == "busy"
    assert s["events"][0]["kind"] == "sports_match" and s["events"][0]["end_hour"] == 24  # an empty window is widened
    assert [p["target"] for p in s["promotions"]] == ["Pepsi"] and s["stockouts"] == ["Snickers"]
    assert 'No product matches the promotion target "Zorblax"; it was left out.' in body["warnings"]
    assert 'No product matches the stock-out "Firewood"; it was left out.' in body["warnings"]
    assert all("applies to" in w or "No product" in w for w in body["warnings"])
    assert body["effects"]["traffic"] < 1.0 and "rain" in body["effects"]["situation"].lower()
    prompt = fake.prompts[0]
    assert "Products: " in prompt and "Pepsi" in prompt and f"Description: {text}" in prompt


def test_without_a_layout_targets_are_not_checked_and_errors_read_as_advice(client, monkeypatch):
    from store_emulator.application import scenarios
    monkeypatch.setattr(scenarios, "assistive_client", lambda *a, **k: _Writer({**DRAFT, "events": []}))
    body = client.post("/api/scenarios/describe", json={"text": "Rainy Friday with a deal on Zorblax"}).json()
    assert [p["target"] for p in body["scenario"]["promotions"]] == ["Pepsi", "Zorblax"] and body["warnings"] == []
    assert client.post("/api/scenarios/describe", json={"text": "x", "project_id": PID, "setup_id": SETUP}).status_code == 422
    assert client.post("/api/scenarios/describe", json={"text": "Rain", "project_id": PID, "setup_id": "nope"}).status_code == 404
    assert client.post("/api/scenarios/describe", json={"text": "Rain", "project_id": "../x", "setup_id": SETUP}).status_code == 400

    class _Broken:
        async def generate_structured_async(self, *a, **k):
            raise RuntimeError("AuthenticationError: invalid api key")

    monkeypatch.setattr(scenarios, "assistive_client", lambda *a, **k: _Broken())
    r = client.post("/api/scenarios/describe", json={"text": "Rainy Friday"})
    assert r.status_code == 502 and "rejected the API key" in r.json()["detail"]


@pytest.mark.parametrize("days", [[0], [8], [5, 9]])
def test_invalid_model_weekdays_do_not_return_an_unrestricted_scenario(client, monkeypatch, days):
    from store_emulator.application import scenarios
    monkeypatch.setattr(scenarios, "assistive_client", lambda *a, **k: _Writer({**DRAFT, "only_days": days}))
    response = client.post("/api/scenarios/describe", json={"text": "Rainy Friday only"})
    assert response.status_code == 502
    assert "scenario" not in response.json()


def test_optional_null_annotations_preserve_the_scenario_and_effects(client, monkeypatch):
    from store_emulator.application import scenarios
    draft = {**DRAFT, "notes": None, "events": [{**DRAFT["events"][0], "note": None}],
             "promotions": [{**DRAFT["promotions"][0], "label": None}]}
    monkeypatch.setattr(scenarios, "assistive_client", lambda *a, **k: _Writer(draft))
    response = client.post("/api/scenarios/describe", json={"text": "Rainy Friday, a match, 1+1 Pepsi",
                           "project_id": PID, "setup_id": SETUP})
    assert response.status_code == 200, response.text
    body = response.json()
    scenario = body["scenario"]
    assert scenario["only_days"] == [5] and scenario["weather"] == "rain"
    assert scenario["notes"] == scenario["events"][0]["note"] == scenario["promotions"][0]["label"] == ""
    assert scenario["promotions"][0]["target"] == "Pepsi" and scenario["promotions"][0]["kind"] == "1+1"
    assert scenario["stockouts"] == ["Snickers"] and body["effects"]["traffic"] < 1


@pytest.mark.parametrize("spelling", ["upper", "title", "padded"])
def test_known_choice_spellings_return_the_same_scenario_and_effects(client, monkeypatch, spelling):
    from store_emulator.application import scenarios
    draft = {**copy.deepcopy(DRAFT), "season": "summer", "music": "calm", "lighting": "bright"}
    text = "Rainy Friday, the game, 1+1 on Pepsi, out of Snickers"
    request = {"text": text, "project_id": PID, "setup_id": SETUP}
    monkeypatch.setattr(scenarios, "assistive_client", lambda *a, **k: _Writer(draft))
    expected = client.post("/api/scenarios/describe", json=request)
    assert expected.status_code == 200
    for container, field in [*((draft, f) for f in ("weather", "season", "day_type", "crowding", "music", "lighting")),
                             *((event, "kind") for event in draft["events"]),
                             *((promo, "kind") for promo in draft["promotions"])]:
        value = container[field]
        container[field] = value.upper() if spelling == "upper" else value.title() if spelling == "title" else f"\u3000{value}\t"
    actual = client.post("/api/scenarios/describe", json=request)
    assert actual.status_code == 200, actual.text
    assert actual.json() == expected.json()
