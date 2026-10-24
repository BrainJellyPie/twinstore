"""Optional response caching must not discard successful text or image answers."""

import asyncio
import errno
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.llm_client import LiteLLMClient


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize('asynchronous', [False, True])
@pytest.mark.parametrize('with_image', [False, True])
@pytest.mark.parametrize('failure', ['blocked_directory', 'mkdir', 'partial_write', 'replace', 'read'])
def test_cache_io_errors_keep_the_answer_and_do_not_repeat_inference(
    tmp_path, monkeypatch, asynchronous, with_image, failure,
):
    root = tmp_path / 'cache'
    client = LiteLLMClient(LLMConfig(model='openai/local', api_base='http://127.0.0.1:9/v1', cache_dir=str(root)))
    image = 'data:image/png;base64,offline'
    messages, _ = (client._messages_with_image('system', 'request', image) if with_image
                   else client._messages('system', 'request'))
    path = client._cache_path(Answer, messages, None)
    calls = []

    def create(*args):
        calls.append(args)
        return Answer(text='usable result'), SimpleNamespace(usage=SimpleNamespace(
            prompt_tokens=10, completion_tokens=5, total_tokens=15))

    async def acreate(*args):
        return create(*args)

    monkeypatch.setattr(client, '_create', create)
    monkeypatch.setattr(client, '_acreate', acreate)
    original = '{}'
    if failure == 'blocked_directory':
        root.write_text('a file occupies the cache directory')
    elif failure in {'replace', 'read'}:
        path.parent.mkdir(parents=True)
        path.write_text(original)

    if failure == 'mkdir':
        mkdir = Path.mkdir

        def denied(directory, *args, **kwargs):
            if directory == path.parent:
                raise PermissionError(errno.EACCES, 'cache is read-only')
            return mkdir(directory, *args, **kwargs)

        monkeypatch.setattr(Path, 'mkdir', denied)
    elif failure == 'partial_write':
        write = Path.write_text

        def full_disk(target, data, *args, **kwargs):
            if target.parent == path.parent and target.suffix == '.tmp':
                write(target, '{partial', *args, **kwargs)
                raise OSError(errno.ENOSPC, 'cache volume is full')
            return write(target, data, *args, **kwargs)

        monkeypatch.setattr(Path, 'write_text', full_disk)
    elif failure == 'replace':
        def locked(source, destination):
            assert destination == path
            raise PermissionError(errno.EACCES, 'cache entry is locked')

        monkeypatch.setattr(llm_client, 'replace_file', locked)
    elif failure == 'read':
        read = Path.read_text

        def unreadable(target, *args, **kwargs):
            if target == path:
                raise PermissionError(errno.EACCES, 'cannot read cache entry')
            return read(target, *args, **kwargs)

        monkeypatch.setattr(Path, 'read_text', unreadable)

    if with_image:
        call = client.generate_structured_with_image_async if asynchronous else client.generate_structured_with_image
        result = call(Answer, 'system', 'request', image)
    else:
        call = client.generate_structured_async if asynchronous else client.generate_structured
        result = call(Answer, 'system', 'request')
    if asynchronous:
        result = asyncio.run(result)
    assert result == Answer(text='usable result') and len(calls) == 1
    usage = client.get_usage()
    assert usage.requests == 1 and usage.cached_requests == 0
    assert usage.prompt_tokens == 10 and usage.completion_tokens == 5
    if failure != 'blocked_directory':
        assert not list(root.rglob('*.tmp'))
    if failure == 'replace':
        assert path.read_text() == original
    if failure == 'read':
        assert json.loads(read(path))['result'] == {'text': 'usable result'}


def test_a_model_failure_is_still_reported_when_cache_is_unavailable(tmp_path, monkeypatch):
    root = tmp_path / 'blocked'
    root.write_text('not a directory')
    client = LiteLLMClient(LLMConfig(model='openai/local', cache_dir=str(root)))

    async def failed(*args):
        raise RuntimeError('model is offline')

    monkeypatch.setattr(client, '_acreate', failed)
    with pytest.raises(RuntimeError, match='model is offline'):
        asyncio.run(client.generate_structured_async(Answer, 'system', 'request'))
    assert client.get_usage().requests == 0
