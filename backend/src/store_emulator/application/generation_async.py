from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import time
from collections import Counter
from pathlib import Path
from collections.abc import Callable
from typing import Any, cast

from filelock import FileLock, Timeout

from store_emulator.application.async_executor import executor, submit_background
from store_emulator.application.errors import AppError, model_failure
from store_emulator.application.estimates import cost_usd, effective_parallel, is_local_base, should_warn
from store_emulator.application.setups import project_layout_transaction, setup_lock_path, setup_tree_transaction
from store_emulator.application.storage.generations import (
    find_active_generation, generation_dir, init_generation, read_status, write_status,
)
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.engine.files import remove_tree
from store_emulator.application.storage.setups import (
    has_run_history, metadata_path, personas_path, read_setup,
)
from store_emulator.application.supplemental import summarize_supplemental, traffic_from_supplemental
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import DaySchedule, validate_weekly_schedule
from store_emulator.engine.generators import persona as gen_persona
from store_emulator.engine.generators.traffic_profile import TrafficProfile
from store_emulator.application.providers import assistive_client
from store_emulator.application.town import neighborhood_text
from store_emulator.engine.llm_client import LiteLLMClient

# How long customer generation waits for the local model when no provider takes a key (its first download).
LOCAL_MODEL_WAIT_SEC = 60 * 60
# What the small model TwinStore runs on this computer is asked for: every visitor like any model (it is free), but
# 5 customers per request (its output stays short and valid), and a quick sample of 20 a day when writing them all
# would take too long.
LOCAL_MODEL_PACE = gen_persona.Pace(daily_cap=gen_persona.DAILY_POPULATION_CAP, batch_size=5, sample_cap=20)
# How long a generation waits for the user to choose how many customers to write (see `_decide`).
CHOICE_WAIT_SEC = 6 * 60 * 60
WRITE_CHOICES = ("all", "sample", "cancel")
_PROGRESS_INTERVAL_SEC = 2.0

logger = logging.getLogger(__name__)


def start_persona_generation(
    config: SimulationConfig,
    project_id: str,
    setup_id: str,
    custom_instruction: str = "",
    *,
    ignore_active_gen_id: str | None = None,
    supplemental_bytes: bytes | None = None,
    supplemental_filename: str = "",
) -> str:
    """Start persona generation. Returns gen_id. Uses weekly_schedule from store metadata.

    spec §4.3 — supplemental_bytes / supplemental_filename are keyword-only.
    When provided, _run_persona_background summarizes them and updates metadata.

    - Any generation on this setup, or persona generation anywhere in the project → AppError(409).
    - Running simulation or simulation history present → personas locked → AppError(409).
    - `ignore_active_gen_id`: lets a layout-chain caller skip its own gen_id
      from the active check. External callers pass None.
    """
    if not metadata_path(project_id).is_file():
        raise AppError(f"Project not found: {project_id}", 404)
    with project_layout_transaction(project_id):
        setup = read_setup(project_id, setup_id)
        if not setup:
            raise AppError(f"Setup not found: {setup_id}", 404)

        # Per-setup single-flight: any in-flight generation (any kind) blocks.
        active = find_active_generation(project_id, setup_id)
        if active and active.get("gen_id") != ignore_active_gen_id:
            raise AppError(
                f"a {active.get('kind')} generation is already in progress (gen={active.get('gen_id')})", 409,
            )

        active_personas = find_active_generation(project_id, kind="persona")
        if active_personas and active_personas.get("gen_id") != ignore_active_gen_id:
            raise AppError("persona generation is already in progress for this project.", 409)

        # Sim run present → personas locked; prevent overwrite.
        from store_emulator.application.storage.setups import list_setups as _list_setups
        setups = _list_setups(project_id)
        if any(s.get("status") == "running" for s in setups):
            raise AppError("personas cannot be regenerated while a simulation is running.", 409)
        if has_run_history(project_id):   # its layout may have been deleted since: the runs still use these customers
            raise AppError("personas cannot be regenerated because the project has simulation history.", 409)

        if supplemental_bytes is not None:
            _keep_upload(project_id, supplemental_bytes, supplemental_filename)
        else:
            kept = _kept_upload(project_id)
            if kept is not None:
                supplemental_bytes, supplemental_filename = kept
        gen_id = init_generation(project_id, setup_id, "persona")
    try:
        submit_background(
            executor, _run_persona_background,
            config, project_id, setup_id, gen_id, custom_instruction,
            supplemental_bytes=supplemental_bytes,
            supplemental_filename=supplemental_filename,
        )
    except RuntimeError as exc:
        message = "Could not start customer generation. Please retry when the worker is available."
        write_status(project_id, gen_id, "failed", error=message)
        raise AppError(message, 503) from exc
    return gen_id


def _upload_dir(project_id: str) -> Path:
    return metadata_path(project_id).parent / "supplemental"


def _keep_upload(project_id: str, data: bytes, filename: str) -> None:
    """The customer data uploaded with a new store, kept on disk: it lived only in memory, so a first generation that
    failed (no key yet, a restart) lost it, and "Try again" generated customers without it, saying nothing."""
    folder = _upload_dir(project_id)
    try:
        if folder.exists():
            remove_tree(folder)
        folder.mkdir(parents=True)
        suffix = Path(filename).suffix.lower()[:10] or ".csv"
        (folder / f"upload{suffix}").write_bytes(data)
        write_json(folder / "upload.json", {"filename": filename, "sha256": hashlib.sha256(data).hexdigest()})
    except OSError:
        logger.warning("[supplemental] could not keep the uploaded file", exc_info=True)


def _kept_upload(project_id: str) -> tuple[bytes, str] | None:
    """Retain source evidence for retry even if only its text summary was saved before interruption."""
    folder = _upload_dir(project_id)
    try:
        if not folder.exists():
            return None
        raw: object = read_json(folder / "upload.json")
        if not isinstance(raw, dict):
            raise ValueError("Upload receipt must be an object")
        receipt = cast(dict[str, object], raw)
        name = receipt.get("filename")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Upload receipt has no filename")
        files = [f for f in folder.iterdir() if f.name.startswith("upload.") and f.suffix != ".json"]
        if len(files) != 1:
            raise ValueError("Expected exactly one retained customer upload")
        data = files[0].read_bytes()
        if not data:
            raise ValueError("Retained customer upload is empty")
        # Older receipts have no digest, but still require intact file/receipt pairs.
        if "sha256" in receipt and receipt["sha256"] != hashlib.sha256(data).hexdigest():
            raise ValueError("Retained customer upload does not match its receipt")
        return data, name
    except (OSError, ValueError) as exc:
        logger.warning("[supplemental] could not read the kept upload", exc_info=True)
        raise AppError("The saved uploaded customer data is missing or damaged. Restore the original upload, "
                       "or create a new store and attach it again before retrying customer generation.", 409) from exc


def _run_persona_background(
    config: SimulationConfig,
    project_id: str,
    setup_id: str,
    gen_id: str,
    custom_instruction: str,
    *,
    supplemental_bytes: bytes | None = None,
    supplemental_filename: str = "",
) -> None:
    """spec §4.3 — sync wrapper. Single asyncio.run invocation of _run_async_pipeline."""
    try:
        try:
            status = read_status(project_id, gen_id)
        except FileNotFoundError:
            return  # A rejected job's project may already have been removed.
        if status.get("status") != "pending":
            return
        write_status(project_id, gen_id, "running")
        meta: dict[str, object] = cast(
            dict[str, object], read_json(metadata_path(project_id)),
        )
        ws_raw = cast(list[Any], meta.get("weekly_schedule") or [])
        schedules = validate_weekly_schedule([DaySchedule.model_validate(d) for d in ws_raw])
        if not any(schedule.is_open for schedule in schedules):
            raise ValueError("Customer generation needs at least one open weekday. "
                             "Check the store's operating schedule before retrying. Existing customers were kept.")

        personas = asyncio.run(_run_async_pipeline(
            config=config,
            project_id=project_id,
            gen_id=gen_id,
            meta=meta,
            schedules=schedules,
            custom_instruction=custom_instruction,
            supplemental_bytes=supplemental_bytes,
            supplemental_filename=supplemental_filename,
        ))

        write_json(personas_path(project_id), [p.model_dump() for p in personas])
        write_status(project_id, gen_id, "completed", progress={"count": len(personas)})
        logger.info(f"[persona generation done] {project_id}/{setup_id} ({len(personas)} personas, gen={gen_id})")
    except Exception as exc:
        logger.exception("[persona generation failed]")
        write_status(project_id, gen_id, "failed", error=_failure_text(exc))


def _failure_text(exc: Exception) -> str:
    """What the preparing screen says: our own messages as they are; a provider's error in words a user can act on
    (the raw one, retries and all, is in the server log)."""
    if isinstance(exc, (ValueError, AppError)):
        return str(exc)
    if isinstance(exc, gen_persona.TooManyBatchesFailed):
        tally = exc.tally
        return model_failure(tally.first_error or exc,
                             f"Customer generation failed ({tally.failed} of {tally.requested} requests to the model)")
    return model_failure(exc, "Customer generation failed")


async def _run_async_pipeline(
    config: SimulationConfig,
    project_id: str,
    meta: dict[str, object],
    schedules: list[DaySchedule],
    custom_instruction: str,
    supplemental_bytes: bytes | None,
    supplemental_filename: str,
    gen_id: str = "",
) -> list[Persona]:
    """spec §4.3 — async orchestration. Summarize supplemental, then generate personas.

    Single LLM instance (token usage aggregated).
    Race / write failures stay isolated in effective_summary.
    """
    last_note = [""]

    def note(message: str) -> None:   # shown while the job waits for the local model
        if gen_id and message != last_note[0]:
            last_note[0] = message
            write_status(project_id, gen_id, "running", progress={"note": message})

    # A text model without a usable API key would fail every batch: the client moves on to a provider that takes its
    # key, else to the local model on this computer, waiting for its first download if need be.
    llm = await asyncio.to_thread(assistive_client, "", config.llm, wait=LOCAL_MODEL_WAIT_SEC, on_wait=note)
    if last_note[0]:   # the wait is over: the preparing screen stops showing it
        write_status(project_id, gen_id, "running", progress={})

    # Default to metadata's existing supplemental_summary. Even when
    # supplemental_bytes is None (manual call, restart, etc.) a previously-stored
    # summary must still flow into the persona prompt (spec §4.3).
    effective_summary = str(meta.get("supplemental_summary", "") or "")
    if supplemental_bytes is not None and not effective_summary:
        summary = await summarize_supplemental(
            supplemental_bytes, supplemental_filename, llm,
        )
        if summary:
            try:
                with setup_tree_transaction(project_id):
                    latest_meta = cast(dict[str, object], read_json(metadata_path(project_id)))
                    if str(latest_meta.get("supplemental_summary", "")) == "":
                        latest_meta["supplemental_summary"] = summary
                        write_json(metadata_path(project_id), latest_meta)
                        effective_summary = summary
                    else:
                        logger.info(
                            "[supplemental] existing supplemental_summary on disk; "
                            "ignoring fresh auto-summary, keeping stored value for persona generation."
                        )
                        effective_summary = str(latest_meta["supplemental_summary"])
            except Exception:
                logger.warning(
                    "[supplemental] metadata read/write failed. Discarding summary and proceeding with persona.",
                    exc_info=True,
                )
                effective_summary = ""

    traffic = _stored_traffic(meta)
    if supplemental_bytes is not None:
        fitted = traffic_from_supplemental(supplemental_bytes, supplemental_filename)
        if fitted is not None:
            traffic = fitted
            try:
                with setup_tree_transaction(project_id):
                    latest_meta = cast(dict[str, object], read_json(metadata_path(project_id)))
                    latest_meta["traffic_profile"] = fitted.model_dump(mode="json")
                    write_json(metadata_path(project_id), latest_meta)
            except Exception:
                logger.warning("[supplemental] could not store the traffic profile", exc_info=True)
            logger.info(f"[supplemental] visit times follow the uploaded data ({fitted.source})")

    # Ground the personas in the project's neighborhood model when there is one.
    try:
        neighborhood = neighborhood_text(project_id)
    except Exception:
        logger.warning("[persona generation] neighborhood model unreadable; generating without it", exc_info=True)
        neighborhood = ""
    if neighborhood:
        effective_summary = f"{effective_summary}\n{neighborhood}".strip()

    estimates: dict[int, int] = {}
    last_progress = [0.0]

    def progress(done: int, total: int) -> None:   # "writing N of M customers" on the preparing screen
        now = time.monotonic()
        if gen_id and (done >= total or now - last_progress[0] >= _PROGRESS_INTERVAL_SEC):
            last_progress[0] = now
            write_status(project_id, gen_id, "running", progress={"written": done, "total": total})

    async def decide(plan: gen_persona.WritePlan) -> int:
        return await _decide(project_id, gen_id, llm, plan)

    personas = await _generate_personas_impl(
        llm=llm,
        estimates=estimates,
        pace=lambda usual: gen_persona.Pace(
            daily_cap=min(usual.daily_cap, LOCAL_MODEL_PACE.daily_cap),
            batch_size=min(usual.batch_size, LOCAL_MODEL_PACE.batch_size),
            sample_cap=min(usual.sample_cap, LOCAL_MODEL_PACE.sample_cap),
        ) if is_local_base(llm.api_base) else usual,
        decide=decide if gen_id else None,
        on_progress=progress,
        address=str(meta.get("address", "")),
        customer_profile=str(meta.get("customer_profile", "")),
        schedules=schedules,
        custom_instruction=custom_instruction,
        supplemental_summary=effective_summary,
        currency=str(meta.get("currency") or config.currency),
        traffic=traffic,
    )
    if estimates:
        try:   # the visitors each day the customers were sampled from (see visitors_per_day)
            with setup_tree_transaction(project_id):
                latest = cast(dict[str, object], read_json(metadata_path(project_id)))
                latest["estimated_daily_visitors"] = {str(day): n for day, n in sorted(estimates.items())}
                write_json(metadata_path(project_id), latest)
        except (OSError, ValueError, AppError):
            logger.warning("[persona generation] could not store the estimated daily visitors", exc_info=True)
    return personas


def write_estimate(llm: LiteLLMClient, plan: gen_persona.WritePlan, size: gen_persona.WriteSize) -> dict[str, object]:
    """About how long and how much writing `size` takes from here, scaled from the timed probe request (already
    written, so it is not counted again)."""
    requests = max(0, size.requests - 1)
    local = is_local_base(llm.api_base)
    minutes = requests * plan.probe_seconds / effective_parallel(local, llm.max_parallel) / 60
    cost: float | None = None
    if not local:
        probe_cost = cost_usd(llm.model, plan.probe_prompt_tokens, plan.probe_completion_tokens)
        cost = None if probe_cost is None else round(probe_cost * requests, 4)
    return {"per_day": size.per_day, "customers": size.customers, "requests": size.requests,
            "minutes": round(minutes, 1), "cost_usd": cost}


async def _decide(project_id: str, gen_id: str, llm: LiteLLMClient, plan: gen_persona.WritePlan) -> int:
    """How many customers a day to write. Every visitor, unless that takes about WARN_MINUTES or costs about WARN_USD:
    then the preparing screen asks (write them all, a quick sample whose twins fill each day, or cancel)."""
    every, sample = write_estimate(llm, plan, plan.all), write_estimate(llm, plan, plan.sample)
    cost = every["cost_usd"]
    if not should_warn(cast(float, every["minutes"]), cost if isinstance(cost, float) else None) or not gen_id:
        return plan.all.per_day
    confirm: dict[str, object] = {
        "model": llm.model, "local": is_local_base(llm.api_base),
        "days": len(plan.visitors), "visitors_per_day": {str(day): n for day, n in sorted(plan.visitors.items())},
        "all": every, "sample": sample,
    }
    logger.info(f"[persona generation] asking before writing {plan.all.customers} customers "
                f"(about {every['minutes']} min, ${every['cost_usd']}) gen={gen_id}")
    write_status(project_id, gen_id, "running", progress={"confirm": confirm})
    choice = await _await_choice(project_id, gen_id)
    logger.info(f"[persona generation] {choice} gen={gen_id}")
    if choice == "cancel":
        raise ValueError("You canceled writing the customers. Use Try again to choose a quick sample or write them all.")
    chosen = plan.all if choice == "all" else plan.sample
    write_status(project_id, gen_id, "running", progress={"written": plan.probe_customers, "total": chosen.customers})
    return chosen.per_day


def _choice_path(project_id: str, gen_id: str) -> Path:
    return generation_dir(project_id, gen_id) / "choice.json"


def _choice_lock_path(project_id: str, gen_id: str) -> Path:
    return setup_lock_path(project_id, gen_id).with_name(f".generation-choice-{gen_id}.lock")


async def _await_choice(project_id: str, gen_id: str) -> str:
    path = _choice_path(project_id, gen_id)
    lock = FileLock(_choice_lock_path(project_id, gen_id), timeout=0)
    deadline = time.monotonic() + CHOICE_WAIT_SEC
    while True:
        try:
            with lock:
                if path.is_file():
                    try:
                        choice = cast(dict[str, object], read_json(path)).get("choice")
                    except (OSError, ValueError):
                        choice = None
                    path.unlink(missing_ok=True)
                    if isinstance(choice, str) and choice in WRITE_CHOICES:
                        return choice
                if time.monotonic() >= deadline:
                    data = read_status(project_id, gen_id)
                    progress = data.get("progress")
                    if data.get("status") == "running" and isinstance(progress, dict) and "confirm" in progress:
                        # Close the answer window before releasing the lock. The
                        # worker records failure after this coroutine raises.
                        write_status(project_id, gen_id, "running", progress={})
                    break
        except Timeout:
            pass  # the answer and its progress update must both commit before the worker resumes
        await asyncio.sleep(0.5)
    raise ValueError("Nobody chose how many customers to write, so generation stopped. Use Try again.")


def choose_write_size(project_id: str, setup_id: str, gen_id: str, choice: str) -> dict[str, Any]:
    """The user's answer to a generation that asks before writing: "all", "sample" or "cancel"."""
    if choice not in WRITE_CHOICES:
        raise AppError(f"choice must be one of {', '.join(WRITE_CHOICES)}", 422)
    if not (generation_dir(project_id, gen_id) / "status.json").is_file():
        raise AppError("generation not found", 404)
    try:
        with FileLock(_choice_lock_path(project_id, gen_id), timeout=10):
            data = read_status(project_id, gen_id)
            if data.get("setup_id") != setup_id:
                raise AppError("no generation found for this setup", 404)
            progress = data.get("progress")
            if data.get("status") != "running" or not isinstance(progress, dict) or "confirm" not in progress:
                raise AppError("This generation is not waiting for a choice.", 409)
            write_json(_choice_path(project_id, gen_id), {"choice": choice})
            chosen = cast(dict[str, object], progress["confirm"]).get(choice) if choice != "cancel" else None
            total = cast(dict[str, object], chosen).get("customers") if isinstance(chosen, dict) else None
            write_status(project_id, gen_id, "running",
                         progress={"written": 0, "total": total} if isinstance(total, int) else {})
            return read_status(project_id, gen_id)
    except FileNotFoundError:
        raise AppError("generation not found", 404) from None
    except Timeout:
        raise AppError("another request is answering this generation. Please retry shortly.", 503) from None


def visitors_per_day(project_id: str, personas: list[Persona]) -> tuple[float, float]:
    """(visitors a day to scale per-visitor results by, customers simulated a day). The model writes every visitor it
    estimated for a day (up to 1000), or a quick sample of them whose twins fill the day; per-day money in reports
    scales by the estimate. Without one (older stores, customers from data) both are the simulated count."""
    counts = Counter(int(p.day) for p in personas)
    days = len(counts) or 1
    estimated = _daily_visitors(project_id, counts)
    return round(sum(n / days for n in estimated.values()), 1), round(len(personas) / days, 1)


def _daily_visitors(project_id: str, counts: Counter[int]) -> dict[int, float]:
    try:
        metadata: object = read_json(metadata_path(project_id))
        raw = cast(dict[str, object], metadata).get("estimated_daily_visitors") if isinstance(metadata, dict) else None
    except (OSError, ValueError):
        raw = None
    estimates = cast(dict[str, object], raw) if isinstance(raw, dict) else {}
    daily = {day: float(n) for day, n in counts.items()}
    for day, n in counts.items():
        value = estimates.get(str(day))
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        try:
            estimated = float(value)
        except OverflowError:
            continue
        if math.isfinite(estimated) and estimated >= 0:
            daily[day] = max(estimated, n)
    return daily


def visitors_per_day_coming(pid: str, everyone: list[Persona], coming: list[Persona]) -> tuple[float, float]:
    """Scale each visiting weekday by its own estimate/sample ratio before averaging the active days."""
    counts = Counter(int(p.day) for p in everyone)
    arriving = Counter(int(p.day) for p in coming)
    estimates = _daily_visitors(pid, counts)
    days = len(arriving) or 1
    per_day = sum(n / days * (estimates[day] / counts[day] if counts[day] else 1)
                  for day, n in arriving.items())
    return round(per_day, 1), round(len(coming) / days, 1)


def _stored_traffic(meta: dict[str, object]) -> TrafficProfile | None:
    raw = meta.get("traffic_profile")
    if not raw:
        return None
    try:
        return TrafficProfile.model_validate(raw)
    except ValueError:  # pydantic's ValidationError
        logger.warning("[supplemental] stored traffic profile is unreadable; ignoring it")
        return None


async def _generate_personas_impl(
    llm: LiteLLMClient,
    address: str,
    customer_profile: str,
    schedules: list[DaySchedule],
    seed: int | None = None,
    custom_instruction: str = "",
    *,
    supplemental_summary: str = "",
    currency: str = "USD",
    traffic: TrafficProfile | None = None,
    pace: Callable[[gen_persona.Pace], gen_persona.Pace] | None = None,
    estimates: dict[int, int] | None = None,
    decide: gen_persona.Decide | None = None,
    on_progress: gen_persona.WriteProgress | None = None,
) -> list[Persona]:
    """Internal impl accepting an LLM instance, with supplemental_summary support.

    spec §4.3 — the background pipeline calls this directly so a single LLM
    instance is shared across summary + persona generation.
    """
    all_personas = await gen_persona.generate_batched(
        llm, address, customer_profile,
        schedules=schedules,
        seed=seed, custom_instruction=custom_instruction,
        supplemental_summary=supplemental_summary,
        currency=currency,
        traffic=traffic,
        pace=pace,
        estimates=estimates,
        decide=decide,
        on_progress=on_progress,
    )
    usage = llm.get_usage()
    logger.info(f"[persona generation] {len(all_personas)} personas done | {usage.total_tokens} tokens")
    if not all_personas and any(s.is_open for s in schedules):
        # Every batch failed or came back empty: say so instead of finishing with a store nobody visits.
        raise ValueError(f"No customers were generated: every request to {getattr(llm, 'model', 'the model')} failed "
                           "or came back empty (see the server log). Try again, or pick another model in Settings → "
                           "Model providers.")
    return all_personas
