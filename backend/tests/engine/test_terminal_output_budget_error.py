"""A stale output-limit rejection cannot override the terminal result of the retry budget."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException

from tests.engine.test_local_output_budget_recovery import exercise, rejection


@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("terminal", ["validation", "truncation", "timeout", "unrelated400", "server503"])
def test_old_context_error_does_not_restart_a_different_terminal_failure(monkeypatch, tmp_path, mode, terminal):
    budgets = []

    def respond(request):
        body = json.loads(request.content)
        budgets.append(body["max_tokens"])
        if len(budgets) == 1:
            return httpx.Response(400, request=request, json={"error": {
                "message": rejection(65535, 8192, 1024), "type": "BadRequestError"}})
        if terminal == "timeout":
            raise httpx.ReadTimeout("offline timeout after earlier rejection", request=request)
        if terminal in {"unrelated400", "server503"}:
            return httpx.Response(400 if terminal == "unrelated400" else 503, request=request,
                json={"error": {"message": "terminal provider failure", "type": "BadRequestError"}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "length" if terminal == "truncation" else "stop",
                "message": {"role": "assistant", "content": '{"text":17}'}}]})

    with pytest.raises(InstructorRetryException):
        asyncio.run(exercise(monkeypatch, mode, respond, cache_dir=str(tmp_path), retries=2))
    assert budgets == [65535, 65535], "A stale context error improperly started another attempt budget"
    assert not list(tmp_path.rglob("*.json"))
