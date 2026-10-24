"""Study drafts written by the text model from the question the user wants answered (assistive; nothing runs)."""

import asyncio
import logging

from instructor.core.exceptions import InstructorRetryException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.engine.marketing.conjoint_design import (
    ConjointDesign,
    design_conjoint,
)
from store_emulator.engine.marketing.experiment_design import (
    ExperimentDesign,
    design_experiment,
)
from store_emulator.engine.marketing.shelf_test_design import (
    ShelfTestDesign,
    design_shelf_test,
)
from store_emulator.engine.marketing.survey_design import SurveyDesign, design_survey
from store_emulator.engine.prompting import display_price

from .currencies import project_currency
from .errors import AppError, model_failure
from .providers import assistive_client
from .scenarios import _store_for  # pyright: ignore[reportPrivateUsage]

logger = logging.getLogger(__name__)


class ConjointDesignRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=5, max_length=500, description="what the study should answer")
    setup_id: str = Field(default="", description="a layout whose products the price levels should bracket")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    model: str = Field(default="", description='model reference; "" = the app text model')


def design(pid: str, req: ConjointDesignRequest, config: SimulationConfig) -> ConjointDesign:
    store = _store_for(pid, req.setup_id) if req.setup_id else None
    store_currency = (store.currency or project_currency(pid, "USD")).upper() if store is not None else req.currency.upper()
    if store_currency != req.currency.upper():
        raise AppError(f"this layout prices in {store_currency}, not {req.currency.upper()}", 422)
    products = [(i.name, i.price) for r in store.product_racks for s in r.slots for i in s.items] if store else []
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 1200})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(design_conjoint(llm, req.question, req.currency, products))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[design] conjoint draft failed: {type(e).__name__}: {e}")
        cause = e.failed_attempts[-1].exception if isinstance(e, InstructorRetryException) and e.failed_attempts else e
        if isinstance(cause, ValidationError):
            for detail in cause.errors(include_url=False, include_input=False):
                if detail["type"] == "conjoint_price":
                    raise AppError(f"The study could not be drafted: {detail['msg']}", 502) from e
        raise AppError(model_failure(e, "The study could not be drafted"), 502) from e


class ExperimentDesignRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=5, max_length=500, description="what the A/B test should answer")
    setup_id: str = Field(min_length=1, description="the control layout")
    model: str = Field(default="", description='model reference; "" = the app text model')


def _last_run_units(pid: str, setup_id: str) -> dict[str, int]:
    """Units sold per SKU in the layout's final run, when it has one (so "the best seller" means something)."""
    from .interview import _load  # pyright: ignore[reportPrivateUsage]
    from .storage.setups import read_setup

    try:
        run_id = str(read_setup(pid, setup_id).get("runId") or "")
        customers = _load(pid, run_id)[0] if run_id else {}
    except (FileNotFoundError, AppError):
        return {}
    units: dict[str, int] = {}
    for c in customers.values():
        for e in c.purchases:
            units[e.product_sku] = units.get(e.product_sku, 0) + e.quantity
    return units


def design_ab(pid: str, req: ExperimentDesignRequest, config: SimulationConfig) -> ExperimentDesign:
    """Variants drafted by the text model from the question, using only the layout's products, shelves and the
    project's product images; changes that point at nothing are dropped and listed in `warnings`."""
    from .shelf_lab import (
        list_packages,  # late import: shelf_lab is heavy and imports capture
    )

    store = _store_for(pid, req.setup_id)
    if store is None:
        raise AppError("this layout has no store yet", 400)
    currency = (store.currency or project_currency(pid, config.currency)).upper()
    packages = [(p.name, p.asset_id) for p in list_packages(pid)]
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 1500})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(design_experiment(llm, req.question, store, currency, packages, _last_run_units(pid, req.setup_id)))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[design] A/B draft failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The test could not be drafted"), 502) from e


class SurveyDesignRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=5, max_length=500, description="what the concept test should answer")
    setup_id: str = Field(default="", description="a layout whose products and prices the images are listed with")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    model: str = Field(default="", description='model reference; "" = the app text model')


def design_concept(pid: str, req: SurveyDesignRequest, config: SimulationConfig) -> SurveyDesign:
    """Images (from the project's library), questions, brief, price and quotas drafted by the text model from the
    question; images that are not in the library are dropped and listed in `warnings`."""
    from .shelf_lab import (
        list_packages,  # late import: shelf_lab is heavy and imports capture
    )

    store = _store_for(pid, req.setup_id) if req.setup_id else None
    store_currency = (store.currency or project_currency(pid, req.currency)).upper() if store is not None else req.currency.upper()
    # The draft's price is asked in the survey's currency: shelf prices in another one would be copied over as they
    # are (₩1,500 read as $1,500), so then the products are listed without them.
    same_money = store_currency == req.currency.upper()

    def listed(name: str, price: int, rack: str) -> str:
        return f"{name} at {display_price(price, store_currency)} on {rack}" if same_money else f"{name} on {rack}"

    on_shelf = {i.sku: listed(i.name, i.price, r.rack_name or "a shelf")
                for r in store.product_racks for s in r.slots for i in s.items} if store is not None else {}
    packages = [(p.name, p.asset_id, p.brand, on_shelf.get(p.sku, "")) for p in list_packages(pid)]
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 1200})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(design_survey(llm, req.question, req.currency, packages))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[design] concept test draft failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The concept test could not be drafted"), 502) from e


class ShelfTestDesignRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=5, max_length=500, description="what the shelf test should answer")
    setup_id: str = Field(min_length=1, description="the layout whose shelf respondents see")
    model: str = Field(default="", description='model reference; "" = the app text model')


def design_shelf(pid: str, req: ShelfTestDesignRequest, config: SimulationConfig) -> ShelfTestDesign:
    """The product under test, its shelf and the change (pack, price, sign) drafted by the text model from the
    question, on the layout's own products and the project's product images."""
    from .shelf_lab import (
        list_packages,  # late import: shelf_lab is heavy and imports capture
    )

    store = _store_for(pid, req.setup_id)
    if store is None:
        raise AppError("this layout has no store yet", 400)
    currency = (store.currency or project_currency(pid, config.currency)).upper()
    packages = [(p.name, p.asset_id) for p in list_packages(pid)]
    llm_config = config.llm_for(EngineType.PATTERN_INTENT_IMPULSE).model_copy(update={"temperature": 0.2, "max_tokens": 900})
    try:
        llm = assistive_client(req.model, llm_config)
    except ValueError as e:
        raise AppError(str(e), 400) from e
    try:
        return asyncio.run(design_shelf_test(llm, req.question, store, currency, packages))
    except Exception as e:  # provider errors reach the user as advice
        logger.warning(f"[design] shelf test draft failed: {type(e).__name__}: {e}")
        raise AppError(model_failure(e, "The shelf test could not be drafted"), 502) from e
