"""Paired 2×2 contrasts from stored individual outcomes, never from arm aggregates."""

import csv
import hashlib
import io
import json
from collections.abc import Sequence

import numpy as np

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.factorial import (
    FactorialCell, FactorialContrast, FactorialReport, FactorialRequest, FactorialRow,
    FactorialSource, PairedArm, PairedOutcome, PairedSnapshot,
    OutcomeMetric,
)
from store_emulator.domain.marketing import ExperimentRequest
from store_emulator.domain.store import Store


def capture_paired_outcomes(
    experiment_id: str, currency: str, request: ExperimentRequest, panel_ids: list[str],
    stores: Sequence[tuple[str, Store, list[str]]], runs: Sequence[list[CustomerResult]],
) -> PairedSnapshot:
    arms: list[PairedArm] = []
    for (name, store, warnings), run in zip(stores, runs, strict=True):
        encoded = json.dumps(store.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
        arms.append(PairedArm(name=name, store_sha256=hashlib.sha256(encoded).hexdigest(), warnings=warnings,
            outcomes=[PairedOutcome(persona_id=r.persona_id, spend=r.total_spent, units=r.units_bought,
                bought=bool(r.purchases)) for r in run]))
    return PairedSnapshot(experiment_id=experiment_id, currency=currency, request=request, panel_ids=panel_ids, arms=arms)


def factorial_source(snapshot: PairedSnapshot, digest: str) -> FactorialSource:
    variants = snapshot.request.variants
    return FactorialSource(available=True, source_sha256=digest,
        price_arms=[v.name for v in variants if len(v.changes) == 1 and v.changes[0].kind in ("price", "discount")],
        sign_arms=[v.name for v in variants if len(v.changes) == 1 and v.changes[0].kind == "promo"],
        combined_arms=[v.name for v in variants if len(v.changes) == 2])


def _value(outcome: PairedOutcome, metric: OutcomeMetric) -> float:
    return float({"spend": outcome.spend, "units": outcome.units, "bought": outcome.bought}[metric])


def analyze_factorial(snapshot: PairedSnapshot, req: FactorialRequest) -> FactorialReport:
    variants = {v.name: v for v in snapshot.request.variants}
    if any(name not in variants for name in (req.price_arm, req.sign_arm, req.combined_arm)):
        raise ValueError("Selected arm is not in this experiment")
    price, sign, combined = [variants[name].changes for name in (req.price_arm, req.sign_arm, req.combined_arm)]
    if len(price) != 1 or price[0].kind not in ("price", "discount") or len(sign) != 1 or sign[0].kind != "promo":
        raise ValueError("Use exactly one price/discount change and exactly one promotion sign change")
    if not price[0].sku or price[0].sku != sign[0].sku or combined not in ([*price, *sign], [*sign, *price]):
        raise ValueError("Both factors must target the same SKU; the combined arm must contain exactly the same two changes")
    names = ["Control", req.price_arm, req.sign_arm, req.combined_arm]
    by_name = {a.name: a for a in snapshot.arms}
    arms = [by_name[name] for name in names]
    if any(a.warnings for a in arms):
        raise ValueError("A selected arm has application warnings; use fully applied factor changes")
    if len({a.store_sha256 for a in arms}) != 4:
        raise ValueError("The four effective layouts must differ; a factor may have made no change")
    maps = [{r.persona_id: r for r in arm.outcomes} for arm in arms]
    complete_ids = sorted(set(snapshot.panel_ids).intersection(*(set(m) for m in maps)))
    values = [[_value(m[pid], req.metric) for m in maps] for pid in complete_ids]
    n = len(values)
    matrix = np.array(values, dtype=float).reshape(n, 4)
    # Columns are 00, 10, 01, 11. Resample rows so all conditions stay paired.
    coefficients = np.array([[-.5, .5, -.5, .5], [-.5, -.5, .5, .5], [1., -1., -1., 1.]])
    contrasts = matrix @ coefficients.T
    intervals = n >= 30 and n == len(snapshot.panel_ids)
    lower: list[float | None] = [None, None, None]
    upper: list[float | None] = [None, None, None]
    if intervals:
        rng = np.random.default_rng(0)
        batches = [contrasts[rng.integers(0, n, size=(200, n))].mean(axis=1) for _ in range(20)]
        bounds = np.quantile(np.concatenate(batches), [0.05 / 6, 1 - 0.05 / 6], axis=0)
        lower = [float(v) for v in bounds[0]]
        upper = [float(v) for v in bounds[1]]
    labels = ["Price main effect", "Sign main effect", "Price × sign interaction"]
    formulas = ["((10-00)+(11-01))/2", "((01-00)+(11-10))/2", "11-10-01+00"]
    return FactorialReport(experiment_id=snapshot.experiment_id, request=req, currency=snapshot.currency,
        engine=snapshot.request.engine, model=snapshot.request.model, simulation_seed=snapshot.request.seed,
        requested_panel=snapshot.request.panel, sampled_panel=len(snapshot.panel_ids), complete_panel=n,
        intervals_available=intervals,
        cells=[FactorialCell(cell=cell, arm=arm.name, available=len(arm.outcomes),
            mean=float(matrix[:, i].mean()) if n else None, changes=[] if i == 0 else variants[arm.name].changes)
            for i, (cell, arm) in enumerate(zip(["00", "10", "01", "11"], arms, strict=True))],
        contrasts=[FactorialContrast(name=name, formula=formulas[i], estimate=float(contrasts[:, i].mean()) if n else None,
            ci_low=lower[i], ci_high=upper[i]) for i, name in enumerate(labels)],
        rows=[FactorialRow(persona_id=pid, complete=all(pid in m for m in maps),
            values=[_value(m[pid], req.metric) if pid in m else None for m in maps]) for pid in sorted(snapshot.panel_ids)],
        notes=[
            "Exploratory synthetic-panel analysis, not preregistered evidence, real customer conversion, or a sales forecast. Selection of arms/outcomes after seeing results can bias interpretation.",
            "00=Control, 10=price only, 01=sign only, 11=both. Main effects average over the other factor; interaction is the difference between conditional price effects, not half that difference. Only the same SKU and exact combined changes are supported.",
            "All four cell means and all contrasts use the same complete shoppers. Missing outcomes are not zero. Excluded shoppers can bias estimates; intervals are withheld unless every sampled shopper has all four cells and there are at least 30 shoppers.",
            "4,000 paired shopper bootstrap resamples, fixed seed 0. Percentile tails use 0.05/(2×3), a Bonferroni adjustment for these three contrasts of one outcome. Nominal family coverage is approximately 95% under bootstrap assumptions, not a finite-sample guarantee.",
            "Intervals do not adjust for repeated selection of metrics, arms or experiments, and do not capture model bias, prompt uncertainty, correlated personas or differences from real stores. Treat patterns as hypotheses for independent validation; no winner or p-value is reported.",
            "Spend is whole-basket minor currency units; units and purchase indicators also cover the whole basket. A free purchase counts as a purchase. No product-specific or daily-traffic effect is inferred.",
            "Rule shoppers treat promotion text as a generic impulse cue; only vision shoppers see the sign. This does not test a real POP design's visual effectiveness. Selected-four-cell cohorts can differ from the existing report's cohort across every experiment arm.",
            "Source snapshots store requested model selection; an empty model means the app default was requested, not a pinned provider/model version. Preserve the source hash and audit; this read-only review does not alter the experiment.",
        ])


def factorial_csv(report: FactorialReport) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    def row(values: list[object]) -> None:
        writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@", "'")) else v for v in values])
    row(["section", "key", "value", "ci_low", "ci_high"])
    for key, value in {"method": report.method, "experiment_id": report.experiment_id,
        "source_sha256": report.request.source_sha256, "metric": report.request.metric, "currency": report.currency,
        "engine": report.engine, "model_requested": report.model, "simulation_seed": report.simulation_seed,
        "requested_panel": report.requested_panel, "sampled_panel": report.sampled_panel, "complete_panel": report.complete_panel,
        "bootstrap_resamples": report.bootstrap_resamples, "bootstrap_seed": report.bootstrap_seed,
        "family_size": report.family_size, "intervals_available": report.intervals_available}.items():
        row(["metadata", key, value, "", ""])
    for cell in report.cells:
        row(["cell_arm", cell.cell, cell.arm, "", ""])
        row(["cell_mean", cell.cell, cell.mean, "", ""])
        row(["cell_available", cell.cell, cell.available, "", ""])
        row(["cell_changes", cell.cell, json.dumps([c.model_dump(mode="json") for c in cell.changes], ensure_ascii=False), "", ""])
    for contrast in report.contrasts:
        row(["contrast", contrast.name, contrast.estimate, contrast.ci_low, contrast.ci_high])
        row(["formula", contrast.name, contrast.formula, "", ""])
    for note in report.notes:
        row(["note", "", note, "", ""])
    row([])
    row(["persona_id", "complete", "00", "10", "01", "11"])
    for sample in report.rows:
        row([sample.persona_id, sample.complete, *sample.values])
    return output.getvalue()
