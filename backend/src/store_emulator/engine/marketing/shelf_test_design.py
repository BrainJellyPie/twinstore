"""A virtual shelf test drafted from the question the user wants answered.

"Would the gold label stand out more on the tea shelf with a SALE sign?" becomes the product under test (a product of
the layout, by name), the shelf it stands on, and the change respondents see on the test shelf: a library pack, a new
price, a sign. Names that point at nothing are dropped and reported; nothing runs.
"""

from collections.abc import Sequence
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from typing import Protocol, Self

from pydantic import BaseModel, Field, field_validator, model_validator

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
MAX_PRICE = 9_007_199_254_740_991


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

    @field_validator("package", "promo", "rationale", mode="before")
    @classmethod
    def _optional_text(cls, value: object) -> object:
        return "" if value is None else value

    @field_validator("age_groups", mode="before")
    @classmethod
    def _optional_ages(cls, value: object) -> object:
        return [] if value is None else value


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
  use a uniquely identifying listed name; never invent a product or guess between different products with the same name;
- the change on the test shelf, only what the question asks about: package (a listed product image, exactly as
  listed, shown instead of the product's pack), price (a new shelf price in major units of {currency}), promo (a short
  sign such as NEW, SALE, 1+1 or -20%); at least one of them;
- age_groups only when the question names an age group; otherwise leave it empty (everyone);
- a short name and rationale.
If a listed product or image name exceeds 160 characters, copy its first 160 characters.
That prefix must identify one target; do not abbreviate shorter names or guess between ambiguous targets.
Use "" for unspecified package, promo and rationale, and [] for unspecified age_groups; do not use null for these fields.
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
    skus_by_name: dict[str, set[str]] = {}
    first_rack: dict[str, str] = {}
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                skus_by_name.setdefault(item.name.strip().casefold(), set()).add(item.sku)
                first_rack.setdefault(item.sku, rack.id)
    hit = resolve_listed(draft.product, skus_by_name, max_name_length=160)
    if hit is None:
        raise ValueError(f'the model chose "{draft.product}", which is not a product of this layout')
    if len(hit) > 1:
        raise ValueError(f'several products of this layout are called "{draft.product}"; choose the product below')
    sku = next(iter(hit))
    rack_id = first_rack[sku]
    warnings: list[str] = []
    changes: list[VariantChange] = []
    if draft.package.strip():
        images: dict[str, set[str]] = {}
        for name, aid in packages:
            images.setdefault(name.strip().casefold(), set()).add(aid)
        asset = resolve_listed(draft.package, images, max_name_length=160)
        if asset is None or len(asset) != 1:
            warnings.append(f'No unique product image "{draft.package}" in the library (missing or ambiguous name); '
                            "the pack change was left out.")
        else:
            changes.append(VariantChange(kind="package", sku=sku, asset_id=next(iter(asset))))
    if draft.price is not None and draft.price > 0:
        zero = currency.upper() in ZERO_DECIMAL
        if not isfinite(draft.price):
            warnings.append("The new price is not finite; the price change was left out.")
        else:
            amount = Decimal(str(draft.price)) * (1 if zero else 100)
            if amount > MAX_PRICE:
                warnings.append("The new price exceeds the safe integer limit; the price change was left out.")
            else:
                price = int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                if price == 0:
                    warnings.append(f"The new price rounds to zero in {currency.upper()}; the price change was left out.")
                else:
                    changes.append(VariantChange(kind="price", sku=sku, price=price, keep_reference=True))
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
    class ShelfDraft(_Draft):
        @model_validator(mode="after")
        def usable_target(self) -> Self:
            to_design(self, store, currency, packages)
            return self

    draft = await llm.generate_structured_async(
        ShelfDraft, DESIGN_PROMPT.format(currency=currency.upper()),
        f"{_listing(store, currency, packages, question)}\n\nQuestion: {question.strip()}", max_retries=2, seed=0,
    )
    return to_design(draft, store, currency, packages)
