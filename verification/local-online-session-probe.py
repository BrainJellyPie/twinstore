"""Run an actual CPU vision shopper from arrival through its exit survey.

Requires a loopback model (port 8081 by default). Uses production screenshots, browser
transitions and policy calls; no model replies or actions are mocked. Raw replies,
images and the full session are retained without HTTP headers. Technical validity,
goal completion and semantic review are distinct: a valid survey is not evidence
that its scores accurately describe the visit. Exit success requires both valid
model responses and completion of the fixture goal. No saved user store is modified.
"""
import argparse
import asyncio
import base64
import json
import shutil
import time
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import httpx
from pydantic import SecretStr

from store_emulator.application.online import _bundled_picture
from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import ModelPolicy
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import at_rival, sample_shoppers

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case', choices=['purchase', 'unavailable', 'browse-rival'], default='unavailable')
parser.add_argument('--device', choices=['desktop', 'mobile'], default='mobile')
parser.add_argument('--structured-output', choices=['json', 'json_schema'], default='json_schema')
parser.add_argument('--endpoint', default='http://127.0.0.1:8081/v1')
parser.add_argument('--max-steps', type=int, default=8)
parser.add_argument('--cache-from', type=Path, help='Explicitly replay a saved model cache directory while testing a changed stage')
parser.add_argument('--output', type=Path, default=Path('.data/local-model-probes'))
args = parser.parse_args()
endpoint = urlsplit(args.endpoint)
if endpoint.scheme != 'http' or endpoint.hostname not in {'localhost', '127.0.0.1', '::1'}:
    parser.error('Use an HTTP loopback endpoint for the local model.')
root = args.output.resolve() / f'online-session-{args.case}-{args.device}-{args.structured_output}-{time.time_ns()}'
root.mkdir(parents=True)
if args.cache_from:
    shutil.copytree(args.cache_from.resolve(), root/'cache')
site = build_site('fashion', site_id='cpu_session', currency='USD')
site.options.welcome_popup = 'none'
site.options.cookie_banner = False
site.options.shipping_fee = site.options.service_fee = 0
site.options.guest_checkout = True
site.options.checkout_flow = 'one_page'
site.options.cart_reminder = False
product = site.products[0]
rival_allowed = None
if args.case == 'browse-rival':
    source = site
    shopper = sample_shoppers(source, 1, seed=4, missions={'browse': 1}, mobile_share=0)[0]
    shopper = shopper.model_copy(update={'device': args.device})
    assert 'the shop' in shopper.goal
    (root/'source-site.json').write_text(source.model_dump_json(indent=2))
    (root/'source-shopper.json').write_text(shopper.model_dump_json(indent=2))
    # A smaller fashion competitor keeps five categories but has no apparel.
    site = source.model_copy(deep=True, update={'id': 'cpu_rival',
        'categories': [c for c in source.categories if c.id != 'apparel'],
        'products': [p for p in source.products if p.category_id != 'apparel']})
    routed = at_rival(site, shopper, source)
    rival_allowed = routed is not None
    if routed is not None:
        shopper = routed
else:
    shopper = sample_shoppers(site, 1, seed=4, missions={'purchase': 1}, mobile_share=0)[0]
    shopper = shopper.model_copy(update={'device': args.device, 'budget': 5000, 'patience_sec': 900,
        'arrival': 'direct', 'target_product': product.id if args.case == 'purchase' else '',
        'target_category': product.category_id if args.case == 'purchase' else '',
        'target_terms': [product.name] if args.case == 'purchase' else ['laptop'],
        'goal': (f'Buy exactly one {product.name} if the total is at most $50.00. Do not add other products.'
                 if args.case == 'purchase' else 'I need a laptop computer only. Leave if no laptops are available. I do not want clothing.')})
client = LiteLLMClient(LLMConfig(model='openai/local-model', api_base=args.endpoint,
    api_key=SecretStr('local'), temperature=0, seed=0, max_tokens=240, timeout_sec=180, max_parallel=1,
    chat_template_thinking=False, structured_output=args.structured_output, structured_sdk_retries=0,
    cache_dir=str(root/'cache')))
policy = ModelPolicy(client, vision=True, max_tokens=240, max_retries=1)
original_send = httpx.AsyncClient.send
calls = 0
attempts = 0

async def traced(self, request, *a, **kw):
    global calls, attempts
    started = time.perf_counter()
    local = request.url.host == endpoint.hostname
    if local:
        attempts += 1
        attempt = attempts
        body = json.loads(request.content)
        pictures = 0
        for message in body.get('messages', []):
            if isinstance(message.get('content'), list):
                for part in message['content']:
                    if part.get('type') == 'image_url':
                        pictures += 1
                        picture = root/f'call-{attempt}-image-{pictures}.png'
                        picture.write_bytes(base64.b64decode(part['image_url']['url'].split(',', 1)[1]))
                        part['image_url']['url'] = picture.name
        # A timeout must retain the exact prompt and rendered page that caused
        # it. Never save headers or inline image bytes in the request trace.
        with (root/'requests.jsonl').open('a') as handle:
            handle.write(json.dumps({'attempt': attempt, 'request': body}, ensure_ascii=False)+'\n')
    response = await original_send(self, request, *a, **kw)
    if local:
        await response.aread()
        calls += 1
        row = {'call': calls, 'attempt': attempt, 'seconds': round(time.perf_counter()-started, 2), 'status': response.status_code,
               'request': body, 'response': response.json()}
        with (root/'http.jsonl').open('a') as handle:
            handle.write(json.dumps(row, ensure_ascii=False)+'\n')
        print(json.dumps({k: row[k] for k in ['call', 'seconds', 'status']}), flush=True)
    return response

(root/'site.json').write_text(site.model_dump_json(indent=2))
(root/'shopper.json').write_text(shopper.model_dump_json(indent=2))
started = time.perf_counter()
result = {'case': args.case, 'device': args.device, 'structured_output': args.structured_output,
          'endpoint': args.endpoint,
          'rival_allowed': rival_allowed,
          'cache_replay_from': str(args.cache_from) if args.cache_from else None,
          'technical_success': False, 'semantic_review': 'Inspect the saved actions, thoughts and survey against the actual visit.'}
try:
    if rival_allowed is False:
        raise ValueError('The whole-shop browser was excluded from a rival before any model choice.')
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
    if args.case == 'browse-rival':
        goal_completed = bool(session.steps) and session.outcome in {'left', 'bounced', 'purchased'}
    else:
        goal_completed = (len(session.order) == 1 and session.order[0].product_id == product.id
                          and session.order[0].quantity == 1 and session.order_total <= shopper.budget
                          if args.case == 'purchase' else not session.order and session.outcome in {'left', 'bounced'})
    result.update(technical_success=not issues, issues=issues, outcome=session.outcome,
        goal_completed=goal_completed,
        steps=len(session.steps), model_choices=policy.answered, failed_choices=policy.failed,
        fallbacks=session.fallbacks, survey=session.survey.model_dump(mode='json') if session.survey else None,
        order_total=session.order_total,
        actions=[{'page': step.page, 'action': step.choice.kind if step.choice else None,
                  'thought': step.thought, 'source': step.source} for step in session.steps])
except Exception as error:
    result['error'] = repr(error)
result['success'] = result['technical_success'] and bool(result.get('goal_completed', False))
result.update(calls=calls, attempted_calls=attempts, seconds=round(time.perf_counter()-started, 2), usage=client.get_usage().model_dump(mode='json'))
(root/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({'root': str(root), **result}, ensure_ascii=False, indent=2), flush=True)
raise SystemExit(0 if result['success'] else 1)
