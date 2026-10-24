"""Shoppers of a run found from a sentence.

"Women in their twenties who stopped at the ice cream freezers but bought nothing after 3 pm" becomes a filter the
run can be checked against: persona groups and purpose words, what they bought or not, where they stopped, when they
came, how much they spent and how long they stayed. The model only writes the filter; matching is done here, on the
run's own records, so every shopper listed really fits it.
"""

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import re
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.persona import AgeGroup, Gender, Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action
from store_emulator.engine.prompting import display_price, resolve_listed

ZERO_DECIMAL = {"KRW", "JPY", "VND", "CLP", "ISK", "HUF", "TWD", "IDR"}
type ShopperSort = Literal["spent", "nothing", "impulse", "longest"]
type Check = Callable[[str, CustomerResult], bool]


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Filter(BaseModel):
    label: str = Field(max_length=60, description="a short name for the group, e.g. 'Afternoon freezer browsers'")
    age_groups: list[AgeGroup] = Field(default_factory=list[AgeGroup])
    genders: list[Gender] = Field(default_factory=list[Gender])
    persona_words: list[str] = Field(default_factory=list[str], max_length=6,
                                     description="words from who they are or why they came, e.g. 'student', 'lunch'")
    bought: Literal["any", "yes", "no"] = "any"
    impulse: bool = Field(default=False, description="only shoppers who bought something on impulse")
    stopped_at: list[str] = Field(default_factory=list[str], max_length=6,
                                  description="listed shelves, exactly as listed; a shopper fits by stopping at any of them")
    bought_there: Literal["any", "yes", "no"] = Field(
        default="any", description="with stopped_at: whether they bought from those shelves (no = stopped but bought nothing there)")
    bought_products: list[str] = Field(default_factory=list[str], max_length=6,
                                       description="listed products, exactly as listed; a shopper fits by buying any of them")
    skipped_products: list[str] = Field(default_factory=list[str], max_length=6,
                                        description="listed products they did not buy")
    arrived_after: str = Field(default="", description="HH:MM, inclusive")
    arrived_before: str = Field(default="", description="HH:MM, exclusive")
    min_spent: float | None = Field(default=None, ge=0, allow_inf_nan=False, description="major units")
    max_spent: float | None = Field(default=None, ge=0, allow_inf_nan=False, description="major units")
    min_minutes: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_minutes: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    sort: ShopperSort = "spent"


class ShopperMatch(BaseModel):
    label: str
    persona_ids: list[str] = []       # every match, in the chosen order
    total: int = 0                    # shoppers in the run
    criteria: list[str] = []          # the filter in words, as applied
    warnings: list[str] = []
    sort: ShopperSort = "spent"
    near_misses: list[str] = []       # when nobody fits: how many would without each condition


FILTER_PROMPT = """You turn a store manager's description of a group of shoppers into a filter over one simulated
trading day. Set only what the description asks for and leave the rest empty:
- age_groups (10s, 20s, 30s, 40s, 50s, 60s+) and genders (Female, Male);
- persona_words: words from who the shoppers are or why they came (e.g. student, office, lunch, commute), matched
  against their persona;
- bought: yes, no or any for the whole trip; impulse: true for shoppers who bought something on impulse;
- stopped_at: shelves they stopped at (any of them), bought_products: products they bought (any of them),
  skipped_products: products they did not buy (none of them), all exactly as listed; bought_there: no for shoppers
  who stopped at those shelves but bought nothing there (use it, not bought, when the description is about the
  shelves), yes for those who bought there;
- arrived_after and arrived_before as HH:MM; min_spent and max_spent in major units of {currency}; min_minutes and
  max_minutes for the length of the visit;
  use valid 24-hour clocks, from 00:00 through 23:59 (24:00 means the end of the day); leave unspecified times empty;
- sort: spent (biggest spenders first), nothing (longest browsing without buying), impulse, or longest (visit);
- a short label for the group.
Write in English."""


def _clock(text: str) -> int | None:
    match = re.fullmatch(r"([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?", text.strip())
    if match is None:
        return None
    h, m, s = int(match[1]), int(match[2]), int(match[3] or 0)
    if h > 24 or m >= 60 or s >= 60 or (h == 24 and (m or s)):
        return None
    return h * 3600 + m * 60 + s


def _listing(store: Store, currency: str) -> str:
    shelves = list(dict.fromkeys(r.rack_name for r in store.product_racks if r.rack_name))
    products = list(dict.fromkeys(i.name for r in store.product_racks for s in r.slots for i in s.items))
    return (f"Shelves: {', '.join(shelves)}\nProducts: {'; '.join(products[:200])}\n"
            f"Prices are in {currency.upper()}; e.g. {display_price(500 if currency.upper() not in ZERO_DECIMAL else 5000, currency)}.")


def apply_filter(
    f: _Filter, customers: Mapping[str, CustomerResult], personas: Mapping[str, Persona], store: Store, currency: str,
) -> ShopperMatch:
    """The run's shoppers that fit the filter, sorted, with the filter in words and what could not be applied."""
    warnings: list[str] = []
    shelves: dict[str, set[str]] = {}
    skus: dict[str, set[str]] = {}
    for rack in store.product_racks:
        if rack.rack_name.strip():
            shelves.setdefault(rack.rack_name.strip().casefold(), set()).add(rack.id)
        for slot in rack.slots:
            for item in slot.items:
                skus.setdefault(item.name.strip().casefold(), set()).add(item.sku)

    def resolve(names: Sequence[str], listed: dict[str, set[str]], what: str) -> list[tuple[str, set[str]]]:
        out: list[tuple[str, set[str]]] = []
        for name in names:
            hit = resolve_listed(name, listed)
            if hit is None:
                warnings.append(f'No {what} "{name}" in this store; that condition was left out.')
            else:
                out.append((name.strip(), hit))
        return out

    stops = resolve(f.stopped_at, shelves, "shelf")
    wanted = resolve(f.bought_products, skus, "product")
    skipped = resolve(f.skipped_products, skus, "product")
    after, before = _clock(f.arrived_after) if f.arrived_after else None, _clock(f.arrived_before) if f.arrived_before else None
    if f.arrived_after and after is None:
        warnings.append(f'"{f.arrived_after}" is not a time; the arrival condition was left out.')
    if f.arrived_before and before is None:
        warnings.append(f'"{f.arrived_before}" is not a time; the arrival condition was left out.')
    scale = 1 if currency.upper() in ZERO_DECIMAL else 100
    # Inclusive inequalities use the next/previous representable minor unit,
    # not nearest-price rounding (at least $1.005 means at least 101 cents).
    min_spent = None if f.min_spent is None else int((Decimal(str(f.min_spent)) * scale).to_integral_value(rounding=ROUND_CEILING))
    max_spent = None if f.max_spent is None else int((Decimal(str(f.max_spent)) * scale).to_integral_value(rounding=ROUND_FLOOR))
    words = [w.strip().casefold() for w in f.persona_words if w.strip()]
    trip_nothing = f.bought == "no"
    if trip_nothing and f.bought_there == "no" and stops:
        # Both say "bought nothing"; tied to shelves it means nothing there (an empty basket is asked for separately).
        trip_nothing = False
        warnings.append('"Bought nothing" was read as nothing bought at those shelves; ask for "bought nothing at all" '
                        "to require an empty basket.")

    conds: list[tuple[str, Check]] = []

    def persona_of(pid: str) -> Persona | None:
        return personas.get(pid)

    def visited(c: CustomerResult) -> set[str]:
        return {e.target_rack for e in c.timeline if e.action in (Action.BROWSE, Action.BUY) and e.target_rack}

    if f.age_groups:
        conds.append((f"Age: {', '.join(f.age_groups)}",
                      lambda pid, _c: (p := persona_of(pid)) is not None and p.age_group in f.age_groups))
    if f.genders:
        conds.append((f"Gender: {', '.join(f.genders)}",
                      lambda pid, _c: (p := persona_of(pid)) is not None and p.gender in f.genders))
    if words:
        def mentions(pid: str, _c: CustomerResult) -> bool:
            p = persona_of(pid)
            text = f"{p.identity} {p.purpose} {p.intent} {p.description}".casefold() if p else ""
            return any(w in text for w in words)
        conds.append((f"Persona mentions: {', '.join(words)}", mentions))
    if f.bought == "yes":
        conds.append(("Bought something", lambda _pid, c: bool(c.purchases)))
    elif trip_nothing:
        conds.append(("Bought nothing", lambda _pid, c: not c.purchases))
    if f.impulse:
        conds.append(("Bought on impulse", lambda _pid, c: any(e.origin == "impulse" for e in c.purchases)))
    if stops:
        racks: set[str] = {rack for _, ids in stops for rack in ids}
        names = " or ".join(name for name, _ in stops)
        conds.append((f"Stopped at {names}", lambda _pid, c: bool(racks & visited(c))))
        if f.bought_there != "any":
            want = f.bought_there == "yes"
            conds.append((f"Bought {'something' if want else 'nothing'} at {names}",
                          lambda _pid, c: any(e.target_rack in racks for e in c.purchases) == want))
    if wanted:
        conds.append((f"Bought {' or '.join(name for name, _ in wanted)}",
                      lambda _pid, c: any(ids & {e.product_sku for e in c.purchases} for _, ids in wanted)))
    for name, ids in skipped:
        conds.append((f"Did not buy {name}", lambda _pid, c, ids=ids: not (ids & {e.product_sku for e in c.purchases})))
    if after is not None:
        conds.append((f"Arrived at or after {f.arrived_after.strip()}",
                      lambda _pid, c: (t := _clock(c.arrival_time)) is not None and t >= after))
    if before is not None:
        conds.append((f"Arrived before {f.arrived_before.strip()}",
                      lambda _pid, c: (t := _clock(c.arrival_time)) is not None and t < before))
    if min_spent is not None:
        conds.append((f"Spent at least {display_price(min_spent, currency)}", lambda _pid, c: c.total_spent >= min_spent))
    if max_spent is not None:
        conds.append((f"Spent at most {display_price(max_spent, currency)}", lambda _pid, c: c.total_spent <= max_spent))
    if f.min_minutes is not None:
        low = f.min_minutes
        conds.append((f"Stayed at least {low:g} min", lambda _pid, c: c.duration_sec / 60 >= low))
    if f.max_minutes is not None:
        high = f.max_minutes
        conds.append((f"Stayed at most {high:g} min", lambda _pid, c: c.duration_sec / 60 <= high))
    criteria = [label for label, _ in conds]

    def fits(pid: str, c: CustomerResult, skip: int = -1) -> bool:
        return all(check(pid, c) for i, (_, check) in enumerate(conds) if i != skip)

    matched = [(pid, c) for pid, c in customers.items() if fits(pid, c)]
    browse = {pid: sum(1 for e in c.timeline if e.action == Action.BROWSE) for pid, c in matched}
    impulse = {pid: sum(e.quantity for e in c.purchases if e.origin == "impulse") for pid, c in matched}
    def order(m: tuple[str, CustomerResult]) -> tuple[int, str]:
        pid, c = m
        match f.sort:
            case "spent":
                return -c.total_spent, pid
            case "nothing":
                return -browse[pid], pid
            case "impulse":
                return -impulse[pid], pid
            case "longest":
                return -c.duration_sec, pid

    matched.sort(key=order)
    near: list[str] = []
    if not matched and len(conds) > 1:
        # Which single condition keeps everyone out: the count without it, largest first.
        counts = [(sum(1 for pid, c in customers.items() if fits(pid, c, skip=i)), label) for i, (label, _) in enumerate(conds)]
        near = [f'Without "{label}": {n} shopper{"" if n == 1 else "s"}' for n, label in sorted(counts, key=lambda x: -x[0])[:3] if n]
    return ShopperMatch(label=f.label.strip() or "Matching shoppers", persona_ids=[pid for pid, _ in matched],
                        total=len(customers), criteria=criteria or ["Everyone"], warnings=warnings, sort=f.sort,
                        near_misses=near)


async def find_shoppers(
    llm: StructuredLLM, text: str, customers: Mapping[str, CustomerResult], personas: Mapping[str, Persona],
    store: Store, currency: str,
) -> ShopperMatch:
    class TimedFilter(_Filter):
        @field_validator("arrived_after", "arrived_before")
        @classmethod
        def valid_clock(cls, value: str) -> str:
            if value and _clock(value) is None:
                raise ValueError(f"{value!r} is not a valid HH:MM 24-hour clock. Correct the requested time; "
                                 "use an empty string only when no time condition was requested.")
            return value

    f = await llm.generate_structured_async(
        TimedFilter, FILTER_PROMPT.format(currency=currency.upper()),
        f"{_listing(store, currency)}\n\nShoppers wanted: {text.strip()}", max_retries=2, seed=0,
    )
    return apply_filter(f, customers, personas, store, currency)
