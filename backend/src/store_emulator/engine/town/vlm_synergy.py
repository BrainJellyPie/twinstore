"""Synergy of a neighboring venue with VLM shoppers: visitor flow from the demand model, baskets
from the VLM.

1. Flow (numeric): focal visitors per day with and without the venue (Huff demand model).
2. Panel: one day of visitors drawn from the demand *with* the venue; each visitor's trip context
   is recomputed in the town without it (chained visitors from the venue get a direct origin from
   the counterfactual demand; others may lose a "passing up a closer store" remark). Visitors whose
   context changes ("affected") are over-sampled into the panel, the rest fill it.
3. Baskets (VLM): the panel is simulated with the venue in the context; the affected visitors are
   simulated again with the counterfactual context — same personas, cues and seeds, so the paired
   difference is the venue's effect on what they buy. Unaffected visitors have identical inputs in
   both worlds, so their (single) result stands for both and their difference is zero.
4. Per-visitor spend and conversion are population estimates (affected share × affected-stratum
   means + the rest); revenue per day = visitors × spend per visitor, decomposed into the visitor
   effect (Δ visitors × spend without) and the basket effect (visitors with × Δ spend).
"""

import math
import random
import time
from collections import defaultdict
from collections.abc import Callable
from typing import cast

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.engine import CustomerBehaviorEngine, EngineMetadataSource
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.town import (
    CategoryShift,
    DayType,
    SynergyExample,
    Town,
    TownArrival,
    VLMSynergyResult,
)
from store_emulator.domain.types import PathFinder, Weekday, stable_seed
from store_emulator.engine.analysis.compare import compare_runs
from store_emulator.engine.perception import category_label
from store_emulator.engine.scenario import (
    apply_to_personas,
    apply_to_store,
    compile_scenario,
)
from store_emulator.engine.simulation.simulator import PerCustomerSimulationRunner
from store_emulator.engine.town.arrivals import (
    counterfactual_arrival,
    plan_arrivals,
    town_context_text,
)
from store_emulator.engine.town.demand import estimate_demand

type CueSampler = Callable[[random.Random], BehaviorCue]
type SynergyProgress = Callable[[str, int, int], None]  # (phase, customers done, customers total)

_DAY_FOR: dict[str, Weekday] = {"weekday": Weekday.WED, "weekend": Weekday.SAT, "holiday": Weekday.SUN}
_AFFECTED_SHARE_OF_PANEL = 2 / 3


def _with_context(persona: Persona, context: str) -> Persona:
    return persona.model_copy(update={"description": f"{persona.description} {context}".strip()})


def _stratum(results: list[CustomerResult]) -> tuple[float, float]:
    """(mean spend, conversion) of a set of customers."""
    if not results:
        return 0.0, 0.0
    return (sum(r.total_spent for r in results) / len(results),
            sum(1 for r in results if r.purchases) / len(results))


def _category_spend(store: Store, results: list[CustomerResult]) -> dict[str, tuple[float, float]]:
    """Category label → (spend, units) summed over `results`."""
    labels = {rack.id: category_label(rack) for rack in store.racks}
    out: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for result in results:
        for event in result.purchases:
            label = labels.get(event.target_rack, "Other")
            out[label][0] += event.price * event.quantity
            out[label][1] += event.quantity
    return {k: (v[0], v[1]) for k, v in out.items()}


async def vlm_basket_synergy(
    town: Town,
    venue_id: str,
    store: Store,
    pool: list[Persona],
    *,
    config: SimulationConfig,
    engine: CustomerBehaviorEngine,
    pathfinder: PathFinder,
    cue_sampler: CueSampler,
    patterns: list[BehaviorPattern],
    customers: int,
    day_type: DayType = "weekday",
    model_label: str = "",
    max_concurrent: int = 4,
    on_progress: SynergyProgress | None = None,
) -> VLMSynergyResult:
    started = time.perf_counter()
    venue = town.get_venue(venue_id)
    focal = town.get_venue(town.focal_venue_id)
    if venue is None:
        raise ValueError(f"venue not found: {venue_id}")
    if focal is None or venue.id == focal.id:
        raise ValueError("pick a venue other than our own store")
    scenario = config.scenario
    effects = compile_scenario(scenario) if scenario is not None else None
    traffic = effects.base_traffic if effects is not None else 1.0
    hourly = (effects.traffic_by_hour or None) if effects is not None else None
    without = town.model_copy(update={"venues": [v for v in town.venues if v.id != venue_id]})
    demand_with = estimate_demand(town, day_type=day_type, traffic_multiplier=traffic, hourly_multiplier=hourly)
    demand_without = estimate_demand(without, day_type=day_type, traffic_multiplier=traffic, hourly_multiplier=hourly)
    linked = sum(t.expected_visitors for t in demand_with.linked_trips if t.from_venue_id == venue_id)

    # One day of visitors with the venue, each with both trip contexts.
    day = Weekday(scenario.only_days[0]) if scenario is not None and scenario.only_days else _DAY_FOR[day_type]
    seed = stable_seed(config.seed, "vlm-synergy", venue_id)
    visitors, arrivals = plan_arrivals(pool, demand_with, town, seed=seed, scale=1.0, day=day)
    contexts: dict[str, tuple[str, str]] = {}
    by_id: dict[str, tuple[Persona, TownArrival]] = {}
    for person, arrival in zip(visitors, arrivals, strict=True):
        alternative = counterfactual_arrival(arrival, venue_id, demand_without, seed=seed)
        contexts[person.id] = (town_context_text(arrival, town), town_context_text(alternative, without))
        by_id[person.id] = (person, arrival)
    affected_all = [pid for pid, (a, b) in contexts.items() if a != b]
    unaffected_all = [pid for pid, (a, b) in contexts.items() if a == b]
    share = len(affected_all) / len(contexts) if contexts else 0.0

    rng = random.Random(stable_seed(seed, "panel"))
    n = min(customers, len(contexts))
    n_affected = min(len(affected_all), math.ceil(n * _AFFECTED_SHARE_OF_PANEL))
    n_unaffected = min(len(unaffected_all), n - n_affected)
    n_affected = min(len(affected_all), n - n_unaffected)
    affected = sorted(rng.sample(affected_all, n_affected))
    unaffected = sorted(rng.sample(unaffected_all, n_unaffected))
    panel_with = [_with_context(by_id[pid][0], contexts[pid][0]) for pid in affected + unaffected]
    panel_without = [_with_context(by_id[pid][0], contexts[pid][1]) for pid in affected]

    if scenario is not None and effects is not None:  # promotions / stock-outs and budgets, as in a town run
        store, _ = apply_to_store(store, scenario)
        every_day = scenario.model_copy(update={"only_days": []})
        panel_with = apply_to_personas(panel_with, every_day, effects, seed=config.seed, scale_traffic=False)
        panel_without = apply_to_personas(panel_without, every_day, effects, seed=config.seed, scale_traffic=False)

    total = len(panel_with) + len(panel_without)
    done_before = 0
    requests = 0
    failed = 0
    plan_errors = 0
    missions: dict[str, dict[str, str]] = {"with": {}, "without": {}}

    async def simulate(arm: str, personas: list[Persona]) -> list[CustomerResult]:
        nonlocal done_before, requests, failed, plan_errors
        if not personas:
            return []
        runner = PerCustomerSimulationRunner(config, engine, pathfinder, cue_sampler, patterns)
        offset = done_before

        def progress(done: int, _failed: int, _total: int) -> None:
            if on_progress is not None:
                on_progress(f"{arm} venue", offset + done, total)

        aggregated, results = await runner.run(store.model_copy(deep=True), personas,
                                               max_concurrent=max_concurrent, on_progress=progress)
        done_before += len(personas)
        requests += aggregated.token_usage.requests
        failed += len(aggregated.diagnostics.failed_customers)
        records = engine.metadata().get("plan_records") if isinstance(engine, EngineMetadataSource) else None
        for record in cast(list[object], records) if isinstance(records, list) else []:
            row = cast(dict[str, object], record) if isinstance(record, dict) else {}
            pid, mission = row.get("persona_id"), row.get("mission")
            plan_errors += row.get("source") == "fallback"
            if isinstance(pid, str) and isinstance(mission, str):
                missions[arm][pid] = mission
        return results

    if on_progress is not None:
        on_progress("with venue", 0, total)
    results_with = await simulate("with", panel_with)
    results_without = await simulate("without", panel_without)

    with_by_id = {r.persona_id: r for r in results_with}
    aff_with = [with_by_id[pid] for pid in affected if pid in with_by_id]
    aff_without = [r for r in results_without if r.persona_id in with_by_id]
    rest = [with_by_id[pid] for pid in unaffected if pid in with_by_id]
    spend_aw, conv_aw = _stratum(aff_with)
    spend_ao, conv_ao = _stratum(aff_without)
    spend_u, conv_u = _stratum(rest)
    if not rest:  # nothing to weight the unaffected stratum with: use the affected one
        spend_u, conv_u = spend_ao, conv_ao
    weight = share if aff_with else 0.0
    spend_with = weight * spend_aw + (1 - weight) * spend_u
    spend_without = weight * spend_ao + (1 - weight) * spend_u
    conversion_with = weight * conv_aw + (1 - weight) * conv_u
    conversion_without = weight * conv_ao + (1 - weight) * conv_u

    notes: list[str] = []
    report = None
    spend_ci: tuple[float | None, float | None, float | None] = (None, None, None)
    conv_ci: tuple[float | None, float | None] = (None, None)
    if aff_with and aff_without:
        report = compare_runs(aff_without, aff_with, run_a="without venue", run_b="with venue", seed=config.seed)
        for m in report.metrics:
            if m.metric == "spend":
                spend_ci = (round(weight * m.ci_low, 3), round(weight * m.ci_high, 3), m.prob_b_greater)
            elif m.metric == "bought":
                conv_ci = (round(weight * m.ci_low, 5), round(weight * m.ci_high, 5))
    elif not affected_all:
        notes.append("No visitor's trip context mentions this venue, so the VLM basket effect is zero by"
                      " construction; the effect is the visitor flow alone.")
    if plan_errors:
        notes.append(f"{plan_errors} VLM entrance plans failed and fell back to the rule plan.")
    if affected_all and len(aff_with) < 30:
        notes.append(f"Only {len(aff_with)} affected visitors were simulated: the basket interval is wide.")

    categories_with = _category_spend(store, aff_with)
    categories_without = _category_spend(store, aff_without)
    shifts: list[CategoryShift] = []
    n_with, n_without = max(1, len(aff_with)), max(1, len(aff_without))
    for label in sorted(set(categories_with) | set(categories_without)):
        sw, uw = categories_with.get(label, (0.0, 0.0))
        so, uo = categories_without.get(label, (0.0, 0.0))
        shifts.append(CategoryShift(
            category=label, spend_with=round(sw / n_with, 3), spend_without=round(so / n_without, 3),
            units_with=round(uw / n_with, 3), units_without=round(uo / n_without, 3),
            spend_diff=round(sw / n_with - so / n_without, 3),
        ))
    shifts.sort(key=lambda c: -abs(c.spend_diff))

    without_by_id = {r.persona_id: r for r in results_without}
    examples = [
        SynergyExample(
            persona_id=pid, context_with=contexts[pid][0], context_without=contexts[pid][1],
            mission_with=missions["with"].get(pid, ""), mission_without=missions["without"].get(pid, ""),
            spend_with=with_by_id[pid].total_spent if pid in with_by_id else 0,
            spend_without=without_by_id[pid].total_spent if pid in without_by_id else 0,
        )
        for pid in affected[:6]
    ]

    visitors_with, visitors_without = demand_with.total_daily_visitors, demand_without.total_daily_visitors
    from_visitors = (visitors_with - visitors_without) * spend_without
    from_baskets = visitors_with * (spend_with - spend_without)
    return VLMSynergyResult(
        venue_id=venue.id, venue_name=venue.name, category=venue.category,
        distance_m=round(math.hypot(venue.x - focal.x, venue.y - focal.y), 1), day_type=day_type,
        scenario=scenario.name if scenario is not None else "", model=model_label,
        visitors_with=round(visitors_with, 3), visitors_without=round(visitors_without, 3),
        delta_visitors=round(visitors_with - visitors_without, 3), linked_visitors_from_venue=round(linked, 3),
        panel_customers=len(panel_with), affected_customers=len(affected), affected_share=round(share, 4),
        spend_per_visitor_with=round(spend_with, 3), spend_per_visitor_without=round(spend_without, 3),
        delta_spend_per_visitor=round(spend_with - spend_without, 3),
        delta_spend_ci_low=spend_ci[0], delta_spend_ci_high=spend_ci[1], prob_spend_higher=spend_ci[2],
        conversion_with=round(conversion_with, 5), conversion_without=round(conversion_without, 5),
        delta_conversion=round(conversion_with - conversion_without, 5),
        delta_conversion_ci_low=conv_ci[0], delta_conversion_ci_high=conv_ci[1],
        affected_comparison=report, category_shifts=shifts,
        revenue_per_day_with=round(visitors_with * spend_with, 2),
        revenue_per_day_without=round(visitors_without * spend_without, 2),
        delta_revenue_per_day=round(from_visitors + from_baskets, 2),
        delta_revenue_from_visitors=round(from_visitors, 2), delta_revenue_from_baskets=round(from_baskets, 2),
        examples=examples, vlm_requests=requests, failed_customers=failed, plan_errors=plan_errors,
        seconds=round(time.perf_counter() - started, 3), notes=notes,
    )
