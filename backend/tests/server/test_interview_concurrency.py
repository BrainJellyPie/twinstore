"""Concurrent tabs must not erase or overwrite an interview in progress."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"
RUN = "run_efd57c"


@pytest.mark.parametrize("operation", ["ask", "clear"])
def test_same_shopper_rejects_overlapping_writes(tmp_path, monkeypatch, operation):
    monkeypatch.chdir(tmp_path)
    from store_emulator.application import interview
    from store_emulator.server.main import app
    entered, release = Event(), Event()
    calls = []

    class Model:
        async def generate_structured_async[T: BaseModel](self, response_model: type[T], *args, **kwargs) -> T:
            calls.append(args)
            if len(calls) == 1:
                entered.set()
                assert release.wait(10), "Test did not release the fake model"
            return response_model.model_validate({"answer": "I wanted a snack.", "steps": []})

    monkeypatch.setattr(interview, "assistive_client", lambda *args, **kwargs: Model())
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        shopper = client.get(f"/api/projects/{PID}/runs/{RUN}/timeline").json()[0]["persona_id"]
        url = f"/api/projects/{PID}/runs/{RUN}/shoppers/{shopper}/interview"
        pending = pool.submit(client.post, url, json={"question": "Why did you visit?"})
        try:
            assert entered.wait(5)
            other = client.delete(url) if operation == "clear" else client.post(url, json={"question": "And the prices?"})
            assert other.status_code == 409, other.text
            assert len(calls) == 1
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 200
        transcript = client.get(url).json()
        assert len(transcript["messages"]) == 2
        assert transcript["messages"][0]["text"] == "Why did you visit?"
        assert client.delete(url).status_code == 204
