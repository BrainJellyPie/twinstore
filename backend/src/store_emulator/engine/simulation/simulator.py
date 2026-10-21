import asyncio
import logging
import math
import random
from collections import Counter
from collections.abc import Callable

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.engine import CustomerBehaviorEngine, EngineMetadataSource, PerCustomerContext
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import AggregatedResult, FailedCustomer
from store_emulator.domain.runner import ProgressCallback
from store_emulator.domain.store import Store
from store_emulator.domain.types import PathFinder, Weekday, stable_seed
from store_emulator.engine.scenario import compile_scenario, hour_effects, priors_for, scale_trip
from store_emulator.engine.validation import validate, clear_blocked_slots, log_cleared
from .aggregator import aggregate
from .customer_executor import execute_decision
from ..generators.arrivals import CustomerEntry, generate_customers
from ..routing.heatmap import compute_pathcalc_heatmap

import traceback

logger = logging.getLogger(__name__)

type CueSampler = Callable[[random.Random], BehaviorCue]

_MAX_ATTEMPTS = 2


def _format_error(e: Exception) -> str:
    """LLM API errors: code+message; code errors: short stacktrace."""
    # Unwrap the original error if instructor wrapped it.
    cause = e.__cause__ or e
    # litellm/openai shape: status_code + message.
    status = getattr(cause, "status_code", None)
    if status is not None:
        msg = getattr(cause, "message", str(cause)).split("\n")[0][:200]
        return f"LLM {status}: {msg}"
    tb = traceback.format_exception(e)
    short = [line for line in tb if "/store_emulator/" in line or line.startswith("  ")]
    return f"{type(e).__name__}: {str(e).split(chr(10))[0][:150]}\n" + "".join(short[-6:])


class PerCustomerSimulationRunner:
    """Runner that calls the engine per persona to decide behavior.

    Used by engines that implement the `CustomerBehaviorEngine` Protocol (PII, RULE).
    `behavior_patterns` is injected by the application layer so the engine layer
    does not depend on application data directly.

    Randomness: each customer's cue, arrival minute, engine seed and timeline
    glances are derived from (config.seed, config.replicate, persona id) — never
    from the store layout. Two layouts simulated with the same seed/replicate
    therefore face the same customers in the same moods (common random numbers),
    which is what makes paired A/B comparisons sharp.
    """
    def __init__(
        self,
        config: SimulationConfig,
        engine: CustomerBehaviorEngine,
        pathfinder: PathFinder,
        cue_sampler: CueSampler,
        behavior_patterns: list[BehaviorPattern],
    ):
        self.config = config
        self.engine = engine
        self.pathfinder = pathfinder
        self.cue_sampler = cue_sampler
        # The pattern presets are sized for convenience stores; basket_scale stretches every
        # pattern's product cap for larger formats (0 stays 0: browse-only patterns).
        scale = config.basket_scale
        self.behavior_patterns = behavior_patterns if scale == 1.0 else [
            p.model_copy(update={"max_products": max(1, math.ceil(p.max_products * scale)) if p.max_products > 0 else 0})
            for p in behavior_patterns
        ]
        self._scenario = compile_scenario(config.scenario) if config.scenario is not None else None

    def _seconds_per_tile(self, customer_seed: int) -> float:
        """This shopper's walking time per tile: the configured pace times a seeded lognormal factor."""
        sd = self.config.walk_pace_sd
        if sd <= 0:
            return self.config.block_move_sec
        z = random.Random(stable_seed(customer_seed, "pace")).gauss(0.0, 1.0)
        return self.config.block_move_sec * math.exp(sd * z)

    def get_engine_metadata(self) -> dict[str, object]:
        if isinstance(self.engine, EngineMetadataSource):
            return self.engine.metadata()
        return {}

    @property
    def run_seed(self) -> int:
        return stable_seed(self.config.seed, self.config.replicate)

    def _validate_and_prepare(
        self, store: Store, personas: list[Persona],
    ) -> tuple[list[list[float]], list[tuple[CustomerEntry, Persona]], Counter[tuple[Weekday, int]]]:
        log_cleared(logger, "[simulation]", clear_blocked_slots(store))

        issues = validate(store)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            msgs = [f"  [{i.code}] {i.message}" for i in errors]
            raise ValueError(f"Store validation failed:\n" + "\n".join(msgs))
        for i in issues:
            if i.severity == "warning":
                logger.warning(f" {i.code}: {i.message}")

        heatmap = compute_pathcalc_heatmap(store)
        customers = generate_customers(personas, seed=self.run_seed)
        if store.weekly_schedule:
            customers = [entry for entry in customers if store.is_open_at(entry.day, entry.hour)]
        persona_map = {p.id: p for p in personas}
        entries = [(e, persona_map[e.persona_id]) for e in customers if e.persona_id in persona_map]
        hourly_counts: Counter[tuple[Weekday, int]] = Counter((entry.day, entry.hour) for entry, _ in entries)
        return heatmap, entries, hourly_counts

    async def run(
        self,
        store: Store,
        personas: list[Persona],
        *,
        max_concurrent: int = 5,
        address: str = "",
        customer_profile: str = "",
        on_progress: ProgressCallback | None = None,
    ) -> tuple[AggregatedResult, list[CustomerResult]]:
        pathcalc_heatmap, entries, hourly_counts = self._validate_and_prepare(store, personas)
        priors = priors_for(store.type, self.config.scenario_priors)
        if self.config.scenario is not None:   # situation effects follow the store's format
            self._scenario = compile_scenario(self.config.scenario, priors)
        # Trip size by situation and part of the day (receipt-sized trips only).
        size_fx = self._scenario if self._scenario is not None else hour_effects(priors)
        prepare = getattr(self.engine, "prepare", None)
        if callable(prepare):
            prepare(store)

        self.engine.reset_usage()

        semaphore = asyncio.Semaphore(max_concurrent)
        total = len(entries)
        completed = 0
        failures: list[FailedCustomer] = []
        run_seed = self.run_seed
        logger.info(f"[simulation] async run start: {total} customers, parallel {max_concurrent}, seed {self.config.seed}/rep {self.config.replicate}")

        def report() -> None:
            if on_progress is not None:
                try:
                    on_progress(completed, len(failures), total)
                except Exception as e:  # noqa: BLE001 — progress reporting must never break a run
                    logger.warning(f"[simulation] progress callback failed: {e}")

        async def simulate_one(entry: CustomerEntry, persona: Persona) -> CustomerResult | None:
            nonlocal completed
            customer_seed = stable_seed(run_seed, persona.id)
            persona = scale_trip(persona, size_fx, entry.hour, customer_seed)
            cue = self.cue_sampler(random.Random(stable_seed(customer_seed, "cue")))
            async with semaphore:
                reason = ""
                for attempt in range(_MAX_ATTEMPTS):
                    try:
                        context = PerCustomerContext(
                            store=store,
                            persona=persona,
                            day=entry.day,
                            arrival_hour=entry.hour,
                            concurrent_visitors_in_hour=hourly_counts.get((entry.day, entry.hour), 0),
                            cue=cue,
                            behavior_patterns=self.behavior_patterns,
                            address=address,
                            customer_profile=customer_profile,
                            # A retry must not replay the exact sampling that just failed.
                            seed=customer_seed if attempt == 0 else stable_seed(customer_seed, "retry", attempt),
                            situation=self._scenario.situation if self._scenario else "",
                        )
                        decision = await self.engine.decide_actions(context)
                        if self._scenario is not None and self._scenario.dwell != 1.0:
                            # Crowding, weather, music: people linger or hurry everywhere in the store.
                            factor = self._scenario.dwell
                            decision.actions = [
                                a.model_copy(update={"dwell": max(1, round(a.dwell * factor))}) if a.dwell else a
                                for a in decision.actions
                            ]
                        result = execute_decision(
                            store, entry.persona_id, entry.day, entry.arrival_time,
                            decision, self.pathfinder, self._seconds_per_tile(customer_seed),
                            rng=random.Random(stable_seed(customer_seed, "timeline")),
                            max_quantity=self.config.max_quantity_per_line,
                        )
                        completed += 1
                        logger.info(f"[simulation] customer {completed}/{total} ({entry.persona_id}) done")
                        report()
                        return result
                    except Exception as e:
                        reason = _format_error(e)
                        if attempt < _MAX_ATTEMPTS - 1:
                            logger.warning(f"[simulation] customer ({entry.persona_id}) failed once, retrying: {reason}")
                completed += 1
                failures.append(FailedCustomer(persona_id=entry.persona_id, reason=reason.split("\n")[0][:300]))
                logger.warning(f"[simulation] customer ({entry.persona_id}) failed {_MAX_ATTEMPTS}x, recorded as failure: {reason}")
                report()
            return None

        tasks = [simulate_one(entry, persona) for entry, persona in entries]
        raw_results = await asyncio.gather(*tasks)
        results = [r for r in raw_results if r is not None]

        aggregated = aggregate(
            store, results, personas, pathcalc_heatmap,
            block_move_sec=self.config.block_move_sec,
            currency=self.config.currency,
        )
        aggregated.token_usage = self.engine.get_usage()
        aggregated.diagnostics.requested_customers = total
        aggregated.diagnostics.failed_customers = sorted(failures, key=lambda f: f.persona_id)
        if failures:
            logger.warning(f"[simulation] {len(failures)}/{total} customers failed — see diagnostics.json")
        logger.info(
            f"[simulation] done: {len(results)}/{total} customers succeeded"
            f" | {aggregated.token_usage.total_tokens} tokens"
            f" | revenue {aggregated.summary.total_revenue} {self.config.currency} minor units"
        )
        return aggregated, results
