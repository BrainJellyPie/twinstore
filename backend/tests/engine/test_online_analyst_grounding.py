"""An online analyst cannot cache or return numerical claims without a verifiable report line."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.online import OnlineRunResult, PairedDelta, VariantComparison
from store_emulator.engine import llm_client
from store_emulator.engine.online import analyst

FACT = "Control: visits 8, orders 2 (25.0%), revenue $71.97."


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["empty", "null", "invented", "partial", "unknown_id", "supported", "repeated", "long_followup", "always"])
def test_numerical_answers_need_report_evidence_before_caching(monkeypatch, tmp_path, mode, kind):
    calls = []
    original = llm_client.litellm.acompletion
    monkeypatch.setattr(analyst, "online_facts", lambda _: FACT)
    run = OnlineRunResult(run_id="r", policy="rule", currency="USD", variants=[], shoppers=[])
    question = "What exact real-world sales uplift will this store achieve next year?"

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        figures = {"empty": [], "null": None, "always": [], "invented": ["Revenue next year: $91.97."],
                   "partial": ["visits 8"], "unknown_id": ["F999"], "supported": [FACT],
                   "repeated": [FACT, FACT], "long_followup": [FACT]}[kind]
        payload = {"answer": "Sales will increase by 33.3% to $91.97 next year.", "figures": figures, "follow_ups": []}
        if kind == "long_followup" and len(calls) == 1:
            payload.update(answer="The control converted 25% of visits.", follow_ups=["The difference is not clear. " * 30])
        elif kind in {"supported", "repeated"}:
            payload["answer"] = "The control had 8 visits and 2 orders, a 25% conversion rate."
        elif len(calls) > 1 and kind != "always":
            payload = {"answer": "The run does not show that. Real-world follow-up data would be needed.",
                       "figures": [], "follow_ups": []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/analyst-evidence", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))
            if kind == "always":
                with pytest.raises(ValueError, match="report figures"):
                    await analyst.answer_online_question(client, run, question, [])
                assert len(calls) == 2 and not list(tmp_path.glob("*/*.json"))
                return
            answer = await analyst.answer_online_question(client, run, question, [])
            assert "91.97" not in answer.answer
            assert len(calls) == (1 if kind in {"supported", "repeated"} else 2)
            assert answer.figures == ([FACT] if kind in {"supported", "repeated"} else [])
            assert FACT in calls[0]["messages"][1]["content"]
            if mode == "json_schema":
                schema = calls[0]["response_format"]["json_schema"]["schema"]
                assert "figures" in schema["required"]
                assert schema["properties"]["figures"]["items"]["enum"] == [FACT]
                assert schema["properties"]["follow_ups"]["items"]["maxLength"] == 200
            before = len(calls)
            again = await analyst.answer_online_question(client, run, question, [])
            assert again.model_dump() == answer.model_dump() and len(calls) == before
            assert client.get_usage().cached_requests == 1
            cached = [json.loads(path.read_text())["result"] for path in tmp_path.glob("*/*.json")]
            assert cached == [answer.model_dump()]
            # Previously cached model output must pass the new evidence check too.
            path = next(tmp_path.glob("*/*.json"))
            stale = json.loads(path.read_text())
            stale["result"].update(answer="Next year's revenue will be $91.97.", figures=[])
            path.write_text(json.dumps(stale))
            repaired = await analyst.answer_online_question(client, run, question, [])
            assert "91.97" not in repaired.answer and len(calls) == before + 1

    asyncio.run(exercise())


@pytest.mark.parametrize("low,high,label", [
    (-.25, 0, "not clear: interval includes zero"),
    (0, .25, "not clear: interval includes zero"),
    (-.25, .25, "not clear: interval includes zero"),
    (0, 0, "not clear: interval includes zero"),
    (.1, .25, "interval excludes zero"),
    (-.25, -.1, "interval excludes zero"),
    (None, None, "interval unavailable"),
    (None, .25, "interval unavailable"),
])
def test_report_supplies_interval_interpretation_including_zero_boundaries(low, high, label):
    difference = (low + high) / 2 if low is not None and high is not None else 0
    delta = PairedDelta(metric="conversion", control=.5, variant=.5 + difference, diff=difference,
                        ci_low=low, ci_high=high, n=8)
    run = OnlineRunResult(run_id="r", policy="rule", currency="USD", variants=[], shoppers=[], comparisons=[
        VariantComparison(site_id="v", site_name="Variant", deltas=[delta])])
    line = next(line for line in analyst.online_facts(run).splitlines() if "minus control" in line)
    assert label in line
