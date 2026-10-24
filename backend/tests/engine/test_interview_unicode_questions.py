"""Distinct non-Latin model questions must survive follow-up and group-question deduplication."""

import asyncio
import json
import unicodedata

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.interview import InterviewMessage, Journey
from store_emulator.engine import llm_client
from store_emulator.engine.interview import suggest_follow_ups, suggest_group_questions
from tests.engine.test_llm_engine_offline import _persona
from tests.engine.test_llm_impulse_exposure import fixture


QUESTIONS = [
    ("왜 차를 골랐나요?", "가격은 어땠나요?", "진열은 어땠나요?"),
    ("为什么选择这款茶？", "价格怎么样？", "陈列怎么样？"),
    ("なぜこのお茶を選びましたか？", "価格はどうでしたか？", "陳列はどうでしたか？"),
    ("आपने चाय क्यों चुनी?", "कीमत कैसी थी?", "दुकान कैसी लगी?"),
    ("لماذا اخترت الشاي؟", "كيف كان السعر؟", "كيف كان العرض؟"),
]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["follow_up", "group"])
@pytest.mark.parametrize("questions", QUESTIONS)
def test_distinct_questions_survive_while_real_duplicates_are_removed(monkeypatch, tmp_path, mode, kind, questions):
    store, _ = fixture()
    journey = Journey(run_id="run-unicode", persona=_persona(), day=1, arrival_time="12:00:00", leave_time="12:01:00",
        engine_type="rule_based", currency="USD", total_spent=0, units=0, steps=[], path=[])
    candidates = [questions[0], questions[1], unicodedata.normalize("NFD", questions[1]), questions[2]]
    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = {"questions": candidates if kind == "follow_up" else [
            {"question": question, "segment": "all", "why": "Learn about the trip."} for question in candidates]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/unicode-questions", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for _ in range(2):
                if kind == "follow_up":
                    result = await suggest_follow_ups(client, journey, store,
                        [InterviewMessage(role="interviewer", text=questions[0])])
                    assert result == list(questions[1:])
                else:
                    result = await suggest_group_questions(client, "A shopper bought tea.")
                    assert [question.question for question in result] == list(questions)
            assert len(calls) == 1 and client.get_usage().cached_requests == 1

    asyncio.run(exercise())
