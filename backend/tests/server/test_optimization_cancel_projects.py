"""Cancellation belongs to a project and job pair, not the short job ID alone."""
from store_emulator.application import optimize
from store_emulator.application.storage.io import write_json
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.optimize import OptimizeSpec
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import SimulationSummary
from store_emulator.engine.layout_gen import generate_store
from store_emulator.engine.optimize.evaluate import LayoutEvaluator


def test_same_job_id_in_another_project_keeps_running(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(optimize, '_cancel_requests', set())
    store = generate_store('mini_mart')
    panel = [Persona(id='p0',identity='Shopper',age_group='20s',gender='Female',description='Tea',intent='tea',purpose='tea')]
    statuses = {}
    for pid in ['proj_a','proj_b']:
        status=optimize.OptimizationStatus(job_id='opt_abcdef',setup_id='setup_test',status='pending',
                                           spec=OptimizeSpec(budget=1,eval_customers=10,validation_customers=0))
        statuses[pid]=status
        write_json(tmp_path / '.data' / pid / 'optimizations' / status.job_id / 'status.json',status.model_dump(mode='json'))

    async def evaluate(self, layout):
        return 100.0,SimulationSummary(store_id=layout.id,revenue_per_visitor=100)
    monkeypatch.setattr(LayoutEvaluator,'evaluate',evaluate)
    optimize.cancel_optimization('proj_a','opt_abcdef')
    optimize._run_job('proj_b',statuses['proj_b'],store,panel,SimulationConfig())
    assert optimize.get_optimization('proj_b','opt_abcdef').status.status=='completed'
    optimize._run_job('proj_a',statuses['proj_a'],store,panel,SimulationConfig())
    assert optimize.get_optimization('proj_a','opt_abcdef').status.status=='canceled'
