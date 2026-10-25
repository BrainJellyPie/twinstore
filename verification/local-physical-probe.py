"""Run a compact store through the actual CPU VLM shopper and customer executor.

Requires a loopback multimodal model server on port 8081. From the repository
root, run with PYTHONPATH=backend/src and the backend Python. No model replies
are mocked. Images, request/reply bodies (without headers), decisions, executed
purchases and engine diagnostics are saved to a fresh output folder. Format
success does not establish sensible product choices; inspect glance_targets
and the saved images for name/number mismatches and implausible reasoning.
"""
import argparse, asyncio, base64, json, sys, time
from pathlib import Path
from unittest.mock import patch
import httpx
from pydantic import SecretStr
from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import LLMConfig, SimulationConfig, EngineType
from store_emulator.domain.engine import PerCustomerContext
from store_emulator.domain.layout_options import TemplateLayoutRequest
from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Weekday, Action
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.perception.product_images import default_product_image
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.customer_executor import execute_decision
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('.data/local-model-probes'))
parser.add_argument('--currency', choices=['USD', 'KRW'], default='USD')
parser.add_argument('--free', action='store_true')
args = parser.parse_args()
root = args.output.resolve() / f'physical-{args.currency}-{time.time_ns()}'
root.mkdir(parents=True)
options = TemplateLayoutRequest(template_id='compact_cvs', width=8, height=6, currency=args.currency, products_per_category=2)
store = generate_store(options.template_id, currency=args.currency, options=options)
items = {p.sku: p for r in store.product_racks for s in r.slots for p in s.items}
cheapest = sorted(items.values(), key=lambda p: p.price)[:2]
if args.free:
    for r in store.product_racks:
        for s in r.slots:
            for p in s.items:
                if p.sku == cheapest[0].sku:
                    p.regular_price = p.price
                    p.price = 0
                    p.promo = 'FREE'
budget = 10000 if args.currency == 'KRW' else 1000
persona = Persona(id='cpu_resident', identity='Nearby resident', age_group='30s', gender='Female', description='A nearby resident making a quick shopping trip.', intent='Buy ' + ' and '.join((p.name for p in cheapest)), purpose='Restock two usual products', preferred_categories=[], usual_products=[p.name for p in cheapest], budget_min=budget, budget_max=budget, basket_size=2)
llm = LLMConfig(model='openai/local-model', api_base='http://127.0.0.1:8081/v1', api_key=SecretStr('local'), temperature=0, seed=0, max_tokens=240, timeout_sec=180, max_parallel=1, chat_template_thinking=False, structured_output='json_schema', structured_sdk_retries=0, cache_dir=str(root / 'cache'))
client = LiteLLMClient(llm)
cfg = SimulationConfig(engine_type=EngineType.VLM_GLANCE, currency=args.currency)
vcfg = cfg.engines.vlm_glance.model_copy(update={'llm': llm, 'max_glances': 2, 'glance_policy': 'all', 'image_width': 512, 'plan_policy': 'vlm', 'max_plan_items': 2, 'entrance_image': True})
cfg = cfg.model_copy(update={'engines': cfg.engines.model_copy(update={'vlm_glance': vcfg})})
engine = VLMGlanceEngine(client, AStarPathFinder(), cfg, image_loader=default_product_image)
context = PerCustomerContext(store=store, persona=persona, day=Weekday.MON, arrival_hour=12, concurrent_visitors_in_hour=3, cue=BehaviorCue(state='목마름', emotion='기분좋음'), behavior_patterns=BEHAVIOR_PATTERNS, seed=4)
original = httpx.AsyncClient.send
calls = 0

async def traced(self, request, *a, **kw):
    global calls
    calls += 1
    started = time.perf_counter()
    response = await original(self, request, *a, **kw)
    await response.aread()
    body = json.loads(request.content)
    for m in body.get('messages', []):
        if isinstance(m.get('content'), list):
            for part in m['content']:
                if part.get('type') == 'image_url':
                    url = part['image_url']['url']
                    filename = f'call-{calls}.png'
                    if url.startswith('data:'):
                        (root / filename).write_bytes(base64.b64decode(url.split(',', 1)[1]))
                    part['image_url']['url'] = filename
    with (root / 'http.jsonl').open('a') as f:
        f.write(json.dumps({'call': calls, 'seconds': round(time.perf_counter() - started, 2), 'request': body, 'response': response.json()}, ensure_ascii=False) + '\n')
    print(json.dumps({'call': calls, 'reply': response.json().get('choices', [{}])[0].get('message', {}).get('content', '')}, ensure_ascii=False), flush=True)
    return response
(root / 'store.json').write_text(store.model_dump_json(indent=2))
(root / 'persona.json').write_text(persona.model_dump_json(indent=2))
started = time.perf_counter()
try:
    with patch.object(httpx.AsyncClient, 'send', traced):
        decision = asyncio.run(engine.decide_actions(context))
    (root / 'decision.json').write_text(decision.model_dump_json(indent=2))
    customer = execute_decision(store, persona.id, Weekday.MON, '12:00:00', decision, AStarPathFinder(), 4)
    (root / 'customer.json').write_text(customer.model_dump_json(indent=2))
    assert decision.spend_limit is None or customer.total_spent <= decision.spend_limit
    result = {'completed': True, 'buys': [x.model_dump(mode='json') for x in decision.actions if x.action == Action.BUY], 'dropped_invalid': decision.dropped_invalid_buys, 'dropped_over_budget': decision.dropped_over_budget, 'spent': customer.total_spent, 'units': customer.units_bought}
except Exception as e:
    result = {'completed': False, 'error': repr(e)}
metadata = engine.metadata()
(root / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
result['format_ok'] = result['completed'] and metadata['errors'] == 0 and (metadata['planning']['plan_errors'] == 0)
result['glance_targets'] = [{'said': r['product'], 'resolved_name': items[r['resolved_sku']].name if r['resolved_sku'] in items else '', 'number': r['number'], 'interest': r['interest'], 'error': r['outcome'] == 'error'} for r in metadata['records']]
result.update(root=str(root), seconds=round(time.perf_counter() - started, 2), calls=calls)
(root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False), flush=True)
sys.exit(0 if result['format_ok'] else 1)
