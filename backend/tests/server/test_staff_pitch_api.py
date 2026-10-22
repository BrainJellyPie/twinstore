import csv
import io
import json
import time

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import marketing, staff_pitch
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.domain.marketing import JobStatus

PID = "proj_67916afd"
SETUP = "setup_7d6d"
ROOT = f"/api/projects/{PID}/staff-pitches"


class FakeLLM:
    async def generate_structured_async(self, response_model, system_prompt, user_prompt, *, max_retries=1, seed=None):
        data = json.loads(user_prompt)
        return response_model.model_validate({
            "purchase_intent": 4 if "compare" in data["employee_script"] else 3,
            "trust": 4, "pressure": 1, "reply": '=HYPERLINK("example")', "reason": "The product suits my trip.",
        })


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    monkeypatch.setattr(staff_pitch, "build_client", lambda *args, **kwargs: FakeLLM())
    monkeypatch.setattr(staff_pitch, "assistive_client", lambda *args, **kwargs: FakeLLM())
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def body(**changes):
    return {"setup_id": SETUP, "sku": "A0017", "panel": 20, "seed": 6, "context": "Browsing a shelf.",
            "variants": [{"name": "Current", "script": "Can I help?"}, {"name": "Helpful", "script": "Would you like to compare these?"}],
            **changes}


def wait(client, jid):
    for _ in range(100):
        data = client.get(f"{ROOT}/{jid}").json()
        if data["status"] in ("completed", "failed"):
            return data
        time.sleep(0.02)
    raise AssertionError("Staff script job did not finish")


def test_staff_script_job_snapshot_export_and_delete(client, tmp_path):
    response = client.post(ROOT, json=body())
    assert response.status_code == 200, response.text
    jid = response.json()["job_id"]
    assert response.json()["kind"] == "pitch"
    result = wait(client, jid)
    assert result["status"] == "completed", result
    report = result["report"]
    assert (report["attempted"], report["pairs"], report["excluded"]) == (20, 20, 0)
    assert report["screening_leader"] == "B" and report["request"]["seed"] == 6
    saved = tmp_path / ".data" / PID / "marketing" / "pitches" / jid
    inputs = read_json(saved / "inputs.json")
    assert len(inputs["personas"]) == 20 and inputs["product"]["sku"] == "A0017"
    assert "api_key" not in (saved / "inputs.json").read_text()
    assert read_json(saved / "request.json") == report["request"]
    assert client.get(ROOT).json()[0]["job_id"] == jid
    export = client.get(f"{ROOT}/{jid}/export.csv")
    assert export.status_code == 200 and "attachment" in export.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert len(rows) == 40 and {row["included_pair"] for row in rows} == {"1"}
    assert all(row["reply"].startswith("'=") for row in rows)
    assert rows[0]["script"] == "Can I help?" and rows[1]["script"] == "Would you like to compare these?"
    assert client.delete(f"{ROOT}/{jid}").status_code == 204
    assert client.get(f"{ROOT}/{jid}").status_code == 404


def test_staff_scripts_keep_the_layout_currency(client, tmp_path):
    from store_emulator.application.storage.setups import metadata_path
    path = metadata_path(PID)
    write_json(path, {**read_json(path), "currency": "JPY"})
    sid = client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "specialty_cafe", "currency": "JPY"}).json()["id"]
    store = client.get(f"/api/projects/{PID}/setups/{sid}").json()["store"]
    sku = next(i["sku"] for r in store["racks"] for s in r["slots"] for i in s["items"])
    response = client.post(ROOT, json=body(setup_id=sid, sku=sku))
    assert response.status_code == 200, response.text
    report = wait(client, response.json()["job_id"])["report"]
    assert report["product"]["currency"] == "JPY"


@pytest.mark.parametrize("change,code", [
    ({"sku": "missing"}, 400), ({"setup_id": "../escape"}, 400), ({"setup_id": "setup_missing"}, 404),
    ({"panel": 2}, 422), ({"context": " "}, 422),
])
def test_invalid_request_creates_no_job(client, change, code):
    assert client.post(ROOT, json=body(**change)).status_code == code
    assert client.get(ROOT).json() == []


def test_model_failures_are_failed_jobs_not_fake_success(client, monkeypatch, tmp_path):
    class Broken(FakeLLM):
        async def generate_structured_async(self, *args, **kwargs):
            raise RuntimeError("secret in provider body")

    monkeypatch.setattr(staff_pitch, "build_client", lambda *args, **kwargs: Broken())

    monkeypatch.setattr(staff_pitch, "assistive_client", lambda *args, **kwargs: Broken())
    jid = client.post(ROOT, json=body()).json()["job_id"]
    result = wait(client, jid)
    assert result["status"] == "failed" and result["report"] is None
    assert "secret" not in result["error"]
    saved = tmp_path / ".data" / PID / "marketing" / "pitches" / jid
    assert len(read_json(saved / "answers.json")) == 20
    assert client.get(f"{ROOT}/{jid}/export.csv").status_code == 409


def test_recovery_and_busy_delete(client, tmp_path):
    path = tmp_path / ".data" / PID / "marketing" / "pitches" / "pit_pending" / "status.json"
    write_json(path, JobStatus(job_id="pit_pending", kind="pitch", status="running").model_dump())
    assert client.delete(f"{ROOT}/pit_pending").status_code == 409
    assert client.delete(f"/api/projects/{PID}").status_code == 409
    assert marketing.recover_running_jobs() == 1
    result = client.get(f"{ROOT}/pit_pending").json()
    assert result["status"] == "failed" and "restart" in result["error"]
    assert client.delete(f"{ROOT}/pit_pending").status_code == 204
