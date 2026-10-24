"""Reasoning with a prompt-prefilled opening tag still ends before the final JSON."""

import asyncio
import json

import pytest

from tests.engine.test_local_thinking_json import Reply, exercise


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("method", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("prefix", [
    'Consider this example:\n```json\n{"value": 99}\n```\n</think>\n',
    '먼저 검토합니다. {"value": 99}\r\n \t</think>\r\n',
    '</think>',
])
def test_prefilled_thinking_uses_only_the_final_answer(monkeypatch, tmp_path, mode, method, prefix):
    result = asyncio.run(exercise(monkeypatch, tmp_path, mode, method,
        prefix + '{"value": 7, "text": "final"}'))
    assert result == Reply(value=7, text="final")


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("final", ["", "No final answer", '{"value": "invalid"}'])
def test_a_reasoning_example_is_not_an_answer_when_the_final_is_missing_or_invalid(monkeypatch, tmp_path, mode, final):
    content = 'Example:\n```json\n{"value": 99}\n```\n</think>\n' + final
    asyncio.run(exercise(monkeypatch, tmp_path, mode, "async", content, expect_error=True, attempts=2))


@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_cleanup_does_not_accept_a_truncated_prefilled_response(monkeypatch, tmp_path, mode):
    content = 'Example: {"value": 99}\n</think>\n{"value": 7}'
    asyncio.run(exercise(monkeypatch, tmp_path, mode, "async_image", content, finish="length", expect_error=True))


@pytest.mark.parametrize("prefix", ["", "Here is the result: ", "```json\n"])
@pytest.mark.parametrize("literal", ['</think>', 'Line one\n</think>\nLine two', 'Escaped quote: "\n</think>'])
def test_closing_markers_inside_json_strings_are_preserved(monkeypatch, tmp_path, prefix, literal):
    answer = Reply(value=7, text=literal)
    content = prefix + answer.model_dump_json() + ('\n```' if prefix.startswith('```') else '')
    result = asyncio.run(exercise(monkeypatch, tmp_path, "json", "async", content))
    assert result == answer


def test_cached_reasoning_example_from_the_previous_parser_is_not_reused(monkeypatch, tmp_path):
    digest = "8be96d98e160c96c756f9edd8c5889e043c6510ff5ae9c5be964e4285b52b925"
    old = tmp_path / digest[:2] / f"{digest}.json"
    old.parent.mkdir()
    old.write_text(json.dumps({"result": {"value": 99, "text": ""}}))
    result = asyncio.run(exercise(monkeypatch, tmp_path, "json", "async", '{"value": 7}'))
    assert result == Reply(value=7) and old.exists()
