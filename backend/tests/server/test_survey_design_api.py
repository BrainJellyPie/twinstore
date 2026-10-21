"""A concept test drafted from a question: library images by name, checked questions, price in minor units and
quotas from the persona groups (fake model, no network)."""

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


def _library(monkeypatch, sku: str = "") -> None:
    from store_emulator.application import shelf_lab
    assets = [shelf_lab.PackageAsset(asset_id="pkg_a", name="Label Gold", width=10, height=10, brand="Tea Co", sku=sku),
              shelf_lab.PackageAsset(asset_id="pkg_b", name="Label Leaf", width=10, height=10, brand="Tea Co")]
    monkeypatch.setattr(shelf_lab, "list_packages", lambda pid: assets)


DRAFT = {
    "name": "Premium labels", "images": ["label gold", '"Label Leaf", brand Tea Co', "Label Gold", "Label Moon"],
    "questions": ["open", "appeal", "preference", "price_vw"], "context": "A new bottled green tea, 500 ml.",
    "reference_price": 1.99, "age_groups": ["20s"], "genders": [], "rationale": "Twenties compare two labels.",
}


def test_a_question_becomes_a_builder_ready_concept_test(client, monkeypatch):
    from store_emulator.application import study_design
    _library(monkeypatch)
    fake = _Designer(DRAFT)
    monkeypatch.setattr(study_design, "build_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/surveys/design",
                    json={"question": "Which label looks more premium to people in their twenties?", "currency": "USD"})
    assert r.status_code == 200, r.text
    d = r.json()
    # Names resolve to library ids in order, duplicates once; an unknown image is reported, not invented.
    assert d["stimuli"] == ["pkg_a", "pkg_b"] and d["stimulus_names"] == ["Label Gold", "Label Leaf"]
    assert any("Label Moon" in w for w in d["warnings"])
    # Questions keep the builder's order; preference stays because two images are shown.
    assert d["questions"] == ["appeal", "price_vw", "preference", "open"]
    assert d["reference_price"] == 199 and d["currency"] == "USD" and d["age_groups"] == ["20s"] and d["genders"] == []
    system, user = fake.calls[0]
    assert "major units of USD" in system and '- "Label Gold", brand Tea Co' in user


def test_one_image_drops_preference_and_shelf_products_are_listed(client, monkeypatch):
    from store_emulator.application import study_design
    from store_emulator.application.scenarios import (
        _store_for,  # pyright: ignore[reportPrivateUsage]
    )
    store = _store_for(PID, SETUP)
    assert store is not None
    item = store.product_racks[0].slots[0].items[0]
    _library(monkeypatch, sku=item.sku)
    fake = _Designer({**DRAFT, "images": ["Label Gold"], "reference_price": 1500})
    monkeypatch.setattr(study_design, "build_client", lambda *a, **k: fake)
    d = client.post(f"/api/projects/{PID}/surveys/design",
                    json={"question": "Would our gold label sell?", "setup_id": SETUP, "currency": "KRW"}).json()
    assert d["stimuli"] == ["pkg_a"] and "preference" not in d["questions"] and d["reference_price"] == 1500
    assert f'"Label Gold", brand Tea Co, shows {item.name} at' in fake.calls[0][1]


def test_an_empty_library_and_a_failing_model_are_explained(client, monkeypatch):
    from store_emulator.application import shelf_lab, study_design
    monkeypatch.setattr(shelf_lab, "list_packages", lambda pid: [])
    monkeypatch.setattr(study_design, "build_client", lambda *a, **k: _Designer({**DRAFT, "reference_price": None}))
    d = client.post(f"/api/projects/{PID}/surveys/design", json={"question": "Which label is best?"}).json()
    assert d["stimuli"] == [] and d["reference_price"] is None
    assert any("no images yet" in w for w in d["warnings"])
    monkeypatch.setattr(study_design, "build_client", lambda *a, **k: _Designer({"name": "x", "questions": []}))
    r = client.post(f"/api/projects/{PID}/surveys/design", json={"question": "Which label is best?"})
    assert r.status_code == 502 and "could not be drafted" in r.json()["detail"]
