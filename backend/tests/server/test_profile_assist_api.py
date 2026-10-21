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
