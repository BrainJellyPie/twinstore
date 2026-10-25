"""Run production starter selection or package reading against a real loopback model; retain wire replies.

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
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.package_reader import read_pack
from store_emulator.engine.perception.product_images import bundled_product_image
from store_emulator.engine.perception.shelf_render import load_font
from store_emulator.engine.validation import validate


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--case", choices=["compact", "cafe", "book", "pack-jam", "pack-label", "pack-wrong-variant", "pack-blank"], default="compact")
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
    temperature=0, seed=0, max_tokens=400 if args.case.startswith("pack-") else 5000, timeout_sec=180, max_parallel=1,
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
    if args.case.startswith("pack-"):
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
