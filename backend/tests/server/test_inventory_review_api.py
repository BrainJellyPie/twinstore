import csv
import io

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.setups import metadata_path

PID = "proj_67916afd"
ROOT = f"/api/projects/{PID}/inventory-review"
HEADER = "sku,opening_units,received_units,sold_units,returned_units,other_in_units,other_out_units,closing_units,net_sales_minor,cogs_minor,opening_cost_minor,closing_cost_minor\n"
DATA = (HEADER + "tea,10,0,4,0,0,0,6,800,400,1000,600\n").encode()
PERIOD = {"start_date": "2026-10-01", "end_date": "2026-10-31", "currency": "USD"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client: yield client


def test_template_preview_and_export_are_connected_and_read_only(client):
    template = client.get(ROOT + "/template.csv")
    assert template.status_code == 200 and template.text == "\ufeff" + HEADER.replace("\n", "\r\n")   # BOM: Excel opens UTF-8
    before = metadata_path(PID).read_bytes()
    response = client.post(ROOT + "/preview", files={"file": ("stock.csv", DATA)}, data=PERIOD)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["rows"][0]["inputs"]["opening_units"] == "10"
    assert result["rows"][0]["gmroi"] == 0.5 and result["totals"]["reconciled_skus"] == 1
    export = client.post(ROOT + "/export.csv", files={"file": ("stock.csv", DATA)}, data=PERIOD)
    assert export.status_code == 200 and "attachment" in export.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(export.text.removeprefix("\ufeff"))))
    assert rows[0]["source_sha256"] == result["source_sha256"] and rows[-1]["row_type"] == "portfolio"
    assert metadata_path(PID).read_bytes() == before


@pytest.mark.parametrize("suffix", ["preview", "export.csv"])
def test_invalid_uploads_periods_deleted_projects_and_limits(client, suffix):
    before = metadata_path(PID).read_bytes()
    for data, changes, status in [(b"bad", {}, 400), (DATA, {"currency": "usd"}, 422),
        (DATA, {"end_date": "2026-09-30"}, 422), (DATA, {"start_date": "2026-02-29"}, 422),
        (DATA, {"end_date": "2039-01-01"}, 422), (b"x" * (2 * 1024 * 1024 + 1), {}, 413)]:
        r = client.post(ROOT + "/" + suffix, files={"file": ("stock.csv", data)}, data={**PERIOD, **changes})
        assert r.status_code == status, r.text
    assert metadata_path(PID).read_bytes() == before
    metadata_path(PID).unlink()
    assert client.post(ROOT + "/" + suffix, files={"file": ("stock.csv", DATA)}, data=PERIOD).status_code == 404
    assert client.get(ROOT + "/template.csv").status_code == 404


def test_concurrent_reviews_do_not_share_or_save_sources(client, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    before = {str(p): p.read_bytes() for p in (tmp_path / '.data').rglob('*') if p.is_file()}
    changed = DATA.replace(b",800,400,", b",400,400,")
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda data: client.post(ROOT + "/preview", files={"file": ("stock.csv", data)}, data=PERIOD), [DATA, changed]))
    assert all(r.status_code == 200 for r in replies)
    assert [r.json()["totals"]["gmroi"] for r in replies] == [0.5, 0]
    assert replies[0].json()["source_sha256"] != replies[1].json()["source_sha256"]
    assert {str(p): p.read_bytes() for p in (tmp_path / '.data').rglob('*') if p.is_file()} == before
