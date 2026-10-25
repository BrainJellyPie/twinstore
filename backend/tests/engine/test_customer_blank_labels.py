"""Blank local-model labels must not become customer traits or grammar choices."""

import asyncio
import json
import re
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("pool", ["empty", "blank", "unicode", "mixed", "repeated"])
@pytest.mark.parametrize("traffic", ["blank", "mixed", "repeated"])
def test_blank_labels_preserve_customer_counts_and_use_valid_choices(monkeypatch, tmp_path, mode, pool, traffic):
    original = llm_client.litellm.acompletion
    calls = []
    blanks = {"empty": [], "blank": [""], "unicode": [" \t", "\u3000", "\n\r"],
              "mixed": ["", "\u3000"], "repeated": ["", "\u3000"]}[pool]
    identity, purpose = ("동네 주민", "茶와 간식") if pool in {"mixed", "repeated"} else ("shopper", "shopping")
    repeats = 3 if pool == "repeated" else 1

    def labels(section):
        return re.findall(r"^  - ([^\n]*)$", section, re.MULTILINE)

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if "hourly_profiles" in system:
            types = ["", "\u3000"] + ([f"  {identity}\t"] * (3 if traffic == "repeated" else 1) if traffic != "blank" else [])
            payload = {"hourly_profiles": [{"visitor_count": 3, "person_types": types}]}
        elif "personas" in system:
            ids, purposes = user.split("## purpose 목록", 1)
            count = len(re.findall(r"^\[\d+\] \d+시", user, re.MULTILINE))
            payload = {"personas": [dict(identity=labels(ids)[0], purpose=labels(purposes)[0],
                age_group="30s", gender="Female", description=f"Shopper {i}", intent="Groceries")
                for i in range(count)]}
        else:
            payload = {"keywords": blanks + (["  住宅街\t"] * repeats if pool in {"mixed", "repeated"} else []),
                       "identities": blanks + ([f"  {identity}\t"] * repeats if pool in {"mixed", "repeated"} else []),
                       "purposes": blanks + ([f"\u3000{purpose}  "] * repeats if pool in {"mixed", "repeated"} else [])}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/blank-labels", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def generate():
                return await gen.generate_batched(client, "offline", "동네 주민",
                    [DaySchedule(day=d, open_hour=9, close_hour=10) for d in [1, 7]], seed=42)

            people = await generate()
            assert {p.identity for p in people} == {identity}
            assert {p.purpose for p in people} == {purpose}
            assert Counter((int(p.day), p.arrival_hour) for p in people) == {(1, 9): 3, (7, 9): 3}
            assert len({p.id for p in people}) == 6 and not any(p.twin_of for p in people)
            assert await generate() == people and len(calls) == 5
            for body in calls:
                system = body["messages"][0]["content"]
                user = next(m["content"] for m in body["messages"] if m["role"] == "user")
                if "hourly_profiles" in system:
                    assert labels(user) == [identity]
                elif "personas" in system:
                    specs = re.findall(r"^\[\d+\] 9시, (.*?), 키워드: (.*)$", user, re.MULTILINE)
                    assert len(specs) == 3
                    assert all(types == identity for types, _ in specs)
                    assert all(keywords == ("住宅街" if pool in {"mixed", "repeated"} else "") for _, keywords in specs)
                    if mode == "json_schema":
                        schema = body["response_format"]["json_schema"]["schema"]
                        choices = schema["$defs"]["LabelledPersona"]["properties"]
                        assert choices["identity"]["enum"] == [identity]
                        assert choices["purpose"]["enum"] == [purpose]

    asyncio.run(exercise())


@pytest.mark.parametrize("field", ["keywords", "identities", "purposes", "person_types"])
@pytest.mark.parametrize("value", [None, [None], [12], "resident", ["x" * 121]])
def test_blank_cleanup_does_not_accept_malformed_labels(field, value):
    model = gen.HourlyProfile if field == "person_types" else gen.TradeAreaProfile
    payload = {"hour": 9, "visitor_count": 3, "person_types": []} if field == "person_types" else {
        "keywords": [], "identities": [], "purposes": []}
    with pytest.raises(ValidationError):
        model.model_validate({**payload, field: value})
