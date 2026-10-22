"""Layout edits written in words: drafted by the text model, reviewed by the user, kept as a new layout."""

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.marketing import VariantChange
from store_emulator.engine.layout_edit import (
    LayoutEditDraft,
    apply_layout_edit,
    draft_layout_edit,
)

from .currencies import project_currency
from .errors import AppError, model_failure
from .providers import assistive_model, build_client
from .scenarios import _store_for  # pyright: ignore[reportPrivateUsage]
from .setups import set_active_setup, setup_summary
from .storage.io import write_json
from .storage.setups import new_setup_data, read_setup, setup_path
from .study_design import _last_run_units  # pyright: ignore[reportPrivateUsage]

logger = logging.getLogger(__name__)


class LayoutEditRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=5, max_length=800, description='e.g. "put the cola at eye level and 10 % off ice cream"')
    model: str = Field(default="", description='model reference; "" = the app text model')


class LayoutEditApply(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(default="", max_length=80, description="name of the new layout")
    changes: list[VariantChange] = Field(min_length=1, max_length=20)


def _source(pid: str, sid: str):
    store = _store_for(pid, sid)
    if store is None:
        raise AppError("this layout has no store yet", 400)
    return store, (store.currency or project_currency(pid, "USD")).upper()


def draft_edit(pid: str, sid: str, req: LayoutEditRequest, config: SimulationConfig) -> LayoutEditDraft:
    """The instructions as layout edits on the layout's own products and shelves, checked on a copy; nothing is saved."""
    store, currency = _source(pid, sid)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 1500})
    try:
        llm = build_client(llm_config, None, model_ref=assistive_model(req.model, llm_config))
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(draft_layout_edit(llm, req.text, store, currency, _last_run_units(pid, sid)))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[layout-edit] draft failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The edits could not be drafted"), 502) from e


def apply_edit(pid: str, sid: str, req: LayoutEditApply) -> dict[str, Any]:
    """The reviewed edits applied to the layout and saved as a new layout (the original stays as it is)."""
    store, currency = _source(pid, sid)
    edited, applied, problems = apply_layout_edit(store, req.changes, currency)
    if not applied:
        raise AppError("None of these edits applies to this layout" + (f": {problems[0]}" if problems else "."), 422)
    source_name = str(read_setup(pid, sid).get("name") or "layout")
    name = req.name or f"{source_name} (edited)"
    memo = "; ".join(applied[:12])
    new_setup = new_setup_data(name[:80], sid, edited.model_dump(mode="json"), memo[:1000])
    write_json(setup_path(pid, new_setup["id"]), new_setup)
    set_active_setup(pid, new_setup["id"])
    return {**setup_summary(pid, new_setup), "applied": applied, "warnings": problems}
