from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from store_emulator.application.async_executor import executor
from store_emulator.application.errors import AppError
from store_emulator.application.storage.generations import (
    find_active_generation, init_generation, write_status,
)
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import (
    metadata_path, personas_path, read_setup,
)
from store_emulator.application.supplemental import summarize_supplemental, traffic_from_supplemental
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import DaySchedule
from store_emulator.engine.generators import persona as gen_persona
from store_emulator.engine.generators.traffic_profile import TrafficProfile
from store_emulator.application.providers import resolve_model
from store_emulator.engine.llm_client import LiteLLMClient

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
    if any(s.get("runId") for s in setups):
        raise AppError("personas cannot be regenerated because the project has simulation history.", 409)

    gen_id = init_generation(project_id, setup_id, "persona")
    executor.submit(
        _run_persona_background,
        config, project_id, setup_id, gen_id, custom_instruction,
        supplemental_bytes=supplemental_bytes,
        supplemental_filename=supplemental_filename,
    )
    return gen_id


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
        write_status(project_id, gen_id, "running")
        meta: dict[str, object] = cast(
            dict[str, object], read_json(metadata_path(project_id)),
        )
        ws_raw = cast(list[Any], meta.get("weekly_schedule") or [])
        schedules = [DaySchedule.model_validate(d) for d in ws_raw]

        personas = asyncio.run(_run_async_pipeline(
            config=config,
            project_id=project_id,
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
        write_status(project_id, gen_id, "failed", error=str(exc))


async def _run_async_pipeline(
    config: SimulationConfig,
    project_id: str,
    meta: dict[str, object],
    schedules: list[DaySchedule],
    custom_instruction: str,
    supplemental_bytes: bytes | None,
    supplemental_filename: str,
) -> list[Persona]:
    """spec §4.3 — async orchestration. Summarize supplemental, then generate personas.

    Single LLM instance (token usage aggregated).
    Race / write failures stay isolated in effective_summary.
    """
    llm = LiteLLMClient(resolve_model(config.llm.model, base=config.llm))

    # Default to metadata's existing supplemental_summary. Even when
    # supplemental_bytes is None (manual call, restart, etc.) a previously-stored
    # summary must still flow into the persona prompt (spec §4.3).
    effective_summary = str(meta.get("supplemental_summary", "") or "")
    if supplemental_bytes is not None:
        summary = await summarize_supplemental(
            supplemental_bytes, supplemental_filename, llm,
        )
        if summary:
            try:
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
                latest_meta = cast(dict[str, object], read_json(metadata_path(project_id)))
                latest_meta["traffic_profile"] = fitted.model_dump(mode="json")
                write_json(metadata_path(project_id), latest_meta)
            except Exception:
                logger.warning("[supplemental] could not store the traffic profile", exc_info=True)
            logger.info(f"[supplemental] visit times follow the uploaded data ({fitted.source})")

    return await _generate_personas_impl(
        llm=llm,
        address=str(meta.get("address", "")),
        customer_profile=str(meta.get("customer_profile", "")),
        schedules=schedules,
        custom_instruction=custom_instruction,
        supplemental_summary=effective_summary,
        currency=str(meta.get("currency") or config.currency),
        traffic=traffic,
    )


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
    )
    usage = llm.get_usage()
    logger.info(f"[persona generation] {len(all_personas)} personas done | {usage.total_tokens} tokens")
    return all_personas
