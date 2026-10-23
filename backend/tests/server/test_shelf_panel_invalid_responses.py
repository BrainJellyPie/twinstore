"""A panel containing only invented choices must fail instead of claiming agreement."""

import pytest

from store_emulator.application import shelf_lab
from store_emulator.engine.simulation.engines.vlm_glance.prompt import ShelfGlance
from tests.engine.test_shelf_panel_invalid_responses import ScriptedVLM
from tests.server.test_shelf_lab_start_snapshot import CID, PID, lab
from tests.server.test_simulation_setup_races import layout


@pytest.mark.parametrize("condition", ["photo", "photo_raw"])
@pytest.mark.parametrize("invalid", [False, True])
def test_sim2real_requires_valid_complete_pairs(lab, monkeypatch, condition, invalid):
    client, submit, _, _ = lab
    reply = ShelfGlance(product="Unicorn battery", interest=10) if invalid else ShelfGlance()
    monkeypatch.setattr(shelf_lab, "LiteLLMClient", lambda config: ScriptedVLM([reply] * 2))
    response = client.post(f"/api/projects/{PID}/captures/{CID}/sim2real", json={"conditions": [condition]})
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    submit.call_args.args[0]()
    response = client.get(f"/api/projects/{PID}/captures/{CID}/lab/jobs/{job_id}")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"]["status"] == ("failed" if invalid else "completed")
    if invalid:
        assert result.get("sim2real") is None
    else:
        assert result["sim2real"]["agreement"][0]["same_pick"] == 1
        assert result["sim2real"]["agreement"][0]["pairs"] == 1
