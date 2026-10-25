"""Retain recent complete exchanges without crowding out the report or current question."""

import asyncio

import pytest
from pydantic import BaseModel

from store_emulator.domain.interview import AnalystMessage
from store_emulator.engine.run_analyst import answer_run_question


class Capture:
    user = ""

    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str,
                                                      user_prompt: str, **_: object) -> T:
        self.user = user_prompt
        return response_model.model_validate({"answer": "The run does not show that.", "figures": [], "follow_ups": []})


def ask(history, *, facts="The complete report.", question="What does this mean?", evidence=False):
    client = Capture()
    asyncio.run(answer_run_question(client, facts, question, history, require_numerical_evidence=evidence))
    return client.user


@pytest.mark.parametrize("evidence", [False, True])
def test_short_history_preserves_the_existing_prompt(evidence):
    history = [AnalystMessage(role="user", text="Why?"), AnalystMessage(role="analyst", text="We need more shoppers.")]
    assert ask(history, evidence=evidence) == (
        "Fact sheet:\nThe complete report.\n\nConversation so far:\nManager: Why?\nAnalyst: We need more shoppers.\n\nManager: What does this mean?")


@pytest.mark.parametrize("evidence", [False, True])
def test_recent_complete_exchange_wins_over_an_orphan_reply(evidence):
    history = [message for i in range(4) for message in [
        AnalystMessage(role="user", text=f"question-{i} " + "x" * 500),
        AnalystMessage(role="analyst", text=(f"answer-{i} " + "y" * 1500)[:1500])]]
    before = [message.model_dump() for message in history]
    prompt = ask(history, evidence=evidence)
    assert "Earlier conversation omitted" in prompt
    assert "question-3" in prompt and "answer-3" in prompt
    assert all(f"question-{i}" not in prompt and f"answer-{i}" not in prompt for i in range(3))
    assert [message.model_dump() for message in history] == before


@pytest.mark.parametrize("extra", [0, 1])
def test_budget_boundary_retains_whole_utf8_exchanges(extra):
    owner = "Older question"
    overhead = len(f"Manager: {owner}\nAnalyst: \n".encode())
    size = 4000 - overhead
    answer = "가" * (size // 3) + "x" * (size % 3) + "가" * extra
    prompt = ask([AnalystMessage(role="user", text=owner), AnalystMessage(role="analyst", text=answer)])
    if extra:
        assert owner not in prompt and answer not in prompt and "Earlier conversation omitted" in prompt
    else:
        assert owner in prompt and answer in prompt and "omitted" not in prompt


def test_oversized_history_never_truncates_facts_or_the_latest_question():
    facts = "모든 매장의 실험 결과와 구간입니다. " * 400
    question = "현재 질문은 그대로 유지해주세요. " * 25
    history = [AnalystMessage(role="user", text="Old question"), AnalystMessage(role="analyst", text="가" * 1500)]
    prompt = ask(history, facts=facts, question=question)
    assert prompt.startswith(f"Fact sheet:\n{facts}\n")
    assert prompt.endswith(f"Manager: {question.strip()}")
    assert "Old question" not in prompt and "가" * 1500 not in prompt


def test_an_existing_orphan_answer_is_not_presented_as_context():
    prompt = ask([AnalystMessage(role="analyst", text="Answer whose question is missing")])
    assert "Answer whose question is missing" not in prompt
