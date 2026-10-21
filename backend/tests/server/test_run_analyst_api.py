"""Questions about a run, answered from its fact sheet (fake model, no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"
RUN = "run_efd57c"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Analyst:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.prompts.append(user_prompt)
        return response_model.model_validate({
            "answer": "Ice cream 1 converts worst: under half of those who stop there buy.",
            "figures": ["Ice cream 1 274 / 120", "Made-up shelf 9 / 9"],
            "follow_ups": ["Why do shoppers leave the freezer empty-handed?", " "],
        })


def test_the_fact_sheet_is_the_runs_own_numbers(client):
    sheet = client.get(f"/api/projects/{PID}/runs/{RUN}/analyst/facts").text
    assert sheet.startswith("Visitors: ") and "By arrival hour" in sheet and "Shelves (stopped / bought there" in sheet
    assert "By age group" in sheet and "entrance" not in sheet
    rates = [int(part.rsplit("/ ", 1)[1].rstrip("%")) for part in sheet.split("Shelves (")[1].split("\n")[0].split("; ")]
    assert all(0 <= r <= 100 for r in rates)  # buys count as stops, so no shelf converts above 100 %


def test_questions_are_answered_from_the_sheet_and_kept(client, monkeypatch):
    from store_emulator.application import run_analyst
    fake = _Analyst()
    monkeypatch.setattr(run_analyst, "build_client", lambda *a, **k: fake)
    url = f"/api/projects/{PID}/runs/{RUN}/analyst"
    assert client.get(url).json()["messages"] == []
    r = client.post(url, json={"question": "Which shelf converts worst?"})
    assert r.status_code == 200, r.text
    user, answer = r.json()["messages"]
    assert user == {**user, "role": "user", "text": "Which shelf converts worst?"}
    assert answer["role"] == "analyst" and answer["text"].startswith("Ice cream 1 converts worst")
    # Only figures that appear in the sheet are kept; empty follow-ups are dropped.
    assert answer["figures"] == ["Ice cream 1 274 / 120"]
    assert answer["follow_ups"] == ["Why do shoppers leave the freezer empty-handed?"]
    assert fake.prompts[0].startswith("Fact sheet:\nVisitors: ") and fake.prompts[0].endswith("Manager: Which shelf converts worst?")
    client.post(url, json={"question": "And by hour?"})
    assert "Analyst: Ice cream 1 converts worst" in fake.prompts[1]
    assert len(client.get(url).json()["messages"]) == 4
    assert client.delete(url).status_code == 204 and client.get(url).json()["messages"] == []


def test_failures_read_as_advice(client, monkeypatch):
    from store_emulator.application import run_analyst

    class _Broken:
        async def generate_structured_async(self, *a, **k):
            raise RuntimeError("RateLimitError")

    monkeypatch.setattr(run_analyst, "build_client", lambda *a, **k: _Broken())
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/analyst", json={"question": "Busiest hour?"})
    assert r.status_code == 502 and "limiting requests" in r.json()["detail"]
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/analyst").json()["messages"] == []
    assert client.get(f"/api/projects/{PID}/runs/run_missing/analyst/facts").status_code == 404
