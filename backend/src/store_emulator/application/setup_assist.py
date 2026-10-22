"""Helpers for the create-store form, written by the text model (nothing is saved)."""

import asyncio
import logging

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.engine.assist_router import AssistRoute, route_request
from store_emulator.engine.generators.profile_writer import draft_profile
from store_emulator.engine.generators.store_setup_writer import (
    StoreSetup,
    draft_store_setup,
)

from .errors import AppError, model_failure
from .providers import assistive_client

logger = logging.getLogger(__name__)


class ProfileRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=1000)
    address: str = Field(default="", max_length=300)
    store_type: str = Field(default="", max_length=80)
    hours: str = Field(default="", max_length=80, description='e.g. "7:00–23:00, every day"')
    locale: str = Field(default="en", max_length=5)
    model: str = Field(default="", description='model reference; "" = the app text model')


class ProfileDraft(BaseModel):
    profile: str


def customer_profile(req: ProfileRequest, config: SimulationConfig) -> ProfileDraft:
    if not (req.name or req.description or req.address or req.store_type):
        raise AppError("Say something about the store first (name, type, description or address).", 400)
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.5, "max_tokens": 700})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        text = asyncio.run(draft_profile(llm, name=req.name, description=req.description, address=req.address,
                                         store_type=req.store_type, hours=req.hours, locale=req.locale))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[setup] profile draft failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "No profile could be written"), 502) from e
    return ProfileDraft(profile=text)


class RouteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=3, max_length=500)
    has_run: bool = False
    model: str = Field(default="", description='model reference; "" = the app text model')


def route(req: RouteRequest, config: SimulationConfig) -> AssistRoute:
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.0, "max_tokens": 200})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(route_request(llm, req.text, has_run=req.has_run))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[assist] routing failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The request could not be routed"), 502) from e


class StoreSetupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=5, max_length=800, description="the store in the owner's words")
    locale: str = Field(default="en", max_length=5)
    model: str = Field(default="", description='model reference; "" = the app text model')


def store_setup(req: StoreSetupRequest, config: SimulationConfig) -> StoreSetup:
    """The create-store form filled from one description, with the starting format chosen from the generator's."""
    from store_emulator.engine.layout_gen import TEMPLATES

    formats = [(t.id, t.name, t.store_type, t.description) for t in TEMPLATES]
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 900})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(draft_store_setup(llm, req.text, formats, req.locale))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[setup] store setup draft failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The form could not be filled"), 502) from e
