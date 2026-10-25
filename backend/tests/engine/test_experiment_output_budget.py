"""The configured draft budget must fit complete multi-product A/B proposals."""

import json

import httpx
import pytest

from store_emulator.application import shelf_lab, study_design
from store_emulator.domain.config import SimulationConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.experiment_design import _Draft
from tests.engine.test_llm_impulse_exposure import fixture


# Qwen3.5 tokenizer-only measurements of the exact compact / indented fixtures.
# tokenizer.json SHA256: 5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42
TOKENS = {("english", 1): (415, 709), ("english", 4): (1273, 2317),
          ("korean", 1): (463, 757), ("korean", 4): (1393, 2437)}


@pytest.mark.parametrize("protocol", ["openai", "ollama"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("language", ["english", "korean"])
@pytest.mark.parametrize("count", [1, 4])
@pytest.mark.parametrize("pretty", [False, True])
def test_complete_price_combinations_fit_the_application_budget_and_cache(monkeypatch, tmp_path, protocol, mode, language, count, pretty):
    names = [f"Organic Sparkling Tea {i:02d} 500ml Lemon Bottle" if language == "english" else
             f"유기농 탄산 녹차 {i:02d} 500ml 레몬맛 병" for i in range(6)]
    payload = _Draft.model_validate({"name": "Tea price combinations", "variants": [
        {"name": f"Combination {j + 1}", "changes": [{"kind": "price", "product": name, "price": round(1.99 + (i + j) / 10, 2)}
            for i, name in enumerate(names)]} for j in range(count)], "focus_products": names, "engine": "rule",
        "rationale": "Compare four combinations of prices across the six tea products."}).model_dump()
    content = json.dumps(payload, ensure_ascii=False, indent=2) if pretty else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    required = TOKENS[language, count][int(pretty)]
    store, _ = fixture()
    store.currency = "USD"
    item = store.racks[0].slots[0].items[0]
    store.racks[0].slots[0].items = [item.model_copy(update={"sku": f"tea{i}", "name": name}) for i, name in enumerate(names)]
    monkeypatch.setattr(study_design, "_store_for", lambda *args: store)
    monkeypatch.setattr(study_design, "_last_run_units", lambda *args: {})
    monkeypatch.setattr(shelf_lab, "list_packages", lambda pid: [])
    calls, clients = [], []
    def respond(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        budget = body.get("max_tokens", body.get("options", {}).get("num_predict"))
        truncated = budget < required
        reason, answer = ("length", content[:32]) if truncated else ("stop", content)
        if protocol == "ollama":
            result = {"model": body["model"], "done": True, "done_reason": reason,
                "message": {"role": "assistant", "content": answer}, "prompt_eval_count": 10, "eval_count": min(required, budget)}
        else:
            result = {"id": "offline", "object": "chat.completion", "created": 0, "model": body["model"],
                "choices": [{"index": 0, "finish_reason": reason, "message": {"role": "assistant", "content": answer}}]}
        return httpx.Response(200, request=request, json=result)
    def send(self, request, *args, **kwargs): return respond(request)
    async def asend(self, request, *args, **kwargs): return respond(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    def make_client(requested, config):
        client = LiteLLMClient(config.model_copy(update={"model": "ollama_chat/experiment-budget" if protocol == "ollama" else "openai/experiment-budget",
            "api_base": "http://127.0.0.1:11434" if protocol == "ollama" else "http://127.0.0.1:8081/v1",
            "structured_output": mode, "cache_dir": str(tmp_path / "cache"), "seed": 0}))
        clients.append(client)
        return client
    monkeypatch.setattr(study_design, "assistive_client", make_client)
    config = SimulationConfig()
    before = store.model_dump_json(), config.model_dump_json()
    request = study_design.ExperimentDesignRequest(question="Compare four combinations of new prices across the six tea products.", setup_id="s")
    first = study_design.design_ab("p", request, config)
    assert len(first.variants) == count and all(len(v.changes) == 6 for v in first.variants)
    assert first.focus_skus == [f"tea{i}" for i in range(6)]
    assert study_design.design_ab("p", request, config) == first
    assert len(calls) == 1 and clients[-1].get_usage().cached_requests == 1
    assert required <= clients[0].max_tokens <= 6144
    assert (store.model_dump_json(), config.model_dump_json()) == before
