"""Shelf Lab from the command line: build the counterfactual benchmark and run vision shoppers on it.

    uv run python -m store_emulator.lab_cli bench --out bench/ --per-template 6 --per-kind 2
    uv run python -m store_emulator.lab_cli bench --out bench_real/ --captures .data/proj_67916afd/captures
    uv run python -m store_emulator.lab_cli levers --bench bench/ --model gemini:gemini-3.8-flash --personas 24 --out levers.jsonl

`bench` writes original / counterfactual / mask triples with exact ground truth (see
engine/shelf_lab/bench.py for the layout). `levers` shows one persona panel each original and its
counterfactual and reports, per edit kind, how the share of shoppers picking the edited product moves.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import cast

from store_emulator.application.capture import capture_llm_config
from store_emulator.application.config import local_config
from store_emulator.application.errors import AppError
from store_emulator.application.presets.behavior import BEHAVIOR_PATTERNS, sample_cue
from store_emulator.domain.persona import Persona
from store_emulator.domain.shelf_lab import EditKind
from store_emulator.engine.capture.synthetic import Severity
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.optimize.evaluate import select_personas
from store_emulator.engine.shelf_lab.bench import (
    ALL_KINDS,
    BenchShelf,
    capture_shelves,
    synthetic_shelves,
    write_bench,
)
from store_emulator.engine.shelf_lab.levers import (
    LeverOutcome,
    load_counterfactuals,
    run_lever,
    summarize_levers,
)

SAMPLE_PERSONAS = Path(__file__).resolve().parents[2] / "sample_data" / "proj_67916afd" / "personas.json"


def _bench(args: argparse.Namespace) -> int:
    kinds = cast(list[EditKind], args.kinds.split(",")) if args.kinds else list(ALL_KINDS)
    if args.captures:
        shelves = capture_shelves(Path(args.captures))
    else:
        severities = cast(list[Severity], args.severity.split(","))
        templates = args.templates.split(",") if args.templates else None
        shelves = synthetic_shelves(templates=templates, per_template=args.per_template, severities=severities,
                                    currency=args.currency, seed=args.seed)

    def limited() -> list[BenchShelf]:
        out: list[BenchShelf] = []
        for s in shelves:
            out.append(s)
            if args.limit and len(out) >= args.limit:
                break
        return out

    counts = write_bench(Path(args.out), iter(limited()), kinds=kinds, per_kind=args.per_kind, seed=args.seed)
    print(json.dumps(counts, indent=1))
    return 0


def _levers(args: argparse.Namespace) -> int:
    config = local_config()
    try:
        llm_config = capture_llm_config(config, args.model)
    except AppError as e:
        print(e.message, file=sys.stderr)
        return 2
    if llm_config is None:
        print("levers needs a vision model", file=sys.stderr)
        return 2
    llm = LiteLLMClient(llm_config.model_copy(update={"max_tokens": 200}))
    personas_path = Path(args.personas_file) if args.personas_file else SAMPLE_PERSONAS
    personas = select_personas([Persona.model_validate(p) for p in json.loads(personas_path.read_text())], args.personas, seed=args.seed)
    kinds = set(args.kinds.split(",")) if args.kinds else None
    cfs = load_counterfactuals(Path(args.bench), limit=args.limit, kinds=kinds)
    outcomes: list[LeverOutcome] = []
    with Path(args.out).open("w") as fh:
        for k, cf in enumerate(cfs):
            outcome = asyncio.run(run_lever(llm, cf, personas, cue_sampler=sample_cue, patterns=BEHAVIOR_PATTERNS, seed=args.seed))
            outcomes.append(outcome)
            fh.write(outcome.model_dump_json() + "\n")
            print(f"[{k + 1}/{len(cfs)}] {cf.id}: {outcome.picked_before:.2f} → {outcome.picked_after:.2f} "
                  f"(changed {outcome.changed_pick:.2f}, errors {outcome.errors})", file=sys.stderr)
    print(f"{'kind':<10} {'n':>4} {'Δ picked':>9} {'95% CI':>18} {'changed':>8}")
    for s in summarize_levers(outcomes, seed=args.seed):
        print(f"{s.kind:<10} {s.counterfactuals:>4} {s.delta_picked:>+9.3f} [{s.ci_low:+.3f}, {s.ci_high:+.3f}] {s.changed_pick:>8.3f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="parastore-lab", description="Shelf Lab benchmark tools")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("bench", help="write a counterfactual benchmark (rendered shelves, or a project's captures)")
    b.add_argument("--out", required=True)
    b.add_argument("--captures", help="a project's captures directory (.data/<pid>/captures) instead of rendered shelves")
    b.add_argument("--templates", help="comma-separated store templates (default: all)")
    b.add_argument("--per-template", type=int, default=4)
    b.add_argument("--severity", default="clean,mild,strong")
    b.add_argument("--kinds", help=f"comma-separated subset of {','.join(ALL_KINDS)}")
    b.add_argument("--per-kind", type=int, default=2)
    b.add_argument("--currency", default="USD")
    b.add_argument("--limit", type=int, default=0, help="at most this many shelves")
    b.add_argument("--seed", type=int, default=0)

    lv = sub.add_parser("levers", help="persona panel on each original and counterfactual of a benchmark")
    lv.add_argument("--bench", required=True)
    lv.add_argument("--model", default="", help='model reference ("" = the app vision model)')
    lv.add_argument("--personas", type=int, default=24)
    lv.add_argument("--personas-file", help="personas.json (default: the sample project's)")
    lv.add_argument("--kinds")
    lv.add_argument("--limit", type=int, default=0)
    lv.add_argument("--seed", type=int, default=0)
    lv.add_argument("--out", default="levers.jsonl")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    return _bench(args) if args.command == "bench" else _levers(args)


if __name__ == "__main__":
    raise SystemExit(main())
