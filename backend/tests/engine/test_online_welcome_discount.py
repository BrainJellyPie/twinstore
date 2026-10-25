"""Welcome offers must describe the configured discount, including no discount."""

import asyncio
import json
import random

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.online import ActionKind, CartLine
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.browser import apply, build_page, cart_totals, initial_state, numbering, outline
from store_emulator.engine.online.policies import Memory, ModelPolicy, RulePolicy, StepView
from tests.engine.test_online_store import _shoppers, _site


@pytest.mark.parametrize("popup", ["newsletter", "coupon"])
@pytest.mark.parametrize("percent", [0, 5, 90])
@pytest.mark.parametrize("code", ["", "SAVE"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_welcome_copy_matches_the_discount_actually_applied(popup, percent, code, currency):
    site = _site(welcome_popup=popup, coupon_percent=percent, coupon_code=code,
                 shipping_fee=0, service_fee=0, preselected_addon_percent=0)
    site.currency = currency
    site.products[0].price = 10000
    state = initial_state(site)
    page = build_page(site, state)
    assert page.overlay is not None
    text = " ".join([page.overlay.title, *(line.text for line in page.overlay.lines)])
    if percent:
        assert f"{percent}% off" in text
    else:
        assert "%" not in text and "discount" not in text.casefold()
    assert "WELCOME" not in text
    accept = next(c for c in page.active if c.action.kind == ActionKind.ACCEPT_POPUP)
    updated = apply(site, state, accept.action)
    assert updated.coupon_applied is (percent > 0)
    updated.cart = [CartLine(product_id=site.products[0].id)]
    total = cart_totals(site, updated.cart, updated, at_review=True)
    assert total.discount == 100 * percent
    assert total.total == 10000 - 100 * percent
    assert not state.coupon_applied


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("popup", ["newsletter", "coupon"])
@pytest.mark.parametrize("percent", [0, 15])
def test_local_model_sees_only_the_real_welcome_incentive(monkeypatch, tmp_path, provider, mode, popup, percent):
    site = _site(welcome_popup=popup, coupon_percent=percent, coupon_code="")
    state = initial_state(site)
    page = build_page(site, state)
    numbers = numbering(page, 123)
    target = next(c for c in page.active if c.action.kind == ActionKind.ACCEPT_POPUP)
    calls = []

    def respond(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        answer = json.dumps({"option": numbers[target.index], "thought": "I'll continue shopping."})
        if provider == "ollama":
            payload = {"model": "welcome-test", "done": True, "done_reason": "stop",
                       "message": {"role": "assistant", "content": answer}, "prompt_eval_count": 10, "eval_count": 5}
        else:
            payload = {"id": "offline", "object": "chat.completion", "created": 0, "model": body["model"],
                       "choices": [{"index": 0, "finish_reason": "stop",
                                    "message": {"role": "assistant", "content": answer}}]}
        return httpx.Response(200, request=request, json=payload)

    def send(self, request, *args, **kwargs): return respond(request)
    async def asend(self, request, *args, **kwargs): return respond(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/welcome-test" if provider == "ollama" else "openai/welcome-test",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path), seed=0))
    policy = ModelPolicy(client, vision=False)
    shopper = _shoppers(site, 1)[0]
    view = StepView(page, state, numbers, outline(page, site))
    for _ in range(2):
        choice = asyncio.run(policy.choose(site, shopper, view, Memory(), random.Random(7)))
        assert choice.source == "model" and choice.control.action.kind == ActionKind.ACCEPT_POPUP
    assert len(calls) == 1 and client.get_usage().cached_requests == 1
    user = calls[0]["messages"][-1]["content"]
    assert page.overlay is not None and page.overlay.title in user
    assert "10% off" not in user and "WELCOME" not in user
    if percent:
        assert "15% off" in user


@pytest.mark.parametrize("popup", ["newsletter", "coupon"])
def test_no_discount_does_not_give_rule_shoppers_a_discount_incentive(popup):
    site = _site(welcome_popup=popup, coupon_percent=0)
    state = initial_state(site)
    page = build_page(site, state)
    view = StepView(page, state, numbering(page), outline(page, site))
    shopper = _shoppers(site, 1)[0]
    shopper.price_sensitivity = 1
    shopper.mission = "deal_hunt"
    # Seed 4: no immediate exit, then a draw below the base acceptance chance.
    accepted = asyncio.run(RulePolicy().choose(site, shopper, view, Memory(), random.Random(4)))
    assert accepted.control.action.kind == ActionKind.ACCEPT_POPUP
    assert "discount" not in accepted.thought.casefold()
    # Seed 0: no immediate exit, then .758: below the old .90 discount incentive,
    # but above the ordinary .15 chance to accept without an incentive.
    closed = asyncio.run(RulePolicy().choose(site, shopper, view, Memory(), random.Random(0)))
    assert closed.control.action.kind == ActionKind.CLOSE_POPUP
