"""JSON booleans must not become measurements, prices or product badges."""

import asyncio
import copy
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Face
from store_emulator.engine import llm_client
from store_emulator.engine.marketing import shelf_test, survey
from store_emulator.engine.shelf_lab.sim2real import TwinViews, glance_panel, summarize
from store_emulator.engine.simulation.engines.vlm_glance.prompt import ShelfGlance, shelf_glance_model
from store_emulator.engine.vision_inputs import _ReceiptLineVLM, _ReceiptVLM, _StorefrontRating, vlm_appeal, vlm_receipt
from tests.engine.test_shelf_panel_boundaries import person, shelf


CASES = ([('survey', f'{scale}_A') for scale in survey.SCALES]
         + [('price', key) for key in ('too_cheap', 'cheap', 'expensive', 'too_expensive')]
         + [('glance', key) for key in ('number', 'interest')]
         + [('shelf', key) for key in ('pick', 'noticed')]
         + [('storefront', key) for key in ('signage', 'entrance', 'window', 'upkeep', 'overall')]
         + [('receipt', key) for key in ('quantity', 'unit_price', 'line_total', 'total')])


@pytest.mark.parametrize('mode', ['json', 'json_schema'])
@pytest.mark.parametrize('kind,field', CASES)
@pytest.mark.parametrize('boolean', [False, True])
def test_boolean_responses_do_not_become_valid_results_or_cache_hits(monkeypatch, tmp_path, shelf,
                                                                    mode, kind, field, boolean):
    rack, view = shelf
    changed = rack.model_copy(update={'rack_name': 'Changed shelf'})
    number = int(boolean)
    if kind == 'survey':
        good = {f'{scale}_A': 3 for scale in survey.SCALES}
    elif kind == 'price':
        good = dict.fromkeys(('too_cheap', 'cheap', 'expensive', 'too_expensive'), number)
    elif kind == 'glance':
        good = {'number': number if field == 'number' else 1, 'product': 'Apple',
                'interest': number if field == 'interest' else 8}
    elif kind == 'shelf':
        good = {'pick': number if field == 'pick' else 1, 'noticed': [1]}
    elif kind == 'storefront':
        good = dict.fromkeys(('signage', 'entrance', 'window', 'upkeep', 'overall'), 8)
    else:
        good = {'currency': 'USD', 'total': 4.98,
                'lines': [{'name': 'Tea', 'quantity': 2, 'unit_price': 2.49, 'line_total': 4.98}]}
    bad = copy.deepcopy(good)
    if kind == 'receipt' and field != 'total':
        bad['lines'][0][field] = boolean
    else:
        bad[field] = [boolean] if field == 'noticed' else boolean
    payload, calls = bad, []
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={'id': 'offline', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps(payload)}}]})

    async def exercise():
        nonlocal payload
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key='offline', base_url='http://127.0.0.1:8081/v1', http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, 'client': adapter, 'api_key': 'offline', 'num_retries': 0})

            monkeypatch.setattr(llm_client.litellm, 'acompletion', completion)
            client = llm_client.LiteLLMClient(LLMConfig(model='openai/boolean-measurement',
                api_base='http://127.0.0.1:8081/v1', structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new('RGB', (2, 2)) as picture:
                async def run(valid):
                    if kind in ('survey', 'price'):
                        questions = list(survey.SCALES) if kind == 'survey' else ['price_vw']
                        rows = await survey.survey_panel(client, [person()], picture, questions, 1)
                        assert bool(rows[0].error) is not valid
                        if valid:
                            if kind == 'survey':
                                assert rows[0].appeal == rows[0].value == rows[0].purchase_intent == rows[0].uniqueness == [3]
                            else:
                                assert [getattr(rows[0], key) for key in good] == [number * 100] * 4
                        else:
                            assert rows[0].appeal == [] and rows[0].too_cheap is None
                        return [row.model_dump() for row in rows]
                    if kind == 'shelf':
                        rows = await shelf_test.shelf_panel(client, [person()], rack, changed, Face.N)
                        assert all(bool(row.error) is not valid for row in rows)
                        if valid:
                            expected = 'A' if good['pick'] else ''
                            assert all(row.pick_sku == expected and row.noticed == ['A'] for row in rows)
                        else:
                            assert shelf_test.compare_shelves(rows, 'A') == []
                            assert shelf_test.pick_shares(rows, {}) == []
                        return [row.model_dump() for row in rows]
                    if kind == 'glance':
                        views = TwinViews(rack, view.face, {'render': view}, {'A': 'Apple', 'B': 'Banana'})
                        rows = await glance_panel(client, views, [person()], conditions=['render'],
                            cue_sampler=lambda rng: BehaviorCue(), patterns=BEHAVIOR_PATTERNS)
                        stats, _ = summarize(rows, ['render'])
                        assert stats[0].answers == int(valid) and stats[0].errors == int(not valid)
                        if valid:
                            assert rows[0].sku == 'A' and rows[0].interest == good['interest']
                        return [row.model_dump() for row in rows]

                    async def read():
                        return await vlm_appeal(client, picture) if kind == 'storefront' else await vlm_receipt(
                            client, picture, receipt_id='r1')

                    if not valid:
                        with pytest.raises(InstructorRetryException):
                            await read()
                        return None
                    result = await read()
                    if kind == 'storefront':
                        assert result.overall == 8 and result.attractiveness == 1.24
                    else:
                        assert result.total == 498 and result.lines[0].quantity == 2
                        assert result.lines[0].unit_price == 249 and result.lines[0].line_total == 498
                    return result.model_dump()

                await run(False)
                assert not list(tmp_path.rglob('*.json'))
                payload = good
                expected = await run(True)
                before = len(calls)
                assert await run(True) == expected and len(calls) == before
                entries = list(tmp_path.rglob('*.json'))
                assert len(entries) == (2 if kind == 'shelf' else 1)
                for path in entries:
                    saved = json.loads(path.read_text())
                    saved['result'] = bad
                    path.write_text(json.dumps(saved))
                assert await run(True) == expected and len(calls) == before + len(entries)
                for path in entries:
                    saved = json.loads(path.read_text())['result']
                    measured = saved['lines'][0][field] if kind == 'receipt' and field != 'total' else saved[field]
                    assert not isinstance(measured, bool)
                    if isinstance(measured, list):
                        assert not any(isinstance(value, bool) for value in measured)

    asyncio.run(exercise())


@pytest.mark.parametrize('as_text', [False, True])
@pytest.mark.parametrize('number', [0, 1, 5])
def test_real_numbers_and_existing_numeric_text_conversion_remain_supported(shelf, as_text, number):
    _, view = shelf
    value = str(number) if as_text else number
    model = shelf_glance_model(view)
    assert model.model_validate({'product': 'Apple', 'number': '1' if as_text else 1, 'interest': value}).interest == number
    rating = _StorefrontRating.model_validate(dict.fromkeys(('signage', 'entrance', 'window', 'upkeep', 'overall'), value))
    assert rating.overall == number
    prices = survey.response_model(['price_vw'], 1)
    assert prices.model_validate(dict.fromkeys(('too_cheap', 'cheap', 'expensive', 'too_expensive'), value)).cheap == number
    if number:
        assert survey.response_model(['appeal'], 1).model_validate({'appeal_A': value}).appeal_A == number
    assert shelf_test.ShelfAnswer.model_validate({'pick': '1' if as_text else 1, 'noticed': ['1'] if as_text else [1]}).pick == 1
    assert _ReceiptLineVLM.model_validate({'name': 'Tea', 'quantity': value, 'line_total': value}).quantity == number
    assert _ReceiptVLM.model_validate({'total': value}).total == number


def test_unknown_receipt_amounts_and_internal_empty_glances_keep_defaults():
    assert ShelfGlance().interest == 0
    line = _ReceiptLineVLM.model_validate({'name': 'Unreadable', 'unit_price': None, 'line_total': None})
    assert line.quantity == 1 and line.unit_price is None and line.line_total is None
    assert _ReceiptVLM.model_validate({'total': None}).total is None
