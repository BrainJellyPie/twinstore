"""The designer's style picker: a store's home page drawn in another style, without changing the store."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_a_store_previews_in_another_style_and_keeps_its_own(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "pet_store"}).json()
    assert site["options"]["page_style"] == "classic"
    url = f"/api/projects/{PID}/online/sites/{site['id']}/preview.png"
    own = client.get(url).content
    neon = client.get(url, params={"style": "neon"})
    assert neon.status_code == 200 and neon.headers["content-type"] == "image/png"
    assert neon.content != own
    assert client.get(url, params={"style": "classic"}).content == own
    assert client.get(url, params={"style": "gothic"}).status_code == 422
    assert client.get(f"/api/projects/{PID}/online/sites/{site['id']}").json()["options"]["page_style"] == "classic"


def test_templates_come_in_their_own_styles(client: TestClient) -> None:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "jewelry_accessories"}).json()
    assert site["options"]["page_style"] == "luxury"
