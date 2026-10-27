"""Exercise production concept-test drafting on a real CPU model and compare requested fields.

This drafts from a fixture image catalog; it does not perform a vision read or
run a respondent survey. No model responses are mocked.
"""
import argparse
import asyncio
import hashlib
import ipaddress
import json
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.survey_design import design_survey

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case', choices=['price-usd', 'price-krw', 'free', 'unknown-price', 'unrestricted', 'male-thirties', 'ambiguous-offers', 'explicit-over-offers'], default='price-usd')
parser.add_argument('--mode', choices=['json_schema', 'json'], default='json_schema')
parser.add_argument('--endpoint', default='http://127.0.0.1:8081/v1')
parser.add_argument('--output', type=Path, default=Path('.data/local-model-probes'))
args = parser.parse_args()
endpoint = urlsplit(args.endpoint)
try:
    local = endpoint.hostname in {'localhost', 'localhost.'} or bool(endpoint.hostname and ipaddress.ip_address(endpoint.hostname).is_loopback)
except ValueError:
    local = False
if not local or endpoint.scheme != 'http':
    parser.error('Use an HTTP loopback endpoint for this CPU probe.')
currency = 'KRW' if args.case == 'price-krw' else 'USD'
expected_price = {'price-usd': 250, 'price-krw': 2500, 'free': 0, 'unknown-price': None,
    'unrestricted': None, 'male-thirties': 250, 'ambiguous-offers': None, 'explicit-over-offers': 250}[args.case]
price_instruction = {
    'price-usd': 'Show Tea Classic at $2.50.',
    'price-krw': 'Tea Classic의 판매가는 2,500원으로 보여 주세요.',
    'free': 'Show Tea Classic as FREE, with a zero shelf price.',
    'unknown-price': 'No shelf price has been supplied. Leave its price unknown; do not estimate it.',
    'unrestricted': 'No shelf price has been supplied. Leave its price unknown; do not estimate it.',
    'male-thirties': 'Show Tea Classic at $2.50.',
    'ambiguous-offers': 'Tea Classic has multiple shelf offers. No offer has been selected; leave its price unknown rather than choosing either offer.',
    'explicit-over-offers': 'Show Tea Classic at $2.50, overriding any listed shelf offers.',
}[args.case]
question = ('Compare Tea Classic (image A) with Tea New (image B). ' + price_instruction +
    ' Recruit only women in their twenties. Ask exactly purchase intention, value for money, preference between the two packs, and an open explanation. Do not ask other questions.')
if args.case == 'price-krw':
    question = ('Tea Classic을 A, Tea New를 B로 비교해 주세요. ' + price_instruction +
        ' 20대 여성만 대상으로 구매 의향, 가격 대비 가치, 두 포장 중 선호, 자유 응답 이유의 네 가지만 질문해 주세요.')
expected_ages, expected_genders = ['20s'], ['Female']
if args.case == 'unrestricted':
    question = question.replace('Recruit only women in their twenties.', 'Recruit everyone, without any age or gender restriction.')
    expected_ages, expected_genders = [], []
elif args.case == 'male-thirties':
    question = question.replace('Recruit only women in their twenties.', 'Recruit only men in their thirties.')
    expected_ages, expected_genders = ['30s'], ['Male']
packages = [('Tea Classic', 'pkg_classic', 'House', 'Green tea, original pack'),
            ('Tea New', 'pkg_new', 'House', 'Green tea, proposed pack')]
if args.case in {'ambiguous-offers', 'explicit-over-offers'}:
    packages[0] = ('Tea Classic', 'pkg_classic', 'House', 'Tea at $2.00 on Drinks; Tea at $3.00 on Endcap')
original = list(packages)
output = args.output.resolve() / f'survey-{args.case}-{args.mode}-{time.time_ns()}'
output.mkdir(parents=True)
source = Path(design_survey.__code__.co_filename)
result = dict(case=args.case, mode=args.mode, endpoint=args.endpoint, currency=currency,
    question=question, expected_price=expected_price, expected_ages=expected_ages, expected_genders=expected_genders,
    source_path=str(source.resolve()),
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), success=False)
# Match application.study_design.design_concept's temperature and output budget.
client = LiteLLMClient(LLMConfig(model='openai/local-model', api_base=args.endpoint,
    api_key=SecretStr('local-probe'), temperature=.2, seed=0, max_tokens=1200,
    timeout_sec=180, max_parallel=1, chat_template_thinking=False, structured_output=args.mode,
    structured_sdk_retries=0, cache_dir=str(output / 'cache')))
send = httpx.AsyncClient.send
calls = attempts = 0


async def traced_send(self, request, *positional, **keywords):
    global calls, attempts
    if request.url.host != endpoint.hostname:
        return await send(self, request, *positional, **keywords)
    attempts += 1
    with (output / 'requests.jsonl').open('a') as trace:
        trace.write(json.dumps(dict(attempt=attempts, request=json.loads(request.content)), ensure_ascii=False) + '\n')
    began = time.perf_counter()
    response = await send(self, request, *positional, **keywords)
    await response.aread()
    calls += 1
    elapsed = round(time.perf_counter() - began, 3)
    with (output / 'http.jsonl').open('a') as trace:
        trace.write(json.dumps(dict(call=calls, status=response.status_code, seconds=elapsed, response=response.json()), ensure_ascii=False) + '\n')
    print(f'Call {calls}: HTTP {response.status_code}, {elapsed}s', flush=True)
    return response


started = time.perf_counter()
try:
    with patch.object(httpx.AsyncClient, 'send', traced_send):
        draft = asyncio.run(design_survey(client, question, currency, packages))
    issues = []
    checks = {
        'image identities and order': draft.stimuli == ['pkg_classic', 'pkg_new'],
        'reference price': draft.reference_price == expected_price,
        'currency': draft.currency == currency,
        'requested question set': set(draft.questions) == {'purchase_intent', 'value', 'preference', 'open'},
        'age quota': draft.age_groups == expected_ages,
        'gender quota': draft.genders == expected_genders,
        'source catalog': packages == original,
        'warnings': not draft.warnings,
    }
    issues = [name for name, passed in checks.items() if not passed]
    result.update(success=not issues, issues=issues, draft=draft.model_dump(mode='json'))
except Exception as error:
    result['error'] = repr(error)
result.update(seconds=round(time.perf_counter() - started, 2), calls=calls, attempted_calls=attempts,
              usage=client.get_usage().model_dump(mode='json'))
(output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(dict(output=str(output), **{k: result[k] for k in ['success', 'seconds', 'calls', 'usage']})), flush=True)
raise SystemExit(0 if result['success'] else 1)
