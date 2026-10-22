"""A run saved by an older version shows the figures added since, worked out from its saved shoppers."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"
RUN = "run_ab0039"   # the bundled sample run, saved before conversion, basket and impulse share were summarized


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _summary_file(tmp_path: Path) -> Path:
    return tmp_path / ".data" / PID / "runs" / RUN / "output" / "summary.json"


def test_the_older_summary_gains_its_missing_figures_without_being_rewritten(client, tmp_path):
    before = _summary_file(tmp_path).read_bytes()
    assert "conversion_rate" not in json.loads(before)
    summary = client.get(f"/api/projects/{PID}/runs/{RUN}/summary").json()["summary"]
    saved = json.loads(before)
    assert summary["total_revenue"] == saved["total_revenue"] and summary["total_customers"] == saved["total_customers"]
    assert 0 < summary["conversion_rate"] <= 1 and summary["avg_basket_value"] > 0 and summary["units_sold"] > 0
    assert summary["impulse_revenue_share"] is None    # the run did not record which purchases were impulse buys
    assert _summary_file(tmp_path).read_bytes() == before


def test_a_summary_that_cannot_be_completed_is_shown_as_saved(client, tmp_path):
    (tmp_path / ".data" / PID / "runs" / RUN / "output" / "timeline.json").write_text("[{}]")
    summary = client.get(f"/api/projects/{PID}/runs/{RUN}/summary").json()["summary"]
    assert "conversion_rate" not in summary and summary["total_customers"] > 0
