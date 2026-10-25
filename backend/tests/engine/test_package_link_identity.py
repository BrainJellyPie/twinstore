"""A missing pack match is never a product identity, even with blank catalog names."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.application import shelf_lab
from store_emulator.application.storage.io import read_json
from store_emulator.engine import llm_client
from tests.engine.test_scenario_target_matching import target_store
from tests.server.test_package_read_conflicts import pack


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("case", ["empty", "null", "omitted", "whitespace", "unknown", "blank_names_only",
    "padded", "duplicate_skus", "duplicate_same_sku", "padded_prefix", "ambiguous_prefix", "existing_link"])
def test_package_link_requires_a_nonblank_unique_normalized_name(pack, monkeypatch, tmp_path, mode, case):
    pid, aid, config = pack
    store = target_store()
    items = store.racks[0].slots[0].items
    items[0].name = ""  # An unknown model match must never select this SKU.
    items[1].name = "\u3000Green Tea 500 ml\t"
    items[2].name = "   "
    target, expected = "", ""
    if case in {"padded", "duplicate_skus", "duplicate_same_sku", "existing_link"}:
        target, expected = "GREEN TEA 500 ML", "s-zero"
        if case.startswith("duplicate"):
            items[2].name = " Green Tea 500 ml "
            if case == "duplicate_same_sku":
                items[2].sku = "s-zero"
            else:
                expected = ""
    elif case in {"padded_prefix", "ambiguous_prefix"}:
        target = ("Leafy tea " * 20)[:120]
        items[1].name = "\u3000" + target + " 500 ml\t"
        expected = "s-zero"
        if case == "ambiguous_prefix":
            items[2].name = " " + target + " 1 litre "
            expected = ""
    elif case == "null":
        target = None
    elif case == "whitespace":
        target = "\u3000\t"
    elif case == "unknown":
        target = "Not listed 500 ml"
    elif case == "blank_names_only":
        for rack in store.racks:
            for slot in rack.slots:
                for item in slot.items:
                    item.name = ""
    if case == "existing_link":
        expected = "manual-choice"
        shelf_lab.update_package(pid, aid, shelf_lab.PackageUpdate(sku=expected))
    monkeypatch.setattr(shelf_lab, "_load_store", lambda *args: store)
    monkeypatch.setattr(shelf_lab, "capture_llm_config", lambda config, model: config.engines.vlm_glance.llm.model_copy(update={
        "model": "openai/package-identity", "api_base": "http://127.0.0.1:8081/v1", "structured_output": mode,
        "cache_dir": str(tmp_path / "cache")}))
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = {"name": "Read tea", "brand": "Read brand", "confidence": .9}
        if case != "omitted":
            payload["shelf_product"] = target
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def completion(**kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)
            return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    path = shelf_lab.package_path(pid, aid)
    image_before, store_before = path.read_bytes(), store.model_dump_json()
    result = shelf_lab.read_package(pid, aid, setup_id="test_setup", config=config)
    assert result.asset.sku == expected
    assert result.linked is bool(expected and case != "existing_link")
    assert result.asset.name == "Read tea" and result.asset.brand == "Read brand"
    assert result.reading.confidence == .9
    repeated = shelf_lab.read_package(pid, aid, setup_id="test_setup", config=config)
    assert not repeated.linked and repeated.asset.sku == expected
    assert len(calls) == 1
    saved = read_json(path.with_suffix(".json"))
    assert saved.get("sku", "") == expected and saved["reading"]["name"] == "Read tea"
    assert path.read_bytes() == image_before and store.model_dump_json() == store_before
