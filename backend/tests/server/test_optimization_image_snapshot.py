"""Vision layout judging compares candidates against the same accepted artwork."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import optimize
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.optimize import OptimizeResult
from store_emulator.domain.rack import SlotItem
from store_emulator.server.main import app
from tests.server.test_simulation_image_snapshot import art, pixels
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.fixture
def judging(layout, monkeypatch):
    monkeypatch.setattr(optimize, "ensure_resolvable", lambda config: None)
    monkeypatch.setattr(optimize, "build_client", lambda *args: object())
    submit = Mock()
    monkeypatch.setattr(optimize.executor, "submit", submit)
    return TestClient(app, raise_server_exceptions=False), submit


def start(client, judge="vlm"):
    return client.post(f"/api/projects/{PID}/setups/{SID}/optimize", json={
        "judge": judge, "calibrate": False, "top_k": 1, "vlm_customers": 4,
        "spec": {"budget": 1, "eval_customers": 10, "validation_customers": 0},
    })


@pytest.mark.parametrize("source", ["package", "sku", "added"])
@pytest.mark.parametrize("when", ["queued", "judging"])
def test_judge_uses_accepted_art(judging, monkeypatch, source, when):
    client, submit = judging
    target, expected, mutate = art(source)
    seen = []

    async def judge(store, spec, judge_spec, **kwargs):
        loader = kwargs["vlm_engine"]._image_loader
        loader(SlotItem(sku="another_shelf", name="Other", price=100))
        if when == "judging":
            mutate()
        accepted = next(i for r in store.racks for s in r.slots for i in s.items if i.sku == target.sku)
        seen.append(pixels(loader(accepted)))
        return OptimizeResult(spec=spec, baseline_score=0, best_score=0, relative_improvement=0,
                              best_store=store, applied_moves=[], history=[], evaluations=1, seconds=0)

    monkeypatch.setattr(optimize, "judge_layout_search", judge)
    response = start(client)
    assert response.status_code == 200, response.text
    if when == "queued":
        mutate()
    job, *args = submit.call_args.args
    job(*args, **submit.call_args.kwargs)
    view = optimize.get_optimization(PID, response.json()["job_id"])
    assert view.status.status == "completed", view.status.error
    assert seen == [expected]


@pytest.mark.parametrize("judge", ["rule", "vlm"])
def test_copy_failure_cleans_vision_job_and_rule_search_never_copies(judging, monkeypatch, judge):
    client, submit = judging
    art("sku")
    save = Image.Image.save

    def fail(self, path, *args, **kwargs):
        if "/optimizations/" in str(path) and "/images/" in str(path):
            raise OSError("snapshot disk full")
        return save(self, path, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "save", fail)
    response = start(client, judge)
    root = metadata_path(PID).parent / "optimizations"
    if judge == "vlm":
        assert response.status_code == 500
        submit.assert_not_called()
        assert not list(root.glob("*"))
    else:
        assert response.status_code == 200, response.text
        assert not list(root.glob("*/images"))
