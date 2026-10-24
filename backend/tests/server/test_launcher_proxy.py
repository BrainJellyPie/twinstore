"""Requests to servers on this computer bypass a proxy taken from the system settings."""

import asyncio
import http.server
import json
import os
import socket
import threading
import urllib.request

import pytest
from openai import AsyncOpenAI, OpenAI

from store_emulator import launcher


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch):
    for name in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)


def test_the_system_proxy_moves_into_the_environment_with_loopback_exempt(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"http": "http://proxy.corp:8080", "https": "http://proxy.corp:8080"})
    launcher.keep_local_requests_direct()
    assert os.environ["https_proxy"] == os.environ["http_proxy"] == "http://proxy.corp:8080"
    assert os.environ["no_proxy"] == os.environ["NO_PROXY"] == "127.0.0.1,localhost,localhost.,::1"
    assert urllib.request.proxy_bypass_environment("127.0.0.1")


def test_a_proxy_and_bypass_list_the_user_set_are_kept(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://mine:3128")
    monkeypatch.setenv("NO_PROXY", "intranet.local,localhost")
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"https": "http://other:8080"})
    launcher.keep_local_requests_direct()
    assert "https_proxy" not in os.environ or os.environ["https_proxy"] == "http://mine:3128"
    assert os.environ["NO_PROXY"] == "intranet.local,localhost,127.0.0.1,localhost.,::1"


def test_no_proxy_anywhere_changes_only_the_bypass_list(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {})
    launcher.keep_local_requests_direct()
    assert "http_proxy" not in os.environ and "https_proxy" not in os.environ
    assert os.environ["no_proxy"] == "127.0.0.1,localhost,localhost.,::1"


@pytest.mark.parametrize("host", ["localhost.", "LOCALHOST."])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_sdk_calls_to_dotted_localhost_bypass_a_configured_proxy(monkeypatch, host, asynchronous):
    calls = {"model": 0, "proxy": 0}
    resolver = socket.getaddrinfo

    def resolve_local(name, *args, **kwargs):
        # Keep the HTTP host/proxy decision real without depending on system DNS
        # support or IPv6 connectivity for the fully qualified localhost name.
        if name in {"localhost.", "LOCALHOST.", b"localhost.", b"LOCALHOST."}:
            name = "127.0.0.1"
        return resolver(name, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", resolve_local)

    def handler(kind):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                calls[kind] += 1
                body = json.dumps({"id": "offline", "object": "chat.completion", "created": 0, "model": "local",
                    "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "ready"}}]}
                    if kind == "model" else {"error": {"message": "Local model requests cannot traverse this proxy"}}).encode()
                self.send_response(200 if kind == "model" else 403)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        return Handler

    servers = [http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler(kind)) for kind in ("model", "proxy")]
    threads = [threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True) for server in servers]
    for thread in threads:
        thread.start()
    try:
        proxy = f"http://127.0.0.1:{servers[1].server_address[1]}"
        monkeypatch.delenv("ALL_PROXY", raising=False)
        monkeypatch.delenv("all_proxy", raising=False)
        monkeypatch.setattr(urllib.request, "getproxies", lambda: {"http": proxy})
        launcher.keep_local_requests_direct()
        base = f"http://{host}:{servers[0].server_address[1]}/v1"

        async def ask():
            async with AsyncOpenAI(api_key="offline", base_url=base, max_retries=0, timeout=2) as client:
                return await client.chat.completions.create(model="local", messages=[{"role": "user", "content": "ready?"}])

        if asynchronous:
            answer = asyncio.run(ask())
        else:
            with OpenAI(api_key="offline", base_url=base, max_retries=0, timeout=2) as client:
                answer = client.chat.completions.create(model="local", messages=[{"role": "user", "content": "ready?"}])
        assert answer.choices[0].message.content == "ready"
        assert calls == {"model": 1, "proxy": 0}
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)
