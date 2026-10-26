"""Traffic types must not contradict the identity vocabulary in the next customer step."""

import asyncio
import json
import re

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from jsonschema import Draft202012Validator
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.store import DaySchedule
from store_emulator.engine import llm_client
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("explicit_hours", [False, True])
@pytest.mark.parametrize("fault", ["unknown", "mixed", "ambiguous"])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_traffic_labels_are_repaired_before_customer_generation_and_cache(
    monkeypatch, tmp_path, mode, explicit_hours, fault, outcome,
):
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    identities = ["Resident", "RESIDENT"] if fault == "ambiguous" else ["Resident"]
    invalid = ["resident"] if fault == "ambiguous" else ["Tourist"] if fault == "unknown" else ["Resident", "Tourist"]
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if "hourly_profiles" in system:
            kind = "traffic"
            bad = phase == "invalid" and not (outcome == "corrected" and calls.count("traffic") > 0)
            payload = {"hourly_profiles": [dict(visitor_count=1, person_types=invalid if bad else ["Resident"],
                **({"hour": 9} if explicit_hours else {}))]}
        elif "personas" in system:
            kind = "customers"
            # Echo the supplied per-customer type: a contradictory spec cannot
            # be repaired by retrying only this downstream generation stage.
            label = re.search(r"^\[0\] 9시, (.+?), 키워드:", user, re.MULTILINE).group(1).split("+")[-1]
            payload = {"personas": [dict(identity=label, purpose="Groceries", age_group="30s", gender="Female",
                description="Nearby customer", intent="Buy groceries")]}
        else:
            kind, payload = "profile", dict(keywords=[], identities=identities, purposes=["Groceries"])
        calls.append(kind)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/traffic-labels", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                return await gen.generate_batched(client, "offline", "동네 주민",
                    [DaySchedule(day=1, open_hour=9, close_hour=10)], batch_size=1, seed=42)

            if outcome == "legacy_cache":
                await run()
                corrupted = []
                for path in tmp_path.rglob("*.json"):
                    data = json.loads(path.read_text())
                    if "hourly_profiles" in data["result"]:
                        data["result"]["hourly_profiles"][0]["person_types"] = invalid
                        path.write_text(json.dumps(data))
                        corrupted.append(path)
                assert len(corrupted) == 1
                phase = "invalid"
            if outcome != "corrected":
                before = calls.count("customers")
                with pytest.raises(InstructorRetryException):
                    await run()
                assert calls.count("customers") == before
                assert calls.count("traffic") == (4 if outcome == "legacy_cache" else 3)
                phase = "complete"
            people = await run()
            assert len(people) == 1 and people[0].identity == "Resident" and people[0].arrival_hour == 9
            assert not people[0].twin_of
            if outcome == "corrected":
                assert calls == ["profile", "traffic", "traffic", "customers"]
            before = len(calls)
            assert await run() == people and len(calls) == before
            saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            assert all(data["hourly_profiles"][0]["person_types"] == ["Resident"]
                       for data in saved if "hourly_profiles" in data)

    asyncio.run(exercise())


@pytest.mark.parametrize("identities,types,expected", [
    (["Resident"], [" resident "], ["Resident"]),
    (["동네 주민"], ["\u3000동네 주민\t"], ["동네 주민"]),
    (["Resident", "RESIDENT"], ["Resident", "RESIDENT"], ["Resident", "RESIDENT"]),
    (["Resident", "RESIDENT"], ["resident"], None),
    ([], ["shopper"], ["shopper"]),
    (["Resident"], [], []),
    (["Resident"], ["\t", " "], []),
])
def test_only_unique_equivalent_traffic_labels_are_normalized(identities, types, expected):
    schema = gen.traffic_response_model(9, 10, identities=identities)
    original = dict(hour=9, visitor_count=2, person_types=types)
    if expected is None:
        with pytest.raises(ValidationError, match="supplied identity"):
            schema.model_validate({"hourly_profiles": [original]})
    else:
        result = schema.model_validate({"hourly_profiles": [original]})
        assert result.hourly_profiles[0].person_types == expected
        assert result.hourly_profiles[0].visitor_count == 2 and original["person_types"] == types


def test_traffic_grammar_uses_shared_identity_choices_and_keeps_empty_hour_fallbacks():
    schema = gen.traffic_response_model(9, 10, identities=["Resident", "동네 주민"])
    json_schema = schema.model_json_schema()
    row = json_schema["properties"]["hourly_profiles"]["properties"]["0"]
    row = json_schema["$defs"][row["$ref"].rsplit("/", 1)[1]]
    item = row["properties"]["person_types"]["items"]
    if "$ref" in item:
        item = json_schema["$defs"][item["$ref"].rsplit("/", 1)[1]]
    assert item["enum"] == ["Resident", "동네 주민"]
    validator = Draft202012Validator(json_schema)
    for types, valid in [(["Resident"], True), (["동네 주민"], True), ([], True), (["Tourist"], False)]:
        assert validator.is_valid({"hourly_profiles": {"0": dict(visitor_count=1, person_types=types)}}) == valid
    # Inactive legacy rows do not determine a customer's identity.
    rows = [dict(hour=8, visitor_count=10, person_types=["Tourist"]),
            dict(hour=9, visitor_count=0, person_types=["Tourist"])]
    assert schema.model_validate({"hourly_profiles": rows}).model_dump()["hourly_profiles"] == rows
