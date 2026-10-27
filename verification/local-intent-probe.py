"""Run production intent generation on a real local model, then resolve its purchases.

This exercises the intent stage only: it does not run pattern selection, impulse
planning, checkout, or a full simulation. Every run uses a fresh response cache
and saves actual HTTP bodies. No model replies or purchase choices are mocked.
"""
import argparse
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from store_emulator.domain.behavior import BehaviorPattern
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent as stage
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import drop_invalid_buys

p=argparse.ArgumentParser();p.add_argument('--case',choices=['one','browse','missing','free'],default='one');p.add_argument('--mode',choices=['json','json_schema'],default='json');p.add_argument('--endpoint',default='http://127.0.0.1:8082/v1');p.add_argument('--output',type=Path,default=Path('.data/local-model-probes'));args=p.parse_args()
endpoint=urlsplit(args.endpoint)
if endpoint.scheme!='http' or endpoint.hostname not in {'localhost','127.0.0.1','::1'}:p.error('Use an HTTP loopback endpoint for the local model.')
root=args.output.resolve()/f'{args.case}-{args.mode}-{time.time_ns()}';root.mkdir(parents=True)
price=0 if args.case=='free' else 250
store=Store(id='intent-probe',name='Tea shop',type='convenience',grid_size=(8,8),racks=[
    Rack(id='entrance',type='entrance',position=(0,0),shape=[[1]]),
    Rack(id='exit',type='exit',position=(7,0),shape=[[1]]),
    Rack(id='counter',type='counter',position=(6,2),shape=[[1]]),
    Rack(id='drinks',type='shelf',rack_name='Drinks',position=(2,2),shape=[[1]],slots=[
        Slot(block=0,face=Face.N,level=3,items=[SlotItem(sku='green-tea',name='Green Tea',price=price),SlotItem(sku='cola',name='Cola',price=700)])])])
intent={'one':'Buy exactly one Green Tea for $2.50. Do not buy Cola or any other item.',
        'free':'Take exactly one free Green Tea. Do not buy paid items.',
        'browse':'Only look around. No purchases or checkout today.',
        'missing':'Buy a laptop only. If no laptop is sold here, leave without buying anything.'}[args.case]
person=Persona(id='visitor',identity='resident',age_group='30s',gender='Female',description='A neighborhood resident.',purpose=intent,intent=intent,budget_min=0,budget_max=250,basket_size=1)
pattern=BehaviorPattern(id='visit',name='Visit',description=intent,grammar='enter -> browse -> optional buy -> optional pay -> exit',browse_required_before_buy=True,max_products=1,allow_no_purchase=True)
records=stage.catalog_records(store);schema=stage.catalog_response_model(stage.IntentResponse,records,max_quantity=1)
client=LiteLLMClient(LLMConfig(model='openai/local-model',api_base=args.endpoint,api_key=SecretStr('local'),temperature=0,max_tokens=3000,structured_output=args.mode,cache_dir=str(root/'cache')))
send=httpx.AsyncClient.send
async def traced(self,request,*a,**kw):
    body=json.loads(request.content);started=time.monotonic()
    with (root/'requests.jsonl').open('a') as f:f.write(json.dumps(body,ensure_ascii=False)+'\n')
    r=await send(self,request,*a,**kw);await r.aread()
    with (root/'http.jsonl').open('a') as f:f.write(json.dumps({'request':body,'response':r.json(),'seconds':time.monotonic()-started},ensure_ascii=False)+'\n')
    print('HTTP',r.status_code,round(time.monotonic()-started,2),flush=True);return r
async def run():
    started=time.monotonic();row={'case':args.case,'mode':args.mode,'temperature':0,'source_stage':'intent_only_then_offer_resolution'}
    try:
        result=await client.generate_structured_async(schema,stage.build_system_prompt(store,records=records,max_quantity=1),stage.build_user_prompt(person,9,1,pattern=pattern),max_retries=2)
        decoded=stage.decode_catalog_response(stage.IntentResponse,result,records,store,pathfinder=AStarPathFinder())
        actions,dropped=drop_invalid_buys(decoded.actions,store)
        purchases=[(a.product_sku,a.quantity) for a in actions if a.action==Action.BUY]
        expected=[('green-tea',1)] if args.case in {'one','free'} else []
        row.update(success=purchases==expected and dropped==0 and any(a.nav=='leave' for a in actions),purchases=purchases,expected=expected,dropped=dropped,result=result.model_dump(mode='json'),decoded=decoded.model_dump(mode='json'))
    except Exception as e:row.update(success=False,error=repr(e))
    row['seconds']=round(time.monotonic()-started,2);row['usage']=client.get_usage().model_dump()
    (root/'result.json').write_text(json.dumps(row,indent=2,ensure_ascii=False));print(json.dumps({'path':str(root),**row},ensure_ascii=False),flush=True)
with patch.object(httpx.AsyncClient,'send',traced):asyncio.run(run())
