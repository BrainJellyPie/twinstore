"""The same customers in both twins: an online run that drew its shoppers from the project's customers, read next to a
store run of those customers — who bought in the store, online, in both or in neither, what they spent in each, and
how that splits by age and gender. Both runs are simulations of the same people, not observed channel choices."""

from pathlib import Path

from pydantic import BaseModel

from store_emulator.domain.persona import Persona
from store_emulator.engine.prompting import display_price

from .errors import AppError
from .interview import _load  # pyright: ignore[reportPrivateUsage]
from .online import get_run
from .storage.io import DATA_DIR, read_json


class ChannelGroup(BaseModel):
    group: str  # an age group or gender as stored on the customer
    customers: int
    both: int
    store_only: int
    online_only: int
    neither: int


class ChannelMix(BaseModel):
    store_run_id: str
    store_run_at: str
    online_store: str  # the online run's first store, whose visits are read
    customers: int  # customers in both runs
    both: int
    store_only: int
    online_only: int
    neither: int
    store_spend: int  # what these customers spent in the store, in the store's currency
    online_spend: int  # what they paid online, in the online store's currency
    store_currency: str
    online_currency: str
    by_age: list[ChannelGroup]
    by_gender: list[ChannelGroup]


def _store_runs(pid: str) -> list[tuple[str, str]]:
    """(run id, created at) of the project's finished store runs, newest first."""
    runs = Path(DATA_DIR) / pid / "runs"
    folders: list[Path] = sorted(runs.iterdir()) if runs.is_dir() else []
    found: list[tuple[str, str]] = []
    for folder in folders:
        if not (folder / "output" / "timeline.json").is_file():
            continue
        try:
            created = str(read_json(folder / "status.json").get("created_at", ""))
        except (OSError, ValueError, AttributeError):  # missing or damaged: still a finished run
            created = ""
        found.append((folder.name, created))
    return sorted(found, key=lambda r: r[1], reverse=True)


def channel_mix(pid: str, online_run_id: str, store_run_id: str | None = None) -> ChannelMix | None:
    """`store_run_id`: the store run to read; by default the newest one that shares customers with the online run.
    None when no store run shares customers with it yet."""
    view = get_run(pid, online_run_id)
    result = view.result
    if result is None:
        raise AppError("This run has no results yet", 409)
    if view.status.request.source != "project":
        raise AppError("This run's shoppers are the built-in panel, not the store's customers", 400)
    online: dict[str, tuple[bool, int]] = {}
    for shopper in result.shoppers:
        visit = (result.visits or {}).get(shopper.id, [])
        if shopper.persona_id and visit:
            online[shopper.persona_id] = (visit[0].outcome == "purchased", visit[0].order_total)
    candidates = [r for r in _store_runs(pid) if store_run_id in (None, r[0])]
    if store_run_id is not None and not candidates:
        raise AppError(f"store run not found: {store_run_id}", 404)
    for run_id, created in candidates:
        customers, personas, _store, currency = _load(pid, run_id)
        shared = sorted(set(customers) & set(online))
        if not shared:
            continue
        in_store = {p: customers[p].total_spent > 0 for p in shared}

        def cells(ids: list[str], group: str) -> ChannelGroup:
            return ChannelGroup(
                group=group, customers=len(ids),
                both=sum(in_store[p] and online[p][0] for p in ids),
                store_only=sum(in_store[p] and not online[p][0] for p in ids),
                online_only=sum(not in_store[p] and online[p][0] for p in ids),
                neither=sum(not in_store[p] and not online[p][0] for p in ids))

        def by(attribute: str) -> list[ChannelGroup]:
            groups: dict[str, list[str]] = {}
            for p in shared:
                persona: Persona | None = personas.get(p)
                groups.setdefault(str(getattr(persona, attribute, "")) if persona else "", []).append(p)
            return [cells(ids, group) for group, ids in sorted(groups.items()) if group]

        total = cells(shared, "all")
        return ChannelMix(
            store_run_id=run_id, store_run_at=created, online_store=result.variants[0].site_name, customers=len(shared),
            both=total.both, store_only=total.store_only, online_only=total.online_only, neither=total.neither,
            store_spend=sum(customers[p].total_spent for p in shared), online_spend=sum(online[p][1] for p in shared),
            store_currency=currency.upper(), online_currency=result.currency.upper(),
            by_age=by("age_group"), by_gender=by("gender"))
    return None


def channel_lines(mix: ChannelMix) -> list[str]:
    """The mix as fact-sheet lines for the online analyst."""
    def split(groups: list[ChannelGroup]) -> str:
        return "; ".join(f"{g.group} {g.customers} customers: both {g.both}, store only {g.store_only}, "
                         f"online only {g.online_only}, nowhere {g.neither}" for g in groups)

    lines = [f"Store and online (the same {mix.customers} customers in store run {mix.store_run_id} and online at "
             f"{mix.online_store}): bought in both {mix.both}, only in the store {mix.store_only}, only online "
             f"{mix.online_only}, nowhere {mix.neither}; spent in the store {display_price(mix.store_spend, mix.store_currency)}, "
             f"paid online {display_price(mix.online_spend, mix.online_currency)}."]
    if len(mix.by_age) > 1:
        lines.append(f"Store and online by age: {split(mix.by_age)}.")
    if len(mix.by_gender) > 1:
        lines.append(f"Store and online by gender: {split(mix.by_gender)}.")
    return lines
