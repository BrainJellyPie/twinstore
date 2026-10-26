"""An A/B test drafted from the question the user wants answered.

"Does a 1+1 sign on Pepsi sell more than a 20 % cut?" becomes variants made of the builder's own changes (price,
discount, promo sign, move, new package, category price) on products and shelves that exist in the layout. The draft
only fills the builder; changes that point at nothing are dropped and reported.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_validator, model_validator

from store_emulator.domain.marketing import ExperimentEngine, Variant, VariantChange
from store_emulator.domain.store import Store
from store_emulator.engine.marketing.variants import apply_changes
from store_emulator.engine.prompting import canonical_identifier, display_price, relevant_first

ZERO_DECIMAL = {"KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"}
MAX_LISTED = 150
MAX_PRICE = 9_007_199_254_740_991


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


_USED_CHANGE_TEXT: dict[str, set[str]] = {
    "price": {"product"}, "discount": {"product"}, "promo": {"product", "promo"},
    "move": {"product", "shelf"}, "package": {"product", "package"}, "category_price": {"category"},
}


class _ChangeTextDefaults(BaseModel):
    @field_validator("kind", mode="before", check_fields=False)
    @classmethod
    def _canonical_kind(cls, value: object) -> object:
        return canonical_identifier(value, _USED_CHANGE_TEXT) if isinstance(value, str) else value

    @field_validator("product", "promo", "shelf", "package", "category", mode="before", check_fields=False)
    @classmethod
    def _unused_text(cls, value: object, info: ValidationInfo) -> object:
        # Both drafts validate kind before these fields. Only an irrelevant null
        # gets its empty default; never invent a missing target or promo message.
        used = _USED_CHANGE_TEXT.get(info.data.get("kind", ""))
        return "" if value is None and used is not None and info.field_name not in used else value


def _change_schema(schema: dict[str, JsonValue]) -> None:
    """Require each operation's actual target/value in the model's grammar."""
    fields = schema["properties"]
    assert isinstance(fields, dict)
    variants: list[JsonValue] = []
    used = {"price": ["product", "price"], "discount": ["product", "discount_basis", "percent"],
            "promo": ["product", "promo"], "move": ["product", "shelf", "level"],
            "package": ["product", "package"], "category_price": ["category", "percent"]}
    for kind, names in used.items():
        properties: dict[str, JsonValue] = {"kind": {"type": "string", "const": kind}}
        for name in names:
            source = fields[name]
            assert isinstance(source, dict)
            definition = dict(source)
            definition.pop("default", None)
            choices = definition.pop("anyOf", None)
            if isinstance(choices, list):
                value = next(choice for choice in choices if isinstance(choice, dict) and choice.get("type") != "null")
                assert isinstance(value, dict)
                definition.update(value)
            if name in {"product", "promo", "shelf", "package", "category"}:
                definition["minLength"] = 1
            if name == "price":
                definition["minimum"] = 0
            if kind == "discount" and name == "percent":
                definition.pop("maximum", None)
                definition["exclusiveMaximum"] = 0
            properties[name] = definition
        required: list[JsonValue] = ["kind", *names]
        if kind == "move":
            required.remove("level")  # Omitted level retains the editor's eye-level default.
        variants.append({"type": "object", "properties": properties, "required": required,
                         "additionalProperties": False})
    schema.clear()
    schema.update(title="Operation", anyOf=variants)


class _Change(_ChangeTextDefaults):
    model_config = ConfigDict(json_schema_extra=_change_schema)

    kind: Literal["price", "discount", "promo", "move", "package", "category_price"]
    product: str = Field(default="", max_length=120, description="the listed product, exactly as listed")
    price: float | None = Field(default=None, description="price: the new shelf price in major units (e.g. 1.99)")
    percent: float | None = Field(default=None, ge=-100, le=300, description="discount (negative) or category_price change")
    discount_basis: Literal["regular", "current"] = Field(default="regular",
        description="regular: set a discount from the original regular price; current: take an additional discount from the current selling price")
    promo: str = Field(default="", max_length=24, description="promo: the sign text, e.g. '1+1', 'SALE', '-30%'")
    shelf: str = Field(default="", max_length=80, description="move: the listed shelf, exactly as listed")
    level: int | None = Field(default=None, ge=1, le=4, description="move: shelf level, 3 = eye level, 1 = bottom")
    package: str = Field(default="", max_length=80, description="package: the listed product image, exactly as listed")
    category: str = Field(default="", max_length=60, description="category_price: a shelf or category word")


class _Variant(BaseModel):
    name: str = Field(max_length=40)
    changes: list[_Change] = Field(min_length=1, max_length=6)


class _Draft(BaseModel):
    name: str = Field(max_length=80)
    variants: list[_Variant] = Field(min_length=1, max_length=5)
    focus_products: list[str] = Field(default_factory=list[str], max_length=8)
    engine: Literal["rule", "vlm"] = "rule"
    rationale: str = Field(default="", max_length=500)

    @field_validator("engine", mode="before")
    @classmethod
    def _canonical_engine(cls, value: object) -> object:
        return canonical_identifier(value, ("rule", "vlm")) if isinstance(value, str) else value

    @field_validator("rationale", mode="before")
    @classmethod
    def _optional_rationale(cls, value: object) -> object:
        return "" if value is None else value

    @field_validator("focus_products", mode="before")
    @classmethod
    def _optional_focus(cls, value: object) -> object:
        return [] if value is None else value


class ExperimentDesign(BaseModel):
    name: str
    variants: list[Variant]
    focus_skus: list[str] = []
    engine: ExperimentEngine = "rule"
    rationale: str = ""
    warnings: list[str] = []


DISCOUNT_BASIS_PROMPT = """For each discount, set discount_basis="current" for an extra/additional reduction of the current selling price; use "regular" to set a discount against the original regular price.
Example: currently 4 with regular price 5, extra 10% off => kind=discount, percent=-10, discount_basis="current". Set 20% off the regular price => kind=discount, percent=-20, discount_basis="regular".
"""


DESIGN_PROMPT = """You design A/B tests for a store's digital twin. From the manager's question, draft up to four
variants against the unchanged layout (the control). Each variant is a short name and one or more changes:
- price: a new everyday shelf price (major units of {currency});
- discount: a cut by a negative percent, the old price shown as "was";
- promo: a sign such as "1+1", "SALE" or "-30%";
- move: the product to another listed shelf and level (3 = eye level, 1 = bottom);
- package: a listed product image shown instead of the product's pack (vision shoppers only);
- category_price: every price of a shelf or category changed by a percent.
Use only products, shelves and images listed below, written exactly as listed. Vary one thing per variant unless the
question asks for combinations, never name a variant "Control", list the products whose sales the question is about
in focus_products, choose engine "vlm" only when the test needs shoppers to see packs or signs, and give a short
rationale. Return at least one change that can be applied to a listed product or category. A discount requires a
negative percent. Prices must be finite and nonnegative. Use 0 for an explicitly free offer;
a positive price must remain positive after currency rounding. Omit the price operation to keep the current price.
Each variant needs an applicable operation. Correct unavailable moves or empty categories when validation reports them.
For text fields unused by a change's kind, use empty strings instead of null. Keep the required target and value explicit.
A promo operation must include its nonblank sign text; do not omit it or leave it empty.
Use the exact lowercase operation kinds above, including the underscore in category_price.
Use "" for an absent rationale and [] for unspecified focus_products, not null.
If a listed product, shelf or image name exceeds its field's character limit, copy its prefix up to that limit.
The prefix must identify one target; do not abbreviate shorter names or guess between ambiguous targets.
Write in English.""" + "\n" + DISCOUNT_BASIS_PROMPT


def _listing(store: Store, currency: str, packages: Sequence[tuple[str, str]], question: str = "",
             sold: Mapping[str, int] | None = None) -> str:
    items: dict[tuple[str, str, str, int, int], tuple[str, str, str]] = {}
    for rack in store.product_racks:
        for slot in rack.slots:
            for item in slot.items:
                units = f", {sold.get(item.sku, 0)} sold in the last run" if sold else ""
                items.setdefault((item.sku, item.name, rack.id, slot.level, item.price), (rack.rack_name, item.name,
                                             f"{item.name} {display_price(item.price, currency)} ({rack.rack_name}, level {slot.level}{units})"))
    shown = relevant_first(list(items.values()), question, MAX_LISTED)
    shelves = list(dict.fromkeys(r.rack_name for r in store.product_racks if r.rack_name))
    lines = [f"Products: {'; '.join(shown)}", f"Shelves: {', '.join(shelves)}"]
    if sold:
        lines.append("Sales figures are totals per SKU across all shelves; repeated placements do not add sales.")
    if packages:
        lines.append(f"Product images: {', '.join(name for name, _ in packages)}")
    return "\n".join(lines)


def _bounded_target(asked: str, targets: Mapping[str, set[str]], limit: int) -> str:
    """Resolve a complete name or a grammar-limited prefix only to one identity."""
    key = asked.strip().casefold()
    if not key:
        return ""
    matches = targets.get(key, set())
    if len(asked) == limit:
        # An exact name at the boundary can also be a longer name's prefix.
        # Include both before deciding; price and placement edits cannot guess.
        matches = {identifier for name, ids in targets.items() if name.startswith(key) for identifier in ids}
    return next(iter(matches)) if len(matches) == 1 else ""


def to_design(draft: _Draft, store: Store, currency: str, packages: Sequence[tuple[str, str]]) -> ExperimentDesign:
    """Draft changes resolved to SKUs, shelf ids, minor-unit prices and image ids; the rest is dropped and reported."""
    product_ids: dict[str, set[str]] = {}
    shelf_ids: dict[str, set[str]] = {}
    image_ids: dict[str, set[str]] = {}
    for rack in store.product_racks:
        if rack.rack_name.strip():
            shelf_ids.setdefault(rack.rack_name.strip().casefold(), set()).add(rack.id)
        for slot in rack.slots:
            for item in slot.items:
                product_ids.setdefault(item.name.strip().casefold(), set()).add(item.sku)
                # Tiny models sometimes copy the displayed price or the entire listing as the name.
                # Match only labels built from this store, and keep collisions ambiguous.
                priced = f"{item.name} {display_price(item.price, currency)}"
                for label in (priced, f"{priced} ({rack.rack_name}, level {slot.level})"):
                    product_ids.setdefault(label.strip().casefold(), set()).add(item.sku)
    for name, aid in packages:
        image_ids.setdefault(name.strip().casefold(), set()).add(aid)
    skus = {name: next(iter(ids)) for name, ids in product_ids.items() if len(ids) == 1}
    zero = currency.upper() in ZERO_DECIMAL
    warnings: list[str] = []
    variants: list[Variant] = []
    used: set[str] = {"control"}
    for v in draft.variants:
        changes: list[VariantChange] = []
        for c in v.changes:
            sku = _bounded_target(c.product, product_ids, 120)
            if c.kind != "category_price" and not sku:
                warnings.append(f'{v.name}: no unique product "{c.product}" in this layout (missing or ambiguous name); that change was left out.')
                continue
            match c.kind:
                case "price":
                    if c.price is None or not isfinite(c.price) or c.price < 0:
                        warnings.append(f"{v.name}: no new price for {c.product}; left out.")
                        continue
                    amount = Decimal(str(c.price)) * (1 if zero else 100)
                    if amount > MAX_PRICE:
                        warnings.append(f"{v.name}: the price for {c.product} exceeds the safe integer limit; left out.")
                        continue
                    price = int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                    if price == 0 and c.price > 0:
                        warnings.append(f"{v.name}: the price for {c.product} rounds to zero in {currency}; left out.")
                        continue
                    changes.append(VariantChange(kind="price", sku=sku, price=price,
                                                 keep_reference=True))
                case "discount":
                    if c.percent is None or c.percent >= 0:
                        warnings.append(f"{v.name}: a discount needs a negative percent; left out.")
                        continue
                    changes.append(VariantChange(kind="discount", sku=sku, percent=c.percent,
                                                 discount_basis=c.discount_basis))
                case "promo":
                    if not c.promo.strip():
                        raise ValueError("A promo operation needs explicit, nonblank sign text; do not invent a default promotion.")
                    changes.append(VariantChange(kind="promo", sku=sku, promo=c.promo.strip()))
                case "move":
                    rack = _bounded_target(c.shelf, shelf_ids, 80)
                    if not rack:
                        warnings.append(f'{v.name}: no unique shelf "{c.shelf}" in this layout (missing or ambiguous name); that move was left out.')
                        continue
                    changes.append(VariantChange(kind="move", sku=sku, rack_id=rack, level=c.level))
                case "package":
                    aid = _bounded_target(c.package, image_ids, 80)
                    if not aid:
                        warnings.append(f'{v.name}: no unique product image "{c.package}" (missing or ambiguous name); that change was left out.')
                        continue
                    changes.append(VariantChange(kind="package", sku=sku, asset_id=aid))
                case "category_price":
                    if c.percent is None or not c.category.strip():
                        warnings.append(f"{v.name}: a category price change needs a category and a percent; left out.")
                        continue
                    changes.append(VariantChange(kind="category_price", category=c.category.strip(), percent=c.percent))
        name = v.name.strip()[:40] or f"Variant {chr(66 + len(variants))}"
        base_name, number = name, len(variants) + 2
        while name.casefold() in used:
            suffix = f" ({number})"
            name = base_name[:40 - len(suffix)] + suffix
            number += 1
        if not changes:
            warnings.append(f"{v.name}: nothing left to change; the variant was left out.")
            continue
        _, applied, problems = apply_changes(store, changes, package_uris={aid: aid for _, aid in packages},
                                             minor_per_major=1 if zero else 100)
        warnings.extend(f"{name}: {p}" for p in problems)
        if not applied:
            warnings.append(f"{name}: no change could be applied; the variant was left out.")
            continue
        used.add(name.casefold())
        variants.append(Variant(name=name, changes=changes))
    if not variants:
        raise ValueError("the model drafted no change that fits this layout. " + " ".join(warnings[:3]))
    focus = list(dict.fromkeys(skus[p.strip().casefold()] for p in draft.focus_products if p.strip().casefold() in skus))
    if not focus:
        focus = list(dict.fromkeys(c.sku for v in variants for c in v.changes if c.sku))
    engine: ExperimentEngine = "vlm" if draft.engine == "vlm" or any(c.kind == "package" for v in variants for c in v.changes) else "rule"
    return ExperimentDesign(name=draft.name.strip()[:80], variants=variants, focus_skus=focus[:20], engine=engine,
                            rationale=draft.rationale.strip(), warnings=warnings)


async def design_experiment(
    llm: StructuredLLM, question: str, store: Store, currency: str, packages: Sequence[tuple[str, str]],
    sold: Mapping[str, int] | None = None,
) -> ExperimentDesign:
    """`sold`: units per SKU in the layout's last run, listed with each product so "the best seller" can be found."""
    class ExperimentDraft(_Draft):
        @model_validator(mode="after")
        def usable_changes(self) -> Self:
            to_design(self, store, currency, packages)
            return self

    draft = await llm.generate_structured_async(
        ExperimentDraft, DESIGN_PROMPT.format(currency=currency.upper()),
        f"{_listing(store, currency, packages, question, sold)}\n\nQuestion: {question.strip()}", max_retries=2, seed=0,
    )
    return to_design(draft, store, currency, packages)
