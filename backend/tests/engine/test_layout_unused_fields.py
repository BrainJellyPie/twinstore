"""Unused null fields must not discard a complete, applicable model edit."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.layout_edit import _EditChange, draft_layout_edit
from store_emulator.engine.marketing.experiment_design import _Change, _Draft, design_experiment
from store_emulator.engine.marketing.variants import apply_changes
from tests.engine.test_layout_applied_changes import fixture


CHANGES = [
    {"kind": "price", "product": "Tea", "price": 1.49},
    {"kind": "discount", "product": "Tea", "percent": -20},
    {"kind": "promo", "product": "Tea", "promo": "NEW"},
    {"kind": "move", "product": "Tea", "shelf": "Destination", "level": 3},
    {"kind": "category_price", "category": "Drinks", "percent": -10},
    {"kind": "package", "product": "Tea", "package": "New pack"},
]


@pytest.mark.parametrize("kind,change", [(kind, change) for kind in ["layout", "experiment"]
    for change in CHANGES if kind == "experiment" or change["kind"] != "package"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("spelling", ["exact", "title", "padded_upper"])
def test_unused_nulls_preserve_edit_effects_and_cache(monkeypatch, tmp_path, kind, change, mode, spelling):
    store, _ = fixture("valid")
    before = store.model_dump_json()
    fields = {"product", "price", "percent", "promo", "shelf", "level", "category"}
    if kind == "experiment":
        fields.add("package")
    nullable = {**dict.fromkeys(fields), **change}
    nullable["kind"] = (change["kind"] if spelling == "exact" else change["kind"].title() if spelling == "title"
                        else f"\u3000{change['kind'].upper()}\t")
    payload = {"name": "Draft", **({"changes": [nullable]} if kind == "layout" else {
        "variants": [{"name": "Variant", "changes": [nullable]}]})}
    if kind == "experiment":
        payload["engine"] = " VLM " if spelling == "padded_upper" else "Rule" if spelling == "title" else "rule"
    calls = []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/unused-edit-fields", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def draft():
                if kind == "layout":
                    return await draft_layout_edit(client, "Apply the requested edit", store, "USD")
                return await design_experiment(client, "Compare the requested edit", store, "USD", [("New pack", "asset")])

            result = await draft()
            changes = result.changes if kind == "layout" else result.variants[0].changes
            assert len(changes) == 1 and changes[0].kind == change["kind"]
            if kind == "experiment":
                assert result.engine == ("vlm" if change["kind"] == "package" or spelling == "padded_upper" else "rule")
            edited, applied, warnings = apply_changes(store, changes, package_uris={"asset": "new-package.png"})
            assert len(applied) == 1 and not warnings and not result.warnings
            items = [i for r in edited.racks for s in r.slots for i in s.items if i.sku == "tea"]
            assert len(items) == 1
            if change["kind"] in {"price", "discount", "category_price"}:
                assert items[0].price == {"price": 149, "discount": 159, "category_price": 179}[change["kind"]]
            elif change["kind"] == "promo":
                assert items[0].promo == "NEW"
            elif change["kind"] == "move":
                assert any(s.level == 3 and any(i.sku == "tea" for i in s.items) for s in edited.racks[2].slots)
            else:
                assert items[0].image_url == "new-package.png" and result.engine == "vlm"
            assert await draft() == result and len(calls) == 1
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("model,change", [(model, change) for model in [_EditChange, _Change]
    for change in CHANGES if model is _Change or change["kind"] != "package"])
@pytest.mark.parametrize("spelling", ["exact", "title", "padded_upper"])
def test_required_text_and_malformed_unused_text_still_fail(model, change, spelling):
    change = {**change, "kind": (change["kind"] if spelling == "exact" else change["kind"].title() if spelling == "title"
                               else f"\u3000{change['kind'].upper()}\t")}
    for field, value in change.items():
        if field != "kind" and isinstance(value, str):
            with pytest.raises(ValidationError):
                model.model_validate({**change, field: None})
    for field in set(model.model_fields) - set(change) - {"price", "percent", "level"}:
        for value in [12, [], {}]:
            with pytest.raises(ValidationError):
                model.model_validate({**change, field: value})


@pytest.mark.parametrize("model", [_EditChange, _Change])
@pytest.mark.parametrize("kind", ["newPrice", "category price", "", None, True, 1, [], {}])
def test_unknown_or_wrong_type_operation_is_not_defaulted(model, kind):
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps({"kind": kind, "product": "Tea", "price": 1.49}), strict=True)


def test_spelling_recovery_does_not_enable_package_changes_for_saved_layouts():
    with pytest.raises(ValidationError):
        _EditChange.model_validate_json(json.dumps({"kind": " PACKAGE ", "product": "Tea", "package": "New pack"}), strict=True)


@pytest.mark.parametrize("engine", ["rule based", "VLMx", "", None, True, 1, [], {}])
def test_unknown_experiment_engine_is_not_guessed(engine):
    with pytest.raises(ValidationError):
        _Draft.model_validate_json(json.dumps({"name": "Draft", "engine": engine,
            "variants": [{"name": "Variant", "changes": [CHANGES[0]]}]}), strict=True)
