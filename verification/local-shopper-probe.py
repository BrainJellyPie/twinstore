"""Show a real checkout screenshot to a tiny loopback VLM.

Run with PYTHONPATH=backend/src and the backend Python. Requires the local
OpenAI-compatible model server on port 8081; no paid provider is used. Saves
the screenshot, shopper, site, raw request/response (without headers), and the
chosen action. A $1 browse customer sees a $19.99 item already in checkout.
Budget delivery and avoiding an unaffordable order are separate observations;
neither proves that the thought and chosen action agree.
"""
import argparse, asyncio, json, random, time
from pathlib import Path
from unittest.mock import patch
import httpx
from pydantic import SecretStr
from store_emulator.application.online import _bundled_picture
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.online import BrowserState, CartLine, PageKind, PageRef
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.browser import build_page, numbering, outline
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import ModelPolicy, Memory, StepView
from store_emulator.engine.online.render import render_page
from store_emulator.engine.online.shoppers import sample_shoppers
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('.data/local-model-probes'))
parser.add_argument('--device', choices=['desktop', 'mobile'], default='desktop')
args = parser.parse_args()
root = args.output.resolve() / f'browse-budget-{time.time_ns()}'
root.mkdir(parents=True)
site = build_site('fashion', site_id='cpu_budget', currency='USD')
site.options.welcome_popup = 'none'
site.options.cookie_banner = False
site.options.shipping_fee = 0
site.options.service_fee = 0
site.options.guest_checkout = True
site.options.checkout_flow = 'one_page'
product = site.products[0]
shopper = sample_shoppers(site, 1, seed=4, missions={'browse': 1}, mobile_share=0)[0]
shopper = shopper.model_copy(update={'budget': 100, 'device': args.device, 'patience_sec': 900, 'goal': 'Window-shop with no planned purchase. I put this item in my cart and am deciding whether to pay.'})
state = BrowserState(device=shopper.device, at=PageRef(page=PageKind.CHECKOUT, checkout_step='review'), cart=[CartLine(product_id=product.id)], guest=True, address_added=True, payment_method='card', cookies_answered=True, welcome_seen=True)
page = build_page(site, state)
numbers = numbering(page, 0)
shot = render_page(page, site, numbers, _bundled_picture)
(root / 'screen.png').write_bytes(shot.png)
view = StepView(page, state, numbers, outline(page, site), 1, product.price, (product.name,), shot.scaled_data_url(896), seed=4, point=0)
client = LiteLLMClient(LLMConfig(model='openai/local-model', api_base='http://127.0.0.1:8081/v1', api_key=SecretStr('local'), temperature=0, seed=0, max_tokens=240, timeout_sec=180, max_parallel=1, chat_template_thinking=False, structured_output='json_schema', structured_sdk_retries=0, cache_dir=str(root / 'cache')))
policy = ModelPolicy(client, vision=True, max_tokens=240, max_retries=1)
original = httpx.AsyncClient.send
calls = 0
prompts = []

async def traced(self, request, *args, **kwargs):
    global calls
    calls += 1
    started = time.perf_counter()
    response = await original(self, request, *args, **kwargs)
    await response.aread()
    body = json.loads(request.content)
    for m in body.get('messages', []):
        if isinstance(m.get('content'), list):
            for part in m['content']:
                if part.get('type') == 'text':
                    prompts.append(part['text'])
                elif part.get('type') == 'image_url':
                    part['image_url']['url'] = '[saved as screen.png]'
        elif isinstance(m.get('content'), str):
            prompts.append(m['content'])
    record = {'call': calls, 'seconds': round(time.perf_counter() - started, 2), 'request': body, 'response': response.json()}
    with (root / 'http.jsonl').open('a') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
    return response
started = time.perf_counter()
with patch.object(httpx.AsyncClient, 'send', traced):
    choice = asyncio.run(policy.choose(site, shopper, view, Memory(steps=['Viewed the product', 'Added it to cart', 'Opened checkout'], elapsed=60), random.Random(4)))
visible = any(('Budget: $1.00' in text for text in prompts))
result = {'root': str(root), 'budget': shopper.budget, 'product_price': product.price, 'budget_visible': visible, 'unaffordable_order_avoided': choice.control.action.kind != 'place_order', 'calls': calls, 'seconds': round(time.perf_counter() - started, 2), 'action': choice.control.action.model_dump(mode='json'), 'thought': choice.thought, 'source': choice.source, 'error': choice.error}
(root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
(root / 'shopper.json').write_text(shopper.model_dump_json(indent=2))
(root / 'site.json').write_text(site.model_dump_json(indent=2))
print(json.dumps(result, ensure_ascii=False), flush=True)
