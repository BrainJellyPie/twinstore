"""Isolate product and quantity selection on an actual loopback CPU model.

Run from the repository root with PYTHONPATH=backend/src and the backend Python.
This diagnostic uses generated catalogs and checks four precise requests: usual
items with quantities, Korean items at the end of the catalog, no purchase, and a
free offer. It is not the production three-stage engine and does not establish
that route generation or impulse decisions are correct. Request/reply bodies
are recorded without headers. No user project or paid provider is used.
"""
import argparse, asyncio, json, sys, time
from pathlib import Path
from unittest.mock import patch
import httpx
from pydantic import BaseModel, Field, SecretStr, create_model
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.layout_options import TemplateLayoutRequest
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.prompting import display_price
from store_emulator.engine.simulation.engines.pattern_intent_impulse.stage2_intent import catalog_records
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('.data/local-model-probes'))
args = parser.parse_args()
root = args.output.resolve() / f'compact-purchases-{time.time_ns()}'
root.mkdir(parents=True)
calls = 0
original = httpx.AsyncClient.send

async def traced(self, request, *a, **kw):
    global calls
    calls += 1
    start = time.perf_counter()
    response = await original(self, request, *a, **kw)
    await response.aread()
    with (root / 'http.jsonl').open('a') as f:
        f.write(json.dumps({'call': calls, 'seconds': round(time.perf_counter() - start, 2), 'request': json.loads(request.content), 'response': response.json()}, ensure_ascii=False) + '\n')
    return response

async def run():
    rows = []
    for case, currency in [('usual', 'USD'), ('last', 'KRW'), ('no-purchase', 'USD'), ('free', 'KRW')]:
        options = TemplateLayoutRequest(template_id='compact_cvs', width=8, height=6, currency=currency, products_per_category=2)
        store = generate_store(options.template_id, currency=currency, options=options)
        if currency == 'KRW':
            cheapest = min((p for r in store.product_racks for slot in r.slots for p in slot.items), key=lambda p: p.price).sku
            for rack in store.product_racks:
                for slot in rack.slots:
                    for product in slot.items:
                        if product.sku == cheapest:
                            product.regular_price = product.price
                            product.price = 0
                            product.promo = 'FREE'
        records = catalog_records(store)
        codes = list(records)
        (root / f'{case}-store.json').write_text(store.model_dump_json(indent=2))
        keys = [codes[0], codes[7]] if case == 'usual' else codes[-2:] if case == 'last' else [next((k for k, p in records.items() if p.price == 0))] if case == 'free' else []
        expected = {k: 2 if i else 1 for i, k in enumerate(keys)}
        instruction = 'Just look around. I do not want to buy anything today.' if not keys else 'Buy ' + ' and '.join((f'{n} x {records[k].name}' for k, n in expected.items())) + '. Buy no other products.'
        budget = sum((records[k].price * n for k, n in expected.items()))
        purchase = create_model('Purchase', product_code=(str, Field(json_schema_extra={'enum': codes})), quantity=(int, Field(ge=1, le=6)))
        plan = create_model('Purchases', purchases=(list[purchase], Field(max_length=5)))
        client = LiteLLMClient(LLMConfig(model='openai/local-model', api_base='http://127.0.0.1:8081/v1', api_key=SecretStr('local'), temperature=0, seed=0, max_tokens=400, timeout_sec=180, max_parallel=1, chat_template_thinking=False, structured_output='json_schema', structured_sdk_retries=0, cache_dir=str(root / case)))
        user = 'Shopper request: ' + instruction + '\nAvailable budget: ' + display_price(budget, currency) + '\nCatalog:\n' + '\n'.join((f'{k}: {p.name}, {display_price(p.price, currency)}' for k, p in records.items()))
        started = time.perf_counter()
        try:
            result = await client.generate_structured_async(plan, 'Choose only the products and quantities this shopper requests and can afford. Use supplied product codes. Include purchases: [] when they choose not to buy. Do not plan paths or narrate a visit.', user, max_retries=1)
            actual = {p.product_code: p.quantity for p in result.purchases}
            row = {'case': case, 'expected': expected, 'actual': actual, 'success': actual == expected and len(result.purchases) == len(actual), 'seconds': round(time.perf_counter() - started, 2)}
        except Exception as error:
            row = {'case': case, 'success': False, 'error': repr(error), 'seconds': round(time.perf_counter() - started, 2)}
        rows.append(row)
        print(json.dumps({'root': str(root), **row}, ensure_ascii=False), flush=True)
    (root / 'result.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    return rows
with patch.object(httpx.AsyncClient, 'send', traced):
    rows = asyncio.run(run())
sys.exit(0 if all(row["success"] for row in rows) else 1)
