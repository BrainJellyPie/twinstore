"""A virtual shelf test drafted from the question the user wants answered.

"Would the gold label stand out more on the tea shelf with a SALE sign?" becomes the product under test (a product of
the layout, by name), the shelf it stands on, and the change respondents see on the test shelf: a library pack, a new
price, a sign. Names that point at nothing are dropped and reported; nothing runs.
"""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, Field

from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.persona import AGE_GROUPS, AgeGroup
from store_emulator.domain.store import Store
from store_emulator.engine.prompting import (
    display_price,
    relevant_first,
    resolve_listed,
)

ZERO_DECIMAL = {"KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"}
MAX_LISTED = 150


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Draft(BaseModel):
    name: str = Field(max_length=80, description="a short test name")
    product: str = Field(max_length=160, description="the listed product the test is about, exactly as listed")
    package: str = Field(default="", max_length=160, description="a listed product image shown instead of its pack, or empty")
    price: float | None = Field(default=None, ge=0, description="a new shelf price in major units, or null to keep it")
    promo: str = Field(default="", max_length=12, description="a sign such as NEW, SALE, 1+1 or -20%, or empty")
    age_groups: list[AgeGroup] = Field(default_factory=list[AgeGroup], max_length=6)
    rationale: str = Field(default="", max_length=500)


class ShelfTestDesign(BaseModel):
    name: str
    rack_id: str
    target_sku: str
    changes: list[VariantChange]
    age_groups: list[AgeGroup] = []
    rationale: str = ""
    warnings: list[str] = []


DESIGN_PROMPT = """You design virtual shelf tests for retail managers. Respondents see one shelf twice, as it is and
with a change to one product, and each time pick what they would take and say what caught their eye first. From the
manager's question, draft one test:
- product: the listed product the question is about, exactly as listed (without its price or shelf);
- the change on the test shelf, only what the question asks about: package (a listed product image, exactly as
  listed, shown instead of the product's pack), price (a new shelf price in major units of {currency}), promo (a short
  sign such as NEW, SALE, 1+1 or -20%); at least one of them;
- age_groups only when the question names an age group; otherwise leave it empty (everyone);
- a short name and rationale.
Write in English."""


def _listing(store: Store, currency: str, packages: Sequence[tuple[str, str]], question: str) -> str:
    items: dict[str, tuple[str, str, str]] = {}
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                items.setdefault(item.name, (rack.rack_name, item.name,
                                             f"{item.name} ({display_price(item.price, currency)}, {rack.rack_name or 'a shelf'})"))
    shown = relevant_first(list(items.values()), question, MAX_LISTED)
    lines = [f"Products: {'; '.join(shown)}"]
    lines.append(f"Product images: {', '.join(name for name, _ in packages)}" if packages else "Product images: none")
    return "\n".join(lines)


def to_design(draft: _Draft, store: Store, currency: str, packages: Sequence[tuple[str, str]]) -> ShelfTestDesign:
    """The product resolved to its SKU and the shelf it stands on, the pack to a library id, the price to minor units."""
    where: dict[str, tuple[str, str]] = {}
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                where.setdefault(item.name.strip().casefold(), (item.sku, rack.id))
    hit = resolve_listed(draft.product, where)
    if hit is None:
        raise ValueError(f'the model chose "{draft.product}", which is not a product of this layout')
    sku, rack_id = hit
    warnings: list[str] = []
    changes: list[VariantChange] = []
    if draft.package.strip():
        asset = resolve_listed(draft.package, {name.strip().casefold(): aid for name, aid in packages})
        if asset is None:
            warnings.append(f'No product image "{draft.package}" in the library; the pack change was left out.')
        else:
            changes.append(VariantChange(kind="package", sku=sku, asset_id=asset))
    if draft.price is not None and draft.price > 0:
        zero = currency.upper() in ZERO_DECIMAL
        changes.append(VariantChange(kind="price", sku=sku, price=round(draft.price) if zero else round(draft.price * 100),
                                     keep_reference=True))
    if draft.promo.strip():
        changes.append(VariantChange(kind="promo", sku=sku, promo=draft.promo.strip().upper()[:12]))
    if not changes:
        warnings.append("The draft changes nothing on the test shelf. Choose a pack, a price or a sign below.")
    return ShelfTestDesign(
        name=draft.name.strip()[:80], rack_id=rack_id, target_sku=sku, changes=changes,
        age_groups=[a for a in AGE_GROUPS if a in draft.age_groups], rationale=draft.rationale.strip(), warnings=warnings,
    )


async def design_shelf_test(
    llm: StructuredLLM, question: str, store: Store, currency: str, packages: Sequence[tuple[str, str]],
) -> ShelfTestDesign:
    """packages: (image name, asset id) for every image in the project's library."""
    draft = await llm.generate_structured_async(
        _Draft, DESIGN_PROMPT.format(currency=currency.upper()),
        f"{_listing(store, currency, packages, question)}\n\nQuestion: {question.strip()}", max_retries=2, seed=0,
    )
    return to_design(draft, store, currency, packages)
