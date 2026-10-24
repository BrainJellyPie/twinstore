"""Local inference preflight supports servers without llama.cpp's health route."""

import io
import json
import http.server
import threading
import urllib.error
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from store_emulator.application import local_vlm, providers
from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.providers import ProviderKind


@pytest.fixture
def responses(monkeypatch):
    routes, calls = {}, []

    def open_url(url, timeout):
        calls.append(url)
        code, body = routes.get(url, (404, {}))
        if isinstance(code, Exception):
            raise code
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        if code != 200:
            raise urllib.error.HTTPError(url, code, "offline fixture", None, io.BytesIO(data))
        response = io.BytesIO(data)
        response.status = code
        return response

    monkeypatch.setattr(local_vlm._DIRECT, "open", open_url)
    monkeypatch.setattr(local_vlm, "manager", lambda: SimpleNamespace(status=lambda: local_vlm.LocalVLMStatus()))
    return routes, calls


@pytest.mark.parametrize("base", [
    "http://127.0.0.1:8081/v1", "http://127.0.0.1:8081/v1/", "http://localhost:1234/v1",
    "http://[::1]:11434", "http://127.0.0.1:8081/gateway/v1?deployment=local",
    "http://127.0.0.1:8081/gateway/v1/?deployment=local#ignored",
])
@pytest.mark.parametrize("protocol", ["health", "models", "ollama", "authenticated"])
def test_ready_model_protocols_pass_inference_preflight_without_a_required_health_route(responses, base, protocol):
    routes, calls = responses
    parsed = urlsplit(base)
    root = parsed.path.rstrip("/").removesuffix("/v1")
    health = parsed._replace(path=root + "/health", fragment="").geturl()
    models = parsed._replace(path=parsed.path.rstrip("/") + "/models", fragment="").geturl()
    tags = parsed._replace(path=root + "/api/tags", fragment="").geturl()
    if protocol == "health":
        routes[health] = (200, {"status": "ok"})
    elif protocol == "models":
        routes[models] = (200, {"data": [{"id": "local-model"}]})
    elif protocol == "ollama":
        routes[tags] = (200, {"models": [{"name": "qwen"}]})
    else:
        routes[models] = (401, {"error": "authentication required"})
    providers.ensure_local_ready(base)
    assert providers.local_model_answers(base)
    assert all(urlsplit(url).query == parsed.query and not urlsplit(url).fragment for url in calls)
    assert len(calls) <= 6


@pytest.mark.parametrize("failure", [503, 500, 429, TimeoutError("not answering"), OSError("offline")])
def test_loading_and_unavailable_servers_are_not_made_ready_by_a_model_list(responses, failure):
    routes, calls = responses
    base = "http://127.0.0.1:8081/v1"
    routes["http://127.0.0.1:8081/health"] = (failure, {"error": "loading"})
    routes[base + "/models"] = (200, {"data": [{"id": "local-model"}]})
    assert not local_vlm.server_answers(base)
    assert calls == ["http://127.0.0.1:8081/health"]


@pytest.mark.parametrize("body", [b"<html>not a model server</html>", {}, [], {"data": "not a list"}, {"models": "not a list"}])
def test_arbitrary_web_servers_do_not_satisfy_model_listing_fallback(responses, body):
    routes, _ = responses
    base = "http://127.0.0.1:8081/v1"
    routes[base + "/models"] = (200, body)
    routes["http://127.0.0.1:8081/api/tags"] = (200, body)
    assert not local_vlm.server_answers(base)


@pytest.mark.parametrize("body", [b"<!doctype html><html><body>Web app</body></html>",
    b"Unknown route", {"app": "A website"}, {"error": "Not found"}, [], {"status": False}])
@pytest.mark.parametrize("has_models", [False, True])
def test_successful_web_routes_do_not_impersonate_model_health(responses, body, has_models):
    routes, calls = responses
    base = "http://127.0.0.1:8081/v1"
    routes["http://127.0.0.1:8081/health"] = (200, body)
    routes[base + "/models"] = (200, {"data": [{"id": "local"}]} if has_models else body)
    routes["http://127.0.0.1:8081/api/tags"] = (200, body)
    assert local_vlm.server_answers(base) is has_models
    assert calls[:2] == ["http://127.0.0.1:8081/health", base + "/models"]
    if not has_models:
        with pytest.raises(ValueError, match="No model server answers"):
            providers.ensure_local_ready(base)


@pytest.mark.parametrize("body", [b"", b" OK\n", b"healthy", "ok", {"status": "ok"},
    {"status": "healthy"}, {"status": "ready"}, {"status": "no slot available"}])
def test_recognized_health_shapes_need_no_model_listing(responses, body):
    routes, calls = responses
    routes["http://127.0.0.1:8081/health"] = (200, body)
    assert local_vlm.server_answers("http://127.0.0.1:8081/v1")
    assert calls == ["http://127.0.0.1:8081/health"]


@pytest.mark.parametrize("kind,base,route,body", [
    (ProviderKind.OLLAMA, "http://127.0.0.1:11434", "/api/tags", {"models": [{"name": "qwen"}]}),
    (ProviderKind.CUSTOM, "http://127.0.0.1:1234/v1", "/v1/models", {"data": [{"id": "local-model"}]}),
])
def test_named_ollama_and_openai_compatible_runs_pass_resolution(responses, monkeypatch, kind, base, route, body):
    routes, _ = responses
    parsed = urlsplit(base)
    routes[parsed._replace(path=route).geturl()] = (200, body)
    settings = {kind: providers.ProviderSettings(kind=kind, api_base=base)}
    monkeypatch.setattr(providers, "load_settings", lambda: settings)
    config = SimulationConfig(engine_type=EngineType.PATTERN_INTENT_IMPULSE,
                              llm=LLMConfig(model=f"{kind.value}:local-model"))
    providers.ensure_resolvable(config)


@pytest.mark.parametrize("kind,base_path,listing_path,payload", [
    (ProviderKind.OLLAMA, "", "/api/tags", {"models": [{"name": "local-model"}]}),
    (ProviderKind.CUSTOM, "/v1", "/v1/models", {"data": [{"id": "local-model"}]}),
])
def test_real_local_http_model_list_allows_a_run_without_health(monkeypatch, kind, base_path, listing_path, payload):
    calls = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            good = self.path == listing_path
            body = json.dumps(payload if good else {"detail": "Not Found"}).encode()
            self.send_response(200 if good else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}{base_path}"
        settings = {kind: providers.ProviderSettings(kind=kind, api_base=base)}
        monkeypatch.setattr(providers, "load_settings", lambda: settings)
        monkeypatch.setattr(local_vlm, "manager", lambda: SimpleNamespace(status=lambda: local_vlm.LocalVLMStatus()))
        providers.ensure_resolvable(SimulationConfig(engine_type=EngineType.PATTERN_INTENT_IMPULSE,
            llm=LLMConfig(model=f"{kind.value}:local-model")))
        assert calls[0] == "/health" and calls[-1] == listing_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("has_models", [False, True])
def test_real_web_app_catchall_cannot_start_model_runs(monkeypatch, has_models):
    calls = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            model_list = self.path == "/v1/models" and has_models
            body = json.dumps({"data": [{"id": "local"}]}).encode() if model_list else b"<html><body>Web app</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "application/json" if model_list else "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}/v1"
        monkeypatch.setattr(providers, "load_settings", lambda: {})
        monkeypatch.setattr(local_vlm, "manager", lambda: SimpleNamespace(status=lambda: local_vlm.LocalVLMStatus()))
        assert providers.local_model_answers(base) is has_models
        for kind in [EngineType.PATTERN_INTENT_IMPULSE, EngineType.VLM_GLANCE]:
            model = LLMConfig(model="openai/local", api_base=base)
            config = SimulationConfig(engine_type=kind, llm=model)
            config.engines.vlm_glance.llm = model
            if has_models:
                providers.ensure_resolvable(config)
            else:
                with pytest.raises(ValueError, match="No model server answers"):
                    providers.ensure_resolvable(config)
        assert "/v1/models" in calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
