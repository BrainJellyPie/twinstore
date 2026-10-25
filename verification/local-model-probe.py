"""Run production starter selection against a real loopback model; retain its wire replies.

From the repository root:
  PYTHONPATH=backend/src backend/.venv/bin/python verification/local-model-probe.py --case compact

Start the local server separately, on CPU for a CPU probe. No responses are mocked.
Every run gets a fresh cache; the trace contains built-in sample prompts, not headers or keys.
"""

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import httpx
from pydantic import SecretStr

from store_emulator.application import template_assortment
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.layout_options import TemplateLayoutRequest
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.validation import validate


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--case", choices=["compact", "cafe", "book"], default="compact")
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
    temperature=0, seed=0, max_tokens=5000, timeout_sec=180, max_parallel=1,
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
        with (output / "http.jsonl").open("a") as trace:
            trace.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"Call {calls}: HTTP {response.status_code}, {record['seconds']}s", flush=True)
    return response


started = time.perf_counter()
result = {"case": args.case, "model": args.model, "endpoint": args.endpoint,
    "layout": options.model_dump(mode="json"), "description": description}
try:
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
