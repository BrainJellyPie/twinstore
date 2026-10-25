"""Echoed questions cannot become persisted analyst messages."""

import pytest

from store_emulator.application import run_analyst
from tests.server.test_run_analyst_api import PID, RUN, client


@pytest.mark.parametrize("echo", ["current", "earlier"])
def test_failed_answer_preserves_thread_and_manual_retry_can_succeed(client, monkeypatch, echo):
    url = f"/api/projects/{PID}/runs/{RUN}/analyst"
    question = "How many visitors bought something?"

    class Model:
        repeat = False
        async def generate_structured_async(self, schema, system, user, **kwargs):
            answer = "Four visitors bought something."
            if self.repeat:
                answer = question if echo == "current" else "Which shelf sold the most?"
            return schema.model_validate({"answer": answer})

    model = Model()
    monkeypatch.setattr(run_analyst, "assistive_client", lambda *args, **kwargs: model)
    previous = client.post(url, json={"question": "Which shelf sold the most?"})
    assert previous.status_code == 200
    before = client.get(url).json()
    model.repeat = True
    failed = client.post(url, json={"question": question})
    assert failed.status_code == 502 and "repeated the question" in failed.text
    assert client.get(url).json() == before
    model.repeat = False
    recovered = client.post(url, json={"question": question})
    assert recovered.status_code == 200 and len(recovered.json()["messages"]) == 4
    assert recovered.json()["messages"][-1]["text"] == "Four visitors bought something."


def test_answer_may_quote_the_question_when_it_also_answers(client, monkeypatch):
    url = f"/api/projects/{PID}/runs/{RUN}/analyst"
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"answer": "How many visitors bought something? Four visitors did."})
    monkeypatch.setattr(run_analyst, "assistive_client", lambda *args, **kwargs: Model())
    result = client.post(url, json={"question": "How many visitors bought something?"})
    assert result.status_code == 200 and len(result.json()["messages"]) == 2
