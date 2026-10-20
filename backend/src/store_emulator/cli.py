"""Headless command line for batch experiments — no server or UI needed.

    parastore simulate --run sample_data/.../run_ab0039 --engine rule_based --replicates 3 --out runs/A
    parastore ab --store-a a.json --store-b b.json --personas personas.json --out runs/ab
    parastore compare runs/A/rep_0 runs/B/rep_0
    parastore fidelity runs/A/rep_0 pos_export.csv
    parastore summary runs/A/rep_0

Every run directory uses the same layout as server runs (input/ + output/), so
results from the CLI and from the app are interchangeable.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from store_emulator.application.config import local_config
from store_emulator.application.pos import parse_pos_csv
from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS
from store_emulator.application.simulation import (
    RunOptions,
    apply_options,
    run_simulation,
    subsample_personas,
)
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.runs import (
    load_run_results,
    load_run_store,
    save_run_dir,
)
from store_emulator.domain.analysis import ComparisonReport
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.result import SimulationSummary
from store_emulator.domain.store import Store
from store_emulator.engine.analysis.compare import compare_runs
from store_emulator.engine.analysis.fidelity import fidelity_report

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

    summ = sub.add_parser("summary", help="print the KPIs of a run directory")
    summ.add_argument("run", type=Path)

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
    p.add_argument("--model", help="LiteLLM model id, e.g. anthropic/claude-sonnet-5-5 or openai/local")
    p.add_argument("--api-base", help="OpenAI-compatible endpoint (vLLM, llama.cpp server)")
    p.add_argument("--cache-dir", help="LLM response cache directory")
    p.add_argument("--currency", help="ISO 4217 code of the price unit (USD, KRW, ...)")
    p.add_argument("--exposure-model", choices=["visibility", "adjacency"])
    p.add_argument("--route-ordering", choices=["planned", "nearest"])
    p.add_argument("--verbose", action="store_true")


def _config(args: argparse.Namespace) -> SimulationConfig:
    config = local_config()
    llm_updates: dict[str, object] = {}
    if args.model:
        llm_updates["model"] = args.model
    if args.api_base:
        llm_updates["api_base"] = args.api_base
    if args.cache_dir:
        llm_updates["cache_dir"] = args.cache_dir
    if llm_updates:
        config = config.model_copy(update={"llm": config.llm.model_copy(update=llm_updates)})
    updates: dict[str, object] = {}
    if args.currency:
        updates["currency"] = args.currency.upper()
    if updates:
        config = config.model_copy(update=updates)
    return apply_options(config, RunOptions(
        engine_type=EngineType(args.engine) if args.engine else None,
        seed=args.seed, exposure_model=args.exposure_model, route_ordering=args.route_ordering,
    ))


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
    for rep in range(args.replicates):
        cfg = config.model_copy(update={"replicate": rep})
        aggregated, customers, _ = asyncio.run(run_simulation(cfg, store, personas, max_concurrent=args.concurrency))
        target = out / f"rep_{rep}"
        save_run_dir(target, aggregated, customers, store, personas, cfg, BEHAVIOR_PATTERNS)
        print(f"\n=== {target} (engine={cfg.engine_type.value}, seed={cfg.seed}, replicate={rep}) ===")
        _print_summary(aggregated.summary)
        d = aggregated.diagnostics
        usage = aggregated.token_usage
        print(f"  failed customers {len(d.failed_customers)} | dropped hallucinated buys {d.dropped_invalid_buys}"
              f" | over-budget {d.dropped_over_budget} | LLM requests {usage.requests} (cached {usage.cached_requests})"
              f" | tokens {usage.total_tokens:,}")


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
