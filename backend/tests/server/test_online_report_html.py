"""An online run's report as one page to share: the verdict, every store, the paired differences and the questions
asked about the run, with every store-written text escaped."""

import time

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Analyst:
    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str, user_prompt: str,
                                                      **_: object) -> T:
        line = next(x for x in user_prompt.split("\n") if "minus control" in x)
        return response_model.model_validate({"answer": "No clear difference yet.", "figures": [line], "follow_ups": []})


def test_the_report_page_shows_the_run_and_the_questions_about_it(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from store_emulator.application import online

    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    variant = client.post(f"/api/projects/{PID}/online/sites/{site['id']}/copy",
                          json={"name": "Quick <b>add</b>", "options": {**site["options"], "quick_add": True}}).json()
    run = client.post(f"/api/projects/{PID}/online/runs", json={"site_ids": [site["id"], variant["id"]], "shoppers": 6}).json()
    for _ in range(300):
        if client.get(f"/api/projects/{PID}/online/runs/{run['run_id']}").json()["status"]["status"] == "completed":
            break
        time.sleep(0.1)
    monkeypatch.setattr(online, "assistive_client", lambda *_a, **_k: _Analyst())
    base = f"/api/projects/{PID}/online/runs/{run['run_id']}"
    assert client.post(f"{base}/analyst", json={"question": "Did quick add help?", "model": "openai/gpt-test"}).status_code == 200

    r = client.get(f"{base}/report.html")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    page = r.text
    assert page.startswith("<!doctype html>") and "online run report" in page
    assert "Quick &lt;b&gt;add&lt;/b&gt;" in page and "<b>add</b>" not in page
    assert "Variants against the control" in page and site["name"] in page
    assert any(call in page for call in ("wins:", "holds:", "Too close to call"))
    assert "Questions about this run" in page and "Did quick add help?" in page and "No clear difference yet." in page
    assert "<script" not in page  # self-contained and static

    saved = client.get(f"{base}/report.html", params={"download": True})
    assert f'filename="{run["run_id"]}-report.html"' in saved.headers["content-disposition"]
    assert client.get(f"/api/projects/{PID}/online/runs/nope/report.html").status_code == 404
