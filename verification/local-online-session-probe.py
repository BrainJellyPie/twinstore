"""Run an actual CPU vision shopper from arrival through its exit survey.

Requires the loopback model at port 8081. Uses production screenshots, browser
transitions and policy calls; no model replies or actions are mocked. Raw replies,
images and the full session are retained without HTTP headers. Technical validity,
goal completion and semantic review are distinct: a valid survey is not evidence
that its scores accurately describe the visit. No saved user store is modified.
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

from store_emulator.application.online import _bundled_picture
from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import ModelPolicy
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case', choices=['purchase', 'unavailable'], default='unavailable')
parser.add_argument('--device', choices=['desktop', 'mobile'], default='mobile')
parser.add_argument('--structured-output', choices=['json', 'json_schema'], default='json_schema')
parser.add_argument('--max-steps', type=int, default=8)
parser.add_argument('--output', type=Path, default=Path('.data/local-model-probes'))
args = parser.parse_args()
root = args.output.resolve() / f'online-session-{args.case}-{args.device}-{args.structured_output}-{time.time_ns()}'
root.mkdir(parents=True)
site = build_site('fashion', site_id='cpu_session', currency='USD')
site.options.welcome_popup = 'none'
site.options.cookie_banner = False
site.options.shipping_fee = site.options.service_fee = 0
site.options.guest_checkout = True
site.options.checkout_flow = 'one_page'
site.options.cart_reminder = False
product = site.products[0]
shopper = sample_shoppers(site, 1, seed=4, missions={'purchase': 1}, mobile_share=0)[0]
shopper = shopper.model_copy(update={'device': args.device, 'budget': 5000, 'patience_sec': 900,
    'arrival': 'direct', 'target_product': product.id if args.case == 'purchase' else '',
    'target_category': product.category_id if args.case == 'purchase' else '',
    'target_terms': [product.name] if args.case == 'purchase' else ['laptop'],
    'goal': (f'Buy exactly one {product.name} if the total is at most $50.00. Do not add other products.'
             if args.case == 'purchase' else 'I need a laptop computer only. Leave if no laptops are available. I do not want clothing.')})
client = LiteLLMClient(LLMConfig(model='openai/local-model', api_base='http://127.0.0.1:8081/v1',
    api_key=SecretStr('local'), temperature=0, seed=0, max_tokens=240, timeout_sec=180, max_parallel=1,
    chat_template_thinking=False, structured_output=args.structured_output, structured_sdk_retries=0,
    cache_dir=str(root/'cache')))
policy = ModelPolicy(client, vision=True, max_tokens=240, max_retries=1)
original_send = httpx.AsyncClient.send
calls = 0

async def traced(self, request, *a, **kw):
    global calls
    started = time.perf_counter()
    response = await original_send(self, request, *a, **kw)
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
                        picture = root/f'call-{calls}-image-{pictures}.png'
                        picture.write_bytes(base64.b64decode(part['image_url']['url'].split(',', 1)[1]))
                        part['image_url']['url'] = picture.name
        row = {'call': calls, 'seconds': round(time.perf_counter()-started, 2), 'status': response.status_code,
               'request': body, 'response': response.json()}
        with (root/'http.jsonl').open('a') as handle:
            handle.write(json.dumps(row, ensure_ascii=False)+'\n')
        print(json.dumps({k: row[k] for k in ['call', 'seconds', 'status']}), flush=True)
    return response

(root/'site.json').write_text(site.model_dump_json(indent=2))
(root/'shopper.json').write_text(shopper.model_dump_json(indent=2))
started = time.perf_counter()
result = {'case': args.case, 'device': args.device, 'structured_output': args.structured_output,
          'technical_success': False, 'semantic_review': 'Inspect the saved actions, thoughts and survey against the actual visit.'}
try:
    with patch.object(httpx.AsyncClient, 'send', traced):
        session = asyncio.run(run_session(site, shopper, policy, seed=4, max_steps=args.max_steps,
            render=True, image_width=896, picture=_bundled_picture, surveyor=policy.survey))
    (root/'session.json').write_text(session.model_dump_json(indent=2))
    issues = []
    if session.fallbacks or policy.failed:
        issues.append('One or more choices used a rule fallback after model failure')
    if session.survey is None:
        issues.append('The exit survey has no usable model answer')
    if session.order_total > shopper.budget:
        issues.append('The order exceeds the explicit budget')
    if session.subtotal != sum(line.price*line.quantity for line in session.order):
        issues.append('Receipt subtotal does not match ordered lines')
    if args.case == 'unavailable' and session.order:
        issues.append('Bought clothing despite unavailable-only laptop intent')
    if args.case == 'purchase' and any(line.product_id != product.id or line.quantity != 1 for line in session.order):
        issues.append('Ordered a different product or quantity from the explicit goal')
    result.update(technical_success=not issues, issues=issues, outcome=session.outcome,
        goal_completed=bool(session.order) if args.case == 'purchase' else session.outcome in {'left', 'bounced'},
        steps=len(session.steps), model_choices=policy.answered, failed_choices=policy.failed,
        fallbacks=session.fallbacks, survey=session.survey.model_dump(mode='json') if session.survey else None,
        order_total=session.order_total,
        actions=[{'page': step.page, 'action': step.choice.kind if step.choice else None,
                  'thought': step.thought, 'source': step.source} for step in session.steps])
except Exception as error:
    result['error'] = repr(error)
result.update(calls=calls, seconds=round(time.perf_counter()-started, 2), usage=client.get_usage().model_dump(mode='json'))
(root/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({'root': str(root), **result}, ensure_ascii=False, indent=2), flush=True)
raise SystemExit(0 if result['technical_success'] else 1)
