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


def test_same_name_products_remain_distinct_in_facts_and_saved_answers(client, monkeypatch):
    from store_emulator.application import run_analyst
    from tests.engine.test_analyst_product_identity import purchases
    from tests.engine.test_shopper_filter_boundaries import STORE

    customers = purchases()
    monkeypatch.setattr(run_analyst, "_load", lambda *args: ({"p": customers[0]}, {}, STORE, "USD"))
    expected = ["Milk (SKU regular) 3 / $4.00 / 1", "Milk (SKU oat) 1 / $5.00 / 1"]

    class Analyst:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            assert all(line in user for line in expected)
            return schema.model_validate({"answer": "The oat SKU earned more.", "figures": expected})

    monkeypatch.setattr(run_analyst, "assistive_client", lambda *args: Analyst())
    url = f"/api/projects/{PID}/runs/{RUN}/analyst"
    sheet = client.get(url + "/facts").text
    assert all(line in sheet for line in expected) and "Milk 4 / $9.00" not in sheet
    response = client.post(url, json={"question": "Compare the two Milk products."})
    assert response.status_code == 200, response.text
    assert response.json()["messages"][-1]["figures"] == expected
    assert client.get(url).json()["messages"][-1]["figures"] == expected


def test_questions_are_answered_from_the_sheet_and_kept(client, monkeypatch):
    from store_emulator.application import run_analyst
    fake = _Analyst()
    monkeypatch.setattr(run_analyst, "assistive_client", lambda *a, **k: fake)
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

    monkeypatch.setattr(run_analyst, "assistive_client", lambda *a, **k: _Broken())
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/analyst", json={"question": "Busiest hour?"})
    assert r.status_code == 502 and "limiting requests" in r.json()["detail"]
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/analyst").json()["messages"] == []
    assert client.get(f"/api/projects/{PID}/runs/run_missing/analyst/facts").status_code == 404


def test_a_comparison_is_explained_from_both_sheets(client, monkeypatch):
    from store_emulator.application import run_analyst

    class _Explainer:
        def __init__(self) -> None:
            self.prompt = ""

        async def generate_structured_async[T: BaseModel](
            self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
        ) -> T:
            self.prompt = user_prompt
            return response_model.model_validate({"summary": "B sells about the same.", "where": "Drinks gain, snacks lose.",
                                                  "caveats": "Within noise.", "figures": ["spend per shopper: A $", "Invented 1 / 2"]})

    fake = _Explainer()
    monkeypatch.setattr(run_analyst, "assistive_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/compare/explain?a=run_ab0039&b={RUN}", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"] == "B sells about the same." and body["figures"] == ["spend per shopper: A $"]
    assert fake.prompt.startswith("Paired comparison (per shopper):\nspend per shopper: A $")
    assert "share who bought: A " in fake.prompt and " pt (95 % interval " in fake.prompt
    assert "Run A (run_ab0039) fact sheet:\nVisitors: " in fake.prompt and f"Run B ({RUN}) fact sheet:\nVisitors: " in fake.prompt
    assert client.post(f"/api/projects/{PID}/compare/explain?a=run_missing&b={RUN}", json={}).status_code == 404


def test_starter_questions_are_read_off_the_fact_sheet(client, monkeypatch):
    from store_emulator.application import run_analyst
    seen: list[str] = []

    class _Starters:
        async def generate_structured_async[T: BaseModel](
            self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
        ) -> T:
            seen.append(user_prompt)
            return response_model.model_validate({"questions": [
                "Why do so few who stop at Ice cream 2 buy there?", "why do so few who stop at  Ice cream 2 buy there?",
                "Why do so few who stop at Ice cream 2 buy there?", "Ok?", "Which hour brings the biggest baskets?",
                "Do shoppers in their 60s spend less per visit?"]})

    monkeypatch.setattr(run_analyst, "assistive_client", lambda *a, **k: _Starters())
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/analyst/suggestions", json={})
    assert r.status_code == 200, r.text
    assert r.json() == ["Why do so few who stop at Ice cream 2 buy there?", "Which hour brings the biggest baskets?",
                        "Do shoppers in their 60s spend less per visit?"]
    assert seen[0].startswith("Fact sheet:\nVisitors: ")
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/analyst").json()["messages"] == []  # nothing is kept
