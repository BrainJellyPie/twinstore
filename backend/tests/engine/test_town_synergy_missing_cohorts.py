import asyncio
import json

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import AggregatedResult, FailedCustomer, RunDiagnostics, SimulationSummary
from store_emulator.domain.store import Store
from store_emulator.domain.town import TownArrival
from store_emulator.domain.types import Weekday
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.town import vlm_synergy
from tests.engine.test_reproducibility import _RecordingEngine
from tests.engine.test_vlm_synergy import SAMPLE, town


@pytest.fixture
def workflow(town, monkeypatch):
    store = Store.model_validate_json((SAMPLE / "store.json").read_text())
    person = Persona.model_validate(json.loads((SAMPLE / "personas.json").read_text())[0])

    def execute(mode="complete", affected=3, unaffected=3, customers=6, seed=5):
        ids = [f"a{i}" for i in range(affected)] + [f"u{i}" for i in range(unaffected)]
        people = [person.model_copy(update={"id": pid}) for pid in ids]
        arrivals = [TownArrival(persona_id=pid, source_persona_id=person.id, hour=10, segment="resident",
                               age_group=person.age_group, purpose="errand", distance_m=10, walk_min=0.2) for pid in ids]
        monkeypatch.setattr(vlm_synergy, "plan_arrivals", lambda *args, **kwargs: (people, arrivals))
        monkeypatch.setattr(vlm_synergy, "counterfactual_arrival", lambda arrival, *args, **kwargs: arrival)
        monkeypatch.setattr(vlm_synergy, "town_context_writer", lambda selected: lambda arrival:
                            ("with" if selected.get_venue("cafe-next-door") else "without")
                            if arrival.persona_id.startswith("a") else "same")
        calls = []

        async def run(_self, _store, panel, **kwargs):
            arm = len(calls)
            assert arm == 0 or mode not in {"all", "affected_with", "unaffected"}, "A second panel cannot repair missing first-arm evidence"
            calls.append([p.id for p in panel])
            keep = []
            failed = []
            for p in panel:
                is_affected = p.id.startswith("a")
                reject = (mode == "all" or mode == "affected_with" and is_affected and arm == 0
                          or mode == "affected_without" and arm == 1
                          or mode == "unaffected" and not is_affected
                          or mode == "disjoint" and is_affected and (int(p.id[1:]) % 2 == arm)
                          or mode == "partial" and p.id in {"a0", "u0"})
                if reject:
                    failed.append(FailedCustomer(persona_id=p.id, reason="offline failure"))
                else:
                    spend = 0 if mode == "no_purchases" else (200 if arm == 0 else 100) if is_affected else 1000
                    keep.append(CustomerResult(persona_id=p.id, day=Weekday.WED, arrival_time="10:00:00", total_spent=spend))
            if progress := kwargs.get("on_progress"):
                progress(len(keep), len(failed), len(panel))
            report = AggregatedResult(summary=SimulationSummary(store_id=store.id), pathcalc_heatmap=[], persona_heatmap=[],
                                      diagnostics=RunDiagnostics(requested_customers=len(panel), succeeded_customers=len(keep),
                                                                 failed_customers=failed))
            return report, keep

        monkeypatch.setattr(vlm_synergy.PerCustomerSimulationRunner, "run", run)
        return asyncio.run(vlm_synergy.vlm_basket_synergy(
            town, "cafe-next-door", store, [person], config=SimulationConfig(seed=seed), engine=_RecordingEngine(),
            pathfinder=AStarPathFinder(), cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS, customers=customers,
        ))

    return execute


@pytest.mark.parametrize("mode", ["all", "affected_with", "affected_without", "unaffected", "disjoint"])
@pytest.mark.parametrize("customers,seed", [(4, 0), (6, 5), (6, 19)])
def test_missing_required_cohort_cannot_be_reported_as_zero_or_borrowed_spend(workflow, mode, customers, seed):
    with pytest.raises(ValueError, match="(?i)(affected|unaffected).*completed"):
        workflow(mode, customers=customers, seed=seed)


@pytest.mark.parametrize("affected,unaffected,with_spend,without_spend", [(3, 3, 600, 550), (6, 0, 200, 100), (0, 6, 1000, 1000)])
def test_cohorts_not_present_in_the_population_need_no_results(workflow, affected, unaffected, with_spend, without_spend):
    result = workflow(affected=affected, unaffected=unaffected)
    assert result.spend_per_visitor_with == with_spend
    assert result.spend_per_visitor_without == without_spend
    assert result.failed_customers == 0


def test_partial_failures_preserve_population_weights_and_report_exclusions(workflow):
    result = workflow("partial")
    assert result.spend_per_visitor_with == 600 and result.spend_per_visitor_without == 550
    assert result.affected_comparison.paired_customers == 2
    assert result.failed_customers == 3
    assert any("failed" in note for note in result.notes)


def test_successful_zero_purchase_results_are_valid_evidence(workflow):
    result = workflow("no_purchases")
    assert result.spend_per_visitor_with == result.spend_per_visitor_without == result.delta_revenue_per_day == 0
    assert result.failed_customers == 0 and result.affected_comparison.paired_customers == 3


def test_positive_traffic_without_sampled_visitors_cannot_predict_zero_revenue(workflow):
    with pytest.raises(ValueError, match="(?i)no visitors.*sample"):
        workflow(affected=0, unaffected=0)
