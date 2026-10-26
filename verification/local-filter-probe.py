"""Run shopper-search requests through a real loopback model and check their meaning.

Use PYTHONPATH=backend/src backend/.venv/bin/python from the repository root.
The fixture has seven complete personas, free and paid purchases, nonbuyers,
and second-level arrival boundaries. No model response is mocked. Saved HTTP
bodies omit headers; matching IDs and applied criteria are checked separately
so an empty result for the wrong reasons does not pass. This is a text task
for the local VLM, not a vision or real-shopper quality evaluation.
"""
import argparse,asyncio,json,time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
import httpx
from pydantic import SecretStr
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.customer import CustomerResult,TimelineEvent
from store_emulator.domain.persona import Persona
from store_emulator.domain.rack import Rack,Slot,SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.shopper_filter import find_shoppers
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--mode',choices=['json_schema','json'],default='json_schema')
p.add_argument('--case',choices=['shelf-only','nothing','free','precision','missing','known','excluded'],required=True)
p.add_argument('--output',type=Path,default=Path('.data/local-model-probes'))
p.add_argument('--endpoint',default='http://127.0.0.1:8082/v1')
args=p.parse_args()
endpoint=urlsplit(args.endpoint)
if endpoint.scheme!='http' or endpoint.hostname not in {'localhost','127.0.0.1','::1'}:
 p.error('Use an HTTP loopback endpoint for the local model.')
root=args.output/f'{args.case}-{args.mode}-{time.time_ns()}';root.mkdir(parents=True)
store=Store(id='filter_cpu',name='Corner shop',type='convenience',grid_size=(8,8),racks=[Rack(id=rid,type='shelf',shape=[[1]],position=(x,1),rack_name=name,slots=[Slot(block=0,face='E',items=[SlotItem(sku=rid,name=product,price=price)])]) for rid,x,name,product,price in [('tea',1,'Tea shelf','Green Tea 500ml',250),('snacks',3,'Snack shelf','Salted Crackers',100)]])
rows=[('empty',True,[],0,'15:00:00'),('elsewhere',True,['snacks'],100,'15:00:29'),('free_elsewhere',True,['snacks'],0,'15:00:30'),('there',True,['tea'],250,'15:00:31'),('both',True,['tea','snacks'],350,'16:00:00'),('away_empty',False,[],0,'14:59:59'),('away_buyer',False,['snacks'],100,'16:01:00')]
customers={}
for pid,stopped,purchases,spent,arrival in rows:
 events=[TimelineEvent(elapsed_sec=0,x=1,y=1,action=Action.BROWSE,target_rack='tea')] if stopped else []
 events += [TimelineEvent(elapsed_sec=10+i,x=1,y=1,action=Action.BUY,target_rack=rid,product_sku=rid,price=spent if len(purchases)==1 else 250 if rid=='tea' else 100) for i,rid in enumerate(purchases)]
 customers[pid]=CustomerResult(persona_id=pid,day=1,arrival_time=arrival,total_spent=spent,timeline=events)
cases={
 'shelf-only':('Find shoppers who stopped at the Tea shelf but bought nothing from that shelf. They may have purchased other products elsewhere.',{'empty','elsewhere','free_elsewhere'}),
 'nothing':('Find shoppers who bought nothing at all, even if they visited shelves.',{'empty','away_empty'}),
 'free':('Find shoppers who purchased at least one item but spent exactly 0 USD in total.',{'free_elsewhere'}),
 'precision':('Find shoppers who arrived at or after 15:00:30 and before 16:00. Apply these exact arrival times only.',{'free_elsewhere','there'}),
 'missing':('Find shoppers who bought Moonberry Soda. This product is not listed in this store.',set()),
 'known':('Find shoppers who bought Green Tea 500ml.',{'there','both'}),
 'excluded':('Find shoppers who did not buy Green Tea 500ml, whether or not they bought something else.',{'empty','elsewhere','free_elsewhere','away_empty','away_buyer'}),
}
query,expected=cases[args.case]
personas={pid:Persona(id=pid,identity='Nearby resident',age_group='30s',gender='Female',description='Lives next to the shop.',intent='Look around the shop',purpose='Personal errand',preferred_categories=[],usual_products=[],budget_min=0,budget_max=1000,basket_size=2) for pid in customers}
(root/'personas.json').write_text(json.dumps({k:v.model_dump(mode='json') for k,v in personas.items()},indent=2))
(root/'store.json').write_text(store.model_dump_json(indent=2));(root/'customers.json').write_text(json.dumps({k:v.model_dump(mode='json') for k,v in customers.items()},indent=2))
client=LiteLLMClient(LLMConfig(model='openai/local-model',api_base=args.endpoint,api_key=SecretStr('local'),temperature=0,seed=0,max_tokens=900,timeout_sec=180,max_parallel=1,chat_template_thinking=False,structured_output=args.mode,structured_sdk_retries=0,cache_dir=str(root/'cache')))
send=httpx.AsyncClient.send;calls=0
async def trace(self,request,*a,**kw):
 global calls
 started=time.monotonic();calls+=1
 response=await send(self,request,*a,**kw);await response.aread()
 with (root/'http.jsonl').open('a') as f:f.write(json.dumps({'request':json.loads(request.content),'response':response.json(),'seconds':round(time.monotonic()-started,2)})+'\n')
 return response
started=time.monotonic()
try:
 with patch.object(httpx.AsyncClient,'send',trace): result=asyncio.run(find_shoppers(client,query,customers,personas,store,'USD'))
 required={
  'shelf-only':{'Stopped at Tea shelf','Bought nothing at Tea shelf'},
  'nothing':{'Bought nothing'},
  'free':{'Bought something','Spent at most $0.00'},
  'precision':{'Arrived at or after 15:00:30','Arrived before 16:00'},
  'missing':{'Bought Moonberry Soda'},
  'known':{'Bought Green Tea 500ml'},
  'excluded':{'Did not buy Green Tea 500ml'},
 }[args.case]
 optional={'free':{'Spent at least $0.00'},'known':{'Bought something'}}.get(args.case,set())
 criteria=set(result.criteria)
 issues=[]
 if set(result.persona_ids)!=expected: issues.append('Matched customer IDs do not equal the requested group')
 if required-criteria: issues.append('Missing requested criteria: '+repr(sorted(required-criteria)))
 if criteria-required-optional: issues.append('Unrequested criteria: '+repr(sorted(criteria-required-optional)))
 outcome={'completed':True,'success':not issues,'issues':issues,'matched_ids_correct':set(result.persona_ids)==expected,'result':result.model_dump(mode='json')}
except Exception as e:outcome={'completed':False,'success':False,'error':repr(e)}
outcome.update(endpoint=args.endpoint,persona_count=len(personas),root=str(root),case=args.case,mode=args.mode,query=query,expected=sorted(expected),temperature=0,calls=calls,seconds=round(time.monotonic()-started,2),usage=client.get_usage().model_dump(mode='json'))
(root/'result.json').write_text(json.dumps(outcome,indent=2));print(json.dumps(outcome),flush=True)

raise SystemExit(0 if outcome["success"] else 1)
