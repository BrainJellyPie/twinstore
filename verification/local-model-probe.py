"""Run production starter selection, package reading, customer generation, design chat or analysis on a real local model.

From the repository root:
  PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case compact

Start the local server separately, on CPU for a CPU probe. No responses are mocked.
Every run gets a fresh cache unless --cache-from explicitly copies a saved cache.
The trace contains built-in sample prompts, not headers or keys.
Use --temperature 1 to match the default customer writer; zero-temperature
customer probes retain their original deterministic stress configuration.
"""

import argparse
import asyncio
import base64
import json
import re
import shutil
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import httpx
from PIL import Image, ImageDraw
from pydantic import SecretStr

from store_emulator.application import online, template_assortment
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.interview import AnalystMessage
from store_emulator.domain.layout_options import TemplateLayoutRequest
from store_emulator.domain.online import DesignMessage, OnlineRunRequest, OnlineRunResult, VariantComparison
from store_emulator.domain.persona import AGE_GROUPS, GENDERS, Persona
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.types import Weekday
from store_emulator.engine.generators.persona import HourlyProfile, Pace, TradeAreaProfile, analyze_daily_traffic, generate_batched, generate_personas_for_day
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.recognize import FacingGroup, VLMLabeler, describe
from store_emulator.engine.layout_edit import apply_layout_edit, draft_layout_edit
from store_emulator.engine.generators.store_setup_writer import draft_store_setup
from store_emulator.engine.generators.profile_writer import draft_profile
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.catalog import build_site, site_from_store
from store_emulator.engine.online.analysis import paired_deltas, segment_deltas, summarize, switches
from store_emulator.engine.online.analyst import answer_online_question, online_facts
from store_emulator.engine.online.design_chat import apply_design, chat_design
from store_emulator.engine.online.policies import RulePolicy
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers
from store_emulator.engine.online.store_changes import apply_store_changes
from store_emulator.engine.package_reader import read_pack
from store_emulator.engine.perception.product_images import bundled_product_image
from store_emulator.engine.perception.shelf_render import load_font
from store_emulator.engine.validation import validate


def customer_text_issues(people: list[Persona]) -> list[str]:
    """Catch observed field mix-ups; passing these checks is not a semantic-quality guarantee."""
    issues: list[str] = []
    seen: set[str] = set()
    seen_without_intro_age: set[str] = set()
    for person in people:
        fingerprint = person.model_dump_json(exclude={"id", "twin_of"})
        exact_repeat = fingerprint in seen
        if exact_repeat:
            issues.append(f"{person.id}: identical independently written profile; inspect customer diversity")
        without_intro_age = person.model_dump(mode="json", exclude={"id", "twin_of"})
        # A different introductory age within the same age group cannot hide
        # otherwise copied records. Keep quantities, family ages and all other fields.
        without_intro_age["description"] = re.sub(
            r"^(\s*(?:an?\s+)?)\d{1,3}([- ]year[- ]old\b)", r"\1<age>\2", person.description, count=1, flags=re.IGNORECASE,
        )
        age_neutral = json.dumps(without_intro_age, sort_keys=True, ensure_ascii=False)
        if age_neutral in seen_without_intro_age and not exact_repeat:
            issues.append(f"{person.id}: profile differs only in its introductory age; inspect customer diversity")
        seen.add(fingerprint)
        seen_without_intro_age.add(age_neutral)
        for field in ("identity", "purpose", "description", "intent", "behavior_tendency"):
            value = getattr(person, field)
            if value and not re.search(r"[A-Za-z]{2,}", value):
                issues.append(f"{person.id}: {field} contains no English words despite the prompt's language instruction")
        if person.identity.strip().casefold() == person.purpose.strip().casefold():
            issues.append(f"{person.id}: identity and visit purpose are the same label; inspect the field meanings")
        if person.behavior_tendency.strip() in {*AGE_GROUPS, *GENDERS}:
            issues.append(f"{person.id}: behavior_tendency is a demographic label, not a behavior")
    return issues


design_requests = {
    "design-color-ko": "테마 색상만 #00AA33으로 변경해 주세요. 나머지 설정은 모두 그대로 두세요.",
    "design-long-history": "테마 색상만 #00AA33으로 변경해 주세요. 나머지 설정은 모두 그대로 두세요.",
    "design-free-popup": "Set delivery to free and remove the welcome popup. Keep every other option unchanged.",
    "design-free-popup-scan": "Set delivery to free and remove the welcome popup. Keep every other option unchanged.",
    "design-neon": "Change only the page style to neon. Keep every other option unchanged.",
    "design-calm": "Make the shop feel premium and calm. Remove pressure tactics. Keep shipping fees and all discount amounts unchanged.",
    "design-no-free-shipping": "Disable free shipping entirely. Charge $4.99 shipping on every order, regardless of the order total. Do not change any other option.",
    "design-always-free": "Set the free-shipping threshold to zero so every order gets free shipping. Keep the stored shipping fee and all other options unchanged.",
    "design-threshold-usd": "Set the free-shipping threshold to $50. Keep the stored shipping fee and all other options unchanged.",
    "design-threshold-fractional": "Set the free-shipping threshold to $7.25. Keep the stored shipping fee and all other options unchanged.",
    "design-threshold-krw": "무료 배송 기준을 30,000원으로 바꿔주세요. 기존 배송비와 다른 설정은 그대로 두세요.",
}
layout_requests = {
    "layout-missing-product": "Set only Dragonfruit Juice to $3.00. If that product is absent, do not change or substitute any existing product. Keep all other products unchanged.",
    "layout-missing-product-ko": "Dragonfruit Juice 상품이 목록에 있을 때만 가격을 3달러로 바꿔주세요. 목록에 없으면 아무것도 바꾸지 마세요. 다른 상품으로 대체하지 마세요.",
    "layout-unsupported-edit": "Paint the shop walls red. Do not change any product prices, signs or shelf placements.",
    "layout-no-changes": "Keep every product price, sign and shelf placement exactly as it is. Do not make any changes.",
    "layout-price-krw": "Green Tea 가격만 3,000원으로 바꿔 주세요. 다른 상품이나 설정은 그대로 유지해 주세요.",
    "layout-discount-promo": "Discount Green Tea by 10 percent and put a SALE sign on Potato Chips. Change nothing else.",
    "layout-category": "Reduce all prices on the Drinks shelf by 10 percent. Change nothing else.",
    "layout-bulk-bridge": "Reduce all prices on the Drinks shelf by 10 percent. Change nothing else.",
    "layout-move": "Move Green Tea to eye level on its current Drinks shelf. Keep its price and other products unchanged.",
    "layout-free-item": "Make only Mineral Water free. Keep all other products and settings unchanged.",
    "layout-full-discount": "Give Green Tea a 100 percent discount, making it free while showing its original $5.00 price. Change nothing else.",
    "layout-set-discount": "Set Green Tea to 20 percent off its regular price. Keep all other products and settings unchanged.",
    "layout-extra-discount": "Green Tea is already discounted from $5.00 to $4.00. Take an extra 10 percent off its CURRENT $4.00 price. Keep its original $5.00 reference price unchanged. Change nothing else.",
    "layout-extra-discount-ko": "Green Tea는 정가 5,000원에서 4,000원으로 이미 할인 중입니다. 현재 판매가 4,000원에서 추가로 10% 할인해 주세요. 정가 표시는 5,000원으로 유지하고 다른 상품은 변경하지 마세요.",
    "layout-sequence": "First set Green Tea to a new regular shelf price of $4.00, then discount it by 10 percent. Put a SALE sign on Mineral Water. Change nothing else.",
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--case", choices=["setup-unspecified", "setup-night", "setup-24h", "setup-pharmacy", "hypermarket", "compact", "cafe", "book", "book-repurpose", "book-excluded", "book-price-range", "book-price-range-krw", "book-price-range-jpy", "book-price-unavailable", "pack-jam", "pack-label", "pack-brand-suffix", "pack-mixed-quantities", "pack-large-catalog", "pack-wrong-variant", "pack-blank", "pack-multipack", "pack-multipack-unlisted", "pack-multipack-count", "pack-multipack-count-unlisted", "pack-multipack-container-count", "pack-multipack-container-count-unlisted",
    "capture-price", "capture-price-krw", "capture-coupon-price", "capture-blank-price", "capture-saving", "capture-saving-up-to", "capture-cash-back", "capture-off", "capture-saving-krw", "capture-was-price", "capture-free-price", "capture-coupon-value", "capture-earn-reward", "capture-reward-value", "capture-rewards-price", "capture-reward-krw", "capture-points", "capture-points-krw", "capture-points-price", "capture-volume-only", "capture-count-only", "capture-count-cash-price", "capture-starting-price", "capture-upper-price", "capture-starting-price-krw", "capture-unit-price", "capture-unit-price-krw", "capture-pack-unit-price", "capture-pack-price", "capture-bottle-price", "capture-container-count-price", "capture-deposit-price", "capture-deposit-suffix", "capture-deposit-included-price",
    "setup-unspecified-ko", "setup-hours-only", "setup-days-only", "setup-location-only",
    "traffic-24h", "traffic-24h-varied", "traffic-last-hour", "traffic-last-hour-zero",
    "profile-draft-night", "profile-draft-bookstore", "profile-draft-sparse",
    "persona-neighborhood", "persona-unspecified", "persona-24h", "persona-cafe", "persona-local-categories", "persona-bookstore", "persona-us", "persona-fractional", "persona-nightmarket", "persona-nightmarket-batch", "persona-nightmarket-local-batches", "analyst-comparison", "analyst-forecast", "analyst-history", *design_requests, *layout_requests], default="compact")
parser.add_argument("--endpoint", default="http://127.0.0.1:8081/v1")
parser.add_argument("--model", default="openai/local-model")
parser.add_argument("--temperature", type=float, help="Override the case's sampling temperature (0 to 2); the default customer writer uses 1")
parser.add_argument("--structured-output", choices=["json_schema", "json"], default="json_schema")
parser.add_argument("--output", type=Path, default=Path(".data/local-model-probes"))
parser.add_argument("--separate-price-tag", action=argparse.BooleanOptionalAction, default=True,
                    help="Read the known synthetic price-tag region separately, as local capture does; disable to compare the combined reader")
parser.add_argument("--cache-from", type=Path, help="Copy a saved response cache for an explicit diagnostic replay")
parser.add_argument("--persona-batch-size", type=int, choices=range(1, 13),
                    help="Customers per model request; override the case's default for a controlled comparison")
args = parser.parse_args()
if args.temperature is not None and not 0 <= args.temperature <= 2:
    parser.error("Temperature must be a finite number between 0 and 2.")
endpoint = urlsplit(args.endpoint)
if endpoint.hostname not in {"localhost", "127.0.0.1", "::1"} or endpoint.scheme != "http":
    parser.error("Use an HTTP loopback endpoint for the local model.")
output = args.output / f"{args.case}-{args.structured_output}-{time.time_ns()}"
output.mkdir(parents=True)
if args.cache_from:
    shutil.copytree(args.cache_from.resolve(), output / "cache")
starter_book_price_bounds = {
    "book-price-unavailable": ("USD", "100.00", "200.00", 10000, 20000),
    "book-price-range": ("USD", "15.00", "20.00", 1500, 2000),
    "book-price-range-krw": ("KRW", "25000", "28000", 25000, 28000),
    "book-price-range-jpy": ("JPY", "2800", "3100", 2800, 3100),
}
options = TemplateLayoutRequest(template_id="compact_cvs", width=8, height=6, currency="KRW")
description = "동네 주민이 자주 방문하는 동네 편의점"
if args.case == "cafe":
    options = TemplateLayoutRequest(template_id="cafe_bakery", width=10, height=8, currency="JPY",
        products_per_category=1, excluded_categories=["beer_alcohol"],
        requirements="No alcoholic products. One product per category. Preserve the cafe and bakery shelf purposes.")
    description = "近所の住民が訪れる小さなカフェ。パンとコーヒー。"
elif args.case.startswith("book"):
    options = TemplateLayoutRequest(template_id="bookstore", width=8, height=6, currency="USD",
        products_per_category=2, requirements="Books and stationery for local residents; no food or drinks.")
    description = "Petite librairie de quartier, livres et papeterie."
    if args.case == "book-repurpose":
        options = options.model_copy(update={"requirements": "Repurpose every shelf for gift wrapping products only. Use gift_wrapping for every section, overriding the books and stationery shelf signs. Select at most two products. No other categories."})
    elif args.case == "book-excluded":
        options = options.model_copy(update={"excluded_categories": ["stationery"], "requirements": "Sell only books. Replace the stationery section with books and keep existing book sections. No food, drinks or other categories."})
    elif args.case in starter_book_price_bounds:
        currency, minimum, maximum, _, _ = starter_book_price_bounds[args.case]
        options = options.model_copy(update={"currency": currency, "products_per_category": 1,
            "requirements": f"Keep the Books and Stationery shelf purposes. Select only books priced from {minimum} to {maximum} {currency} each, inclusive. For stationery choose any catalog product. At most one product per category. No food or drinks."})
elif args.case == "hypermarket":
    options = TemplateLayoutRequest(template_id="hypermarket", width=32, height=26, currency="KRW",
        products_per_category=1, excluded_categories=["beer_alcohol"],
        requirements="Choose a coherent supermarket assortment, with one product per category. No alcoholic products. Keep cold products in fridges and respect department signs.")
    description = "동네 주민과 가족들이 식료품과 생활필수품을 구입하는 대형 슈퍼마켓"
temperature = (args.temperature if args.temperature is not None else
    .5 if args.case.startswith("profile-draft-") else .2 if args.case in design_requests or args.case.startswith("analyst-") else 0)
client = LiteLLMClient(LLMConfig(model=args.model, api_base=args.endpoint, api_key=SecretStr("local-probe"),
    temperature=temperature, seed=0,
    max_tokens=700 if args.case.startswith("profile-draft-") else 900 if args.case in design_requests else 1500 if args.case in layout_requests else 400 if args.case.startswith(("pack-", "capture-")) else 1600 if args.case.startswith("analyst-") else 4096 if args.case.startswith(("persona-", "traffic-")) else 5000,
    timeout_sec=180, max_parallel=1,
    chat_template_thinking=False, structured_output=args.structured_output, structured_sdk_retries=0,
    cache_dir=str(output / "cache")))
send = httpx.AsyncClient.send
calls = 0
attempts = 0
wire_output_modes: set[str] = set()


async def traced_send(self, request, *positional, **keywords):
    global calls, attempts
    started = time.perf_counter()
    local = request.url.host == endpoint.hostname
    if local:
        attempts += 1
        attempt = attempts
        payload = json.loads(request.content)
        response_format = payload.get("response_format", {})
        wire_output_modes.add(str(response_format.get("type", "unspecified")))
        image_index = 0
        for message in payload.get("messages", []):
            if isinstance(message.get("content"), list):
                for part in message["content"]:
                    if part.get("type") == "image_url":
                        image_index += 1
                        url = part["image_url"]["url"]
                        if url.startswith("data:image/") and ";base64," in url:
                            media, encoded = url.split(";base64,", 1)
                            extension = {"data:image/jpeg": "jpg", "data:image/png": "png", "data:image/webp": "webp"}.get(media, "bin")
                            filename = f"request-{attempt}-image-{image_index}.{extension}"
                            (output / filename).write_bytes(base64.b64decode(encoded, validate=True))
                            part["image_url"] = {"url": f"[input saved as {filename}]"}
                        else:
                            part["image_url"] = {"url": "[non-data image input]"}
        # Persist before waiting: timeout/disconnection must not erase the
        # request that caused it. Keep image bytes in the image artifact only.
        with (output / "requests.jsonl").open("a") as trace:
            trace.write(json.dumps({"attempt": attempt, "request": payload}, ensure_ascii=False) + "\n")
    response = await send(self, request, *positional, **keywords)
    if local:
        await response.aread()
        calls += 1
        record = {"call": calls, "attempt": attempt, "status": response.status_code,
            "seconds": round(time.perf_counter() - started, 3), "request": payload, "response": response.json()}
        with (output / "http.jsonl").open("a") as trace:
            trace.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"Call {calls}: HTTP {response.status_code}, {record['seconds']}s", flush=True)
    return response


started = time.perf_counter()
result = {"case": args.case, "model": args.model, "endpoint": args.endpoint, "structured_output": args.structured_output,
          "temperature": temperature, "cache_replay_from": str(args.cache_from) if args.cache_from else None}
try:
    if args.case in design_requests:
        site = build_site("fashion", site_id="cpu-probe", currency="KRW" if args.case in {"design-color-ko", "design-long-history", "design-threshold-krw"} else "USD")
        site.options.welcome_popup = "coupon"
        site.options.coupon_percent = 15
        site.options.shipping_fee = 4990 if args.case == "design-threshold-krw" else 499
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
            "design-free-popup-scan": {"shipping_fee": 0, "welcome_popup": "none"},
            "design-neon": {"page_style": "neon"},
            "design-calm": {"urgency": False, "social_proof": False, "welcome_popup": "none"},
            "design-no-free-shipping": {},
            "design-always-free": {"free_shipping_threshold": 0},
            "design-threshold-usd": {"free_shipping_threshold": 5000},
            "design-threshold-fractional": {"free_shipping_threshold": 725},
            "design-threshold-krw": {"free_shipping_threshold": 30000},
        }[args.case]
        allowed = set(expected) | ({"page_style", "theme_color"} if args.case == "design-calm" else set())
        issues = [f"Expected {key}={value!r}, received {after[key]!r}" for key, value in expected.items() if after[key] != value]
        issues += [f"Unrequested change: {key}" for key in changed if key not in allowed]
        if args.case == "design-no-free-shipping" and (reply.changes.model_dump(exclude_none=True) or not reply.reply.rstrip().endswith("?")):
            issues.append("An unavailable never-free-shipping policy needs clarification without setting contradictory options.")
        if args.case == "design-free-popup-scan":
            captured = []

            def record_panel(*positional, **keywords):
                people = sample_shoppers(*positional, **keywords)
                captured.extend(people)
                return people

            with patch.object(online, "get_site", return_value=site), patch.object(online, "sample_shoppers", record_panel):
                scan = online.scan_site("proj_cpu", site.id, online.ScanRequest(candidates=[
                    online.ScanCandidate(id="same", options=site.options), online.ScanCandidate(id="draft", options=edited)]))
            defaults = OnlineRunRequest(site_ids=[site.id])
            expected_panel = sample_shoppers(site, scan.shoppers, seed=0, missions=defaults.missions,
                mobile_share=defaults.mobile_share, arrivals=defaults.arrivals)
            if captured != expected_panel:
                issues.append("Quick scan did not use the ordinary run's default customer conditions")
            if scan.rows[0].won or scan.rows[0].lost or any(delta.diff != 0 for delta in scan.rows[0].deltas):
                issues.append("Unchanged store did not produce an identical paired result")
            result.update(scan=scan.model_dump(mode="json"), arrivals=dict(Counter(p.arrival for p in captured)),
                expected_arrivals=dict(Counter(p.arrival for p in expected_panel)))
            (output / "scan-shoppers.json").write_text(json.dumps([p.model_dump(mode="json") for p in captured], ensure_ascii=False))
        result.update(success=not issues, request=design_requests[args.case], before=before, after=after,
            reply=reply.model_dump(mode="json"), changed=changed, issues=issues, messages=len(messages),
            characters=sum(len(message.text) for message in messages))
    elif args.case in layout_requests:
        currency = "KRW" if args.case in {"layout-price-krw", "layout-extra-discount-ko"} else "USD"
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

        if args.case == "layout-bulk-bridge":
            items = [SlotItem(sku=f"drink-{i:02}", name=f"Beverage {i:02}", price=500 + i * 10) for i in range(30)]
            store.racks[0].shape = [[1, 1]]
            store.racks[0].slots = [Slot(block=i // 4, face="N", level=i % 4 + 1, items=items[i * 4:(i + 1) * 4]) for i in range(8)]
        if args.case in {"layout-set-discount", "layout-extra-discount", "layout-extra-discount-ko"}:
            tea = store.racks[0].slots[0].items[0]
            tea.price, tea.regular_price = 400 * scale, 500 * scale
        expected = products(store)
        if args.case == "layout-price-krw":
            expected["tea"]["price"] = 3000
        elif args.case == "layout-discount-promo":
            expected["tea"].update(price=450, regular_price=500)
            expected["chips"]["promo"] = "SALE"
        elif args.case in {"layout-category", "layout-bulk-bridge"}:
            for item in expected.values():
                if item["rack"] == "drinks":
                    item["price"] = round(item["price"] * .9)
        elif args.case == "layout-free-item":
            expected["water"]["price"] = 0
        elif args.case == "layout-full-discount":
            expected["tea"].update(price=0, regular_price=500)
        elif args.case == "layout-set-discount":
            expected["tea"].update(price=400, regular_price=500)
        elif args.case in {"layout-extra-discount", "layout-extra-discount-ko"}:
            expected["tea"].update(price=360 * scale, regular_price=500 * scale)
        elif args.case == "layout-sequence":
            expected["tea"].update(price=360, regular_price=400)
            expected["water"]["promo"] = "SALE"
        elif args.case == "layout-move":
            expected["tea"]["level"] = 3
        with patch.object(httpx.AsyncClient, "send", traced_send):
            reply = asyncio.run(draft_layout_edit(client, layout_requests[args.case], store, currency))
        edited, applied, warnings = apply_layout_edit(store, reply.changes, currency)
        if args.case == "layout-bulk-bridge":
            control = site_from_store(store, site_id="control", name="Control", currency=currency)
            web_products, _, skipped = apply_store_changes(control, reply.changes, minor_per_major=100)
            variant = control.model_copy(deep=True, update={"id": "variant", "variant_of": control.id, "products": web_products})
            # Exercise the production snapshot reader without touching any saved user project.
            with patch.object(online, "DATA_DIR", str(output / "data")):
                folder = online._run_dir("proj_cpu", "orun_cpu")
                folder.mkdir(parents=True)
                (folder / "sites.json").write_text(json.dumps([site.model_dump(mode="json") for site in [control, variant]]))
                (folder / "shoppers.json").write_text("[]")
                transfer = online.run_store_changes("proj_cpu", "orun_cpu", 1)
            edited, applied, warnings = apply_layout_edit(store, transfer.changes, currency)
            warnings += skipped + transfer.skipped
            result["transferred_changes"] = len(transfer.changes)
        after = products(edited)
        if args.case == "layout-free-item" and after["water"]["regular_price"] in {0, 100}:
            # A free offer may be an everyday zero price or a 100% discount with a was-price.
            expected["water"]["regular_price"] = after["water"]["regular_price"]
        issues = [f"Unexpected fields or placement for {sku}" for sku in expected if after.get(sku) != expected[sku]]
        if set(after) != set(expected):
            issues.append("Product identities changed")
        if args.case in {"layout-missing-product", "layout-missing-product-ko", "layout-unsupported-edit", "layout-no-changes"}:
            if reply.changes or applied or not reply.summary.strip():
                issues.append("Expected an explicit no-change explanation with no operations.")
        if args.case.startswith("layout-missing-product") and any(phrase in reply.summary.casefold() for phrase in (
            "no edits requested", "not present in the instructions", "no english instruction",
        )):
            issues.append("The explanation mistakes an absent product for an absent or unsupported-language instruction.")
        if args.case == "layout-no-changes" and "product is not listed" in reply.summary.casefold():
            issues.append("A request to leave everything unchanged was incorrectly explained as an absent product.")
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
        history = []
        if args.case == "analyst-history":
            sites = [control, variant, control.model_copy(deep=True), control.model_copy(deep=True)]
            labels = ["기본 배송비와 팝업을 유지한 우리 동네 신선식품 온라인 매장",
                "빠른 담기와 팝업 제거를 적용한 우리 동네 신선식품 온라인 매장",
                "배송비를 없애고 비교하는 우리 동네 신선식품 온라인 매장",
                "회원 가입 없이 구매하는 우리 동네 신선식품 온라인 매장"]
            sites[2].options.shipping_fee, sites[3].options.guest_checkout = 0, True
            for i, site in enumerate(sites):
                site.id, site.name = f"site-{i}", labels[i]
            sessions = [asyncio.run(visits(site)) for site in sites]
            report.name = "Quick add study"
            report.variants = [summarize(site, by_id, session) for site, session in zip(sites, sessions)]
            report.comparisons = []
            for site, session in zip(sites[1:], sessions[1:]):
                won, lost, changed, rows = switches(sessions[0], session)
                report.comparisons.append(VariantComparison(site_id=site.id, site_name=site.name,
                    deltas=paired_deltas(sessions[0], session, seed=4), segments=segment_deltas(sessions[0], session, by_id, seed=4),
                    won=won, lost=lost, changed=changed, switches=rows))
            owner = ("모바일 고객이 장바구니와 결제 화면에서 이탈하는 이유를 알고 싶습니다. 할인 팝업과 배송비를 바꾼 매장을 비교해주세요. " * 20)[:600]
            old_answer = ("이 실험은 가상 고객의 방문을 비교한 결과입니다. 고객군별 전환율과 매출은 서로 다르므로 전체 수치와 함께 살펴보아야 합니다. 실제 매출을 예측하려면 실제 방문과 주문 자료가 필요합니다. " * 20)[:1500]
            history = [AnalystMessage(role="user" if i % 2 == 0 else "analyst", text=owner if i % 2 == 0 else old_answer) for i in range(8)]
        question = ("What exact real-world sales uplift will this store achieve next year?" if args.case in {"analyst-forecast", "analyst-history"}
                    else "Did the variant improve conversion? Quote both overall conversion rates and say whether the difference is clear.")
        (output / "run.json").write_text(report.model_dump_json(indent=2))
        (output / "facts.txt").write_text(online_facts(report))
        with patch.object(httpx.AsyncClient, "send", traced_send):
            reply = asyncio.run(answer_online_question(client, report, question, history, seed=0))
        issues = []
        if args.case == "analyst-forecast":
            if "does not show" not in reply.answer.casefold() or any(c.isdigit() for c in reply.answer):
                issues.append("Expected an explicit refusal to invent a future real-world forecast")
        elif args.case == "analyst-history":
            if "does not show" not in reply.answer.casefold():
                issues.append("Expected an explicit refusal to invent a future forecast")
            if any(word in reply.answer.casefold() for word in ["major driver", "differs significantly", "significant improvement"]):
                issues.append("Unsupported causal or significance claim in this inconclusive fixture")
        else:
            expected_rates = {round(summary.conversion * 100, 1) for summary in report.variants}
            quoted_rates = {float(value) for value in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:%|percent\b)", reply.answer, re.I)}
            if not reply.figures or not expected_rates <= quoted_rates:
                issues.append(f"Expected cited overall conversion rates of {sorted(expected_rates)} percent")
            if not any(word in reply.answer.casefold() for word in ["not clear", "includes zero", "includes 0", "not statistically significant"]):
                issues.append("Expected the interval including zero to be recognized as inconclusive")
            if any(word in reply.answer.casefold() for word in ["is statistically significant", "is significant", "significant increase", "significant improvement"]):
                issues.append("Contradicts this fixture's interval including zero")
        result.update(success=not issues, completed=True, question=question, reply=reply.model_dump(mode="json"), issues=issues,
            expected_conversion=[summary.conversion for summary in report.variants], history_characters=sum(len(message.text) for message in history))
    elif args.case.startswith("setup-"):
        descriptions = {
            "setup-unspecified": "A small neighborhood bookshop.",
            "setup-night": "서울 마포구의 '밤샘 편의점'입니다. 매일 오후 8시부터 다음 날 오전 2시까지만 영업합니다. 24시간 영업은 아닙니다.",
            "setup-24h": "서울 마포구의 '우리 편의점'입니다. 매일 24시간 영업하고 동네 주민이 방문합니다.",
            "setup-pharmacy": "서울 마포구의 '동네 약국'입니다. 토요일과 일요일만 오전 10시부터 오후 6시까지 영업하고 의약품과 생활용품을 판매합니다.",
            "setup-unspecified-ko": "동네 주민을 위한 작은 빵집입니다.",
            "setup-hours-only": "A pet shop open from 9 to 17.",
            "setup-days-only": "A bakery open on Saturdays and Sundays.",
            "setup-location-only": "A cafe in Kyoto, Japan.",
        }
        # Separate omitted facts from stated facts: a partly specified description
        # must neither lose its supplied values nor acquire plausible defaults.
        expectations = {
            "setup-unspecified": ("books", (None, None), None, None, []),
            "setup-night": ("convenience", (None, None), "7", "KRW", ["서울", "마포"]),
            "setup-24h": ("convenience", (0, 24), "7", "KRW", ["서울", "마포"]),
            "setup-pharmacy": ("pharmacy", (10, 18), "weekend", "KRW", ["서울", "마포"]),
            "setup-unspecified-ko": ("bakery", (None, None), None, None, []),
            "setup-hours-only": ("pets", (9, 17), None, None, []),
            "setup-days-only": ("bakery", (None, None), "weekend", None, []),
            "setup-location-only": ("cafe", (None, None), None, "JPY", ["Kyoto", "Japan"]),
        }
        expected_type, expected_hours, expected_days, expected_currency, place_parts = expectations[args.case]
        locale = "ko" if args.case in {"setup-night", "setup-24h", "setup-pharmacy", "setup-unspecified-ko"} else "en"
        with patch.object(httpx.AsyncClient, "send", traced_send):
            draft = asyncio.run(draft_store_setup(client, descriptions[args.case],
                [(t.id, t.name, t.store_type, t.description) for t in TEMPLATES], locale))
        format_issues = []
        if draft.store_type != expected_type:
            format_issues.append(f"Expected store type {expected_type}, received {draft.store_type}")
        if draft.template_id not in {template.id for template in TEMPLATES}:
            format_issues.append("No known starting format selected")
        if args.case == "setup-night" and draft.template_id not in {"compact_cvs", "urban_cvs"}:
            format_issues.append("A plain night convenience store acquired an unrelated specialized setting")
        issues = list(format_issues)
        if not draft.name.strip():
            issues.append("The draft lost the supplied store identity instead of proposing a name")
        if not draft.description.strip():
            issues.append("The draft lost the supplied store description")
        if (draft.open_hour, draft.close_hour) != expected_hours:
            issues.append(f"Expected hours {expected_hours}, received {(draft.open_hour, draft.close_hour)}")
        if args.case == "setup-night" and not draft.warnings:
            issues.append("Unsupported overnight hours must be shown for user correction")
        if args.case != "setup-night" and draft.warnings:
            issues.append("The supported or unspecified schedule acquired an unexpected warning")
        if draft.open_days != expected_days:
            issues.append("Opening days differ from the owner's description")
        if draft.currency != expected_currency:
            issues.append("Currency differs from the supplied location or invents an unspecified one")
        if not place_parts and draft.address:
            issues.append("Invented an unspecified location")
        if place_parts and not all(part.casefold() in draft.address.casefold() for part in place_parts):
            issues.append("Supplied location was not retained")
        if not place_parts and any(word in (draft.name + draft.description).casefold() for word in ["campus", "캠퍼스"]):
            issues.append("Invented a campus location in the name or description")
        if locale == "ko" and draft.description and not re.search(r"[가-힣]", draft.description):
            issues.append("The requested Korean store description was written in another language")
        result.update(success=not issues, format_ok=not format_issues, facts_ok=len(issues) == len(format_issues), description=descriptions[args.case], draft=draft.model_dump(mode="json"), issues=issues)
    elif args.case.startswith("profile-draft-"):
        inputs = {
            "profile-draft-night": dict(name="밤약국", description="야간 근무를 마친 동네 주민이 일반의약품을 사러 옵니다. 음식과 음료는 판매하지 않습니다.",
                address="Seoul, South Korea", store_type="pharmacy", hours="Monday-Friday 22:00-24:00. Closed Saturday and Sunday.", locale="ko"),
            "profile-draft-bookstore": dict(name="Evening Books", description="Used books and stationery only, for nearby residents. Typical purchase: $5 to $20.",
                address="Austin, Texas, USA", store_type="bookstore", hours="Tuesday and Thursday 18:00-21:00. Closed on all other days.", locale="en"),
            "profile-draft-sparse": dict(name="Corner Shop", description="", address="", store_type="", hours="", locale="en"),
        }[args.case]
        with patch.object(httpx.AsyncClient, "send", traced_send):
            profile = asyncio.run(draft_profile(client, **inputs))
        issues = []
        if inputs["locale"] == "ko" and not re.search(r"[가-힣]", profile):
            issues.append("Korean draft contains no Korean text")
        if inputs["locale"] == "en" and not re.search(r"[A-Za-z]{3}", profile):
            issues.append("English draft contains no English words")
        sentences = Counter(part.strip() for part in re.split(r"[.!?。！？]+", profile) if len(part.strip()) >= 10)
        if any(count > 1 for count in sentences.values()):
            issues.append("The profile repeats an entire sentence")
        result.update(success=False if issues else None, structure_ok=True, automated_checks_ok=not issues,
            inputs=inputs, profile=profile, issues=issues,
            semantic_review="Inspect hours, products and unsupported claims manually; language-presence checks are not semantic validation.")
    elif args.case.startswith("traffic-"):
        # A supplied profile is the input to this stage; this is a real traffic
        # request, not a claim to have run the upstream area or persona writers.
        opening, closing = (0, 24) if args.case.startswith("traffic-24h") else (23, 24)
        identities = ["local resident", "night shift worker", "commuter", "student"]
        area = TradeAreaProfile(keywords=["neighborhood"], identities=identities, purposes=["buy snacks"])
        source = "Neighborhood residents buy snacks and drinks at this small convenience store."
        evidence = "Observed visitors: exactly one visitor in each open hour. Preserve these supplied hourly counts."
        observed = {hour: 1 for hour in range(opening, closing)}
        if args.case == "traffic-24h-varied":
            observed = {hour: [0, 2, 5, 1][hour // 6] for hour in range(24)}
        elif args.case == "traffic-last-hour-zero":
            observed = {23: 0}
        if args.case in {"traffic-24h-varied", "traffic-last-hour-zero"}:
            evidence = "Observed visitors by opening-hour slot; preserve these supplied counts:\n" + "\n".join(
                f"{hour:02d}:00–{hour + 1:02d}:00: {count} visitors" for hour, count in observed.items())
        with patch.object(httpx.AsyncClient, "send", traced_send):
            traffic = asyncio.run(analyze_daily_traffic(client, "Mapo-gu, Seoul, South Korea", source, area,
                Weekday.MON, opening, closing, supplemental_summary=evidence))
        issues = []
        if [row.hour for row in traffic] != list(range(opening, closing)):
            issues.append("Opening-hour slots are missing, duplicated, outside hours or reordered")
        if any(row.visitor_count != observed.get(row.hour) for row in traffic):
            issues.append("Observed hourly visitor counts were changed")
        if any(row.visitor_count > 0 and (not row.person_types or any(label not in identities for label in row.person_types)) for row in traffic):
            issues.append("Positive traffic lost its supplied customer types")
        result.update(success=not issues, opening=opening, closing=closing, evidence=evidence, observed_counts=observed,
            traffic=[row.model_dump(mode="json") for row in traffic], issues=issues)
    elif args.case.startswith("persona-"):
        address, currency, categories, budget = "Mapo-gu, Seoul, South Korea", "KRW", None, (3000, 10000)
        profile = "동네 주민. 편의점에서 간단한 간식과 음료를 사러 옵니다. 1회 예산은 3,000~10,000원입니다."
        if args.case == "persona-unspecified":
            profile, budget = "동네 주민", (0, 0)
        if args.case in {"persona-cafe", "persona-local-categories"}:
            address, currency, categories, budget = "Tokyo, Japan", "JPY", ["coffee", "bakery"], (500, 1500)
            profile = "近所の住民がパンとコーヒーを買いに訪れる小さなカフェです。一人の予算は500〜1500円です。"
            if args.case == "persona-local-categories":
                categories = ["コーヒー", "パン"]
        elif args.case == "persona-bookstore":
            address, currency, categories, budget = "Lyon, France", "EUR", ["books", "stationery"], (500, 2000)
            profile = "Une librairie de quartier pour les habitants qui achètent des livres et de la papeterie. Le budget par visite est de 5 à 20 euros."
        elif args.case == "persona-us":
            address, currency, categories, budget = "Austin, Texas, USA", "USD", ["snacks", "drinks"], (300, 1000)
            profile = "Una tienda de barrio para vecinos que compran aperitivos y bebidas. El presupuesto por visita es de 3 a 10 dólares estadounidenses."
        elif args.case == "persona-fractional":
            address, currency, categories, budget = "Lyon, France", "EUR", ["coffee", "bakery"], (250, 775)
            profile = "Un petit café de quartier pour les habitants qui achètent du café et des pâtisseries. Le budget par visite est de 2,50 à 7,75 euros."
        expected_hour, customer_count = 9, 2
        if args.case.startswith("persona-nightmarket"):
            expected_hour, customer_count = 23, 12
            categories = ["drinks", "snacks"]
            profile = "동네 주민과 야간 근무자가 심야에 간단한 간식과 음료를 삽니다. 1회 예산은 3,000~10,000원입니다."
        opening, closing, evidence = expected_hour, expected_hour + 1, ""
        if args.case == "persona-24h":
            opening, closing, budget = 0, 24, (0, 0)
            profile = "동네 주민이 간식과 음료를 사는 24시간 편의점입니다."
            evidence = "Observed visitors: exactly one visitor in each open hour. Preserve these supplied hourly counts."
        schedules = [DaySchedule(day=day, is_open=day == Weekday.MON, open_hour=opening, close_hour=closing) for day in Weekday]
        estimates = {}
        persona_batch_size = args.persona_batch_size or (5 if args.case == "persona-nightmarket-local-batches" else customer_count)
        with patch.object(httpx.AsyncClient, "send", traced_send):
            if args.case in {"persona-nightmarket-batch", "persona-nightmarket-local-batches"}:
                # A fixed observed cohort exercises the writer's batch boundary;
                # an upstream traffic estimate may otherwise request just one.
                area = TradeAreaProfile(keywords=["neighborhood", "night"],
                    identities=["local resident", "night shift worker"], purposes=["buy snacks", "buy drinks"])
                hourly = [HourlyProfile(hour=expected_hour, visitor_count=customer_count, person_types=area.identities)]
                people = asyncio.run(generate_personas_for_day(client, address, area, Weekday.MON, hourly,
                    seed=4, batch_size=persona_batch_size, max_concurrent=1, categories=categories,
                    currency=currency, customer_profile=profile))
                result["source_stage"] = "customer_writer_only_with_fixed_cohort"
            else:
                people = asyncio.run(generate_batched(client, address, profile, schedules, seed=4,
                    batch_size=persona_batch_size, max_concurrent=1, categories=categories, currency=currency, supplemental_summary=evidence,
                    pace=lambda usual: Pace(daily_cap=customer_count, batch_size=persona_batch_size, sample_cap=customer_count), estimates=estimates))
        written = [person for person in people if not person.twin_of]
        issues = []
        if not written or len({person.id for person in people}) != len(people):
            issues.append("No written customers or duplicate customer IDs")
        if args.case in {"persona-nightmarket-batch", "persona-nightmarket-local-batches"} and len(written) != customer_count:
            issues.append(f"Expected {customer_count} independently written customers, received {len(written)}")
        if any(person.day != Weekday.MON or not opening <= person.arrival_hour < closing for person in people):
            issues.append("Arrival outside the open hours")
        if args.case == "persona-24h" and Counter(person.arrival_hour for person in people) != {hour: 1 for hour in range(24)}:
            issues.append("The full population did not preserve one observed visitor in each of the 24 hours")
        if categories and any(category not in categories for person in people for category in person.preferred_categories):
            issues.append("Preference outside the supplied category list")
        if categories and any(not person.preferred_categories for person in people):
            issues.append("Missing preferences despite the fixture's explicit buying intent and listed categories")
        if budget == (0, 0) and any(person.budget_min or person.budget_max for person in people):
            issues.append("Invented a budget absent from the supplied profile")
        elif budget != (0, 0) and any(person.budget_min < budget[0] or person.budget_max == 0 or person.budget_max > budget[1] for person in people):
            issues.append("Budget outside the supplied range")
        population_ok = not issues
        text_issues = customer_text_issues(written)
        issues.extend(text_issues)
        result.update(success=not issues, population_ok=population_ok, text_ok=not text_issues,
            address=address, currency=currency, profile=profile, categories=categories, persona_batch_size=persona_batch_size,
            estimates=estimates, count=len(people), written=[person.model_dump(mode="json") for person in written], issues=issues)
        (output / "personas.json").write_text(json.dumps([person.model_dump(mode="json") for person in people], ensure_ascii=False, indent=2))
    elif args.case.startswith("capture-"):
        tags = {"capture-price": "$1.00", "capture-price-krw": "1,000원", "capture-coupon-price": "$1.00 WITH COUPON", "capture-blank-price": "", "capture-saving": "SAVE $1.00", "capture-saving-up-to": "SAVE UP TO $1.00",
                "capture-cash-back": "$1.00 CASH BACK", "capture-off": "$1.00 OFF",
                "capture-saving-krw": "1,000원 할인", "capture-was-price": "WAS $1.00", "capture-free-price": "FREE $0.00", "capture-coupon-value": "$1.00 COUPON",
                "capture-earn-reward": "EARN $1.00", "capture-reward-value": "$1.00 REWARD", "capture-rewards-price": "REWARDS PRICE $1.00", "capture-reward-krw": "1,000원 적립",
                "capture-points": "100 POINTS", "capture-points-krw": "100포인트", "capture-points-price": "$1.00 WITH POINTS",
                "capture-volume-only": "500 ml", "capture-count-only": "6 PACK", "capture-count-cash-price": "$6 PACK",
                "capture-starting-price": "FROM $1.00", "capture-upper-price": "UNDER $1.00", "capture-starting-price-krw": "1,000원부터",
                "capture-unit-price": "$1.00 / L", "capture-unit-price-krw": "리터당 1,000원",
                "capture-pack-unit-price": "$1.00 / BOTTLE", "capture-pack-price": "$6.00 / PACK", "capture-bottle-price": "$1.00 / BOTTLE",
                "capture-container-count-price": "$1.00 / BOTTLE", "capture-deposit-price": "DEPOSIT $0.10",
                "capture-deposit-suffix": "$0.10 DEPOSIT", "capture-deposit-included-price": "DEPOSIT INCLUDED $1.00"}
        currency = "KRW" if args.case.endswith("-krw") else "USD"
        fixture = Image.new("RGB", (448, 512), "#f5f1e9")
        drawing = ImageDraw.Draw(fixture)
        drawing.rounded_rectangle((138, 24, 310, 376), radius=28, fill="#553023", outline="black", width=3)
        drawing.rectangle((174, 12, 274, 44), fill="#ca3333")
        drawing.rectangle((140, 140, 308, 292), fill="#ca3333")
        package_size = "6 PACK" if args.case.startswith("capture-pack-") else "500 ml"
        if args.case == "capture-container-count-price":
            package_size = "6 BOTTLES"
        for text, y, size in [("ACME", 150, 26), ("COLA", 188, 42), (package_size, 246, 24)]:
            drawing.text((224, y), text, fill="white", font=load_font(size, bold=True), anchor="mt")
        drawing.rectangle((0, 400, 448, 512), fill="#fff4a5", outline="black", width=3)
        tag_font = 28 if args.case in {"capture-deposit-included-price", "capture-rewards-price", "capture-points-price", "capture-count-cash-price"} else 36
        drawing.text((224, 439), tags[args.case], fill="black", font=load_font(tag_font, bold=True), anchor="mt")
        fixture.save(output / "image.png")
        with patch.object(httpx.AsyncClient, "send", traced_send):
            label = asyncio.run(VLMLabeler(client, currency=currency, separate_price_tag=args.separate_price_tag).label(
                fixture, price_tag=fixture.crop((0, 400, fixture.width, fixture.height)) if args.separate_price_tag else None))
        # Known fixture geometry isolates real label recognition and conversion;
        # this is not a detector benchmark or a photograph of a real shelf.
        frame = make_frame(fixture)
        detection = Detection(x1=138, y1=24, x2=310, y2=376, band=0)
        group = FacingGroup(band=0, facings=[detection], descriptor=describe(fixture, detection), label=label)
        items, _ = build_items(frame, [group], [3], currency=currency, rack_type="shelf")
        item = items[0]
        issues = []
        if not item.labeled or "cola" not in item.name.casefold():
            issues.append("The printed product identity was not retained.")
        if args.case in {"capture-price", "capture-price-krw", "capture-coupon-price", "capture-free-price", "capture-pack-price", "capture-bottle-price", "capture-deposit-included-price", "capture-rewards-price", "capture-points-price", "capture-count-cash-price"}:
            expected_price = {"capture-price": 100, "capture-price-krw": 1000, "capture-coupon-price": 100, "capture-free-price": 0, "capture-pack-price": 600, "capture-bottle-price": 100, "capture-deposit-included-price": 100, "capture-rewards-price": 100, "capture-points-price": 100, "capture-count-cash-price": 600}[args.case]
            if item.price != expected_price or item.price_estimated:
                issues.append(f"The printed selling price was not retained as {expected_price} cents.")
        elif not item.price_estimated:
            issues.append("A non-selling or unreadable tag became an exact package selling price.")
        result.update(success=not issues, issues=issues, fixture_tag=tags[args.case], currency=currency,
                      separate_price_tag=args.separate_price_tag,
                      label=label.model_dump(mode="json"), item=item.model_dump(mode="json"))
    elif args.case.startswith("pack-"):
        products = ["Strawberry Jam 340g", "Apricot Jam 340g", "Marmalade 340g"]
        picture = Image.new("RGB", (600, 800), "white")
        if args.case == "pack-jam":
            picture = bundled_product_image("/api/catalog-images/starter-01/15.webp")
            assert picture is not None
        elif args.case in {"pack-label", "pack-brand-suffix", "pack-mixed-quantities", "pack-large-catalog", "pack-wrong-variant", "pack-multipack", "pack-multipack-unlisted", "pack-multipack-count", "pack-multipack-count-unlisted", "pack-multipack-container-count", "pack-multipack-container-count-unlisted"}:
            # A deterministic positive-control label, not a photograph or model-generated picture.
            drawing = ImageDraw.Draw(picture)
            drawing.rounded_rectangle((100, 110, 500, 740), radius=70, fill="#dbeed0", outline="#245737", width=6)
            drawing.rounded_rectangle((220, 30, 380, 140), radius=15, fill="#245737")
            drawing.rectangle((110, 280, 490, 630), fill="white")
            labels = [(320, "LEAFY", 55), (420, "GREEN TEA", 44), (520, "500 ml", 48)]
            if args.case == "pack-mixed-quantities":
                labels = [(320, "LEAFY", 55), (420, "GREEN TEA", 44), (500, "NET 500 g", 38), (560, "SERVING 100 ml", 30)]
            if args.case.startswith("pack-multipack"):
                labels = [(320, "LEAFY", 55), (420, "GREEN TEA", 44), (520, "6 x 500 ml", 42)]
            if args.case.startswith(("pack-multipack-count", "pack-multipack-container-count")):
                count_text = "6 BOTTLES" if "container-count" in args.case else "6 PACK"
                labels = [(320, "LEAFY", 55), (420, "GREEN TEA", 44), (500, "500 ml", 42), (560, count_text, 38)]
            for y, label, size in labels:
                drawing.text((300, y), label, font=load_font(size, True), fill="#153d24", anchor="mt")
            products = ["Leafy Green Tea 1 L", "Leafy Black Tea 500 ml"]
            if args.case in {"pack-label", "pack-large-catalog"}:
                products.insert(0, "Leafy Green Tea 500 ml")
            if args.case == "pack-brand-suffix":
                products.insert(0, "Green Tea 500 ml — Leafy")
            if args.case == "pack-mixed-quantities":
                products = ["Green Tea 500 ml — Leafy", "Leafy Green Tea 100 g"]
            if args.case == "pack-large-catalog":
                products = [f"Unrelated product {i:03d}" for i in range(180)] + products
            if args.case.startswith("pack-multipack"):
                products = ["Leafy Green Tea 500 ml"]
                if args.case == "pack-multipack":
                    products.append("Leafy Green Tea 6 x 500 ml")
                if args.case == "pack-multipack-count":
                    products.append("Leafy Green Tea 500 ml 6 pack")
                if args.case == "pack-multipack-container-count":
                    products.append("Leafy Green Tea 500 ml 6 bottles")
        picture.save(output / "image.png")
        with patch.object(httpx.AsyncClient, "send", traced_send):
            reading = asyncio.run(read_pack(client, picture, products))
        issues = []
        expected_match = ("Leafy Green Tea 6 x 500 ml" if args.case == "pack-multipack" else
            "Leafy Green Tea 500 ml 6 pack" if args.case == "pack-multipack-count" else
            "Leafy Green Tea 500 ml 6 bottles" if args.case == "pack-multipack-container-count" else
            "Green Tea 500 ml — Leafy" if args.case == "pack-brand-suffix" else
            "Leafy Green Tea 500 ml" if args.case in {"pack-label", "pack-large-catalog"} else "")
        if reading.shelf_product != expected_match:
            issues.append(f"Expected product match {expected_match!r}, received {reading.shelf_product!r}")
        if args.case in {"pack-jam", "pack-blank"} and (reading.brand or reading.size):
            issues.append("Unlabelled image acquired a brand or printed size")
        result.update(success=not issues, products=products, reading=reading.model_dump(mode="json"), issues=issues)
    else:
        result.update(layout=options.model_dump(mode="json"), description=description)
        store = generate_store(options.template_id, currency=options.currency, options=options)
        original = store.model_dump(mode="json")
        (output / "source-store.json").write_text(store.model_dump_json(indent=2))
        if args.case == "book-price-unavailable":
            _, _, _, minimum, maximum = starter_book_price_bounds[args.case]
            available_prices = [catalog_slot_item(entry, options.currency).price for entry in CATALOG["books"]]
            result["available_book_prices"] = available_prices
            if any(minimum <= price <= maximum for price in available_prices):
                raise AssertionError("The unavailable-price fixture now has an eligible catalog book; update its bounds.")
        # Inject the real loopback client at the provider-selection seam, without editing saved settings.
        with patch.object(template_assortment, "assistive_client", return_value=client), \
                patch.object(httpx.AsyncClient, "send", traced_send):
            stocked, choices = template_assortment.select_initial_assortment(SimulationConfig(), store, options, description)
        issues = [issue.model_dump(mode="json") for issue in validate(stocked)]
        if store.model_dump(mode="json") != original:
            issues.append({"error": "Automatic stocking mutated its source layout."})
        choices_by_rack = {row.rack_id: row for row in choices}
        if len(choices_by_rack) != len(choices):
            issues.append({"error": "A rack was assigned more than once."})
        placed = set()
        selected = {sku for row in choices for sku in row.skus or []}
        for rack in stocked.racks:
            row = choices_by_rack.get(rack.id)
            if row is None:
                continue
            limit = options.category_product_limits.get(row.category, options.products_per_category or 16)
            if row.category in options.excluded_categories or not row.skus or len(row.skus) > limit:
                issues.append({"error": f"{rack.id}: category exclusion or product limit violated."})
            catalog = {p.sku: p for entry in CATALOG[row.category]
                       for p in [catalog_slot_item(entry, options.currency)]}
            for slot in rack.slots:
                for item in slot.items:
                    placed.add(item.sku)
                    if item.sku not in (row.skus or []) or item != catalog.get(item.sku):
                        issues.append({"error": f"{rack.id}: placed product differs from its selected catalog identity or price."})
        if selected != placed:
            issues.append({"error": "Selected and actually placed product identities differ."})
        result.update(selected_skus=len(selected), placed_skus=len(placed),
            placements=sum(len(slot.items) for rack in stocked.racks if rack.id in choices_by_rack for slot in rack.slots))
        if args.case == "hypermarket":
            original_categories = {rack.id: rack.rack_desc for rack in store.racks}
            categories = {row.category for row in choices}
            result.update(category_count=len(categories),
                          suggested_category_count=len({original_categories[row.rack_id] for row in choices}),
                          reassigned_racks=sum(row.category != original_categories[row.rack_id] for row in choices))
            if len(categories) <= 16:
                issues.append({"error": "The large template collapsed to at most 16 departments."})
            if categories & set(options.excluded_categories) or any(len(row.skus) != 1 for row in choices):
                issues.append({"error": "The assortment violated category exclusions or the one-product limit."})
        if args.case.startswith("book") or args.case == "cafe":
            replacement = {"book-repurpose": "gift_wrapping", "book-excluded": "books"}.get(args.case)
            expected = {rack.id: replacement or rack.rack_desc for rack in store.racks}
            mismatches = [{"rack": row.rack_id, "expected": expected[row.rack_id], "actual": row.category}
                          for row in choices if row.category != expected[row.rack_id]]
            result["category_mismatches"] = mismatches
            if mismatches:
                issues.append({"error": "The category choices ignored this fixture's explicit requirements or shelf purposes."})
        if args.case in starter_book_price_bounds:
            _, _, _, minimum, maximum = starter_book_price_bounds[args.case]
            books = {item.sku: item.price for rack in stocked.racks if rack.rack_desc == "books"
                     for slot in rack.slots for item in slot.items}
            result["book_prices"] = books
            if not books or any(not minimum <= price <= maximum for price in books.values()):
                issues.append({"error": "Selected books outside the explicitly requested per-product price range."})
        result.update(success=not issues, choices=[choice.model_dump(mode="json") for choice in choices], issues=issues)
        (output / "store.json").write_text(stocked.model_dump_json(indent=2))
except Exception as error:
    result.update(success=False, error=repr(error))
result.update(seconds=round(time.perf_counter() - started, 2), calls=calls, attempted_calls=attempts,
              wire_output_modes=sorted(wire_output_modes), usage=client.get_usage().model_dump(mode="json"))
(output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({"output": str(output), **{key: result[key] for key in ("success", "seconds", "calls", "attempted_calls", "usage")}}, indent=2))
raise SystemExit(0 if result["success"] else 1)
