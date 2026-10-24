"""A resumed model must contain the full resource, not merely one valid HTTP chunk."""

import io
import urllib.error

import pytest

from store_emulator.application.local_vlm import LocalVLMManager


class Response(io.BytesIO):
    def __init__(self, body, status=200, content_range=None, length='auto'):
        super().__init__(body)
        self.status = status
        self.headers = {}
        if length is not None:
            self.headers['Content-Length'] = str(len(body) if length == 'auto' else length)
        if content_range is not None:
            self.headers['Content-Range'] = content_range


@pytest.mark.parametrize('prefix', [b'', b'abc'])
def test_a_valid_partial_range_is_kept_for_resume_but_not_promoted_to_a_model(tmp_path, prefix):
    target = tmp_path / 'model.gguf'
    part = tmp_path / 'model.gguf.part'
    if prefix:
        part.write_bytes(prefix)
    responses = [Response(b'de' if prefix else b'abcde', 206, f'bytes {len(prefix)}-4/8'),
                 Response(b'fgh', 206, 'bytes 5-7/8')]
    ranges = []

    def open_response(request):
        ranges.append(request.get_header('Range'))
        return responses.pop(0)

    manager = LocalVLMManager(tmp_path, opener=open_response)
    with pytest.raises(RuntimeError, match='incomplete'):
        manager._download('https://offline.invalid/model', target, label='model')
    assert not target.exists() and part.read_bytes() == b'abcde'
    assert manager._download('https://offline.invalid/model', target, label='model').read_bytes() == b'abcdefgh'
    assert not part.exists() and ranges == (['bytes=3-', 'bytes=5-'] if prefix else [None, 'bytes=5-'])


@pytest.mark.parametrize('content_range,body,length', [
    (None, b'defgh', 'auto'),
    ('bytes 0-4/8', b'abcde', 'auto'),
    ('bytes 3-2/8', b'd', 'auto'),
    ('bytes 3-8/8', b'defgh', 'auto'),
    ('bytes 3-7/*', b'defgh', 'auto'),
    ('bytes 3-7/8', b'defg', 'auto'),
    ('bytes 3-4/8', b'defgh', None),
])
def test_unverifiable_or_inconsistent_ranges_never_create_a_cached_model(tmp_path, content_range, body, length):
    target = tmp_path / 'model.gguf'
    part = tmp_path / 'model.gguf.part'
    part.write_bytes(b'abc')
    manager = LocalVLMManager(tmp_path, opener=lambda request: Response(body, 206, content_range, length))
    with pytest.raises(RuntimeError, match='[Dd]ownload'):
        manager._download('https://offline.invalid/model', target, label='model')
    assert not target.exists() and not part.exists()


def test_a_short_range_without_content_length_does_not_count_as_a_complete_model(tmp_path):
    target = tmp_path / 'model.gguf'
    part = tmp_path / 'model.gguf.part'
    part.write_bytes(b'abc')
    manager = LocalVLMManager(tmp_path, opener=lambda request: Response(b'de', 206, 'bytes 3-7/8', None))
    with pytest.raises(RuntimeError, match='incomplete'):
        manager._download('https://offline.invalid/model', target, label='model')
    assert not target.exists() and part.read_bytes() == b'abcde'


@pytest.mark.parametrize('saved', [b'abc', b'abcdefgh', b'longer stale partial'])
def test_an_unsatisfiable_resume_retries_once_without_a_range(tmp_path, saved):
    target = tmp_path / 'model.gguf'
    part = tmp_path / 'model.gguf.part'
    part.write_bytes(saved)
    ranges = []

    def open_response(request):
        ranges.append(request.get_header('Range'))
        if len(ranges) == 1:
            raise urllib.error.HTTPError(request.full_url, 416, 'Range Not Satisfiable', {}, io.BytesIO())
        return Response(b'abcdefgh')

    manager = LocalVLMManager(tmp_path, opener=open_response)
    assert manager._download('https://offline.invalid/model', target, label='model').read_bytes() == b'abcdefgh'
    assert ranges == [f'bytes={len(saved)}-', None] and not part.exists()


def test_a_server_ignoring_range_replaces_the_partial_instead_of_appending(tmp_path):
    target = tmp_path / 'model.gguf'
    (tmp_path / 'model.gguf.part').write_bytes(b'abc')
    manager = LocalVLMManager(tmp_path, opener=lambda request: Response(b'abcdefgh'))
    assert manager._download('https://offline.invalid/model', target, label='model').read_bytes() == b'abcdefgh'


@pytest.mark.parametrize('has_partial', [False, True])
def test_repeated_unsatisfiable_ranges_stop_without_a_retry_loop(tmp_path, has_partial):
    calls = []
    if has_partial:
        (tmp_path / 'model.gguf.part').write_bytes(b'abc')

    def rejected(request):
        calls.append(request)
        raise urllib.error.HTTPError(request.full_url, 416, 'Range Not Satisfiable', {}, io.BytesIO())

    manager = LocalVLMManager(tmp_path, opener=rejected)
    with pytest.raises(urllib.error.HTTPError):
        manager._download('https://offline.invalid/model', tmp_path / 'model.gguf', label='model')
    assert len(calls) == (2 if has_partial else 1)


def test_a_complete_range_without_content_length_can_finish(tmp_path):
    target = tmp_path / 'model.gguf'
    (tmp_path / 'model.gguf.part').write_bytes(b'abc')
    manager = LocalVLMManager(tmp_path, opener=lambda request: Response(b'defgh', 206, 'bytes 3-7/8', None))
    assert manager._download('https://offline.invalid/model', target, label='model').read_bytes() == b'abcdefgh'


def test_cancellation_after_a_rejected_range_does_not_start_a_full_download(tmp_path):
    from store_emulator.application.local_vlm import _StartCancelled

    target = tmp_path / 'model.gguf'
    part = tmp_path / 'model.gguf.part'
    part.write_bytes(b'abc')
    calls = []

    def rejected(request):
        calls.append(request)
        manager.stop()
        raise urllib.error.HTTPError(request.full_url, 416, 'Range Not Satisfiable', {}, io.BytesIO())

    manager = LocalVLMManager(tmp_path, opener=rejected)
    with pytest.raises(_StartCancelled):
        manager._download('https://offline.invalid/model', target, label='model')
    assert len(calls) == 1 and not target.exists() and not part.exists()
