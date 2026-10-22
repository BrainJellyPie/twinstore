"""An alternative staff script drafted for the same product and offer (fake model, no network)."""

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


def test_a_script_is_drafted_with_the_offer_and_only_the_given_facts(client, monkeypatch):
    from store_emulator.application import staff_pitch
    store = client.get(f"/api/projects/{PID}/setups/{SETUP}").json()["store"]
    item = next(i for r in store["racks"] for s in r.get("slots", []) for i in s["items"])
    seen: list[tuple[str, str]] = []

    class _Writer:
        async def generate_structured_async[T: BaseModel](
            self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
        ) -> T:
            seen.append((system_prompt, user_prompt))
            return response_model.model_validate({"name": "Value first", "script": "Hi!   This one is   a good deal today.",
                                                  "differs_by": "Leads with value."})

    monkeypatch.setattr(staff_pitch, "build_client", lambda *a, **k: _Writer())

    monkeypatch.setattr(staff_pitch, "assistive_client", lambda *a, **k: _Writer())
    r = client.post(f"/api/projects/{PID}/staff-pitches/draft-script", json={
        "setup_id": SETUP, "sku": item["sku"], "context": "Shopper at the shelf.", "product_facts": "500 ml.",
        "current": "Can I help you?", "direction": "lead with value"})
    assert r.status_code == 200, r.text
    assert r.json() == {"name": "Value first", "script": "Hi! This one is a good deal today.", "differs_by": "Leads with value."}
    system, user = seen[0]
    assert "Keep the same product, price and promotion" in system
    assert f"Product: {item['name']}. Offer on the shelf: $" in user and "Verified facts: 500 ml." in user
    assert "Current script: Can I help you?" in user and user.endswith("Direction: lead with value")
    bad = client.post(f"/api/projects/{PID}/staff-pitches/draft-script", json={"setup_id": SETUP, "sku": "NOPE"})
    assert bad.status_code == 400
