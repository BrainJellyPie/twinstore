"""Display aliases do not identify the models behind an ensemble's past work."""

from pathlib import Path
from shutil import copytree

import pytest

from store_emulator.application import run_estimate
from store_emulator.application.simulation import RunOptions
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.runs import build_manifest
from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.providers import EnsembleConfig, EnsembleMember
from store_emulator.domain.store import Store


@pytest.fixture(params=[EngineType.PATTERN_INTENT_IMPULSE, EngineType.VLM_GLANCE])
def history(request, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = Store(id="s", name="Shop", type="Convenience store", grid_size=(5, 5))
    people = [Persona(id=f"p{i}", identity="Visitor", age_group="20s", gender="Female",
                      description="", intent="", purpose="snack") for i in range(100)]
    monkeypatch.setattr(run_estimate, "_inputs", lambda *args: (store, people))
    monkeypatch.setattr(run_estimate, "resolve_model", lambda ref, **kwargs: LLMConfig(model=ref))
    monkeypatch.setattr(run_estimate, "cost_usd", lambda model, prompt, completion: (prompt + completion) / 1000)
    ensemble = EnsembleConfig(members=[EnsembleMember(model="first-model", label="Shopper A", weight=1.0000001),
                                       EnsembleMember(model="second-model", label="Shopper B")])
    config = SimulationConfig(engine_type=request.param, ensemble=ensemble)
    folder = Path(".data/project/runs/prior")

    def estimate():
        return run_estimate.estimate_run("project", "s", RunOptions(), config)

    baseline = estimate()
    write_json(folder / "status.json", {"status": "completed", "completed_customers": 100,
        "started_at": "2026-10-23T09:00:00+00:00", "finished_at": "2026-10-23T09:00:06+00:00"})
    write_json(folder / "output/manifest.json", build_manifest(store, people, config).model_dump(mode="json"))
    write_json(folder / "output/token_usage.json", {"requests": 100, "prompt_tokens": 1000,
                                                    "completion_tokens": 1000, "cached_requests": 0})
    return estimate, baseline, folder, config


@pytest.mark.parametrize("change", ["one_model", "both_models", "rounded_weight"])
def test_aliases_and_rounded_weight_labels_cannot_reuse_different_model_work(history, change):
    estimate, baseline, folder, config = history
    previous = config.model_copy(deep=True)
    if change == "one_model":
        previous.ensemble.members[0].model = "old-first-model"
    elif change == "both_models":
        for member in previous.ensemble.members:
            member.model = "old-" + member.model
    else:
        previous.ensemble.members[0].weight = 1.0000002
    assert run_estimate._model_label(previous) == run_estimate._model_label(config)
    write_json(folder / "input/config.json", previous.model_dump(mode="json"))
    assert estimate() == baseline


@pytest.mark.parametrize("saved", [None, {}, [], {"ensemble": None}, {"ensemble": {"members": []}},
                                    {"ensemble": {"members": [{"model": "first-model", "weight": "invalid"}]}}])
def test_history_without_readable_ensemble_identity_uses_engine_defaults(history, saved):
    estimate, baseline, folder, _ = history
    if saved is not None:
        write_json(folder / "input/config.json", saved)
    assert estimate() == baseline


def test_same_ensemble_still_reuses_its_recorded_work(history):
    estimate, baseline, folder, config = history
    write_json(folder / "input/config.json", config.model_dump(mode="json"))
    result = estimate()
    assert result != baseline
    assert result.model_calls == 100 and result.cost_usd == 2 and result.minutes == .1


def test_newer_incompatible_ensemble_does_not_hide_an_older_matching_measurement(history):
    estimate, _, folder, config = history
    write_json(folder / "input/config.json", config.model_dump(mode="json"))
    expected = estimate()
    older = folder.with_name("older")
    copytree(folder, older)
    write_json(older / "status.json", {"status": "completed", "completed_customers": 100,
        "started_at": "2026-10-22T09:00:00+00:00", "finished_at": "2026-10-22T09:00:06+00:00"})
    previous = config.model_copy(deep=True)
    previous.ensemble.members[0].model = "old-first-model"
    write_json(folder / "input/config.json", previous.model_dump(mode="json"))
    write_json(folder / "output/token_usage.json", {"requests": 900, "prompt_tokens": 9000,
                                                    "completion_tokens": 9000, "cached_requests": 0})
    assert estimate() == expected
