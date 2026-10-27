"""Run the real local VLM through receipt reading, matching, review and CSV export.

Synthetic, legible fixtures isolate transcription and money/quantity handling;
this is not evidence of accuracy on arbitrary photographed receipts. No model
responses are mocked. No user project or sales data is read or written.
"""
import argparse
import asyncio
import base64
import csv
import hashlib
import io
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

import httpx
from PIL import Image, ImageDraw, ImageFont
from pydantic import SecretStr

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.receipt_review import review_receipts
from store_emulator.engine.vision_inputs import match_lines, vlm_receipt

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case', choices=['simple', 'krw', 'fractional', 'free', 'date-only', 'foreign', 'no-purchase', 'subtotal-only'], default='simple')
parser.add_argument('--mode', choices=['json', 'json_schema'], default='json_schema')
parser.add_argument('--endpoint', default='http://127.0.0.1:8082/v1')
parser.add_argument('--output', type=Path, default=Path('.data/local-model-probes'))
args = parser.parse_args()
endpoint = urlsplit(args.endpoint)
if endpoint.hostname not in {'localhost', '127.0.0.1', '::1'} or endpoint.scheme != 'http':
    parser.error('Use an HTTP loopback endpoint for this probe.')
root = args.output.resolve() / f'receipt-{args.case}-{args.mode}-{time.time_ns()}'
root.mkdir(parents=True)
currency = 'KRW' if args.case == 'krw' else 'EUR' if args.case == 'foreign' else 'USD'
store_currency = 'USD' if args.case == 'foreign' else currency
names = {'tea': 'GREEN TEA', 'water': 'WATER', 'apple': 'APPLES'}
expected = [('tea', 2, 250, 500), ('water', 1, 100, 100)]
lines = ['GREEN TEA        2  2.50    5.00', 'WATER            1  1.00    1.00']
subtotal, tax, total, paid, change = '6.00', '0.60', '6.60', '10.00', '3.40'
expected_total = 660
if args.case == 'krw':
    lines = ['GREEN TEA        2  2500    5000', 'WATER            1  1000    1000']
    expected = [('tea', 2, 2500, 5000), ('water', 1, 1000, 1000)]
    subtotal, tax, total, paid, change, expected_total = '6000', '0', '6000', '10000', '4000', 6000
elif args.case == 'fractional':
    lines = ['APPLES         0.5  4.00    2.00', 'WATER            1  1.00    1.00']
    expected = [('apple', 0.5, 400, 200), ('water', 1, 100, 100)]
    subtotal, tax, total, paid, change, expected_total = '3.00', '0.00', '3.00', '5.00', '2.00', 300
elif args.case == 'free':
    lines = ['GREEN TEA        1  0.00    0.00', 'WATER            1  1.00    1.00']
    expected = [('tea', 1, 0, 0), ('water', 1, 100, 100)]
    subtotal, tax, total, paid, change, expected_total = '1.00', '0.00', '1.00', '5.00', '4.00', 100
texts = ['CORNER STORE', '2026-10-27' + ('' if args.case == 'date-only' else '  14:05'), f'CURRENCY {currency}',
         '------------------------------', 'ITEM           QTY  UNIT AMOUNT', *lines,
         '------------------------------', f'SUBTOTAL                 {subtotal:>6}', f'TAX                      {tax:>6}',
         f'TOTAL                    {total:>6}', f'CASH                     {paid:>6}', f'CHANGE                   {change:>6}']
if args.case == 'no-purchase':
    texts = texts[:3] + ['TRANSACTION CANCELLED', 'NO ITEMS PURCHASED', 'TOTAL                      0.00']
    expected, expected_total = [], 0
elif args.case == 'subtotal-only':
    texts = [line for line in texts if not line.startswith(('TOTAL ', 'CASH ', 'CHANGE '))]
    expected_total = None
image = Image.new('RGB', (512, 520), 'white')
draw = ImageDraw.Draw(image)
font = ImageFont.truetype('DejaVuSansMono.ttf', 24)
for i, line in enumerate(texts):
    draw.text((24, 20 + i * 36), line, font=font, fill='black')
image.save(root / 'image.png')
(root / 'expected.json').write_text(json.dumps(dict(lines=expected, total=expected_total, currency=currency, printed=texts), indent=2))
client = LiteLLMClient(LLMConfig(model='openai/local-model', api_base=args.endpoint, api_key=SecretStr('local-probe'),
    temperature=0, seed=0, max_tokens=6144, timeout_sec=180, max_parallel=1,
    chat_template_thinking=False, structured_output=args.mode, structured_sdk_retries=0, cache_dir=str(root / 'cache')))
original = httpx.AsyncClient.send
attempts = calls = 0

async def trace(self, request, *positional, **keywords):
    global attempts, calls
    local = request.url.host == endpoint.hostname
    started = time.monotonic()
    if local:
        attempts += 1
        attempt = attempts
        payload = json.loads(request.content)
        for m in payload.get('messages', []):
            if isinstance(m.get('content'), list):
                for index, part in enumerate(m['content']):
                    if part.get('type') == 'image_url':
                        url = part['image_url']['url']
                        if url.startswith('data:image/'):
                            kind, encoded = url.split(';base64,', 1)
                            path = root / f'request-{attempt}-image-{index}.{ "jpg" if kind.endswith("jpeg") else "png" }'
                            path.write_bytes(base64.b64decode(encoded))
                            part['image_url']['url'] = f'[saved as {path.name}]'
        with (root / 'requests.jsonl').open('a') as out:
            out.write(json.dumps(dict(attempt=attempt, request=payload), ensure_ascii=False) + '\n')
    response = await original(self, request, *positional, **keywords)
    if local:
        calls += 1
        with (root / 'http.jsonl').open('a') as out:
            out.write(json.dumps(dict(call=calls, attempt=attempt, seconds=round(time.monotonic()-started,3),
                status=response.status_code, request=payload, response=response.json()), ensure_ascii=False) + '\n')
        print(f'HTTP {calls}: {response.status_code}', flush=True)
    return response

async def run():
    started = time.monotonic()
    source = Path(vlm_receipt.__code__.co_filename).resolve()
    result = dict(case=args.case, mode=args.mode, currency=currency, store_currency=store_currency,
                  source_path=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    try:
        reading = await vlm_receipt(client, image, receipt_id='fixture', default_currency=store_currency)
        matched = match_lines(reading, names)
        review = review_receipts([matched], names, store_currency)
        observed = [(line.sku, line.quantity, line.unit_price, line.line_total) for line in matched.lines]
        issues = []
        if observed != expected:
            issues.append('Purchased products, quantities or money fields differ from the printed fixture.')
        if reading.total != expected_total or reading.currency != currency:
            issues.append('Printed receipt total or currency differs from the fixture.')
        if args.case == 'date-only':
            if reading.timestamp != '2026-10-27':
                issues.append('Missing transaction time was invented or the printed date changed.')
        else:
            try:
                if datetime.fromisoformat(reading.timestamp) != datetime(2026, 10, 27, 14, 5):
                    issues.append('Printed date/time changed.')
            except ValueError:
                issues.append('Printed date/time could not be parsed.')
        expected_ready = args.case not in {'date-only', 'foreign', 'no-purchase'}
        if review.ready != expected_ready:
            issues.append('Review readiness does not match the known currency/time conditions.')
        if review.ready:
            exported = list(csv.DictReader(io.StringIO(review.csv)))
            if len(exported) != len(expected) or sum(float(row['line_total']) for row in exported) != sum(row[3] for row in expected):
                issues.append('CSV changed purchased amounts or included tax/payment lines.')
        result.update(success=not issues, issues=issues, expected=expected, observed=observed,
            reading=reading.model_dump(mode='json'), review=review.model_dump(mode='json'))
    except Exception as exc:
        result.update(success=False, error=repr(exc))
    result.update(seconds=round(time.monotonic()-started,2), calls=calls, attempts=attempts, usage=client.get_usage().model_dump())
    (root / 'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(dict(path=str(root), **result), ensure_ascii=False, indent=2), flush=True)
    return result['success']

with patch.object(httpx.AsyncClient, 'send', trace):
    success = asyncio.run(run())
raise SystemExit(0 if success else 1)
