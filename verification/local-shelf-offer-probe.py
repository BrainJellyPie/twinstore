"""Probe repeated shelf offers with the actual local CPU VLM and production prompts.

Run from the repository root with PYTHONPATH=backend/src and the backend Python.
Requires a loopback image-capable server on port 8081. The four cases mirror a
free KRW offer and a one-dollar USD offer against an identically named/SKU item.
--shuffle-seed changes badge assignment independently of the cheap offer's side.
This calls production glance prompts, grammar and resolution, not the full visit
or purchase executor. Matching the explicit request is a diagnostic check; a
valid JSON response does not establish correct price/location understanding.
The free cases pass zero *remaining* money explicitly; Persona.budget_max=0 by
itself means an unspecified trip limit. No user stores or model replies are edited.
"""
import argparse, asyncio, json, random, time, sys
from pathlib import Path
from unittest.mock import patch
import httpx
from pydantic import SecretStr
from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.types import Face
from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.persona import Persona
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.perception import render_face
from store_emulator.engine.simulation.engines.vlm_glance.prompt import shelf_glance_model, glance_system_prompt, user_prompt, resolve
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=Path('.data/local-model-probes'))
parser.add_argument('--shuffle-seed',type=int,default=7)
parser.add_argument('--structured-output',choices=['json_schema','json'],default='json_schema')
args=parser.parse_args()
root=args.output.resolve()/f'shelf-offers-{args.shuffle_seed}-{args.structured_output}-{time.time_ns()}'
root.mkdir(parents=True)
original=httpx.AsyncClient.send
calls=0
async def trace(self,request,*args,**kw):
    global calls
    calls+=1;start=time.perf_counter()
    response=await original(self,request,*args,**kw);await response.aread()
    body=json.loads(request.content)
    for message in body.get('messages',[]):
        if isinstance(message.get('content'),list):
            for part in message['content']:
                if part.get('type')=='image_url':part['image_url']['url']='saved shelf image'
    with (root/'http.jsonl').open('a') as f:
        f.write(json.dumps({'call':calls,'seconds':round(time.perf_counter()-start,2),'request':body,'response':response.json()},ensure_ascii=False)+'\n')
    return response
async def run():
    results=[]
    for case,currency,free_block,budget in [('free-left','KRW',0,0),('free-right','KRW',1,0),('discount-left','USD',0,100),('discount-right','USD',1,100)]:
        price=0 if currency=='KRW' else 100
        rack=Rack(id='offers',type='shelf',rack_name='Water',position=(3,1),shape=[[1,1]],slots=[
            Slot(block=block,face=Face.N,level=3,items=[SlotItem(sku='water',name='Mineral Water 500ml',price=price if block==free_block else 5000,regular_price=5000,promo=('FREE' if price==0 else 'SALE') if block==free_block else '')]) for block in range(2)])
        view=render_face(rack,Face.N,currency=currency,width=512,rng=random.Random(args.shuffle_seed))
        (root/f'{case}.png').write_bytes(view.png)
        shopper=Persona(id='resident',identity='Nearby resident',age_group='30s',gender='Female',description='A thirsty resident seeking the cheapest water.',intent='Choose the free water offer only.' if price==0 else 'Choose the one-dollar water offer only.',purpose='Buy one water bottle.',usual_products=['Mineral Water 500ml'],budget_min=budget,budget_max=budget,basket_size=1)
        prompt=user_prompt(shopper,BehaviorCue(state='목마름'),next(p for p in BEHAVIOR_PATTERNS if p.id=='purposeful'),view,basket=[],money_left=budget,currency=currency)
        client=LiteLLMClient(LLMConfig(model='openai/local-model',api_base='http://127.0.0.1:8081/v1',api_key=SecretStr('local'),temperature=0,seed=0,max_tokens=240,timeout_sec=180,max_parallel=1,chat_template_thinking=False,structured_output=args.structured_output,structured_sdk_retries=0,cache_dir=str(root/case)))
        start=time.perf_counter()
        try:
            answer=await client.generate_structured_with_image_async(shelf_glance_model(view),glance_system_prompt(),prompt,view.data_url(),seed=0,max_retries=1)
            hit,how=resolve(view,answer)
            r={'case':case,'reply':answer.model_dump(),'resolved_by':how,'selected_price':hit.item.price if hit else None,'expected_price':price,'intended_offer':hit is not None and hit.item.price==price,'visible':[{'mark':m.mark,'name':m.item.name,'price':m.item.price} for m in view.items]}
        except Exception as e:r={'case':case,'error':repr(e)}
        r['seconds']=round(time.perf_counter()-start,2);results.append(r)
        print(json.dumps({'root':str(root),**r},ensure_ascii=False),flush=True)
    (root/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    return results
with patch.object(httpx.AsyncClient,'send',trace):
    results=asyncio.run(run())
sys.exit(0 if all(row.get('intended_offer') for row in results) else 1)
