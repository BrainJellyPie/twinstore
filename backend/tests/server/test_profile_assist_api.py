"""A customer profile drafted for the create-store form (fake model, no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_a_profile_is_drafted_in_the_form_language(client, monkeypatch):
    from store_emulator.application import setup_assist
    seen: list[tuple[str, str]] = []

    class _Writer:
        async def generate_structured_async[T: BaseModel](
            self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
        ) -> T:
            seen.append((system_prompt, user_prompt))
            return response_model.model_validate({"profile": "Office workers   buy lunch between 12 and 1.  Students come after 4."})

    monkeypatch.setattr(setup_assist, "build_client", lambda *a, **k: _Writer())
    r = client.post("/api/assist/customer-profile", json={"name": "Campus Mart", "store_type": "convenience",
                                                          "address": "84 Heukseok-ro, Seoul", "hours": "7:00–23:00", "locale": "ko"})
    assert r.status_code == 200, r.text
    assert r.json()["profile"] == "Office workers buy lunch between 12 and 1. Students come after 4."
    system, user = seen[0]
    assert system.endswith("Write in Korean.") and "Store: Campus Mart" in user and "Opening hours: 7:00–23:00" in user
    assert client.post("/api/assist/customer-profile", json={}).status_code == 400


@pytest.mark.parametrize(("picked", "has_run", "expected"), [
    ("ab_test", True, "ab_test"), ("concept_test", False, "concept_test"), ("shelf_test", True, "shelf_test"), ("run_question", True, "run_question"),
    ("run_question", False, "none"),
])
def test_requests_are_routed_to_a_tool(client, monkeypatch, picked, has_run, expected):
    from store_emulator.application import setup_assist
    prompts: list[str] = []

    class _Router:
        async def generate_structured_async[T: BaseModel](
            self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
        ) -> T:
            prompts.append(system_prompt)
            return response_model.model_validate({"destination": picked, "reason": "because"})

    monkeypatch.setattr(setup_assist, "build_client", lambda *a, **k: _Router())
    r = client.post("/api/assist/route", json={"text": "Would a 1+1 on cola beat a 20 % cut?", "has_run": has_run})
    assert r.status_code == 200 and r.json()["destination"] == expected
    assert ("no simulated day yet" in prompts[0]) is (not has_run)
