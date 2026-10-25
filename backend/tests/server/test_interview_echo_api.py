"""Question echoes are errors, not persisted customer answers or group themes."""

import pytest

from store_emulator.application import interview
from tests.server.test_interview_api import PID, RUN, _shopper, client


class Echo:
    def __init__(self, echoes):
        self.echoes = echoes

    async def generate_structured_async(self, schema, system, user, **kwargs):
        if "themes" in schema.model_fields:
            return schema.model_validate({"themes": ["Could not find the right size"], "assignments": [0, 0]})
        answer = "I couldn't find the size I wanted."
        if self.echoes:
            self.echoes -= 1
            answer = user.rsplit("Researcher: ", 1)[-1]
        return schema.model_validate({"answer": answer, "steps": [1]})


def test_echo_failure_does_not_append_a_transcript_and_the_user_can_retry(client, monkeypatch):
    sid = _shopper(client)
    url = f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview"
    model = Echo(1)
    monkeypatch.setattr(interview, "assistive_client", lambda *args, **kwargs: model)
    body = {"question": "Why did you leave?"}
    failed = client.post(url, json=body)
    assert failed.status_code == 502 and "repeated the question" in failed.text
    assert client.get(url).json()["messages"] == []
    recovered = client.post(url, json=body)
    assert recovered.status_code == 200 and len(recovered.json()["messages"]) == 2
    assert recovered.json()["messages"][1]["text"] == "I couldn't find the size I wanted."


@pytest.mark.parametrize("echoes", [1, 3])
def test_group_themes_exclude_echoed_questions(client, monkeypatch, echoes):
    url = f"/api/projects/{PID}/runs/{RUN}/group-interviews"
    model = Echo(echoes)
    monkeypatch.setattr(interview, "assistive_client", lambda *args, **kwargs: model)
    result = client.post(url, json={"question": "Why did you leave?", "size": 3})
    if echoes == 3:
        assert result.status_code == 502 and "repeated the question" in result.text
        assert client.get(url).json() == []
    else:
        assert result.status_code == 200, result.text
        group = result.json()
        assert group["errors"] == 1
        failed = [a for a in group["answers"] if a["error"]]
        assert len(failed) == 1 and failed[0]["answer"] == "" and failed[0]["theme"] == -1
        assert sum(t["count"] for t in group["themes"]) == 2
