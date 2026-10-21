"""Omitting capture currency inherits project units; explicit photo currencies remain valid."""

import io
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path

PID = "proj_67916afd"


@pytest.mark.parametrize("budget,explicit,expected", [("KRW", "", "KRW"), ("JPY", "", "JPY"), ("KRW", "JPY", "JPY")])
def test_capture_without_currency_uses_project_units(tmp_path, monkeypatch, budget, explicit, expected):
    monkeypatch.chdir(tmp_path)
    from store_emulator.application import capture
    from store_emulator.server.main import app
    submit = Mock()
    monkeypatch.setattr(capture.executor, "submit", submit)
    data = io.BytesIO()
    Image.new("RGB", (120, 120)).save(data, format="PNG")
    with TestClient(app) as client:
        path = metadata_path(PID)
        write_json(path, {**read_json(path), "currency": budget})
        response = client.post(f"/api/projects/{PID}/captures", files={"image": ("shelf.png", data.getvalue(), "image/png")},
                               data={"detector": "classic", "model": "none", "currency": explicit})
        assert response.status_code == 200, response.text
        assert response.json()["options"]["currency"] == expected
        assert submit.call_args.args[2].options.currency == expected
