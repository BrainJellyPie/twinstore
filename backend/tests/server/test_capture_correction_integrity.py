"""Corrections must not duplicate one source product or persist blank names."""

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.io import write_json
from store_emulator.domain.capture import Box, CaptureItem, CaptureResult, CaptureStatus


@pytest.fixture
def capture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / ".data" / "proj_test" / "captures" / "cap_test"
    result = CaptureResult(image_size=(90, 60), items=[
        CaptureItem(id=f"i{i}", band=0, level=1, order=i - 1, name=f"Tea {i}", sku=f"tea{i}", price=100,
                    labeled=True, boxes=[Box(x1=(i - 1) * 30, y1=5, x2=i * 30, y2=45)]) for i in range(1, 4)
    ])
    write_json(folder / "result.json", result.model_dump(mode="json"))
    write_json(folder / "status.json", CaptureStatus(capture_id="cap_test", status="completed").model_dump(mode="json"))
    Image.new("RGB", (90, 60)).save(folder / "image.jpg")
    Image.new("RGB", (90, 60)).save(folder / "overlay.png")
    from store_emulator.server.main import app
    return TestClient(app), folder


@pytest.mark.parametrize("items", [
    [{"id": "i1", "name": "Tea", "merged_from": ["i2", "i2"]}],
    [{"id": "i1", "name": "Tea", "merged_from": ["i3"]}, {"id": "i2", "name": "Juice", "merged_from": ["i3"]}],
])
def test_each_source_can_only_be_merged_once(capture, items):
    client, folder = capture
    previous = {p.name: p.read_bytes() for p in folder.iterdir()}
    response = client.put("/api/projects/proj_test/captures/cap_test", json={"items": items})
    assert response.status_code == 400, response.text
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == previous


@pytest.mark.parametrize("name", [" ", "\t\n", "\u3000"])
def test_blank_name_does_not_replace_recognized_product(capture, name):
    client, folder = capture
    previous = {p.name: p.read_bytes() for p in folder.iterdir()}
    response = client.put("/api/projects/proj_test/captures/cap_test", json={"items": [{"id": "i1", "name": name}]})
    assert response.status_code == 422, response.text
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == previous


def test_valid_merge_preserves_each_source_box_and_trims_name(capture):
    client, _ = capture
    response = client.put("/api/projects/proj_test/captures/cap_test", json={"items": [
        {"id": "i1", "name": "  Tea  ", "merged_from": ["i2", "i3"], "facings": 3},
    ]})
    assert response.status_code == 200, response.text
    items = response.json()["result"]["items"]
    assert len(items) == 1 and items[0]["name"] == "Tea"
    assert len(items[0]["boxes"]) == 3 and items[0]["facings"] == 3
