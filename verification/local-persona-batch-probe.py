"""Exercise real local-model customer-batch truncation and recovery on CPU.

Run from the repository root with PYTHONPATH=backend/src and the backend Python.
Requires the loopback model server on port 8081. Defaults reproduce a five-person
batch with a 512-token output ceiling. Requests and replies are real; the area
profile below is normalized output from the earlier night-market CPU run.
"""
import argparse
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch

import httpx
from pydantic import SecretStr

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine.generators.persona import (
    BatchTally, HourlyProfile, TradeAreaProfile, generate_personas_for_day,
)
from store_emulator.engine.llm_client import LiteLLMClient

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=Path(".data/local-model-probes"))
parser.add_argument("--count", type=int, choices=range(1, 13), default=5)
parser.add_argument("--max-tokens", type=int, default=512)
parser.add_argument("--mixed-hours", action="store_true")
args = parser.parse_args()
if args.max_tokens < 1:
    parser.error("--max-tokens must be positive")
root = args.output.resolve() / f"persona-batch-{time.time_ns()}"
root.mkdir(parents=True)
profile = TradeAreaProfile(keywords=["동네", "점심", "음료", "간식", "출근"],
    identities=["동네 주민", "야간 근무자", "점심시간 회사원"], purposes=["점심 도시락"])
description = "동네 주민과 야간 근무자가 심야에 간단한 간식과 음료를 삽니다. 1회 예산은 3,000~10,000원입니다."
hours = list(range(24 - args.count, 24)) if args.mixed_hours else [23] * args.count
traffic = ([HourlyProfile(hour=hour, visitor_count=1, person_types=profile.identities) for hour in hours]
           if args.mixed_hours else [HourlyProfile(hour=23, visitor_count=args.count, person_types=profile.identities)])
client = LiteLLMClient(LLMConfig(model="openai/local-model", api_base="http://127.0.0.1:8081/v1",
    api_key=SecretStr("local-probe"), temperature=0, seed=0, max_tokens=args.max_tokens,
    timeout_sec=180, max_parallel=1, chat_template_thinking=False,
    structured_output="json_schema", structured_sdk_retries=0, cache_dir=str(root / "cache")))
send = httpx.AsyncClient.send
calls = 0


async def traced(self, request, *positional, **keywords):
    global calls
    started = time.perf_counter()
    response = await send(self, request, *positional, **keywords)
    if request.url.host in {"127.0.0.1", "localhost"}:
        await response.aread()
        calls += 1
        data = response.json()
        record = {"call": calls, "seconds": round(time.perf_counter() - started, 3),
                  "status": response.status_code, "request": json.loads(request.content), "response": data}
        with (root / "http.jsonl").open("a") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps({"call": calls, "seconds": record["seconds"],
                          "finish": data.get("choices", [{}])[0].get("finish_reason")}), flush=True)
    return response


(root / "input.json").write_text(json.dumps({"profile": profile.model_dump(), "description": description,
    "hours": hours, "max_tokens": args.max_tokens}, ensure_ascii=False, indent=2))
tally = BatchTally()
started = time.perf_counter()
with patch.object(httpx.AsyncClient, "send", traced):
    people = asyncio.run(generate_personas_for_day(client, "Mapo-gu, Seoul, South Korea", profile,
        Weekday.MON, traffic, seed=4, batch_size=args.count, max_concurrent=1,
        categories=["drinks", "snacks"], currency="KRW", customer_profile=description, tally=tally))
issues = []
if len(people) != args.count or len({person.id for person in people}) != len(people):
    issues.append("Missing customers or duplicate IDs")
if [person.arrival_hour for person in people] != hours or any(person.day != Weekday.MON for person in people):
    issues.append("Customers shifted between arrival slots")
if any(not 3000 <= person.budget_min <= person.budget_max <= 10000 for person in people):
    issues.append("Customer budget outside the supplied range")
if any(set(person.preferred_categories) - {"drinks", "snacks"} for person in people):
    issues.append("Preferences outside the supplied categories")
result = {"success": not issues, "issues": issues, "count": len(people), "calls": calls,
          "seconds": round(time.perf_counter() - started, 2), "requested": tally.requested,
          "failed": tally.failed, "error": str(tally.first_error)[:500] if tally.first_error else "",
          "usage": client.get_usage().model_dump(mode="json")}
(root / "personas.json").write_text(json.dumps([person.model_dump(mode="json") for person in people], ensure_ascii=False, indent=2))
(root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({"output": str(root), **result}, ensure_ascii=False, indent=2), flush=True)
raise SystemExit(0 if result["success"] else 1)
