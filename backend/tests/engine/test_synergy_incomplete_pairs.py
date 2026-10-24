"""Identical shopper outcomes cannot become a basket effect when one arm fails."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.town import TownSpec, VenueCategory
from store_emulator.domain.types import Action, TokenUsage, stable_seed
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner
from store_emulator.engine.simulation.engines.rule_based import RuleBasedEngine
from store_emulator.engine.town import generate_town, place_venue
from store_emulator.engine.town.vlm_synergy import vlm_basket_synergy
from tests.engine.test_reproducibility import _RecordingEngine
from tests.engine.test_vlm_synergy import SAMPLE


@pytest.mark.parametrize('seed', range(5))
@pytest.mark.parametrize('failed_arm', ['none', 'one-with', 'one-without', 'all-with', 'all-without', 'different-in-each'])
@pytest.mark.parametrize('basket_change', [0, 50])
def test_basket_effects_use_only_complete_pairs(monkeypatch, seed, failed_arm, basket_change):
    town = generate_town(TownSpec(seed=4, size_m=400, n_competitors=1, venue_density=0.0))
    focal = town.get_venue(town.focal_venue_id)
    town = place_venue(town, VenueCategory.CAFE, focal.x + 12, focal.y, venue_id='cafe-next-door', name='Corner Cafe')
    store = Store.model_validate(json.loads((SAMPLE / 'store.json').read_text()))
    pool = [Persona.model_validate(p) for p in json.loads((SAMPLE / 'personas.json').read_text())][:300]
    calls = []
    requested = []
    rejected = []

    async def run(_self, _store, personas, **kwargs):
        arm = len(calls)
        results = []
        failed = []
        requested.append({person.id for person in personas})
        for i, person in enumerate(personas):
            reject = (
                (failed_arm == 'one-with' and arm == 0 and i == 0)
                or (failed_arm == 'one-without' and arm == 1 and i == 0)
                or (failed_arm == 'all-with' and arm == 0)
                or (failed_arm == 'all-without' and arm == 1)
                or (failed_arm == 'different-in-each' and i == arm)
            )
            if reject:
                failed.append(person.id)
                continue
            spend = 100 * (1 + stable_seed(person.id) % 11) + (basket_change if arm == 0 else 0)
            results.append(CustomerResult(persona_id=person.id, day=person.day, arrival_time='12:00:00', total_spent=spend,
                timeline=[TimelineEvent(elapsed_sec=1, x=0, y=0, action=Action.BUY, price=spend, target_rack=store.racks[0].id)]))
        calls.append({r.persona_id: r for r in results})
        rejected.extend(failed)
        return SimpleNamespace(token_usage=TokenUsage(), diagnostics=SimpleNamespace(failed_customers=failed)), results

    monkeypatch.setattr(PerCustomerSimulationRunner, 'run', run)
    study = vlm_basket_synergy(town, 'cafe-next-door', store, pool, config=SimulationConfig(seed=seed),
        engine=_RecordingEngine(), pathfinder=AStarPathFinder(), cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS, customers=12)
    if failed_arm in ('all-with', 'all-without'):
        with pytest.raises(ValueError, match='No affected visitors completed'):
            asyncio.run(study)
        assert len(calls) == (1 if failed_arm == 'all-with' else 2)
        return
    result = asyncio.run(study)
    assert len(calls) == 2 and result.failed_customers == len(rejected)
    paired = set(calls[0]) & set(calls[1]) & requested[1]
    expected_change = basket_change if paired else 0
    assert result.delta_spend_per_visitor == pytest.approx(result.affected_share * expected_change, abs=0.003)
    assert result.delta_conversion == 0
    assert all(shift.spend_diff == expected_change for shift in result.category_shifts)
    if basket_change == 0 or not paired:
        assert result.delta_revenue_from_baskets == 0
    if paired:
        assert result.affected_comparison.paired_customers == len(paired)
        spend_metric = next(m for m in result.affected_comparison.metrics if m.metric == 'spend')
        assert spend_metric.diff == expected_change
        assert result.delta_spend_ci_low <= result.delta_spend_per_visitor <= result.delta_spend_ci_high
    else:
        assert result.affected_comparison is None
        assert result.delta_spend_ci_low is None and result.delta_spend_ci_high is None
    assert all(example.persona_id in paired for example in result.examples)
    assert all(example.spend_with - example.spend_without == expected_change for example in result.examples)
    if rejected:
        assert any('fail' in note.lower() for note in result.notes)
    json.dumps(result.model_dump(mode='json'), allow_nan=False)


@pytest.mark.parametrize('seed', [0, 3, 5])
def test_real_runner_retries_do_not_create_a_basket_effect(seed):
    town = generate_town(TownSpec(seed=4, size_m=400, n_competitors=1, venue_density=0.0))
    focal = town.get_venue(town.focal_venue_id)
    town = place_venue(town, VenueCategory.CAFE, focal.x + 12, focal.y, venue_id='cafe-next-door', name='Corner Cafe')
    store = Store.model_validate(json.loads((SAMPLE / 'store.json').read_text()))
    pool = [Persona.model_validate(p) for p in json.loads((SAMPLE / 'personas.json').read_text())][:300]
    config = SimulationConfig(seed=seed)
    pathfinder = AStarPathFinder()

    class FailingCounterfactual(RuleBasedEngine):
        arm = 0
        failed_id = None
        rejected_calls = 0

        def reset_usage(self):
            self.arm += 1

        async def decide_actions(self, context):
            if self.arm == 2:
                if self.failed_id is None:
                    self.failed_id = context.persona.id
                if context.persona.id == self.failed_id:
                    self.rejected_calls += 1
                    raise RuntimeError('Scripted customer failure')
            return await super().decide_actions(context)

    engine = FailingCounterfactual(pathfinder, config)
    progress = []
    result = asyncio.run(vlm_basket_synergy(town, 'cafe-next-door', store, pool, config=config,
        engine=engine, pathfinder=pathfinder, cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS, customers=12,
        on_progress=lambda *args: progress.append(args)))
    assert engine.rejected_calls == 2 and result.failed_customers == 1
    assert result.delta_spend_per_visitor == result.delta_conversion == result.delta_revenue_from_baskets == 0
    assert result.affected_comparison.paired_customers == result.affected_customers - 1
    assert all(example.persona_id != engine.failed_id for example in result.examples)
    assert all(shift.spend_diff == 0 for shift in result.category_shifts)
    assert progress[-1][1] == progress[-1][2] == result.panel_customers + result.affected_customers
