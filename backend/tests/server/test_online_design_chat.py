"""Changing an online store's design by asking for it: the model's proposal is applied to the design being edited,
checked like the designer form, and nothing is saved until the owner keeps it (fake model, no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Designer:
    def __init__(self, *replies: dict[str, object]) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.calls.append((system_prompt, user_prompt))
        return response_model.model_validate(self.replies.pop(0))


def _fake(monkeypatch, *replies: dict[str, object]) -> _Designer:  # type: ignore[no-untyped-def]
    from store_emulator.application import online
    fake = _Designer(*replies)
    monkeypatch.setattr(online, "assistive_client", lambda *a, **k: fake)
    monkeypatch.setattr(online, "assistive_model", lambda requested, config: "fake:designer")
    return fake


def test_a_request_in_words_becomes_a_checked_draft_and_nothing_is_saved(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "pet_store"}).json()
    fake = _fake(monkeypatch, {
        "page_style": "luxury", "theme_color": "#14532d", "urgency": False, "quick_add": None, "shipping_fee": 2.5,
        "hero_text": "Only the best for your best friend",
        "reply": "Switched to a luxury look with a deep green theme and removed the urgency notes.",
    })
    url = f"/api/projects/{PID}/online/sites/{site['id']}/design-chat"
    r = client.post(url, json={"messages": [{"role": "owner", "text": "Make it feel premium and calm, cheaper delivery"}]})
    assert r.status_code == 200, r.text
    reply = r.json()
    assert reply["reply"].startswith("Switched to a luxury look") and reply["model"] == "fake:designer"
    assert reply["options"]["page_style"] == "luxury" and reply["options"]["theme_color"] == "#14532d"
    assert reply["options"]["shipping_fee"] == 250  # major units from the model, minor units in the store
    assert reply["options"]["quick_add"] == site["options"]["quick_add"]  # null leaves an option alone
    assert set(reply["changed"]) == {"page_style", "theme_color", "shipping_fee", "hero_text"}  # urgency was already off
    system, user = fake.calls[0]
    assert "luxury" in system and "major units of USD" in system and "Write reply in English." in system
    assert "page_style: classic" in user and user.endswith("Owner: Make it feel premium and calm, cheaper delivery")
    assert client.get(f"/api/projects/{PID}/online/sites/{site['id']}").json()["options"] == site["options"]

    # The next turn edits the draft, not the saved store, and sees the whole conversation.
    _fake(monkeypatch, {"quick_add": True, "reply": "Added add-to-cart buttons to the cards."})
    r = client.post(url, json={"options": reply["options"], "messages": [
        {"role": "owner", "text": "Make it feel premium and calm, cheaper delivery"},
        {"role": "designer", "text": reply["reply"], "changed": reply["changed"]},
        {"role": "owner", "text": "Also let people add to cart from the list"},
    ]})
    second = r.json()
    assert second["options"]["page_style"] == "luxury" and second["options"]["quick_add"] is True
    assert second["changed"] == ["quick_add"]


def test_a_question_back_changes_nothing_and_bad_proposals_are_refused(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "pet_store"}).json()
    url = f"/api/projects/{PID}/online/sites/{site['id']}/design-chat"
    fake = _fake(monkeypatch, {"reply": "Which colour would you like?"})
    r = client.post(url, json={"messages": [{"role": "owner", "text": "Change the colour"}]}).json()
    assert r["changed"] == [] and r["options"] == site["options"] and len(fake.calls) == 1
    _fake(monkeypatch, {"grid_columns": 9, "reply": "Done."})
    r = client.post(url, json={"messages": [{"role": "owner", "text": "Nine columns please"}]})
    assert r.status_code == 502 and "could not be changed" in r.json()["detail"]
    r = client.post(url, json={"messages": [{"role": "designer", "text": "Hello"}]})
    assert r.status_code == 400


def test_an_unsaved_design_can_be_previewed(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "pet_store"}).json()
    url = f"/api/projects/{PID}/online/sites/{site['id']}/preview.png"
    saved = client.get(url).content
    draft = client.post(url, json={"options": {**site["options"], "page_style": "neon"}})
    assert draft.status_code == 200 and draft.headers["content-type"] == "image/png" and draft.content != saved
    assert client.post(url, json={"options": site["options"]}).content == saved
    assert client.post(url, json={"options": {**site["options"], "grid_columns": 9}}).status_code == 422


def test_a_reply_that_sets_nothing_is_asked_again_once(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "pet_store"}).json()
    url = f"/api/projects/{PID}/online/sites/{site['id']}/design-chat"
    fake = _fake(monkeypatch, {"reply": "I made it neon."}, {"page_style": "neon", "reply": "It is neon now."})
    r = client.post(url, json={"messages": [{"role": "owner", "text": "Make it neon"}]}).json()
    assert r["changed"] == ["page_style"] and r["reply"] == "It is neon now."
    assert len(fake.calls) == 2 and fake.calls[1][1].endswith("Set every option you change, or ask a question.")
    # A second empty answer is passed on as it is: the owner sees that nothing changed.
    _fake(monkeypatch, {"reply": "I made it neon."}, {"reply": "I made it neon."})
    r = client.post(url, json={"messages": [{"role": "owner", "text": "Make it neon"}]}).json()
    assert r["changed"] == [] and r["options"] == site["options"]

@pytest.mark.parametrize("character", ["A", "한", "🛍"])
def test_long_history_keeps_current_design_and_the_full_latest_request(client, monkeypatch, character):
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "pet_store"}).json()
    options = {**site["options"], "theme_color": "#ABCDEF", "shipping_fee": 1234}
    latest = "Latest request: " + character * 1100
    messages = [{"role": "owner" if i % 2 == 0 else "designer", "text": f"Old request {i}: " + character * 1100}
                for i in range(38)] + [{"role": "owner", "text": latest}]
    fake = _fake(monkeypatch, {"reply": "Which design option should I change?"})
    response = client.post(f"/api/projects/{PID}/online/sites/{site['id']}/design-chat",
                           json={"options": options, "messages": messages})
    assert response.status_code == 200, response.text
    assert response.json()["options"] == options
    prompt = fake.calls[0][1]
    assert "theme_color: #ABCDEF" in prompt and "12.34" in prompt
    assert "Old request 0:" not in prompt
    assert prompt.endswith("Owner: " + latest)
    conversation = prompt.split("\n\nConversation:\n", 1)[1]
    notice, recent = conversation.split("\n", 1)
    assert "Earlier messages omitted" in notice
    assert recent.startswith("Owner:")
    assert len(recent.encode("utf-8")) <= max(4000, len(("Owner: " + latest).encode("utf-8")))
    assert client.get(f"/api/projects/{PID}/online/sites/{site['id']}").json()["options"] == site["options"]
