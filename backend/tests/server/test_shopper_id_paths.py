"""Encoded slashes in saved customer IDs survive every shopper detail route."""

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import interview
from store_emulator.server.main import app
from tests.server.test_interview_customer_identifiers import saved_run


@pytest.mark.parametrize("sid", ["shop/customer", "/customer", "customer/", "a//b", "../outside",
                                  "a/../b", "고객/001", "a/interview", "a/journey", "a/interview/suggestions"])
def test_all_customer_detail_routes_preserve_the_exact_encoded_id(saved_run, monkeypatch, sid):
    # Keep the final component as a distinct valid customer; a route must not silently fall back to it.
    base = saved_run([sid, "customer", "001"])

    async def followups(*args):
        return ["How did the shelf affect your choice?"]

    monkeypatch.setattr(interview, "suggest_follow_ups", followups)
    client = TestClient(app)
    url = f"/api/projects/project/runs/run/shoppers/{quote(sid, safe='')}"
    journey = client.get(f"{url}/journey")
    assert journey.status_code == 200, journey.text
    assert journey.json()["persona"]["id"] == sid
    assert client.get(f"{url}/interview").json()["messages"] == []
    answered = client.post(f"{url}/interview", json={"question": "Why did you visit?"})
    assert answered.status_code == 200, answered.text
    assert answered.json()["persona_id"] == sid
    suggested = client.post(f"{url}/interview/suggestions", json={})
    assert suggested.status_code == 200, suggested.text
    assert suggested.json()["persona_id"] == sid
    assert suggested.json()["suggestions"] == ["How did the shelf affect your choice?"]
    assert client.get(f"{url}/interview").json() == suggested.json()
    assert interview.get_interview("project", "run", "customer").messages == []
    paths = list((base / "interviews").rglob("*.json"))
    assert len(paths) == 1 and paths[0].parent.name == "by-id"
    assert client.delete(f"{url}/interview").status_code == 204
    assert client.get(f"{url}/interview").json()["messages"] == []
