"""Run production starter selection, package reading, customer generation, design chat or analysis on a real local model.

From the repository root:
  PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case compact

Start the local server separately, on CPU for a CPU probe. No responses are mocked.
Every run gets a fresh cache; the trace contains built-in sample prompts, not headers or keys.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import httpx
from PIL import Image, ImageDraw
from pydantic import SecretStr

from store_emulator.application import template_assortment
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.layout_options import TemplateLayoutRequest
from store_emulator.domain.online import DesignMessage, OnlineRunResult, VariantComparison
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.types import Weekday
from store_emulator.engine.generators.persona import Pace, generate_batched
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.layout_edit import apply_layout_edit, draft_layout_edit
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.analysis import paired_deltas, segment_deltas, summarize, switches
from store_emulator.engine.online.analyst import answer_online_question, online_facts
from store_emulator.engine.online.design_chat import apply_design, chat_design
from store_emulator.engine.online.policies import RulePolicy
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers
from store_emulator.engine.package_reader import read_pack
from store_emulator.engine.perception.product_images import bundled_product_image
from store_emulator.engine.perception.shelf_render import load_font
from store_emulator.engine.validation import validate


design_requests = {
    "design-color-ko": "테마 색상만 #00AA33으로 변경해 주세요. 나머지 설정은 모두 그대로 두세요.",
    "design-long-history": "테마 색상만 #00AA33으로 변경해 주세요. 나머지 설정은 모두 그대로 두세요.",
    "design-free-popup": "Set delivery to free and remove the welcome popup. Keep every other option unchanged.",
    "design-neon": "Change only the page style to neon. Keep every other option unchanged.",
    "design-calm": "Make the shop feel premium and calm. Remove pressure tactics. Keep shipping fees and all discount amounts unchanged.",
}
layout_requests = {
    "layout-price-krw": "Green Tea 가격만 3,000원으로 바꿔 주세요. 다른 상품이나 설정은 그대로 유지해 주세요.",
    "layout-discount-promo": "Discount Green Tea by 10 percent and put a SALE sign on Potato Chips. Change nothing else.",
    "layout-category": "Reduce all prices on the Drinks shelf by 10 percent. Change nothing else.",
    "layout-move": "Move Green Tea to eye level on its current Drinks shelf. Keep its price and other products unchanged.",
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--case", choices=["compact", "cafe", "book", "pack-jam", "pack-label", "pack-wrong-variant", "pack-blank",
    "persona-neighborhood", "persona-cafe", "analyst-comparison", "analyst-forecast", *design_requests, *layout_requests], default="compact")
parser.add_argument("--endpoint", default="http://127.0.0.1:8081/v1")
parser.add_argument("--model", default="openai/local-model")
parser.add_argument("--output", type=Path, default=Path(".data/local-model-probes"))
args = parser.parse_args()
endpoint = urlsplit(args.endpoint)
if endpoint.hostname not in {"localhost", "127.0.0.1", "::1"} or endpoint.scheme != "http":
    parser.error("Use an HTTP loopback endpoint for the local model.")
output = args.output / f"{args.case}-{time.time_ns()}"
output.mkdir(parents=True)
options = TemplateLayoutRequest(template_id="compact_cvs", width=8, height=6, currency="KRW")
description = "동네 주민이 자주 방문하는 동네 편의점"
if args.case == "cafe":
    options = TemplateLayoutRequest(template_id="cafe_bakery", width=10, height=8, currency="JPY",
        products_per_category=1, excluded_categories=["beer_alcohol"],
        requirements="No alcoholic products. One product per category. Preserve the cafe and bakery shelf purposes.")
    description = "近所の住民が訪れる小さなカフェ。パンとコーヒー。"
elif args.case == "book":
    options = TemplateLayoutRequest(template_id="bookstore", width=8, height=6, currency="USD",
        products_per_category=2, requirements="Books and stationery for local residents; no food or drinks.")
    description = "Petite librairie de quartier, livres et papeterie."
client = LiteLLMClient(LLMConfig(model=args.model, api_base=args.endpoint, api_key=SecretStr("local-probe"),
    temperature=.2 if args.case in design_requests or args.case.startswith("analyst-") else 0, seed=0,
    max_tokens=900 if args.case in design_requests else 1500 if args.case in layout_requests else 400 if args.case.startswith("pack-") else 1600 if args.case.startswith("analyst-") else 4096 if args.case.startswith("persona-") else 5000,
    timeout_sec=180, max_parallel=1,
    chat_template_thinking=False, structured_output="json_schema", structured_sdk_retries=0,
    cache_dir=str(output / "cache")))
send = httpx.AsyncClient.send
calls = 0


async def traced_send(self, request, *positional, **keywords):
    global calls
    started = time.perf_counter()
    response = await send(self, request, *positional, **keywords)
    if request.url.host == endpoint.hostname:
        await response.aread()
        calls += 1
        record = {"call": calls, "status": response.status_code, "seconds": round(time.perf_counter() - started, 3),
            "request": json.loads(request.content), "response": response.json()}
        for message in record["request"].get("messages", []):
            if isinstance(message.get("content"), list):
                for part in message["content"]:
                    if part.get("type") == "image_url":
                        part["image_url"] = {"url": "[input saved as image.png]"}
        with (output / "http.jsonl").open("a") as trace:
            trace.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"Call {calls}: HTTP {response.status_code}, {record['seconds']}s", flush=True)
    return response


started = time.perf_counter()
result = {"case": args.case, "model": args.model, "endpoint": args.endpoint}
try:
    if args.case in design_requests:
        site = build_site("fashion", site_id="cpu-probe", currency="KRW" if args.case in {"design-color-ko", "design-long-history"} else "USD")
        site.options.welcome_popup = "coupon"
        site.options.coupon_percent = 15
        site.options.shipping_fee = 499
        before = site.options.model_dump(mode="json")
        messages = [DesignMessage(role="owner", text=design_requests[args.case])]
        if args.case == "design-long-history":
            old = ("동네 주민이 편안하게 쇼핑할 수 있는 온라인 매장을 만들고 싶습니다. 기존 배송비와 할인율은 그대로 유지해주세요. 상품 색상과 크기는 다양합니다. " * 18)[:1200]
            messages = [DesignMessage(role="owner" if i % 2 == 0 else "designer", text=old) for i in range(38)] + messages
        with patch.object(httpx.AsyncClient, "send", traced_send):
            reply = asyncio.run(chat_design(client, site, site.options, messages))
        edited, changed = apply_design(site.options, reply.changes, site.currency)
        after = edited.model_dump(mode="json")
        expected = {
            "design-color-ko": {"theme_color": "#00AA33"},
            "design-long-history": {"theme_color": "#00AA33"},
            "design-free-popup": {"shipping_fee": 0, "welcome_popup": "none"},
            "design-neon": {"page_style": "neon"},
            "design-calm": {"urgency": False, "social_proof": False, "welcome_popup": "none"},
        }[args.case]
        allowed = set(expected) | ({"page_style", "theme_color"} if args.case == "design-calm" else set())
        issues = [f"Expected {key}={value!r}, received {after[key]!r}" for key, value in expected.items() if after[key] != value]
        issues += [f"Unrequested change: {key}" for key in changed if key not in allowed]
        result.update(success=not issues, request=design_requests[args.case], before=before, after=after,
            reply=reply.model_dump(mode="json"), changed=changed, issues=issues, messages=len(messages),
            characters=sum(len(message.text) for message in messages))
    elif args.case in layout_requests:
        currency = "KRW" if args.case == "layout-price-krw" else "USD"
        scale = 10 if currency == "KRW" else 1
        store = Store(id="cpu-layout", name="Corner shop", type="convenience", currency=currency, grid_size=(8, 8), racks=[
            Rack(id="drinks", rack_name="Drinks", type="shelf", shape=[[1]], position=(3, 3), slots=[
                Slot(block=0, face="N", level=1, items=[SlotItem(sku="tea", name="Green Tea", price=500 * scale)]),
                Slot(block=0, face="N", level=2, items=[SlotItem(sku="water", name="Mineral Water", price=100 * scale)]),
                Slot(block=0, face="N", level=3, items=[])]),
            Rack(id="snacks", rack_name="Snacks", type="shelf", shape=[[1]], position=(5, 3), slots=[
                Slot(block=0, face="N", level=1, items=[SlotItem(sku="chips", name="Potato Chips",
                    price=200 * scale, regular_price=300 * scale)])])])

        def products(layout):
            return {item.sku: {"rack": rack.id, "level": slot.level, **item.model_dump(mode="json")}
                    for rack in layout.racks for slot in rack.slots for item in slot.items}

        expected = products(store)
        if args.case == "layout-price-krw":
            expected["tea"]["price"] = 3000
        elif args.case == "layout-discount-promo":
            expected["tea"].update(price=450, regular_price=500)
            expected["chips"]["promo"] = "SALE"
        elif args.case == "layout-category":
            expected["tea"]["price"], expected["water"]["price"] = 450, 90
        else:
            expected["tea"]["level"] = 3
        with patch.object(httpx.AsyncClient, "send", traced_send):
            reply = asyncio.run(draft_layout_edit(client, layout_requests[args.case], store, currency))
        edited, applied, warnings = apply_layout_edit(store, reply.changes, currency)
        after = products(edited)
        issues = [f"Unexpected fields or placement for {sku}" for sku in expected if after.get(sku) != expected[sku]]
        if set(after) != set(expected):
            issues.append("Product identities changed")
        result.update(success=not issues and not warnings, request=layout_requests[args.case],
            reply=reply.model_dump(mode="json"), applied=applied, warnings=warnings, issues=issues)
        (output / "before.json").write_text(store.model_dump_json(indent=2))
        (output / "after.json").write_text(edited.model_dump_json(indent=2))
    elif args.case.startswith("analyst-"):
        control = build_site("fashion", site_id="control", currency="USD")
        control.name = "Control"
        variant = control.model_copy(deep=True)
        variant.id, variant.name = "variant", "Quick add without popup"
        variant.options.quick_add, variant.options.welcome_popup = True, "none"
        shoppers = sample_shoppers(control, 8, seed=4, missions={"purchase": .5, "browse": .5}, mobile_share=.5)
        by_id = {shopper.id: shopper for shopper in shoppers}

        async def visits(site):
            return [await run_session(site, shopper, RulePolicy(), seed=4, max_steps=20, render=False) for shopper in shoppers]

        a, b = asyncio.run(visits(control)), asyncio.run(visits(variant))
        won, lost, changed, rows = switches(a, b)
        report = OnlineRunResult(run_id="cpu-analyst", name="Two design changes", policy="rule", currency="USD",
            shoppers=shoppers, variants=[summarize(control, by_id, a), summarize(variant, by_id, b)],
            comparisons=[VariantComparison(site_id=variant.id, site_name=variant.name, deltas=paired_deltas(a, b, seed=4),
                segments=segment_deltas(a, b, by_id, seed=4), won=won, lost=lost, changed=changed, switches=rows)])
        question = ("What exact real-world sales uplift will this store achieve next year?" if args.case == "analyst-forecast"
                    else "Did the variant improve conversion? Quote both overall conversion rates and say whether the difference is clear.")
        (output / "run.json").write_text(report.model_dump_json(indent=2))
        (output / "facts.txt").write_text(online_facts(report))
        with patch.object(httpx.AsyncClient, "send", traced_send):
            reply = asyncio.run(answer_online_question(client, report, question, [], seed=0))
        issues = []
        if args.case == "analyst-forecast":
            if "does not show" not in reply.answer.casefold() or any(c.isdigit() for c in reply.answer):
                issues.append("Expected an explicit refusal to invent a future real-world forecast")
        else:
            if not reply.figures or "25" not in reply.answer or "12.5" not in reply.answer:
                issues.append("Expected cited overall conversion rates of 25% and 12.5%")
            if not any(word in reply.answer.casefold() for word in ["not clear", "includes zero", "includes 0", "not statistically significant"]):
                issues.append("Expected the interval including zero to be recognized as inconclusive")
            if any(word in reply.answer.casefold() for word in ["is statistically significant", "is significant", "significant increase", "significant improvement"]):
                issues.append("Contradicts this fixture's interval including zero")
        result.update(success=not issues, question=question, reply=reply.model_dump(mode="json"), issues=issues,
            expected_conversion=[summary.conversion for summary in report.variants])
    elif args.case.startswith("persona-"):
        address, currency, categories, budget = "Mapo-gu, Seoul, South Korea", "KRW", None, (3000, 10000)
        profile = "동네 주민. 편의점에서 간단한 간식과 음료를 사러 옵니다. 1회 예산은 3,000~10,000원입니다."
        if args.case == "persona-cafe":
            address, currency, categories, budget = "Tokyo, Japan", "JPY", ["coffee", "bakery"], (500, 1500)
            profile = "近所の住民がパンとコーヒーを買いに訪れる小さなカフェです。一人の予算は500〜1500円です。"
        schedules = [DaySchedule(day=day, is_open=day == Weekday.MON, open_hour=9, close_hour=10) for day in Weekday]
        estimates = {}
        with patch.object(httpx.AsyncClient, "send", traced_send):
            people = asyncio.run(generate_batched(client, address, profile, schedules, seed=4,
                batch_size=2, max_concurrent=1, categories=categories, currency=currency,
                pace=lambda usual: Pace(daily_cap=2, batch_size=2, sample_cap=2), estimates=estimates))
        written = [person for person in people if not person.twin_of]
        issues = []
        if not written or len({person.id for person in people}) != len(people):
            issues.append("No written customers or duplicate customer IDs")
        if any(person.day != Weekday.MON or person.arrival_hour != 9 for person in people):
            issues.append("Arrival outside the open hour")
        if categories and any(category not in categories for person in people for category in person.preferred_categories):
            issues.append("Preference outside the supplied category list")
        if any(person.budget_min < budget[0] or person.budget_max == 0 or person.budget_max > budget[1] for person in people):
            issues.append("Budget outside the supplied range")
        result.update(success=not issues, address=address, currency=currency, profile=profile, categories=categories,
            estimates=estimates, count=len(people), written=[person.model_dump(mode="json") for person in written], issues=issues)
        (output / "personas.json").write_text(json.dumps([person.model_dump(mode="json") for person in people], ensure_ascii=False, indent=2))
    elif args.case.startswith("pack-"):
        products = ["Strawberry Jam 340g", "Apricot Jam 340g", "Marmalade 340g"]
        picture = Image.new("RGB", (600, 800), "white")
        if args.case == "pack-jam":
            picture = bundled_product_image("/api/catalog-images/starter-01/15.webp")
            assert picture is not None
        elif args.case in {"pack-label", "pack-wrong-variant"}:
            # A deterministic positive-control label, not a photograph or model-generated picture.
            drawing = ImageDraw.Draw(picture)
            drawing.rounded_rectangle((100, 110, 500, 740), radius=70, fill="#dbeed0", outline="#245737", width=6)
            drawing.rounded_rectangle((220, 30, 380, 140), radius=15, fill="#245737")
            drawing.rectangle((110, 280, 490, 630), fill="white")
            for y, label, size in [(320, "LEAFY", 55), (420, "GREEN TEA", 44), (520, "500 ml", 48)]:
                drawing.text((300, y), label, font=load_font(size, True), fill="#153d24", anchor="mt")
            products = ["Leafy Green Tea 1 L", "Leafy Black Tea 500 ml"]
            if args.case == "pack-label":
                products.insert(0, "Leafy Green Tea 500 ml")
        picture.save(output / "image.png")
        with patch.object(httpx.AsyncClient, "send", traced_send):
            reading = asyncio.run(read_pack(client, picture, products))
        issues = []
        expected_match = "Leafy Green Tea 500 ml" if args.case == "pack-label" else ""
        if reading.shelf_product != expected_match:
            issues.append(f"Expected product match {expected_match!r}, received {reading.shelf_product!r}")
        if args.case in {"pack-jam", "pack-blank"} and (reading.brand or reading.size):
            issues.append("Unlabelled image acquired a brand or printed size")
        result.update(success=not issues, products=products, reading=reading.model_dump(mode="json"), issues=issues)
    else:
        result.update(layout=options.model_dump(mode="json"), description=description)
        store = generate_store(options.template_id, currency=options.currency, options=options)
        # Inject the real loopback client at the provider-selection seam, without editing saved settings.
        with patch.object(template_assortment, "assistive_client", return_value=client), \
                patch.object(httpx.AsyncClient, "send", traced_send):
            stocked, choices = template_assortment.select_initial_assortment(SimulationConfig(), store, options, description)
        issues = [issue.model_dump(mode="json") for issue in validate(stocked)]
        result.update(success=not issues, choices=[choice.model_dump(mode="json") for choice in choices], issues=issues)
        (output / "store.json").write_text(stocked.model_dump_json(indent=2))
except Exception as error:
    result.update(success=False, error=repr(error))
result.update(seconds=round(time.perf_counter() - started, 2), calls=calls, usage=client.get_usage().model_dump(mode="json"))
(output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({"output": str(output), **{key: result[key] for key in ("success", "seconds", "calls", "usage")}}, indent=2))
raise SystemExit(0 if result["success"] else 1)
