import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.setups import metadata_path

PID = "proj_67916afd"
ROOT = f"/api/projects/{PID}/price-checks"
HEADER = b"check_id,sku,pack_reference,checked_on,currency,price_minor,terms\n"
LABEL = HEADER + b"a,tea,box,2026-10-21,USD,100,public\n"
CHECKOUT = HEADER + b"a,tea,box,2026-10-21,USD,110,public\n"
SCOPE = {"store_ref": "ours", "audit_date": "2026-10-21"}


def files(labels=LABEL, checkouts=CHECKOUT):
    return {"labels": ("labels.csv", labels), "checkouts": ("checkout.csv", checkouts)}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client: yield client


def test_api_preview_template_and_export(client):
    assert client.get(ROOT + "/template.csv").status_code == 200
    before = metadata_path(PID).read_bytes()
    response = client.post(ROOT + "/preview", files=files(), data=SCOPE)
    assert response.status_code == 200, response.text
    result = response.json(); assert result["rows"][0]["difference_minor"] == 10
    exported = client.post(ROOT + "/export.csv", files=files(), data={**SCOPE, "source_sha256": result["source_sha256"]})
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    assert result["source_sha256"] in exported.text
    assert metadata_path(PID).read_bytes() == before


@pytest.mark.parametrize("suffix", ["preview", "export.csv"])
def test_input_errors_boundaries_and_missing_project(client, suffix):
    digest = client.post(ROOT + "/preview", files=files(), data=SCOPE).json()["source_sha256"]
    form = {**SCOPE, "source_sha256": digest}
    for changes in [{"store_ref": " "}, {"store_ref": "x" * 121}, {"store_ref": "x\u200b"}, {"audit_date": "2026-02-29"}, {"audit_date": "0"}, {"audit_date": "1792540800"}]:
        response = client.post(ROOT + "/" + suffix, files=files(), data={**form, **changes})
        assert response.status_code == 422, (changes, response.text)
    assert client.post(ROOT + "/" + suffix, files={"labels": ("x.csv", LABEL)}, data=form).status_code == 422
    for label, checkout in [(b"bad", CHECKOUT), (LABEL, b"\xff"), (HEADER, HEADER), (LABEL, CHECKOUT + CHECKOUT.splitlines(keepends=True)[1])]:
        assert client.post(ROOT + "/" + suffix, files=files(label, checkout), data=form).status_code == 400
    for size, expected in [(2 * 1024 * 1024, 400), (2 * 1024 * 1024 + 1, 413)]:
        for label, checkout in [(b"x" * size, CHECKOUT), (LABEL, b"x" * size)]:
            assert client.post(ROOT + "/" + suffix, files=files(label, checkout), data=form).status_code == expected
    metadata_path(PID).unlink()
    assert client.get(ROOT + "/template.csv").status_code == 404
    assert client.post(ROOT + "/" + suffix, files=files(), data=form).status_code == 404


def test_export_rejects_either_changed_source_changed_scope_and_swapped_sides(client):
    digest = client.post(ROOT + "/preview", files=files(), data=SCOPE).json()["source_sha256"]
    for sources, changes in [(files(CHECKOUT, LABEL), {}), (files(HEADER, CHECKOUT), {}), (files(LABEL, HEADER), {}), (files(), {"store_ref": "another"}), (files(), {"audit_date": "2026-10-20"})]:
        response = client.post(ROOT + "/export.csv", files=sources, data={**SCOPE, **changes, "source_sha256": digest})
        assert response.status_code == 409, response.text
    assert client.post(ROOT + "/export.csv", files=files(), data={**SCOPE, "source_sha256": "bad"}).status_code == 422


def test_concurrent_reviews_and_exports_are_isolated_and_read_only(client, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    before = {str(p): p.read_bytes() for p in (tmp_path / ".data").rglob("*") if p.is_file()}
    def review(store):
        scope = {**SCOPE, "store_ref": store}
        result = client.post(ROOT + "/preview", files=files(), data=scope)
        assert result.status_code == 200
        digest = result.json()["source_sha256"]
        exported = client.post(ROOT + "/export.csv", files=files(), data={**scope, "source_sha256": digest})
        assert exported.status_code == 200 and digest in exported.text
        return digest
    with ThreadPoolExecutor(max_workers=2) as pool: digests = list(pool.map(review, ["one", "two"]))
    assert len(set(digests)) == 2
    assert {str(p): p.read_bytes() for p in (tmp_path / ".data").rglob("*") if p.is_file()} == before
