import csv
import io

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.setups import metadata_path

PID = "proj_67916afd"
ROOT = f"/api/projects/{PID}/unit-prices"
HEADER = "offer_id,comparison_group,retailer,observed_on,currency,pack_count,quantity_per_pack,unit,price_minor,availability,terms\n"
DATA = (HEADER + "tea,tea,ours,2026-10-21,USD,2,250,g,300,in_stock,public\n" + "tea,tea,other,2026-10-21,USD,1,0.5,kg,250,in_stock,public\n").encode()
SCOPE = {"focal_retailer": "ours", "as_of": "2026-10-21", "max_age_days": "7"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client: yield client


def test_connected_preview_template_and_export_do_not_change_project(client):
    assert client.get(ROOT + "/template.csv").text == "\ufeff" + HEADER.replace("\n", "\r\n")
    before = metadata_path(PID).read_bytes()
    response = client.post(ROOT + "/preview", files={"file": ("offers.csv", DATA)}, data=SCOPE)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["comparisons"][0]["gap_percent"] == "20"
    exported = client.post(ROOT + "/export.csv", files={"file": ("offers.csv", DATA)}, data={**SCOPE, "source_sha256": result["source_sha256"]})
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert rows[0]["source_sha256"] == result["source_sha256"] and rows[-1]["gap_minor"] == "100"
    assert metadata_path(PID).read_bytes() == before


@pytest.mark.parametrize("suffix", ["preview", "export.csv"])
def test_api_validation_size_stale_source_and_deleted_project(client, suffix):
    import hashlib
    form = {**SCOPE, "source_sha256": hashlib.sha256(DATA).hexdigest()}
    cases = [(b"bad", {}, 400), (DATA, {"focal_retailer": "missing"}, 400), (DATA, {"focal_retailer": " ours"}, 422),
        (DATA, {"as_of": "2026-02-29"}, 422), (DATA, {"max_age_days": "-1"}, 422), (DATA, {"max_age_days": "366"}, 422),
        (DATA, {"max_age_days": "NaN"}, 422), (DATA, {"max_age_days": "1.5"}, 422),
        (DATA.replace(b",250,g,", b",0.5,item,"), {}, 400),
        (b"x" * (2 * 1024 * 1024), {}, 400), (b"x" * (2 * 1024 * 1024 + 1), {}, 413)]
    for data, changes, expected in cases:
        response = client.post(ROOT + "/" + suffix, files={"file": ("offers.csv", data)}, data={**form, **changes})
        assert response.status_code == expected, response.text
    if suffix == "export.csv":
        response = client.post(ROOT + "/" + suffix, files={"file": ("offers.csv", DATA.replace(b",300,", b",200,"))}, data=form)
        assert response.status_code == 409 and "changed" in response.text
    metadata_path(PID).unlink()
    assert client.get(ROOT + "/template.csv").status_code == 404
    assert client.post(ROOT + "/" + suffix, files={"file": ("offers.csv", DATA)}, data=form).status_code == 404


def test_independent_concurrent_reviews_and_exports(client, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    before = {str(p): p.read_bytes() for p in (tmp_path / ".data").rglob("*") if p.is_file()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda data: client.post(ROOT + "/preview", files={"file": ("offers.csv", data)}, data=SCOPE), [DATA, DATA.replace(b",300,", b",200,")]))
    assert all(r.status_code == 200 for r in responses)
    assert [r.json()["comparisons"][0]["relation"] for r in responses] == ["above", "below"]
    assert responses[0].json()["source_sha256"] != responses[1].json()["source_sha256"]
    assert {str(p): p.read_bytes() for p in (tmp_path / ".data").rglob("*") if p.is_file()} == before
