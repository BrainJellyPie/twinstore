"""Run real CPU VLM visits through planning, shelf images, execution and shared stock.

Requires the loopback vision server at port 8081. No model replies or purchase
choices are mocked. Saves request images, raw replies, decisions and final
receipts. The deliberately small fixtures separate invariants from whether the
model made enough purchases to exercise a boundary. No saved user stores change.
"""
import argparse
import asyncio
import base64
import json
import time
from pathlib import Path
from unittest.mock import patch

import httpx
from pydantic import SecretStr

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.operations import OperationsConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import DaySchedule, Store
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner
from store_emulator.engine.validation import validate

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case', choices=['stock-one', 'same-sku', 'free', 'browse', 'unavailable', 'plan-disabled'], default='stock-one')
parser.add_argument('--output', type=Path, default=Path('.data/local-model-probes'))
parser.add_argument('--structured-output', choices=['json_schema', 'json'], default='json_schema')
parser.add_argument('--cache-from', type=Path, help='Explicitly replay cached model replies for diagnostic repairs')
parser.add_argument('--seed', type=int, default=4)
args = parser.parse_args()
root = args.output.resolve() / f'visit-{args.case}-{args.structured_output}-{time.time_ns()}'
root.mkdir(parents=True)
currency, price, budget = ('KRW', 0, 1) if args.case == 'free' else ('USD', 100, 100)
count = 2 if args.case == 'stock-one' else 1
slots = [Slot(block=0, face=Face.N, level=3, items=[SlotItem(sku='water', name='Mineral Water 500ml', price=price)])]
if args.case == 'same-sku':
    slots.append(Slot(block=1, face=Face.N, level=3, items=[SlotItem(sku='water', name='Mineral Water 500ml', price=5000)]))
store = Store(id='cpu-visit', name='Water shop', type='convenience', currency=currency, grid_size=(8, 8),
    weekly_schedule=[DaySchedule(day=Weekday.MON, open_hour=9, close_hour=12)], racks=[
        Rack(id='entrance', type='entrance', position=(0, 0), shape=[[1]]),
        Rack(id='exit', type='exit', position=(7, 0), shape=[[1]]),
        Rack(id='counter', type='counter', position=(6, 2), shape=[[1]]),
        Rack(id='water', type='shelf', rack_name='Water', position=(2, 2),
             shape=[[1, 1]] if args.case == 'same-sku' else [[1]], slots=slots)])
intent = ('Take one free bottle of Mineral Water 500ml. Do not buy any paid item.' if args.case == 'free'
          else 'Buy exactly one bottle of Mineral Water 500ml for $1.00. Do not pay more than $1.00.')
if args.case == 'browse':
    intent = 'Only look around. Not thirsty, no shopping list, no planned purchases today.'
elif args.case == 'unavailable':
    intent = 'Need a laptop computer only. Leave if the store has no computers. Do not buy food or drinks.'
no_purchase = args.case in {'browse', 'unavailable'}
people = [Persona(id=f'P{i+1}', day=Weekday.MON, arrival_hour=9, identity='Nearby resident', age_group='30s', gender='Female',
    description=intent if no_purchase else 'A thirsty resident making a short trip for one water bottle.', intent=intent, purpose=intent,
    preferred_categories=[] if no_purchase else ['Water'], usual_products=[] if no_purchase else ['Mineral Water 500ml'],
    budget_min=0, budget_max=budget, basket_size=0 if no_purchase or args.case == 'plan-disabled' else 1) for i in range(count)]
live_config = LLMConfig(model='openai/local-model', api_base='http://127.0.0.1:8081/v1', api_key=SecretStr('local-probe'),
    temperature=0, seed=0, max_tokens=160, timeout_sec=180, max_parallel=1, chat_template_thinking=False,
    structured_output=args.structured_output, structured_sdk_retries=0, cache_dir=str(args.cache_from.resolve() if args.cache_from else root/'cache'))
client = LiteLLMClient(live_config)
cfg = SimulationConfig(engine_type=EngineType.VLM_GLANCE, currency=currency, seed=args.seed,
    budget_tolerance=1.0, max_quantity_per_line=1,
    operations=OperationsConfig(stock_per_facing=1, restock_every_min=None, backroom_per_product=0,
        substitute_share=0, crowd_limit=None))
cfg.engines.vlm_glance.max_plan_items = 0 if args.case == 'plan-disabled' else 1
cfg.engines.vlm_glance.llm = live_config.model_copy()
cfg.engines.vlm_glance.max_glances = 0 if no_purchase else 2
cfg.engines.vlm_glance.glance_policy = 'all'
cfg.engines.vlm_glance.image_width = 512
paths = AStarPathFinder()
engine = VLMGlanceEngine(client, paths, cfg)
runner = PerCustomerSimulationRunner(cfg, engine, paths, lambda rng: BehaviorCue() if no_purchase else BehaviorCue(state='목마름'),
    [BehaviorPattern(id='window_shopping' if args.case == 'browse' else 'purposeful', name='Visit', description=intent, grammar='',
        max_products=1, browse_required_before_buy=True, allow_no_purchase=no_purchase)])
for name, data in [('store', store.model_dump(mode='json')), ('personas', [p.model_dump(mode='json') for p in people]),
                   ('config', cfg.model_dump(mode='json'))]:
    (root/f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2))
errors = [issue for issue in validate(store) if issue.severity == 'error']
if errors:
    raise RuntimeError(str(errors))
send = httpx.AsyncClient.send
calls = 0
async def traced(self, request, *a, **kw):
    global calls
    started = time.perf_counter()
    response = await send(self, request, *a, **kw)
    if request.url.host == '127.0.0.1':
        await response.aread()
        calls += 1
        body = json.loads(request.content)
        pictures = 0
        for message in body.get('messages', []):
            if isinstance(message.get('content'), list):
                for part in message['content']:
                    if part.get('type') == 'image_url':
                        pictures += 1
                        image_path = root/f'call-{calls}-image-{pictures}.png'
                        image_path.write_bytes(base64.b64decode(part['image_url']['url'].split(',', 1)[1]))
                        part['image_url'] = {'url': image_path.name}
        row = {'call': calls, 'seconds': round(time.perf_counter()-started, 3), 'status': response.status_code,
               'request': body, 'response': response.json()}
        with (root/'http.jsonl').open('a') as handle:
            handle.write(json.dumps(row, ensure_ascii=False)+'\n')
        print(json.dumps({k: row[k] for k in ['call','seconds','status']}), flush=True)
    return response
start = time.perf_counter()
result = {'case': args.case, 'seed': args.seed, 'success': False, 'cache_replay_from': str(args.cache_from) if args.cache_from else None}
try:
    with patch.object(httpx.AsyncClient, 'send', traced):
        aggregated, customers = asyncio.run(runner.run(store, people, max_concurrent=1, path_heatmap=False,
            address='Seoul, South Korea' if currency == 'KRW' else 'Austin, Texas, USA', customer_profile=intent))
    (root/'aggregate.json').write_text(aggregated.model_dump_json(indent=2))
    (root/'customers.json').write_text(json.dumps([r.model_dump(mode='json') for r in customers], ensure_ascii=False, indent=2))
    (root/'planned-customers.json').write_text(json.dumps([r.model_dump(mode='json') for r in aggregated.planned_customers], ensure_ascii=False, indent=2))
    (root/'engine.json').write_text(json.dumps(engine.metadata(), ensure_ascii=False, indent=2))
    issues = []
    if len(customers) != count or aggregated.diagnostics.failed_customers:
        issues.append('Missing or failed visits')
    for customer in customers:
        if not customer.timeline or customer.timeline[-1].action != Action.EXIT:
            issues.append(f'{customer.persona_id}: visit does not end with exit')
        if customer.total_spent != sum(p.price*p.quantity for p in customer.purchases) or customer.total_spent > budget:
            issues.append(f'{customer.persona_id}: receipt total or budget mismatch')
        if any(p.product_sku != 'water' or p.price != price for p in customer.purchases):
            issues.append(f'{customer.persona_id}: wrong purchased SKU or offer price')
        if customer.purchases and not any(e.action == Action.PAY for e in customer.timeline):
            issues.append(f'{customer.persona_id}: purchased without checkout')
    units = sum(c.units_bought for c in customers)
    if units > 1:
        issues.append('Sold more than the single available affordable/free unit')
    before_stock = sum(c.units_bought for c in aggregated.planned_customers)
    coverage = before_stock == count and units == 1 and bool(engine.glance_log)
    if no_purchase:
        coverage = len(engine.plan_log) == count and before_stock == units == 0
    if args.case == 'plan-disabled':
        coverage = bool(engine.plan_log) and bool(engine.glance_log)
    model_issues = []
    for plan in engine.plan_log:
        if no_purchase or args.case == 'plan-disabled':
            if plan.items:
                model_issues.append(f'{plan.persona_id}: unexpected planned purchase')
        elif not plan.items:
            model_issues.append(f'{plan.persona_id}: explicit water purchase omitted from plan')
        if args.case == 'unavailable' and plan.enter:
            model_issues.append(f'{plan.persona_id}: entered despite unavailable-only intent')
        if args.case == 'browse' and not plan.enter:
            model_issues.append(f'{plan.persona_id}: turned around despite browse-only intent')
        if plan.error:
            model_issues.append(f'{plan.persona_id}: entry error: {plan.error}')
    model_issues.extend(f'{glance.persona_id}: shelf response failed' for glance in engine.glance_log if glance.outcome == 'error')
    result.update(success=not issues and not model_issues and coverage, invariants_ok=not issues, coverage_ok=coverage,
        model_ok=not model_issues, issues=issues, model_issues=model_issues,
        units_before_shared_stock=before_stock, entry_plan_lines=sum(len(plan.items) for plan in engine.plan_log),
        sold_units=units, lost_units=sum(c.lost_units for c in customers),
        revenue=sum(c.total_spent for c in customers), visits=len(customers), glances=len(engine.glance_log),
        plans=len(engine.plan_log))
except Exception as error:
    result['error'] = repr(error)
result.update(seconds=round(time.perf_counter()-start, 2), calls=calls, usage=client.get_usage().model_dump(mode='json'))
(root/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({'output': str(root), **result}, ensure_ascii=False, indent=2), flush=True)
raise SystemExit(0 if result['success'] else 1)
