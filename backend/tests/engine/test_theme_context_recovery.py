"""Theme coding must preserve the selected population when a local prompt is too large."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, InstructorRetryException
from litellm.exceptions import BadRequestError, ContextWindowExceededError
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.interview import code_themes
from store_emulator.engine.marketing.reading import Reason, code_reasons, read_study


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("count,capacity", [(8, 4), (17, 4), (160, 40), (160, 160)])
def test_context_recovery_retains_every_answer_and_group_count(monkeypatch, tmp_path, mode, count, capacity):
    original, requests = llm_client.litellm.acompletion, []
    successful = []

    def respond(request):
        body = json.loads(request.content)
        prompt = next(m["content"] for m in body["messages"] if m["role"] == "user")
        requests.append(prompt)
        if prompt.startswith("Report:"):
            assert f"over {count} answers" in prompt
            payload = {"summary": "Price and packaging shaped the answers.", "interpretation": "", "next_steps": ""}
        elif "Answers:\n" in prompt:
            answers = prompt.split("Answers:\n", 1)[1].splitlines()
            if len(answers) > capacity:
                return httpx.Response(400, request=request, json={"error": {
                    "message": "request (10874 tokens) exceeds the available context size (8192 tokens)",
                    "type": "exceed_context_size_error", "code": "context_length_exceeded"}})
            # Separate batches phrase the same reasons differently; one answer
            # is deliberately unclassified, which must stay Other when merged.
            labels = ["Too expensive", "Clear packaging"] if len(successful) % 2 == 0 else ["High price", "Readable pack"]
            assignments = [99 if "[unknown]" in a else (0 if "[price]" in a else 1) for a in answers]
            payload = {"themes": labels, "assignments": assignments}
        else:
            entries = json.loads(prompt.split("Batch themes:\n", 1)[1])
            assert all(e["count"] > 0 and e["label"] != "Other" for e in entries)
            labels = ["High price", "Readable pack"]
            assignments = [0 if e["label"] in {"Too expensive", "High price"} else 1 for e in entries]
            payload = {"themes": labels, "assignments": assignments}
        successful.append(prompt)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/theme-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path), max_tokens=2000))
            # Deliberate repeated answers retain distinct respondents and groups.
            reasons = [Reason(text="[unknown]" if i == count - 1 else "[price] Too expensive" if i % 2 == 0 else "[pack] Clear packaging",
                              group="A" if i % 2 == 0 else "B") for i in range(count)]
            result = await code_reasons(client, "Why?", reasons)
            successes = len(successful)
            assert await code_reasons(client, "Why?", reasons) == result
            assert len(successful) == successes and client.get_usage().cached_requests > 0
            themes, coded, groups = result
            assert coded == count and groups == ["A", "B"]
            by_label = {t.label: t for t in themes}
            price = by_label["High price" if capacity < count else "Too expensive"]
            pack = by_label["Readable pack" if capacity < count else "Clear packaging"]
            assert price.count == count // 2 and price.by_group == {"A": count // 2, "B": 0}
            assert pack.count == (count - 1) // 2 and pack.by_group == {"A": 0, "B": (count - 1) // 2}
            assert by_label["Other"].count == 1
            assert by_label["Other"].by_group == {"A": int(count % 2 == 1), "B": int(count % 2 == 0)}
            assert sum(t.count for t in themes) == count and sum(t.share for t in themes) == pytest.approx(1, abs=2e-4)
            if capacity == count:
                assert len(requests) == 1
            else:
                leaves = [p for p in successful if "Answers:\n" in p]
                # Identical batches can share cache entries without losing respondents.
                assert 0 < sum(len(p.split("Answers:\n", 1)[1].splitlines()) for p in leaves) <= count
                assert len(requests) < 4 * count
            reading = await read_study(client, "survey", '{"respondents": 160}', "Why?", reasons)
            assert reading.summary and reading.answers_coded == count
            assert reading.themes == themes and reading.groups == groups
            assert await read_study(client, "survey", '{"respondents": 160}', "Why?", reasons) == reading

    asyncio.run(exercise())


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("context", [False, True])
def test_irreducible_or_unrelated_failures_do_not_keep_decomposing(context, wrapped):
    error = (ContextWindowExceededError if context else BadRequestError)(
        "context too small" if context else "unsupported server configuration", model="openai/local", llm_provider="openai")
    if wrapped:
        error = InstructorRetryException("retries exhausted", n_attempts=1, total_usage=0, failed_attempts=[FailedAttempt(1, error)])

    class Model:
        calls = 0

        async def generate_structured_async(self, *args, **kwargs):
            self.calls += 1
            raise error

    model = Model()
    with pytest.raises(type(error)):
        asyncio.run(code_themes(model, "Why?", ["one"] if context else ["one", "two", "three"]))
    assert model.calls == 1


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("kind", ["other", "same", "missing_merge"])
def test_recovery_preserves_other_and_avoids_unnecessary_merges(wrapped, kind):
    class Model:
        calls = 0

        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            self.calls += 1
            if self.calls == 1:
                error = ContextWindowExceededError("too large", model="openai/local", llm_provider="openai")
                if wrapped:
                    raise InstructorRetryException("retries exhausted", n_attempts=1, total_usage=0,
                                                   failed_attempts=[FailedAttempt(1, error)])
                raise error
            if "Batch themes:\n" in prompt:
                assert kind == "missing_merge"
                return schema(themes=["Unused"], assignments=[])
            return schema(themes=["Reason" if kind != "missing_merge" else f"Reason {self.calls}"],
                          assignments=[99, 99] if kind == "other" else [0, 0])

    model = Model()
    labels, codes = asyncio.run(code_themes(model, "Why?", ["a", "b", "c", "d"]))
    assert [labels[k] for k in codes] == ["Reason" if kind == "same" else "Other"] * 4
    assert model.calls == (4 if kind == "missing_merge" else 3)


def test_theme_limit_uses_global_respondent_counts_after_merging():
    class Model:
        calls = 0

        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ContextWindowExceededError("too large", model="openai/local", llm_provider="openai")
            if "Batch themes:\n" in prompt:
                entries = json.loads(prompt.split("Batch themes:\n", 1)[1])
                assert {e["label"]: e["count"] for e in entries} == dict(A=20, B=4, C=3, D=3, E=2, F=2, G=36)
                return schema(themes=list("ABCDEFG"), assignments=list(range(7)))
            assignments = [0] * 20 + [1] * 4 + [2] * 3 + [3] * 3 + [4] * 2 + [5] * 2 + [6]
            return schema(themes=list("ABCDEFG"), assignments=assignments if self.calls == 2 else [6] * 35)

    model = Model()
    labels, codes = asyncio.run(code_themes(model, "Why?", [str(i) for i in range(70)]))
    assert labels == ["A", "B", "C", "D", "G", "Other"] and len(codes) == 70
    assert [codes.count(i) for i in range(len(labels))] == [20, 4, 3, 3, 36, 4]
    assert model.calls == 4
