"""The project list carries the active layout's fixtures as rectangles for the gallery tile."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.projects import _footprint  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def test_the_sample_project_lists_its_layout_footprint(client):
    sample = next(p for p in client.get("/api/projects").json() if p["project_id"] == "proj_67916afd")
    fp = sample["footprint"]
    assert fp["grid"] == [8, 6] and fp["racks"]
    assert all(len(r) == 5 and r[4] in ("shelf", "fridge", "counter", "table") for r in fp["racks"])
    assert all(0 <= r[0] < 8 and 0 <= r[1] < 6 for r in fp["racks"])


def test_rotated_and_odd_fixtures():
    store = {"grid_size": [10, 6], "racks": [
        {"type": "shelf", "shape": [[1, 1, 1]], "position": [2, 3], "rotation": 90},
        {"type": "fridge", "shape": [[1, 1]], "position": [0, 0]},
        {"type": "entrance", "shape": [[1]], "position": [5, 5]},
        {"type": "shelf", "shape": [], "position": [1, 1]},
    ]}
    assert _footprint(store) == {"grid": [10, 6], "racks": [[2, 3, 1, 3, "shelf"], [0, 0, 2, 1, "fridge"]]}
    assert _footprint({"grid_size": "8x6"}) is None
