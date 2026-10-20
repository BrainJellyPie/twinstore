"""Headless command line for batch experiments — no server or UI needed.

    parastore simulate --run sample_data/.../run_ab0039 --engine rule_based --replicates 3 --out runs/A
    parastore ab --store-a a.json --store-b b.json --personas personas.json --out runs/ab
    parastore compare runs/A/rep_0 runs/B/rep_0
    parastore fidelity runs/A/rep_0 pos_export.csv
    parastore summary runs/A/rep_0
    parastore capture shelf.jpg --project proj_67916afd --model llamacpp:local

Every run directory uses the same layout as server runs (input/ + output/), so
results from the CLI and from the app are interchangeable.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import cast

from store_emulator.application import capture as capture_service
from store_emulator.application.config import local_config
from store_emulator.application.errors import AppError
from store_emulator.application.pos import parse_pos_csv
from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.application.scenarios import PRESETS as SCENARIO_PRESETS
from store_emulator.application.scenarios import prepare_inputs
from store_emulator.application.simulation import (
    RunOptions,
    apply_options,
    run_simulation,
    subsample_personas,
)
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.runs import (
    load_run_results,
    load_run_store,
    save_run_dir,
)
from store_emulator.domain.analysis import ComparisonReport
from store_emulator.domain.capture import CaptureOptions
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.providers import EnsembleConfig, EnsembleMember
from store_emulator.domain.result import SimulationSummary
from store_emulator.domain.scenario import Scenario
from store_emulator.domain.store import Store
from store_emulator.engine.analysis.compare import compare_runs
from store_emulator.engine.analysis.fidelity import fidelity_report
from store_emulator.engine.capture import display_name, render_overlay
from store_emulator.engine.prompting import display_price

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="parastore", description="Parastore headless experiments")
    sub = parser.add_subparsers(dest="command", required=True)

    sim = sub.add_parser("simulate", help="run one store layout (optionally several replicates)")
    _add_input_args(sim)
    _add_run_args(sim)
    sim.add_argument("--out", required=True, type=Path, help="output directory (rep_<k>/ per replicate)")

    ab = sub.add_parser("ab", help="run two layouts with common random numbers and compare them")
    ab.add_argument("--store-a", required=True, type=Path)
    ab.add_argument("--store-b", required=True, type=Path)
    ab.add_argument("--personas", required=True, type=Path)
    _add_run_args(ab)
    ab.add_argument("--out", required=True, type=Path)

    cmp_ = sub.add_parser("compare", help="paired comparison of two run directories (B − A)")
    cmp_.add_argument("run_a", type=Path)
    cmp_.add_argument("run_b", type=Path)
    cmp_.add_argument("--n-bootstrap", type=int, default=2000)
    cmp_.add_argument("--json", type=Path, help="also write the report as JSON")

    fid = sub.add_parser("fidelity", help="score a run against a real POS export")
    fid.add_argument("run", type=Path)
    fid.add_argument("pos", type=Path, help="POS export (.csv / .xlsx)")
    fid.add_argument("--json", type=Path)

    sub.add_parser("scenarios", help="list scenario presets")

    summ = sub.add_parser("summary", help="print the KPIs of a run directory")
    summ.add_argument("run", type=Path)

    cap = sub.add_parser("capture", help="shelf photo → planogram (levels, products, facings, prices, gaps)")
    cap.add_argument("image", type=Path)
    cap.add_argument("--project", help="also store the capture in this project, ready to apply from the app")
    cap.add_argument("--detector", choices=["auto", "gdino", "vlm", "classic"], default="auto")
    cap.add_argument("--model", default="", help='vision model reference ("llamacpp:local", "gemini:gemini-3.8-flash"), '
                                                 'a raw LiteLLM id, or "none" to skip recognition; default: the app\'s VLM')
    cap.add_argument("--api-base", help="endpoint for a raw LiteLLM model id (e.g. http://127.0.0.1:8081/v1)")
    cap.add_argument("--currency", help="ISO 4217 code of the price tags (default: server config)")
    cap.add_argument("--rack-type", choices=["shelf", "fridge"], default="shelf")
    cap.add_argument("--out", type=Path, help="write result.json and overlay.png to this directory")
    cap.add_argument("--verbose", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING if not args.__dict__.get("verbose") else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    for lib in ("LiteLLM", "litellm", "instructor", "httpx", "httpcore"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    if args.command == "simulate":
        store, personas = _load_inputs(args.run, args.store, args.personas)
        _simulate_replicates(store, personas, _config(args), args, args.out)
    elif args.command == "ab":
        store_a = Store.model_validate(read_json(args.store_a))
        store_b = Store.model_validate(read_json(args.store_b))
        personas = [Persona.model_validate(p) for p in read_json(args.personas)]
        config = _config(args)
        _simulate_replicates(store_a, personas, config, args, args.out / "A")
        _simulate_replicates(store_b, personas, config, args, args.out / "B")
        for rep in range(args.replicates):
            print(f"\n=== replicate {rep}: B vs A ===")
            report = compare_runs(
                load_run_results(args.out / "A" / f"rep_{rep}"), load_run_results(args.out / "B" / f"rep_{rep}"),
                run_a="A", run_b="B",
            )
            _print_comparison(report)
            (args.out / f"compare_rep_{rep}.json").write_text(report.model_dump_json(indent=2))
    elif args.command == "compare":
        report = compare_runs(load_run_results(args.run_a), load_run_results(args.run_b),
                              run_a=str(args.run_a), run_b=str(args.run_b), n_bootstrap=args.n_bootstrap)
        _print_comparison(report)
        if args.json:
            args.json.write_text(report.model_dump_json(indent=2))
    elif args.command == "fidelity":
        lines = parse_pos_csv(args.pos.read_bytes(), args.pos.name)
        report = fidelity_report(load_run_store(args.run), load_run_results(args.run), lines)
        print(f"sim customers {report.sim_customers} | real transactions {report.real_transactions} | SKUs {report.matched_skus}")
        for m in report.metrics:
            value = "n/a" if m.value is None else f"{m.value:.4f}"
            print(f"  {m.name:<26} {value:>10}   ({m.better})  {m.description}")
        for note in report.notes:
            print(f"  note: {note}")
        if args.json:
            args.json.write_text(report.model_dump_json(indent=2))
    elif args.command == "summary":
        _print_summary(SimulationSummary.model_validate(read_json(args.run / "output" / "summary.json")))
    elif args.command == "capture":
        return _capture(args)
    elif args.command == "scenarios":
        for s in SCENARIO_PRESETS:
            print(f"  {s.id:<20} {s.name:<34} {s.description}")
    return 0


def _add_input_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--run", type=Path, help="existing run directory to take input/store.json and input/personas.json from")
    p.add_argument("--store", type=Path, help="store JSON (overrides --run)")
    p.add_argument("--personas", type=Path, help="personas JSON array (overrides --run)")


def _add_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--engine", choices=[e.value for e in EngineType], help="default: server config / PARASTORE_ENGINE")
    p.add_argument("--seed", type=int)
    p.add_argument("--replicates", type=int, default=1)
    p.add_argument("--max-customers", type=int)
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--model", help='model reference ("openai:gpt-6-luna", "anthropic:claude-haiku-5-5", '
                                    '"gemini:gemini-3.8-flash", "qwen:qwen3.7-plus", "vllm:<served name>", '
                                    '"llamacpp:local") or a raw LiteLLM id')
    p.add_argument("--ensemble", help='comma-separated "model[=weight]" list, e.g. '
                                       '"openai:gpt-6-luna=2,anthropic:claude-haiku-5-5,qwen:qwen3.7-plus"')
    p.add_argument("--ensemble-mode", choices=["mixture", "vote"], default="mixture")
    p.add_argument("--scenario", help="scenario preset id (see `parastore scenarios`) or path to a scenario JSON file")
    p.add_argument("--plan-policy", choices=["vlm", "rule"],
                   help="vlm_glance: who plans the visit (default vlm: the model at the entrance)")
    p.add_argument("--api-base", help="endpoint override for a raw LiteLLM model id (vLLM, llama.cpp server)")
    p.add_argument("--cache-dir", help="LLM response cache directory")
    p.add_argument("--currency", help="ISO 4217 code of the price unit (USD, KRW, ...)")
    p.add_argument("--exposure-model", choices=["visibility", "adjacency"])
    p.add_argument("--route-ordering", choices=["planned", "nearest"])
    p.add_argument("--verbose", action="store_true")


def _parse_ensemble(spec: str | None, mode: str) -> EnsembleConfig | None:
    if not spec:
        return None
    members: list[EnsembleMember] = []
    for part in (s.strip() for s in spec.split(",") if s.strip()):
        ref, _, weight = part.partition("=")
        members.append(EnsembleMember(model=ref.strip(), weight=float(weight) if weight else 1.0))
    return EnsembleConfig(members=members, mode="vote" if mode == "vote" else "mixture")


def _scenario_option(spec: str | None) -> tuple[str | None, Scenario | None]:
    if not spec:
        return None, None
    path = Path(spec)
    if path.suffix == ".json" and path.exists():
        return None, Scenario.model_validate(read_json(path))
    return spec, None


def _config(args: argparse.Namespace) -> SimulationConfig:
    config = local_config()
    scenario_id, scenario = _scenario_option(args.scenario)
    if args.currency:
        config = config.model_copy(update={"currency": args.currency.upper()})
    config = apply_options(config, RunOptions(
        engine_type=EngineType(args.engine) if args.engine else None,
        seed=args.seed, exposure_model=args.exposure_model, route_ordering=args.route_ordering,
        model=args.model, ensemble=_parse_ensemble(args.ensemble, args.ensemble_mode),
        scenario_id=scenario_id, scenario=scenario,
        plan_policy="vlm" if args.plan_policy == "vlm" else "rule" if args.plan_policy == "rule" else None,
    ))
    llm_updates: dict[str, object] = {}
    if args.api_base:
        llm_updates["api_base"] = args.api_base
    if args.cache_dir:
        llm_updates["cache_dir"] = args.cache_dir
    if llm_updates and config.engine_type != EngineType.RULE_BASED:
        engines = config.engines
        if config.engine_type == EngineType.VLM_GLANCE:
            vlm = engines.vlm_glance
            engines = engines.model_copy(update={"vlm_glance": vlm.model_copy(update={"llm": vlm.llm.model_copy(update=llm_updates)})})
        else:
            pii = engines.pattern_intent_impulse
            llm = (pii.llm or config.llm).model_copy(update=llm_updates)
            engines = engines.model_copy(update={"pattern_intent_impulse": pii.model_copy(update={"llm": llm})})
        config = config.model_copy(update={"engines": engines})
    return config


def _load_inputs(run: Path | None, store: Path | None, personas: Path | None) -> tuple[Store, list[Persona]]:
    store_path = store or (run / "input" / "store.json" if run else None)
    persona_path = personas or (run / "input" / "personas.json" if run else None)
    if store_path is None or persona_path is None:
        sys.exit("error: give --run, or both --store and --personas")
    return (
        Store.model_validate(read_json(store_path)),
        [Persona.model_validate(p) for p in read_json(persona_path)],
    )


def _simulate_replicates(
    store: Store, personas: list[Persona], config: SimulationConfig, args: argparse.Namespace, out: Path,
) -> None:
    personas = subsample_personas(personas, args.max_customers, config.seed)
    store, personas = prepare_inputs(config, store, personas)
    for rep in range(args.replicates):
        cfg = config.model_copy(update={"replicate": rep})
        aggregated, customers, runner = asyncio.run(run_simulation(cfg, store, personas, max_concurrent=args.concurrency))
        target = out / f"rep_{rep}"
        save_run_dir(target, aggregated, customers, store, personas, cfg, BEHAVIOR_PATTERNS)
        meta = runner.get_engine_metadata()
        if meta:
            write_json(target / "output" / f"{cfg.engine_type.value}_meta.json", meta)
        print(f"\n=== {target} (engine={cfg.engine_type.value}, seed={cfg.seed}, replicate={rep}) ===")
        _print_summary(aggregated.summary)
        planning = meta.get("planning")
        if isinstance(planning, dict):
            p = cast(dict[str, object], planning)
            print(f"  VLM plans {p.get('plans')} (errors {p.get('plan_errors')}) | enter rate {p.get('enter_rate')}"
                  f" | items/plan {p.get('mean_items_named')} | resolved {p.get('resolution_rate')}"
                  f" | top categories {p.get('top_categories')}")
        d = aggregated.diagnostics
        usage = aggregated.token_usage
        print(f"  failed customers {len(d.failed_customers)} | dropped hallucinated buys {d.dropped_invalid_buys}"
              f" | over-budget {d.dropped_over_budget} | LLM requests {usage.requests} (cached {usage.cached_requests})"
              f" | tokens {usage.total_tokens:,}")


def _capture(args: argparse.Namespace) -> int:
    config = local_config()
    options = CaptureOptions(
        detector=args.detector, model=args.model, currency=(args.currency or config.currency).upper(),
        rack_type=args.rack_type,
    )
    try:
        photo = capture_service.prepare_photo(args.image.read_bytes(), args.image.name)
        llm_config = capture_service.capture_llm_config(config, args.model)
        if llm_config is not None and args.api_base:
            llm_config = llm_config.model_copy(update={"api_base": args.api_base, "structured_output": "json_schema"})
        result = capture_service.run_capture_sync(photo, options, llm_config, salt=args.image.name)
        stored = capture_service.save_capture(args.project, photo, args.image.name, options, result) if args.project else None
    except AppError as e:
        print(f"error: {e.message}", file=sys.stderr)
        return 1
    print(f"{args.image.name}: {len(result.bands)} shelves, {len(result.items)} products, {result.facings} facings, "
          f"{len(result.gaps)} gaps | detector {result.detector} | model {result.model or '-'} "
          f"({result.vlm_calls} calls) | tilt {result.tilt_deg:+.1f}° | {result.timings.get('total_sec', 0):.1f}s")
    for band in result.bands:
        items = sorted((i for i in result.items if i.band == band.index), key=lambda i: i.order)
        gaps = sum(1 for g in result.gaps if g.band == band.index)
        print(f"  shelf {band.index + 1} → level {band.level}" + (f"  ({gaps} gap{'s' if gaps != 1 else ''})" if gaps else ""))
        for item in items:
            price = display_price(item.price, result.currency) if item.price is not None else "?"
            mark = "~" if item.price_estimated else " "
            print(f"    {item.facings}× {display_name(item)[:44]:<44} {mark}{price:>10}  {item.category or '-':<14} {item.sku}")
    for note in result.notes:
        print(f"  note: {note}")
    if stored is not None:
        print(f"  stored as {stored.capture_id} in {args.project} (apply it from the app or POST .../captures/{stored.capture_id}/apply)")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        (args.out / "overlay.png").write_bytes(render_overlay(photo, result))
    return 0


def _print_summary(s: SimulationSummary) -> None:
    print(f"  visitors {s.total_customers} | buyers {s.buyers} | conversion {s.conversion_rate:.1%}"
          f" | revenue {s.total_revenue:,} ({s.currency})")
    print(f"  units/buyer {s.avg_units_per_buyer:.2f} | basket {s.avg_basket_value:,.0f} | revenue/visitor {s.revenue_per_visitor:,.0f}"
          f" | impulse share {s.impulse_revenue_share:.1%} | visit {s.avg_visit_sec:.0f}s | path {s.avg_path_tiles:.1f} tiles")
    top = ", ".join(s.top_products_by_units[:5])
    if top:
        print(f"  top by units: {top}")


def _print_comparison(report: ComparisonReport) -> None:
    print(f"  paired customers {report.paired_customers} (unpaired A {report.unpaired_a}, B {report.unpaired_b})")
    print(f"  {'metric':<14}{'A':>12}{'B':>12}{'B−A':>12}{'rel':>9}   {int(report.confidence * 100)}% CI{'':>14}P(B>A)  n@5%")
    for m in report.metrics:
        print(f"  {m.metric:<14}{m.mean_a:>12.3f}{m.mean_b:>12.3f}{m.diff:>12.3f}{m.rel_diff:>8.1%}"
              f"   [{m.ci_low:>9.3f}, {m.ci_high:>9.3f}]  {m.prob_b_greater:>6.1%}  {m.n_for_5pct_effect:>6}")
    for note in report.notes:
        print(f"  note: {note}")


if __name__ == "__main__":
    raise SystemExit(main())
