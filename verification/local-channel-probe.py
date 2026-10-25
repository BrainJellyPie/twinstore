"""Exercise a real CPU-model free offer through channel comparison.

Run from the repository root with PYTHONPATH=backend/src and the backend Python.
The companion probe calls the loopback model and saves raw inference artifacts.
A controlled physical purchase is executed by the production timeline builder at
that generated price; the 40 online sessions use the real rule policy. Storage
reads are isolated to this scratch fixture. No user project is modified.
"""

import argparse
import asyncio, json, subprocess, sys, time
from pathlib import Path
from unittest.mock import patch
from store_emulator.application import channels, interview, online
from store_emulator.domain.action import CustomerAction
from store_emulator.domain.online import OnlineRunRequest, OnlineRunResult, OnlineRunStatus, VisitBrief
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine.online.analysis import summarize
from store_emulator.engine.online.catalog import site_from_store
from store_emulator.engine.online.policies import RulePolicy
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers
from store_emulator.engine.routing.route_builder import JourneyStep
from store_emulator.engine.routing.timeline_builder import build_timeline
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('.data/local-model-probes'))
args = parser.parse_args()
root = args.output.resolve() / f'channels-{time.time_ns()}'
root.mkdir(parents=True)
with (root / 'model.log').open('w') as log:
    subprocess.run([sys.executable, str(Path(__file__).with_name('local-model-probe.py')), '--case', 'layout-full-discount', '--output', str(root)], stdout=log, stderr=subprocess.STDOUT, check=True)
model_dir = next(root.glob('layout-full-discount-*'))
store = Store.model_validate_json((model_dir / 'after.json').read_text())
assert store.racks[0].slots[0].items[0].price == 0
persona = Persona(id='person_a', identity='Resident', age_group='30s', gender='Female', description='Nearby resident', intent='buy groceries', purpose='Shopping', budget_max=10000)
action = CustomerAction(nav='path', action=Action.BUY, target=(3, 2), face=Face.N, product_sku='tea', product_level=1, quantity=1)
customer = build_timeline(persona.id, Weekday.MON, '12:00:00', [JourneyStep(action=action, path=[(3, 2)])], store)
assert customer.units_bought == 1 and customer.total_spent == 0
site = site_from_store(store, site_id='web_cpu', name='CPU store', currency='USD')
site.options.shipping_fee = 0
site.options.service_fee = 0
site.options.welcome_popup = 'none'
site.options.cookie_banner = False
site.options.guest_checkout = True
people = sample_shoppers(site, 40, seed=4, missions={'purchase': 0.75, 'browse': 0.25}, mobile_share=0.5, personas=[persona])

async def visit():
    return [await run_session(site, p, RulePolicy(), seed=4, max_steps=24, render=False) for p in people]
sessions = asyncio.run(visit())
by_id = {s.shopper_id: s for s in sessions}
assert any((s.outcome == 'purchased' for s in sessions)) and any((s.outcome != 'purchased' for s in sessions))
report = OnlineRunResult(run_id='orun_cpu', policy='rule', currency='USD', shoppers=people, variants=[summarize(site, {p.id: p for p in people}, sessions)], visits={s.shopper_id: [VisitBrief(outcome=s.outcome, order_total=s.order_total)] for s in sessions})
view = online.OnlineRunView(status=OnlineRunStatus(run_id=report.run_id, status='completed', site_ids=[site.id], request=OnlineRunRequest(site_ids=[site.id], source='project')), result=report)
data = root / 'data'
folder = data / 'proj_cpu' / 'runs' / 'run_cpu'
(folder / 'input').mkdir(parents=True)
(folder / 'output').mkdir()
(folder / 'status.json').write_text(json.dumps({'created_at': '2026-10-25'}))
(folder / 'input' / 'store.json').write_text(store.model_dump_json())
(folder / 'output' / 'timeline.json').write_text(json.dumps([customer.model_dump(mode='json')]))
(folder / 'output' / 'personas.json').write_text(json.dumps({persona.id: persona.model_dump(mode='json')}))
(folder / 'output' / 'summary.json').write_text(json.dumps({'currency': 'USD'}))
rows = []
with patch.object(channels, 'DATA_DIR', str(data)), patch.object(interview, 'DATA_DIR', str(data)), patch.object(channels, 'get_run', return_value=view):
    for buyers_first in [True, False]:
        report.shoppers = sorted(people, key=lambda p: by_id[p.id].outcome == 'purchased', reverse=buyers_first)
        mix = channels.channel_mix('proj_cpu', 'orun_cpu')
        assert mix is not None
        rows.append(mix.model_dump(mode='json'))
expected_spend = sum((s.order_total for s in sessions))
issues = []
if rows[0] != rows[1]:
    issues.append('Customer list ordering changes the channel comparison')
for mix in rows:
    if mix['both'] != 1 or mix['store_only'] or mix['online_only'] or mix['neither']:
        issues.append('A free physical purchase or an online purchase disappeared')
    if mix['online_spend'] != expected_spend:
        issues.append('Repeated customer visits lost online spending')
result = {'success': not issues, 'issues': list(dict.fromkeys(issues)), 'model_probe': str(model_dir), 'physical_units': customer.units_bought, 'physical_spent': customer.total_spent, 'visits': len(sessions), 'orders': sum((s.outcome == 'purchased' for s in sessions)), 'expected_online_spend': expected_spend, 'mixes': rows}
(root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
(root / 'online-run.json').write_text(report.model_dump_json(indent=2))
print(json.dumps({'root': str(root), **result}, ensure_ascii=False), flush=True)
sys.exit(0 if result['success'] else 1)
