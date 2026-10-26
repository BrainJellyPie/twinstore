"""Draft real local-model A/B operations and apply them to an isolated layout.

Run from the repository root with PYTHONPATH=backend/src and the backend Python.
This checks draft semantics and the production edit application, not shopper
outcomes. The package case uses an identifier fixture; it performs no vision read.
"""
import argparse
import asyncio
import copy
import ipaddress
import json
import shutil
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.experiment_design import design_experiment
from store_emulator.engine.marketing.variants import apply_changes

QUESTIONS = {
    "discount-promo": "Compare exactly two Tea variants against the unchanged control: a 20% discount and a 1+1 sign. Keep the regular price and all other products unchanged.",
    "fixed-price-krw": "Tea만 비교하는 두 가지 안을 만들어 주세요: 판매가 1,500원으로 변경하는 안과 20% 할인하는 안. 기존 정가 1,990원과 다른 상품은 그대로 두세요.",
    "free-discount": "Compare exactly two Tea variants: a 100% discount making it free, and a 20% discount. Show the original $1.99 price in both. Change no other products or signs.",
    "extra-discount": "Tea is currently $4.00, with an original regular price of $5.00. Compare exactly two Tea variants: an EXTRA 10% reduction of the CURRENT $4.00 selling price, and setting a 10% discount against the REGULAR $5.00 price. Keep the original $5.00 reference price and all other products unchanged.",
    "rounding-discount": "Tea is currently $0.81, with an original regular price of $1.01. Compare exactly two Tea variants: a 50% discount against the REGULAR $1.01 price, and an EXTRA 50% reduction of the CURRENT $0.81 selling price. Keep the original $1.01 reference price and all other products unchanged.",
    "move": "Create exactly one variant moving only Tea to level 3 on Endcap. Keep all prices, signs, packages and other products unchanged.",
    "package": "Create exactly one variant changing only Tea's package to the listed Tea package B. Keep all prices, signs, placements and other products unchanged.",
    "category": "Create exactly one variant reducing all prices on the Drinks shelf by 10 percent. Keep other shelves, signs, packages and placements unchanged.",
}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--case", choices=list(QUESTIONS), default="discount-promo")
parser.add_argument("--structured-output", "--mode", dest="mode", choices=["json", "json_schema"], default="json_schema")
parser.add_argument("--endpoint", default="http://127.0.0.1:8082/v1")
parser.add_argument("--model", default="openai/local-model")
parser.add_argument("--output", type=Path, default=Path(".data/local-model-probes"))
parser.add_argument("--cache-from", type=Path, help="Copy a saved response cache; report cache hits separately from inference")
args = parser.parse_args()
host = urlsplit(args.endpoint).hostname
try:
    local = host in {"localhost", "localhost."} or bool(host and ipaddress.ip_address(host).is_loopback)
except ValueError:
    local = False
if not local:
    parser.error("Use a loopback model endpoint for this local probe.")
output = args.output.resolve() / f"ab-{args.case}-{args.mode}-{time.time_ns()}"
output.mkdir(parents=True)
if args.cache_from:
    shutil.copytree(args.cache_from.resolve(), output / "cache")
krw = args.case == "fixed-price-krw"
currency, price = ("KRW", 1990) if krw else ("USD", 199)
store = Store(id="probe", name="Corner store", type="convenience", currency=currency, grid_size=(8, 8), racks=[
    Rack(id="drinks", rack_name="Drinks", type="shelf", shape=[[1]], position=(3, 3), slots=[
        Slot(block=0, face="N", level=1, items=[SlotItem(sku="tea", name="Tea", price=price)]),
        Slot(block=0, face="N", level=2, items=[SlotItem(sku="water", name="Water", price=990 if krw else 99)])])])
if args.case in {"extra-discount", "rounding-discount"}:
    current, regular = (400, 500) if args.case == "extra-discount" else (81, 101)
    store.racks[0].slots[0].items[0].price = current
    store.racks[0].slots[0].items[0].regular_price = regular
if args.case in {"move", "package", "category"}:
    store.racks.append(Rack(id="endcap", rack_name="Endcap", type="shelf", shape=[[1]], position=(5, 3), slots=[
        Slot(block=0, face="N", level=1, items=[SlotItem(sku="chips", name="Chips", price=299)])]))
packages = [("Tea package B", "probe-pack")] if args.case == "package" else []
package_uris = {"probe-pack": "probe://package-b"}


def products(layout):
    return {item.sku: {**item.model_dump(mode="json"), "rack": rack.id, "block": slot.block,
            "face": str(slot.face), "level": slot.level}
            for rack in layout.racks for slot in rack.slots for item in slot.items}


before = store.model_dump_json()
base_products = products(store)
expected = []
updates = {
    "discount-promo": [{"price": 159, "regular_price": 199}, {"promo": "1+1"}],
    "fixed-price-krw": [{"price": 1500, "regular_price": 1990}, {"price": 1592, "regular_price": 1990}],
    "free-discount": [{"price": 0, "regular_price": 199}, {"price": 159, "regular_price": 199}],
    "extra-discount": [{"price": 360, "regular_price": 500}, {"price": 450, "regular_price": 500}],
    "rounding-discount": [{"price": 50, "regular_price": 101}, {"price": 40, "regular_price": 101}],
    "move": [{"rack": "endcap", "level": 3}],
    "package": [{"image_url": "probe://package-b"}],
    "category": [{"price": 179, "regular_price": 199}],
}[args.case]
for update in updates:
    row = copy.deepcopy(base_products)
    row["tea"].update(update)
    if args.case == "category":
        row["water"].update(price=89, regular_price=99)
    expected.append(row)
# Match application.study_design.design_ab's draft temperature/output budget.
client = LiteLLMClient(LLMConfig(model=args.model, api_base=args.endpoint, api_key=SecretStr("local-probe"),
    temperature=.2, seed=0, max_tokens=6144, timeout_sec=180, max_parallel=1, chat_template_thinking=False,
    structured_output=args.mode, structured_sdk_retries=0, cache_dir=str(output / "cache")))
send = httpx.AsyncClient.send
calls = attempts = 0


async def traced_send(self, request, *positional, **keywords):
    global calls, attempts
    if request.url.host != host:
        return await send(self, request, *positional, **keywords)
    attempts += 1
    payload = json.loads(request.content)
    with (output / "requests.jsonl").open("a") as trace:
        trace.write(json.dumps({"attempt": attempts, "request": payload}, ensure_ascii=False) + "\n")
    started = time.perf_counter()
    response = await send(self, request, *positional, **keywords)
    await response.aread()
    calls += 1
    elapsed = round(time.perf_counter() - started, 3)
    with (output / "http.jsonl").open("a") as trace:
        trace.write(json.dumps({"call": calls, "status": response.status_code, "seconds": elapsed,
            "response": response.json()}, ensure_ascii=False) + "\n")
    print(f"Call {calls}: HTTP {response.status_code}, {elapsed}s", flush=True)
    return response


started = time.perf_counter()
result = {"case": args.case, "model": args.model, "endpoint": args.endpoint, "structured_output": args.mode,
          "question": QUESTIONS[args.case], "currency": currency, "success": False,
          "cache_replay_from": str(args.cache_from) if args.cache_from else None}
try:
    with patch.object(httpx.AsyncClient, "send", traced_send):
        draft = asyncio.run(design_experiment(client, QUESTIONS[args.case], store, currency, packages))
    rows, issues = [], []
    for variant in draft.variants:
        edited, applied, warnings = apply_changes(store, variant.changes,
            package_uris=package_uris, minor_per_major=1 if krw else 100)
        rows.append({"variant": variant.model_dump(mode="json"), "products": products(edited),
                     "applied": applied, "warnings": warnings})
        if warnings:
            issues.append("Unapplied operations")
    if len(rows) != len(expected):
        issues.append(f"Expected exactly {len(expected)} variants")
    observed = sorted(json.dumps(row["products"], sort_keys=True) for row in rows)
    if observed != sorted(json.dumps(row, sort_keys=True) for row in expected):
        issues.append("Drafts do not preserve the requested products, prices, promotions and placements")
    if store.model_dump_json() != before:
        issues.append("Source layout mutated")
    if args.case == "discount-promo" and draft.engine != "vlm":
        result["engine_note"] = "Rule shoppers use a generic sign impulse boost; this probe checks drafted operations, not literal sign interpretation."
    result.update(success=not issues, draft=draft.model_dump(mode="json"), rows=rows, issues=issues)
except Exception as error:
    result["error"] = repr(error)
result.update(seconds=round(time.perf_counter() - started, 2), calls=calls, attempted_calls=attempts,
              usage=client.get_usage().model_dump(mode="json"))
(output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
(output / "before.json").write_text(before)
print(json.dumps({"output": str(output), **{key: value for key, value in result.items()
    if key in {"success", "seconds", "calls", "issues", "error", "usage"}}}, ensure_ascii=False), flush=True)
raise SystemExit(0 if result["success"] else 1)
