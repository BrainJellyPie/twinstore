"""A survey must not reinterpret project shoppers' budgets in another currency."""

import io
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.domain.config import LLMConfig
from store_emulator.engine.shelf_lab.edits import synth_package

PID = "proj_67916afd"


@pytest.mark.parametrize("budget_currency,survey_currency,status", [
    ("USD", "JPY", 422), ("KRW", "USD", 422), ("KRW", "KRW", 200),
])
def test_survey_currency_matches_saved_budgets(tmp_path, monkeypatch, budget_currency, survey_currency, status):
    monkeypatch.chdir(tmp_path)
    from store_emulator.application import marketing
    from store_emulator.server.main import app
    submit = Mock()
    model = Mock(return_value=LLMConfig(model="fake"))
    monkeypatch.setattr(marketing.executor, "submit", submit)
    monkeypatch.setattr(marketing, "capture_llm_config", model)
    with TestClient(app) as client:
        metadata = tmp_path / ".data" / PID / "metadata.json"
        write_json(metadata, {**read_json(metadata), "currency": budget_currency})
        data = io.BytesIO()
        synth_package("Test").save(data, format="PNG")
        upload = client.post(f"/api/projects/{PID}/lab/packages", files={"image": ("test.png", data.getvalue(), "image/png")})
        assert upload.status_code == 200, upload.text
        response = client.post(f"/api/projects/{PID}/surveys", json={
            "stimuli": [upload.json()["asset_id"]], "questions": ["price_vw"], "currency": survey_currency,
        })
        assert response.status_code == status, response.text
        if status == 422:
            model.assert_not_called()
            submit.assert_not_called()
            assert client.get(f"/api/projects/{PID}/surveys").json() == []
        else:
            submit.assert_called_once()
