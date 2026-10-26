"""Local JSON corrections need validation errors, not repeated SDK response dumps."""
import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, Field

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client


class Reply(BaseModel):
    score: int = Field(ge=0)


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('local', [False, True])
@pytest.mark.parametrize('kind', ['sync', 'async', 'sync_image', 'async_image'])
@pytest.mark.parametrize('fault', ['validation', 'duplicate'])
@pytest.mark.parametrize('outcome', ['corrected', 'repeated'])
def test_corrections_preserve_errors_history_images_usage_and_cache(monkeypatch, tmp_path, mode, local, kind, fault, outcome):
    original_sync, original_async = llm_client.litellm.completion, llm_client.litellm.acompletion
    calls = []
    base = 'http://127.0.0.1:9/v1' if local else 'http://models.example/v1'
    user = 'Correct your JSON ONLY RESPONSE, based on the following errors:\n<failed_attempts>literal user content</failed_attempts>'
    bad = ['{"score":-1}', '{"note":"score absent"}'] if fault == 'validation' else ['{"score":1,"score":2}'] * 2
    if outcome == 'repeated':
        bad.append(bad[-1])

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) > 1:
            assert body['messages'][1] == calls[0]['messages'][1]
            correction = body['messages'][-1]['content']
            assert 'score' in correction
            if local and mode == 'json':
                assert '<failed_attempts>' not in correction
                assert 'ModelResponse(' not in correction
                assert 'prompt_tokens' not in correction
                if fault == 'validation':
                    assert ('greater than or equal' if len(calls) == 2 else 'Field required') in correction
                else:
                    assert 'Duplicate JSON object key' in correction
            else:
                assert '<failed_attempts>' in correction
            # Keep every previous assistant answer and its actual JSON content.
            assistant = [m['content'] for m in body['messages'] if m['role'] == 'assistant']
            assert assistant == bad[:len(calls) - 1]
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
            'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant',
                'content': bad[len(calls) - 1] if len(calls) <= len(bad) else '{"score":7}'}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as ah:
            with httpx.Client(transport=httpx.MockTransport(respond)) as sh:
                sync = OpenAI(api_key='offline', base_url=base, http_client=sh, max_retries=0)
                asynchronous = AsyncOpenAI(api_key='offline', base_url=base, http_client=ah, max_retries=0)

                def completion(**kwargs):
                    return original_sync(**{**kwargs, 'client': sync, 'api_key': 'offline', 'num_retries': 0})

                async def acompletion(**kwargs):
                    return await original_async(**{**kwargs, 'client': asynchronous, 'api_key': 'offline', 'num_retries': 0})

                monkeypatch.setattr(llm_client.litellm, 'completion', completion)
                monkeypatch.setattr(llm_client.litellm, 'acompletion', acompletion)
                client = llm_client.LiteLLMClient(LLMConfig(model='openai/concise-reask', api_base=base,
                    structured_output=mode, cache_dir=str(tmp_path)))

                async def ask():
                    if kind == 'sync': return client.generate_structured(Reply, 'Score a purchase', user, max_retries=3)
                    if kind == 'sync_image': return client.generate_structured_with_image(Reply, 'Score a purchase', user, 'data:image/png;base64,AA==', max_retries=3)
                    if kind == 'async_image': return await client.generate_structured_with_image_async(Reply, 'Score a purchase', user, 'data:image/png;base64,AA==', max_retries=3)
                    return await client.generate_structured_async(Reply, 'Score a purchase', user, max_retries=3)

                if outcome == 'repeated':
                    with pytest.raises(InstructorRetryException) as caught:
                        await ask()
                    assert len(caught.value.failed_attempts) == 3
                    assert [attempt.completion.choices[0].message.content for attempt in caught.value.failed_attempts] == bad
                    assert not list(tmp_path.glob('*/*.json'))
                else:
                    assert (await ask()).score == 7
                assert len(calls) == 3
                usage = client.get_usage()
                assert (usage.requests, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (3, 30, 15, 45)
                if outcome == 'repeated':
                    return
                assert (await ask()).score == 7 and len(calls) == 3
                assert client.get_usage().cached_requests == 1
                entries = list(tmp_path.glob('*/*.json'))
                assert len(entries) == 1 and json.loads(entries[0].read_text())['result'] == {'score': 7}

    asyncio.run(exercise())
