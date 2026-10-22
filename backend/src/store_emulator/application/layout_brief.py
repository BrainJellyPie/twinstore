"""A layout design brief read into the template generator's options by the text model (assistive; nothing is built)."""

import asyncio
import logging

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_brief import BriefReading, read_brief
from store_emulator.engine.layout_gen import get_template
from store_emulator.engine.layout_gen.catalog import category_label

from .errors import AppError, model_failure
from .providers import assistive_model, build_client

logger = logging.getLogger(__name__)


class BriefRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    brief: str = Field(min_length=5, max_length=2000)
    options: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue], description="the options chosen so far")
    model: str = Field(default="", description='model reference; "" = the app text model')

    @field_validator("options")
    @classmethod
    def valid_options(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        # Older clients also sent template/seed metadata; validate the generator fields before any model call.
        chosen = {key: v for key, v in value.items() if key in LayoutOptions.model_fields}
        return LayoutOptions.model_validate(chosen).model_dump(mode="json", exclude_unset=True)


def read(template_id: str, req: BriefRequest, config: SimulationConfig) -> BriefReading:
    t = get_template(template_id)
    if t is None:
        raise AppError(f"unknown store format: {template_id}", 404)
    categories = [(c, category_label(c, "USD")) for c in sorted(set(t.fridges + t.freezers + t.wall_shelves + t.gondolas + t.near_counter))]
    info: dict[str, JsonValue] = {"name": t.name, "store_type": t.store_type, "description": t.description, "grid": list(t.grid), "style": t.style,
            "checkouts": t.checkouts, "dining_tables": t.dining_tables}
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 1200})
    try:
        llm = build_client(llm_config, None, model_ref=assistive_model(req.model, llm_config))
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(read_brief(llm, req.brief, info, categories, req.options))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[layout-brief] reading failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The brief could not be read"), 502) from e
