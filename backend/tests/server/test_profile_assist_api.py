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

    monkeypatch.setattr(setup_assist, "assistive_client", lambda *a, **k: _Writer())
    r = client.post("/api/assist/customer-profile", json={"name": "Campus Mart", "store_type": "convenience",
                                                          "address": "84 Heukseok-ro, Seoul", "hours": "7:00–23:00", "locale": "ko"})
    assert r.status_code == 200, r.text
    assert r.json()["profile"] == "Office workers buy lunch between 12 and 1. Students come after 4."
    system, user = seen[0]
    assert system.endswith("Write in Korean.") and "Store: Campus Mart" in user and "Opening hours: 7:00–23:00" in user
    assert client.post("/api/assist/customer-profile", json={}).status_code == 400


@pytest.mark.parametrize(("picked", "has_run", "expected"), [
    ("ab_test", True, "ab_test"), ("concept_test", False, "concept_test"), ("shelf_test", True, "shelf_test"),
    ("layout_edit", True, "layout_edit"), ("find_shoppers", True, "find_shoppers"), ("find_shoppers", False, "none"),
    ("optimize", True, "optimize"), ("optimize", False, "none"), ("run_question", True, "run_question"),
    ("run_question", False, "none"),
])
@pytest.mark.parametrize("spelling", ["exact", "mixed"])
def test_requests_are_routed_to_a_tool(client, monkeypatch, picked, has_run, expected, spelling):
    from store_emulator.application import setup_assist
    prompts: list[str] = []

    class _Router:
        async def generate_structured_async[T: BaseModel](
            self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
        ) -> T:
            prompts.append(system_prompt)
            return response_model.model_validate({"destination": picked if spelling == "exact" else f" {picked.upper()} ", "reason": "because"})

    monkeypatch.setattr(setup_assist, "assistive_client", lambda *a, **k: _Router())
    r = client.post("/api/assist/route", json={"text": "Would a 1+1 on cola beat a 20 % cut?", "has_run": has_run})
    assert r.status_code == 200 and r.json()["destination"] == expected
    assert ("no simulated day yet" in prompts[0]) is (not has_run)


class _Setup:
    def __init__(self, reply: dict[str, object]) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.calls.append((system_prompt, user_prompt))
        return response_model.model_validate(self.reply)


@pytest.mark.parametrize("spelling", ["exact", "mixed"])
def test_the_create_store_form_is_filled_from_a_description(client, monkeypatch, spelling):
    from store_emulator.application import setup_assist
    fake = _Setup({"name": "중앙 캠퍼스 마트", "description": "학생들이 주로 찾는 캠퍼스 편의점입니다.", "address": "Chung-Ang University, Seoul",
                   "format": "University campus store (convenience)", "open_days": "weekday", "open_hour": 7, "close_hour": 23,
                   "currency": "KRW", "rationale": "A campus store open on weekdays."})
    if spelling == "mixed":
        fake.reply.update(open_days=" Weekday ", currency=" krw ")
    monkeypatch.setattr(setup_assist, "assistive_client", lambda *a, **k: fake)
    r = client.post("/api/assist/store-setup", json={"text": "중앙대 캠퍼스 편의점, 평일 7시-23시, 학생 위주", "locale": "ko"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["template_id"] == "campus_cvs" and d["store_type"] == "convenience" and d["open_days"] == "weekday"
    assert (d["open_hour"], d["close_hour"], d["currency"]) == (7, 23, "KRW") and d["warnings"] == []
    system, user = fake.calls[0]
    assert system.endswith("give a short rationale in English.") and "Write the name and description in Korean" in system
    assert "- University campus store (convenience):" in user and user.endswith("Description: 중앙대 캠퍼스 편의점, 평일 7시-23시, 학생 위주")


def test_unknown_formats_and_overnight_hours_are_left_for_the_user(client, monkeypatch):
    from store_emulator.application import setup_assist
    monkeypatch.setattr(setup_assist, "assistive_client", lambda *a, **k: _Setup(
        {"name": "Night owl", "format": "Moon base", "open_hour": 22, "close_hour": 6}))
    d = client.post("/api/assist/store-setup", json={"text": "A late-night store open 10 pm to 6 am"}).json()
    assert d["template_id"] == "" and d["open_hour"] is None and d["close_hour"] is None
    assert any("Moon base" in w for w in d["warnings"]) and any("overnight" in w for w in d["warnings"])
    assert client.post("/api/assist/store-setup", json={"text": "hi"}).status_code == 422


@pytest.mark.parametrize("field", ["name", "description", "address", "format", "rationale"])
def test_optional_model_nulls_do_not_turn_a_store_draft_into_a_gateway_error(client, monkeypatch, field):
    from store_emulator.application import setup_assist
    monkeypatch.setattr(setup_assist, "assistive_client", lambda *a, **k: _Setup(
        {field: None, "open_hour": 7, "close_hour": 23, "currency": "KRW"}))
    response = client.post("/api/assist/store-setup", json={"text": "A small neighborhood shop"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["open_hour"], data["close_hour"], data["currency"]) == (7, 23, "KRW")
    assert all(data[key] == "" for key in ["name", "description", "address", "template_id", "rationale"])
