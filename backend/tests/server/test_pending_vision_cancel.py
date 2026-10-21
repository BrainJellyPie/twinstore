"""A job canceled while queued must not initialize a model client."""
from unittest.mock import Mock
from store_emulator.application import optimize
from store_emulator.application.storage.io import write_json
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.optimize import JudgeSpec, OptimizeSpec
from store_emulator.domain.persona import Persona
from store_emulator.engine.layout_gen import generate_store


def test_pending_vision_cancellation_precedes_model_initialization(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(optimize,'_cancel_requests',set())
    pid,job='proj_test','opt_test'
    status=optimize.OptimizationStatus(job_id=job,setup_id='setup_test',status='pending',
        spec=OptimizeSpec(budget=1,eval_customers=10),judge=JudgeSpec(judge='vlm',calibrate=False))
    write_json(tmp_path/'.data'/pid/'optimizations'/job/'status.json',status.model_dump(mode='json'))
    client=Mock(side_effect=AssertionError('Model initialization should not run'))
    monkeypatch.setattr(optimize,'build_client',client)
    panel=[Persona(id='p0',identity='Shopper',age_group='20s',gender='Female',description='Tea',intent='tea',purpose='tea')]
    optimize.cancel_optimization(pid,job)
    optimize._run_job(pid,status,generate_store('mini_mart'),panel,SimulationConfig(),SimulationConfig())
    client.assert_not_called()
    view=optimize.get_optimization(pid,job)
    assert view.status.status=='canceled'
    assert view.result is None
