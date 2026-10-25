"""Tests suggested from what shoppers said in a group interview or from the run analyst's answer (fake model)."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"
RUN = "run_efd57c"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Writer:
    def __init__(self, reply: dict[str, object]) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.prompts.append(user_prompt)
        return response_model.model_validate(self.reply)


TESTS = {"tests": [
    {"question": "Would a 20 % discount on Ice cream 1 sell more than today's price?", "kind": "ab_test", "why": "prices felt high"},
    {"question": "would a 20 %  discount on Ice cream 1 sell more than today's price?", "kind": "ab_test", "why": "dup"},
    {"question": "Short?", "kind": "shelf_test"},
    {"question": "Does a SALE sign make the ice cream stand out on its shelf?", "kind": "shelf_test", "why": "could not find it"},
]}


def _group(tmp_path) -> str:
    from store_emulator.application.interview import (
        _groups_dir,  # pyright: ignore[reportPrivateUsage]
    )
    from store_emulator.application.storage.io import write_json
    from store_emulator.domain.interview import GroupAnswer, GroupInterview, Theme
    group = GroupInterview(group_id="grp_test1", run_id=RUN, question="What would have made you buy?", segment="empty_handed",
                           answers=[GroupAnswer(persona_id="p", identity="Student", age_group="20s", gender="Female", spent=0,
                                                units=0, answer="The ice cream felt too expensive.")],
                           themes=[Theme(label="Prices felt high", count=1, share=1.0)])
    folder = _groups_dir(PID, RUN)
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "grp_test1.json", group.model_dump(mode="json"))
    return group.group_id


@pytest.mark.parametrize("spelling", ["exact", "mixed"])
def test_a_group_interview_becomes_test_questions(client, monkeypatch, tmp_path, spelling):
    from store_emulator.application import hypotheses
    gid = _group(tmp_path)
    fake = _Writer({"tests": [{**row, "kind": f" {row['kind'].upper()} "} for row in TESTS["tests"]]}
                   if spelling == "mixed" else TESTS)
    monkeypatch.setattr(hypotheses, "assistive_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/tests-to-run", json={"source": "group", "group_id": gid})
    assert r.status_code == 200, r.text
    assert [(t["kind"], t["question"][:20]) for t in r.json()] == [("ab_test", "Would a 20 % discoun"), ("shelf_test", "Does a SALE sign mak")]
    said = fake.prompts[0]
    assert "Themes (shoppers): Prices felt high (1)" in said and "The ice cream felt too expensive." in said and "Shelves: " in said
    assert client.post(f"/api/projects/{PID}/runs/{RUN}/tests-to-run", json={"source": "group", "group_id": "grp_none"}).status_code == 404


def test_the_analyst_answer_becomes_test_questions(client, monkeypatch):
    from store_emulator.application import hypotheses
    from store_emulator.application import run_analyst as analyst
    fake = _Writer(TESTS)
    monkeypatch.setattr(hypotheses, "assistive_client", lambda *a, **k: fake)
    empty = client.post(f"/api/projects/{PID}/runs/{RUN}/tests-to-run", json={"source": "analyst"})
    assert empty.status_code == 400 and "Ask the analyst" in empty.json()["detail"]

    class _Analyst:
        async def generate_structured_async[T: BaseModel](self, response_model: type[T], *_a: object, **_k: object) -> T:
            return response_model.model_validate({"answer": "Ice cream 2 converts worst.", "figures": [], "follow_ups": []})

    monkeypatch.setattr(analyst, "assistive_client", lambda *a, **k: _Analyst())
    assert client.post(f"/api/projects/{PID}/runs/{RUN}/analyst", json={"question": "Which shelf converts worst?"}).status_code == 200
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/tests-to-run", json={"source": "analyst"})
    assert r.status_code == 200 and len(r.json()) == 2
    assert "Manager asked: Which shelf converts worst?" in fake.prompts[0] and "Analyst answered: Ice cream 2 converts worst." in fake.prompts[0]
