"""A description of the area becomes a neighborhood generator spec (fake model, no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"


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


def test_a_description_becomes_a_spec_that_generates(client, monkeypatch):
    from store_emulator.application import town_assist
    text = "A busy university street, two other convenience stores within a block, a cafe and a PC room next door"
    fake = _Writer({"name": "Campus street", "archetype": "university", "size_m": 640, "density": 0.83, "n_competitors": 2,
                    "neighbor_categories": ["cafe", "pc_room", "cafe"], "venue_density": 1.7, "rationale": "Students and rivals."})
    monkeypatch.setattr(town_assist, "build_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/town/describe", json={"text": text, "seed": 7})
    assert r.status_code == 200, r.text
    spec = r.json()["spec"]
    assert spec["archetype"] == "university" and spec["size_m"] == 650 and spec["n_competitors"] == 2
    assert spec["neighbor_categories"] == ["cafe", "pc_room"] and spec["seed"] == 7 and spec["name"] == "Campus street"
    assert r.json()["rationale"] == "Students and rivals." and fake.prompts[0] == f"Description: {text}"
    town = client.post(f"/api/projects/{PID}/town/generate", json=spec)
    assert town.status_code == 200 and town.json()["archetype"] == "university"


def test_errors_read_as_advice(client, monkeypatch):
    from store_emulator.application import town_assist

    class _Broken:
        async def generate_structured_async(self, *a, **k):
            raise TimeoutError("read timed out")

    monkeypatch.setattr(town_assist, "build_client", lambda *a, **k: _Broken())
    r = client.post(f"/api/projects/{PID}/town/describe", json={"text": "Quiet suburb"})
    assert r.status_code == 502 and "took too long" in r.json()["detail"]
    assert client.post(f"/api/projects/{PID}/town/describe", json={"text": "x"}).status_code == 422
