"""A layout design brief read into the template generator's options: each option checked against the current
choice, categories resolved to the format's own, the rest listed as not expressible (fake model, no network)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Reader:
    def __init__(self, reading: dict[str, object]) -> None:
        self.reading = reading
        self.calls: list[tuple[str, str]] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.calls.append((system_prompt, user_prompt))
        return response_model.model_validate(self.reading)


def _categories(client) -> list[dict[str, str]]:
    info = next(t for t in client.get("/api/store-templates").json() if t["id"] == "urban_cvs")
    return info["categories"]


def test_a_brief_becomes_checked_layout_options(client, monkeypatch):
    from store_emulator.application import layout_brief
    cats = _categories(client)
    fake = _Reader({
        "style": "loop", "density": "spacious", "width": 18, "depth": 12, "gate_wall": "front", "entrance": "center",
        "checkouts": 2, "checkout_placement": "near_entrance", "design_theme": "botanical",
        "design_colors": {"wall": "#E8F0E8", "accent": "sage"}, "aisle_width": 9,
        "excluded_categories": [cats[0]["label"], "Moon rocks"], "not_expressible": ["warm task lighting"],
        "rationale": "A calm loop with two tills by the door.",
    })
    monkeypatch.setattr(layout_brief, "assistive_client", lambda *a, **k: fake)
    r = client.post("/api/store-templates/urban_cvs/brief", json={
        "brief": "A calm loop, 18 by 12 cells, two tills by the door, botanical, sage walls, no first category, warm lights",
        "options": {"templateId": "urban_cvs", "seed": 0, "density": "balanced", "excluded_categories": []},
    })
    assert r.status_code == 200, r.text
    d = r.json()
    o = d["options"]
    assert o["style"] == "loop" and o["density"] == "spacious" and o["width"] == 18 and o["height"] == 12
    assert o["checkouts"] == 2 and o["checkout_placement"] == "near_entrance" and o["design_theme"] == "botanical"
    assert o["excluded_categories"] == [cats[0]["id"]]
    # An out-of-range aisle and a color that is not #rrggbb are reported, not applied; valid colors are kept.
    assert "aisle_width" not in o and o["design_colors"] == {"wall": "#e8f0e8"}
    assert any("Aisle width" in w for w in d["warnings"]) and any('accent color "sage"' in w for w in d["warnings"])
    assert any("Moon rocks" in w for w in d["warnings"])
    assert d["not_expressible"] == ["warm task lighting"] and "Style: loop" in d["applied"]
    _, user = fake.calls[0]
    assert "Format: Urban convenience store" in user and "Brief: A calm loop" in user


def test_unknown_formats_and_model_failures(client, monkeypatch):
    from store_emulator.application import layout_brief
    assert client.post("/api/store-templates/nowhere/brief", json={"brief": "a calm store"}).status_code == 404
    monkeypatch.setattr(layout_brief, "assistive_client", lambda *a, **k: _Reader({"style": "zigzag"}))
    r = client.post("/api/store-templates/urban_cvs/brief", json={"brief": "a zigzag store"})
    assert r.status_code == 502 and "could not be read" in r.json()["detail"]


@pytest.mark.parametrize("options", [
    {"excluded_categories": 3}, {"excluded_categories": {"tea": True}},
    {"density": "impossible"}, {"width": 100}, {"design_colors": {"wall": "sage"}},
    {"table_mix": {"two_seat": 2}, "dining_tables": 3},
])
def test_invalid_current_options_are_rejected_before_calling_a_model(client, monkeypatch, options):
    from store_emulator.application import layout_brief
    calls=[]
    def build(*args, **kwargs):
        calls.append(1)
        return _Reader({"style":"loop", "excluded_categories":["Tea"]})
    monkeypatch.setattr(layout_brief,"assistive_client",build)
    response=client.post("/api/store-templates/urban_cvs/brief",json={"brief":"Make a spacious store","options":options})
    assert response.status_code==422, response.text
    assert not calls
