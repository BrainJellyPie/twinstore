"""A run saved by an older version shows the figures added since, worked out from its saved shoppers."""

import json
import shutil
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


@pytest.mark.parametrize("relative,damaged", [
    ("input/store.json", "{}"),
    ("output/personas.json", "[{}]"),
    ("output/pathcalc_heatmap.json", "null"),
])
def test_cached_enrichment_rechecks_changed_inputs_without_rewriting_them(client, tmp_path, relative, damaged):
    url = f"/api/projects/{PID}/runs/{RUN}/summary"
    assert "conversion_rate" in client.get(url).json()["summary"]
    base = _summary_file(tmp_path).parents[1]
    (base / relative).write_text(damaged)
    before = {str(path.relative_to(base)): path.read_bytes() for path in base.rglob("*") if path.is_file()}
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["summary"] == json.loads(_summary_file(tmp_path).read_text())
    assert {str(path.relative_to(base)): path.read_bytes() for path in base.rglob("*") if path.is_file()} == before


def test_copied_data_roots_do_not_share_cached_enrichment(client, tmp_path, monkeypatch):
    url = f"/api/projects/{PID}/runs/{RUN}/summary"
    assert "conversion_rate" in client.get(url).json()["summary"]
    other = tmp_path / "second-data-root"
    target = other / ".data" / PID / "runs" / RUN
    shutil.copytree(_summary_file(tmp_path).parents[1], target)
    (target / "input" / "store.json").write_text("{}")
    with monkeypatch.context() as context:
        context.chdir(other)
        response = client.get(url)
    assert response.status_code == 200
    assert response.json()["summary"] == json.loads(_summary_file(tmp_path).read_text())


@pytest.mark.parametrize("conversion", [0, 0.5, 1])
def test_modern_summaries_keep_their_saved_values_without_loading_shoppers(client, tmp_path, conversion):
    path = _summary_file(tmp_path)
    saved = {**json.loads(path.read_text()), "conversion_rate": conversion, "avg_basket_value": 0}
    path.write_text(json.dumps(saved))
    path.with_name("timeline.json").unlink()
    before = path.read_bytes()
    response = client.get(f"/api/projects/{PID}/runs/{RUN}/summary")
    assert response.status_code == 200 and response.json()["summary"] == saved
    assert path.read_bytes() == before


@pytest.mark.parametrize("name", ["personas.json", "pathcalc_heatmap.json"])
def test_optional_inputs_can_disappear_after_a_cached_read(client, tmp_path, name):
    from store_emulator.application.simulation import get_run_summary

    before = get_run_summary(PID, RUN)
    assert isinstance(before, dict)
    _summary_file(tmp_path).with_name(name).unlink()
    after = get_run_summary(PID, RUN)
    assert isinstance(after, dict)
    assert after["conversion_rate"] == before["conversion_rate"]
    assert after["units_sold"] == before["units_sold"]
    assert after["impulse_revenue_share"] is None


def test_a_damaged_timeline_can_be_repaired_after_a_cached_read(client, tmp_path):
    url = f"/api/projects/{PID}/runs/{RUN}/summary"
    before = client.get(url).json()["summary"]
    path = _summary_file(tmp_path).with_name("timeline.json")
    original = path.read_bytes()
    path.write_text("[{}]")
    assert "conversion_rate" not in client.get(url).json()["summary"]
    path.write_bytes(original)
    assert client.get(url).json()["summary"] == before
    assert path.read_bytes() == original
