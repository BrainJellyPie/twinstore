"""Layout edits written in words: drafted by the text model, reviewed by the user, kept as a new layout."""

import asyncio
import logging
from filelock import FileLock, Timeout

from pydantic import BaseModel, ConfigDict, Field, field_validator

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.layout_options import BuildingFloorInfo
from store_emulator.domain.product_edits import MAX_PRICE, ProductEditsReceipt
from store_emulator.domain.store import Store
from store_emulator.engine.layout_edit import (
    LayoutEditDraft,
    apply_layout_edit,
    draft_layout_edit,
)

from .errors import AppError, model_failure
from .providers import assistive_client
from .product_sources import check_product_layout, read_product_source
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
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(default="", max_length=80, description="name of the new layout")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    changes: list[VariantChange] = Field(min_length=1, max_length=20)

    @field_validator("changes")
    @classmethod
    def safe_prices(cls, changes: list[VariantChange]) -> list[VariantChange]:
        if any(c.price is not None and c.price > MAX_PRICE for c in changes):
            raise ValueError("A price exceeds the safe integer limit")
        return changes


class LayoutEditRecord(BaseModel):
    layout_edit_request: LayoutEditApply
    layout_edit_result: dict[str, object]


def _source(pid: str, sid: str) -> tuple[Store, str, str]:
    store, digest = read_product_source(pid, sid)
    return store, (store.currency or "USD").upper(), digest


def draft_edit(pid: str, sid: str, req: LayoutEditRequest, config: SimulationConfig) -> LayoutEditDraft:
    """The instructions as layout edits on the layout's own products and shelves, checked on a copy; nothing is saved."""
    store, currency, digest = _source(pid, sid)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 1500})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        draft = asyncio.run(draft_layout_edit(llm, req.text, store, currency, _last_run_units(pid, sid)))
        return draft.model_copy(update={"source_sha256": digest})
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[layout-edit] draft failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The edits could not be drafted"), 502) from e


def apply_edit(pid: str, sid: str, req: LayoutEditApply) -> dict[str, object]:
    """Save the reviewed snapshot once; retries retain later edits, selection and deletion."""
    check_product_layout(pid, sid)
    path = setup_path(pid, f"setup_edit_{req.request_id}")
    receipt = path.parent / ".layout-edits" / f"{req.request_id}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(path.parent / ".layout-edits.lock", timeout=0):
            if receipt.exists() and ProductEditsReceipt.model_validate_json(receipt.read_bytes()).source_id != sid:
                raise AppError("This request belongs to another source layout", 409)
            if path.exists():
                record = LayoutEditRecord.model_validate_json(path.read_bytes())
                if record.layout_edit_request != req:
                    raise AppError("This request already saved different edits. Draft and review again", 409)
                return record.layout_edit_result
            if receipt.exists():
                raise AppError("This draft was removed or its write was interrupted. Check Layouts, then draft again", 409)
            store, currency, digest = _source(pid, sid)
            if digest != req.source_sha256:
                raise AppError("The source layout or currency changed. Draft and review the edits again", 409)
            edited, applied, problems = apply_layout_edit(store, req.changes, currency)
            if not applied:
                raise AppError("None of these edits applies to this layout" + (f": {problems[0]}" if problems else "."), 422)
            if any(max(item.price, item.regular_price) > MAX_PRICE for rack in edited.racks for slot in rack.slots for item in slot.items):
                raise AppError("The resulting price exceeds the safe integer limit. Choose a smaller change", 422)
            source = read_setup(pid, sid)
            source_name = str(source.get("name") or "layout")
            name = req.name or f"{source_name} (edited)"
            new_setup = new_setup_data(name[:80], sid, edited.model_dump(mode="json"), "; ".join(applied[:12])[:1000])
            if source.get("building") is not None:
                new_setup["building"] = BuildingFloorInfo.model_validate(source["building"]).model_dump(mode="json")
            new_setup["id"] = path.stem
            result: dict[str, object] = {**setup_summary(pid, new_setup), "applied": applied, "warnings": problems}
            new_setup["layout_edit_request"] = req.model_dump(mode="json")
            new_setup["layout_edit_result"] = result
            write_json(receipt, {"source_id": sid})
            write_json(path, new_setup)
            set_active_setup(pid, path.stem)
            return result
    except Timeout as exc:
        raise AppError("Another layout edit is saving. Retry this save shortly", 409) from exc
    except (OSError, ValueError) as exc:
        raise AppError("Could not save the edited layout. Retry the same request to check whether it completed", 500) from exc
