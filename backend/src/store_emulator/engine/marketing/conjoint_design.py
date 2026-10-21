"""A conjoint study drafted from the question the user wants answered.

"Would people pay more for zero-sugar iced tea in a bigger bottle?" becomes the product respondents choose, two to
four attributes with their levels, and price levels in the store's currency that bracket what comparable products on
its shelves cost. The draft fills the builder; nothing runs until the user starts it.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, Field

from store_emulator.domain.marketing import ConjointAttribute
from store_emulator.engine.prompting import display_price

ZERO_DECIMAL = {"KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"}
MAX_LISTED = 120


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Attribute(BaseModel):
    name: str = Field(max_length=40, description="e.g. 'Sugar'; never 'Price'")
    levels: list[str] = Field(min_length=1, max_length=8, description="short level labels; the first is the usual one")


class _Draft(BaseModel):
    name: str = Field(max_length=80, description="a short study name")
    product: str = Field(max_length=160, description="what respondents choose, e.g. 'a 500 ml bottle of iced tea'")
    context: str = Field(default="", max_length=300, description="one sentence on where and when they choose it")
    attributes: list[_Attribute] = Field(min_length=1, max_length=8)
    prices: list[float] = Field(default_factory=list[float], max_length=10,
                                description="price levels in major units of the currency (e.g. 1.49 USD, 1500 KRW)")
    rationale: str = Field(default="", max_length=500, description="why these attributes, levels and prices answer the question")
    comparable: list[str] = Field(default_factory=list[str], max_length=8,
                                  description="names of the listed store products whose prices the levels bracket, as listed")


class ConjointDesign(BaseModel):
    name: str
    product: str
    context: str = ""
    attributes: list[ConjointAttribute]
    prices: list[int] = []            # minor units
    currency: str
    rationale: str = ""
    comparable: list[str] = []        # store products the price levels were set against


DESIGN_PROMPT = """You design choice-based conjoint studies for retail managers. From the question the manager wants
answered, draft one study:

- the product respondents choose between, phrased so a shopper understands it, without fixing anything an attribute
  varies (no size in the product when size is an attribute);
- two to four attributes (never price, which is separate) with two to four short levels each, the usual or current
  level first; only attributes the question is about or that a shopper would weigh for this product;
- three to five price levels in {currency}, written in major units, evenly spread and bracketing what comparable
  products in this store cost (listed below), unless the question asks for no price;
- a one-sentence context and a short rationale.
Keep levels concrete (sizes with units, named claims). Write in English."""


def _shelf_text(products: Sequence[tuple[str, int]], currency: str) -> str:
    if not products:
        return "No store products given."
    shown = list(dict.fromkeys(products))[:MAX_LISTED]
    return "Products in this store: " + "; ".join(f"{name} {display_price(price, currency)}" for name, price in shown)


def to_minor(price: float, currency: str) -> int:
    return round(price) if currency.upper() in ZERO_DECIMAL else round(price * 100)


def to_design(draft: _Draft, currency: str, products: Sequence[tuple[str, int]]) -> ConjointDesign:
    """The draft as builder-ready values: unique names, price levels in minor units, sorted and de-duplicated."""
    attributes: list[ConjointAttribute] = []
    seen: set[str] = {"price"}
    for a in draft.attributes:
        name = a.name.strip()[:40]
        levels = list(dict.fromkeys(level.strip()[:60] for level in a.levels if level.strip()))
        if not name or name.casefold() in seen or len(levels) < 2:
            continue
        seen.add(name.casefold())
        attributes.append(ConjointAttribute(name=name, levels=levels[:6]))
    if not attributes:
        raise ValueError("the model drafted no usable attribute")
    prices = sorted({to_minor(p, currency) for p in draft.prices if p > 0})
    if len(prices) < 2:
        prices = []
    listed = {name.casefold(): (name, price) for name, price in products}
    named = [listed[n.strip().casefold()] for n in draft.comparable if n.strip().casefold() in listed]
    comparable = [f"{name} {display_price(price, currency)}" for name, price in dict.fromkeys(named)][:6]
    return ConjointDesign(name=draft.name.strip(), product=draft.product.strip(), context=draft.context.strip(),
                          attributes=attributes[:6], prices=prices[:6], currency=currency.upper(),
                          rationale=draft.rationale.strip(), comparable=comparable)


async def design_conjoint(
    llm: StructuredLLM, question: str, currency: str, products: Sequence[tuple[str, int]],
) -> ConjointDesign:
    draft = await llm.generate_structured_async(
        _Draft, DESIGN_PROMPT.format(currency=currency.upper()),
        f"{_shelf_text(products, currency)}\n\nQuestion: {question.strip()}", max_retries=2, seed=0,
    )
    return to_design(draft, currency, products)
