"""Layout edits written in words.

"Put the Coca-Cola at eye level, 10 % off all ice cream and a SALE sign on the chips" becomes the same edits the A/B
builder makes (price, discount, sign, move, category price), on products and shelves of the layout, checked by
applying them to a copy. Nothing is saved until the user keeps the result as a new layout.
"""

from collections.abc import Mapping
from typing import Literal, Protocol, Self

from pydantic import BaseModel, Field, model_validator

from store_emulator.domain.marketing import VariantChange
from store_emulator.domain.store import Store
from store_emulator.engine.marketing.experiment_design import (
    _Change,  # pyright: ignore[reportPrivateUsage]
    _Draft,  # pyright: ignore[reportPrivateUsage]
    _listing,  # pyright: ignore[reportPrivateUsage]
    _Variant,  # pyright: ignore[reportPrivateUsage]
    to_design,
)
from store_emulator.engine.marketing.variants import apply_changes

ZERO_DECIMAL = {"KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"}
EDIT_KINDS = ("price", "discount", "promo", "move", "category_price")


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _EditChange(BaseModel):
    kind: Literal["price", "discount", "promo", "move", "category_price"]
    product: str = Field(default="", max_length=120, description="the listed product, exactly as listed")
    price: float | None = Field(default=None, description="price: the new shelf price in major units (e.g. 1.99)")
    percent: float | None = Field(default=None, ge=-90, le=300, description="discount (negative) or category_price change")
    promo: str = Field(default="", max_length=24, description="promo: the sign text, e.g. '1+1', 'SALE', '-30%'")
    shelf: str = Field(default="", max_length=80, description="move: the listed shelf, exactly as listed")
    level: int | None = Field(default=None, ge=1, le=4, description="move: shelf level, 3 = eye level, 1 = bottom")
    category: str = Field(default="", max_length=60, description="category_price: a shelf or category word")


class _EditDraft(BaseModel):
    name: str = Field(max_length=40, description="a short name for the edited layout")
    changes: list[_EditChange] = Field(min_length=1, max_length=12)
    summary: str = Field(default="", max_length=400, description="one or two sentences on what the edits do")


class LayoutEditDraft(BaseModel):
    name: str
    source_sha256: str = ""
    summary: str = ""
    changes: list[VariantChange]
    applied: list[str] = []      # each change in words, as applied to a copy of the layout
    warnings: list[str] = []


EDIT_PROMPT = """You turn a store manager's instructions into edits of the store's layout:
- price: a new everyday shelf price (major units of {currency});
- discount: a cut by a negative percent, the old price shown as "was";
- promo: a sign such as "1+1", "SALE" or "-30%";
- move: the product to another listed shelf and level (3 = eye level, 1 = bottom); keep its shelf to change only the
  level;
- category_price: every price of a shelf or category changed by a percent.
Make exactly the edits the manager asked for, one change per product and edit, using only products and shelves listed
below, written exactly as listed. Return at least one change that fits a listed product or category. A discount
requires a negative percent. Prices must be finite and positive after currency rounding.
Return at least one applicable operation; correct unavailable moves or empty categories when validation reports them.
Name the edited layout in a few words and summarize the edits. Write in English."""


def to_edit(draft: _EditDraft, store: Store, currency: str) -> LayoutEditDraft:
    """The edits resolved like an A/B variant (SKUs, shelf ids, minor-unit prices), then applied to a copy."""
    changes = [_Change.model_validate(c.model_dump()) for c in draft.changes]
    # Every change is validated above. Layout instructions allow twelve changes; an A/B variant allows six.
    variant = _Variant.model_construct(name="Edit", changes=changes)
    try:
        design = to_design(_Draft(name=draft.name or "Edited layout", variants=[variant]), store, currency, [])
    except ValueError as e:
        raise ValueError(f"none of the edits fits this layout's products and shelves: {e}") from e
    changes = design.variants[0].changes
    _, applied, problems = apply_changes(store, changes, minor_per_major=1 if currency.upper() in ZERO_DECIMAL else 100)
    warnings = [w.removeprefix("Edit: ") for w in design.warnings]
    warnings.extend(p for p in problems if p not in warnings)
    return LayoutEditDraft(name=draft.name.strip()[:40] or "Edited layout", summary=draft.summary.strip(), changes=changes,
                           applied=applied, warnings=list(dict.fromkeys(warnings)))


async def draft_layout_edit(
    llm: StructuredLLM, text: str, store: Store, currency: str, sold: Mapping[str, int] | None = None,
) -> LayoutEditDraft:
    class EditDraft(_EditDraft):
        @model_validator(mode="after")
        def usable_changes(self) -> Self:
            to_edit(self, store, currency)
            return self

    draft = await llm.generate_structured_async(
        EditDraft, EDIT_PROMPT.format(currency=currency.upper()),
        f"{_listing(store, currency, [], text, sold)}\n\nInstructions: {text.strip()}", max_retries=2, seed=0,
    )
    return to_edit(draft, store, currency)


def apply_layout_edit(store: Store, changes: list[VariantChange], currency: str) -> tuple[Store, list[str], list[str]]:
    """The edited layout, the edits in words and what could not be applied (package changes are test-only)."""
    kept = [c for c in changes if c.kind in EDIT_KINDS]
    skipped = ["a new package is only shown in tests, not saved to a layout"] if len(kept) < len(changes) else []
    # A saved layout's category price change is its new everyday price, not a test against the old one.
    edited, applied, problems = apply_changes(store, kept, minor_per_major=1 if currency.upper() in ZERO_DECIMAL else 100,
                                              remember_old_prices=False)
    return edited, applied, skipped + problems
