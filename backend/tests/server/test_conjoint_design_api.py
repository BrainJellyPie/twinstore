"""A conjoint study drafted from a question: builder-ready attributes and price levels in the layout's currency,
bracketing comparable products (fake model, no network)."""

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


class _Designer:
    def __init__(self, draft: dict[str, object]) -> None:
        self.draft = draft
        self.calls: list[tuple[str, str]] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.calls.append((system_prompt, user_prompt))
        return response_model.model_validate(self.draft)


DRAFT = {
    "name": "Zero-sugar tea", "product": "a bottle of iced tea", "context": "In the drinks fridge.",
    "attributes": [{"name": "Sugar", "levels": ["Regular", "Zero sugar", "Zero sugar"]},
                   {"name": "Price", "levels": ["1", "2"]}, {"name": "Size", "levels": ["500 ml", "1 L"]},
                   {"name": "Brand", "levels": ["Known"]}],
    "prices": [2.29, 1.49, 1.99, 1.99, -1], "rationale": "Sugar and size are what the question is about.",
    "comparable": ["Arizona Green Tea 23oz", "arizona green tea 23oz", "Imaginary Tea"],
}


def test_a_question_becomes_a_builder_ready_conjoint_draft(client, monkeypatch):
    from store_emulator.application import study_design
    fake = _Designer(DRAFT)
    monkeypatch.setattr(study_design, "assistive_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/conjoints/design",
                    json={"question": "Would people pay more for zero-sugar tea?", "setup_id": SETUP, "currency": "USD"})
    assert r.status_code == 200, r.text
    d = r.json()
    # Duplicate levels, a "Price" attribute and one-level attributes are dropped; prices become sorted cents.
    assert [(a["name"], a["levels"]) for a in d["attributes"]] == [("Sugar", ["Regular", "Zero sugar"]), ("Size", ["500 ml", "1 L"])]
    assert d["prices"] == [149, 199, 229] and d["currency"] == "USD" and d["product"] == "a bottle of iced tea"
    system, user = fake.calls[0]
    assert "levels in USD" in system and "Products in this store: " in user and "$" in user
    assert user.endswith("Question: Would people pay more for zero-sugar tea?")
    # Only products that exist in the layout are cited, with their shelf price.
    assert len(d["comparable"]) == 1 and d["comparable"][0].startswith("Arizona Green Tea 23oz $")


def test_zero_decimal_currencies_and_errors(client, monkeypatch):
    from store_emulator.application import study_design
    monkeypatch.setattr(study_design, "assistive_client", lambda *a, **k: _Designer({**DRAFT, "prices": [1500, 1800]}))
    d = client.post(f"/api/projects/{PID}/conjoints/design", json={"question": "Tea at what price?", "currency": "KRW"}).json()
    assert d["prices"] == [1500, 1800] and d["currency"] == "KRW" and d["comparable"] == []
    mismatch = client.post(f"/api/projects/{PID}/conjoints/design", json={"question": "Tea at what price?", "setup_id": SETUP, "currency": "KRW"})
    assert mismatch.status_code == 422 and "USD" in mismatch.json()["detail"]
    monkeypatch.setattr(study_design, "assistive_client", lambda *a, **k: _Designer({**DRAFT, "attributes": [{"name": "Price", "levels": ["a", "b"]}]}))
    r = client.post(f"/api/projects/{PID}/conjoints/design", json={"question": "Tea at what price?"})
    assert r.status_code == 502 and "could not be drafted" in r.json()["detail"]
