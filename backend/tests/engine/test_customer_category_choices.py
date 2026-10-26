"""Listed shopper preferences stay tied to real departments through validation and cache reads."""
import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen
from tests.engine.test_generated_budget_bounds import PERSON

GOOD = {**PERSON, "identity": "Resident", "purpose": "Shopping", "preferred_categories": ["Books — 새책·헌책"]}
CATEGORIES = ["Books — 새책·헌책", "Stationery / 紙もの 🌿"]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("bad", [["books"], [""], ["Books — 새책·헌책", "invented"]])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_unknown_categories_are_repaired_before_customers_or_cache_can_accept_them(monkeypatch, tmp_path, mode, bad, outcome):
    original, calls = llm_client.litellm.acompletion, []
    phase = "prime" if outcome == "legacy_cache" else "invalid"

    def respond(request):
        body = json.loads(request.content)
        if mode == "json_schema":
            schema = body["response_format"]["json_schema"]["schema"]
        else:
            system = next(m["content"] for m in reversed(body["messages"]) if m["role"] == "system")
            schema = json.JSONDecoder().raw_decode(system.rsplit("matching this schema:", 1)[-1].lstrip())[0]
        person_schema = schema["properties"]["personas"]["items"]
        if "$ref" in person_schema:
            person_schema = schema["$defs"][person_schema["$ref"].rsplit("/", 1)[1]]
        item = person_schema["properties"]["preferred_categories"]["items"]
        assert item == {"type": "string", "maxLength": 80, "enum": CATEGORIES}
        invalid = phase == "invalid" and not (outcome == "corrected" and calls)
        calls.append(body)
        person = {**GOOD, "preferred_categories": bad} if invalid else GOOD
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"personas": [person]})}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:9/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/customer-categories", api_base="http://127.0.0.1:9/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                tally = gen.BatchTally()
                people = await gen.generate_personas_for_day(client, "offline",
                    gen.TradeAreaProfile(keywords=[], identities=["Resident"], purposes=["Shopping"]), Weekday.MON,
                    [gen.HourlyProfile(hour=9, visitor_count=1, person_types=["Resident"])], categories=CATEGORIES, tally=tally)
                return people, tally

            if outcome == "legacy_cache":
                people, tally = await run()
                assert len(people) == 1 and not tally.failed
                caches = list(tmp_path.rglob("*.json"))
                assert len(caches) == 1
                data = json.loads(caches[0].read_text())
                data["result"]["personas"][0]["preferred_categories"] = bad
                caches[0].write_text(json.dumps(data))
                phase = "invalid"
            if outcome in {"repeated", "legacy_cache"}:
                before = len(calls)
                people, tally = await run()
                assert people == [] and tally.failed == 1
                assert len(calls) == before + 3
                assert "supplied category" in str(tally.first_error)
                phase = "complete"
            people, tally = await run()
            assert len(people) == 1 and people[0].preferred_categories == GOOD["preferred_categories"] and not tally.failed
            if outcome == "corrected":
                assert len(calls) == 2
            before = len(calls)
            repeated, _ = await run()
            assert repeated == people and len(calls) == before
            for path in tmp_path.rglob("*.json"):
                assert json.loads(path.read_text())["result"]["personas"][0]["preferred_categories"] == GOOD["preferred_categories"]

    asyncio.run(exercise())


@pytest.mark.parametrize("categories,asked,expected", [
    (["Books"], [" books "], ["Books"]),
    (["Books", "BOOKS"], ["Books", "BOOKS"], ["Books", "BOOKS"]),
    (["Books", "BOOKS"], ["books"], None),
    (["Books", "Books"], ["books"], ["Books"]),
    ([" 도서 "], [" 도서 "], [" 도서 "]),
    (CATEGORIES, CATEGORIES, CATEGORIES),
    (CATEGORIES, [], []), (CATEGORIES, None, []),
    (None, ["inferred"], ["inferred"]), ([], ["inferred"], ["inferred"]),
])
def test_preferences_normalize_only_unambiguous_labels_and_keep_inference_without_a_list(categories, asked, expected):
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"personas": [{**GOOD, "preferred_categories": asked}]})

    tally = gen.BatchTally()
    people = asyncio.run(gen.generate_personas_for_day(Model(), "offline",
        gen.TradeAreaProfile(keywords=[], identities=["Resident"], purposes=["Shopping"]), Weekday.MON,
        [gen.HourlyProfile(hour=9, visitor_count=1, person_types=["Resident"])], categories=categories, tally=tally))
    if expected is None:
        assert people == [] and tally.failed == 1
    else:
        assert len(people) == 1 and people[0].preferred_categories == expected and not tally.failed
