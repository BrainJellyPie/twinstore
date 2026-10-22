"""Shoppers who share one store.

The engines decide each shopper's visit on their own (in parallel, the model calls unchanged). This pass then plays
all visits of a day in clock order against one store: a product a shopper takes is gone for the next one until staff
fill the shelf again, and shoppers with something to pay wait for a till to come free. A shopper who finds a product
gone takes another one from the same shelf face (a seeded share of them) or does without; a shopper whose wait at the
tills runs past their patience leaves the line and the basket goes back to the shelves.

Every draw here is keyed by (run seed, shopper, day, step), never by the layout, so two layouts run on the same seed
still face the same shoppers with the same patience (common random numbers)."""

import bisect
import heapq
import logging
import math
import random
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.operations import (
    BackroomStats, EmptySpell, OperationsConfig, OperationsReport, QueueHour, StockoutStats,
)
from store_emulator.domain.rack import SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, Weekday, stable_seed

logger = logging.getLogger(__name__)

type FaceKey = tuple[str, Face, str]   # rack id, shelf face, SKU

# Events of the same second: shelves are filled first, put-back baskets land next, then picks, then the tills, and
# last the crew picks up its next refill (so a shopper reaching the tills that second is served first).
_RESTOCK, _FACE_DONE, _PUT_BACK, _PICK, _PAY, _CREW = 0, 1, 2, 3, 4, 5
_MAX_COUNTERS_ADVISED = 30
_STOCKOUTS_REPORTED = 60
_SPELLS_REPORTED = 3000


@dataclass
class _Product:
    """One product on one shelf face."""
    item: SlotItem
    full: int
    stats: StockoutStats


@dataclass
class _Checkout:
    """What a shopper did at the tills."""
    pay_index: int
    arrived: float              # clock second the shopper reached the till
    units: int = 0              # units in the basket on reaching the till
    spend: int = 0
    wait: float = 0.0
    service: float = 0.0
    abandoned: bool = False
    nothing_to_pay: bool = False


@dataclass
class _Day:
    day: int = 0
    stock: dict[FaceKey, int] = field(default_factory=dict[FaceKey, int])
    empty_since: dict[FaceKey, float] = field(default_factory=dict[FaceKey, float])
    spells: list[EmptySpell] = field(default_factory=list[EmptySpell])
    # Each shelf's stops (start, end, shopper), sorted: who stands at a shelf when someone else picks there.
    stops: dict[str, list[tuple[float, float, int]]] = field(default_factory=dict[str, list[tuple[float, float, int]]])
    longest_stop: int = 1

    touched: list[FaceKey] | None = None   # with a crew: faces a pick took units from, for the crew to look at


@dataclass
class _Backroom:
    """Units behind the shelves, per product with a finite backroom (others never run short)."""
    units: dict[str, int]
    levels: dict[str, int]
    stats: dict[str, BackroomStats]
    carry: dict[FaceKey, int] | None = None   # the shelves as the last day closed (they are not emptied overnight)

    def take(self, sku: str, wanted: int, day: int, moment: float) -> int:
        """Units staff can move to the shelf: what is wanted, or what the backroom has."""
        if sku not in self.units or wanted <= 0:
            return max(0, wanted)
        taken = min(wanted, self.units[sku])
        self.units[sku] -= taken
        stats = self.stats[sku]
        stats.refilled += taken
        stats.short_units += wanted - taken
        if self.units[sku] == 0 and not stats.dry_at and wanted > taken:
            stats.dry_day, stats.dry_at = day, _hms(moment)
        return taken


def _backroom(config: OperationsConfig, products: dict[FaceKey, "_Product"]) -> _Backroom | None:
    names = {sku: product.item.name for (_, _, sku), product in products.items()}
    levels: dict[str, int] = {}
    for sku in names:
        level = config.backroom_overrides.get(sku, config.backroom_per_product)
        if level is not None:
            levels[sku] = level
    if not levels:
        return None
    return _Backroom(units=dict(levels), levels=levels,
                     stats={sku: BackroomStats(sku=sku, name=names[sku], level=level) for sku, level in levels.items()})


@dataclass
class _Crew:
    """With OperationsConfig.crew: when each staff member is next free, and the shelf faces waiting for a refill."""
    config: OperationsConfig
    tills: int
    keys: list[FaceKey]
    free: list[float]
    waiting: dict[FaceKey, float] = field(default_factory=dict[FaceKey, float])     # face → since (refill point)
    working: dict[FaceKey, float] = field(default_factory=dict[FaceKey, float])     # face being refilled → since
    dry: set[FaceKey] = field(default_factory=set[FaceKey])   # faces the backroom has nothing more for today
    queue: list[tuple[int, float, int]] = field(default_factory=list[tuple[int, float, int]])   # (low, since, face)
    serving: float = 0.0
    refilling: float = 0.0
    refills: int = 0
    waited: float = 0.0
    backlog: int = 0

    def low(self, stock: int, full: int) -> bool:
        return full > 0 and stock <= full * self.config.refill_at

    def note(self, key: FaceKey, face: int, stock: int, full: int, moment: float) -> None:
        """A face lost units: once it is down to its refill point it waits for whoever is free first."""
        if key in self.working or key in self.dry or not self.low(stock, full):
            return
        if key not in self.waiting:
            self.waiting[key] = moment
            self.backlog = max(self.backlog, len(self.waiting))
            heapq.heappush(self.queue, (int(stock > 0), moment, face))
        elif stock == 0:
            heapq.heappush(self.queue, (0, self.waiting[key], face))   # now empty: it goes before the low ones

    def dispatch(
        self, moment: float, on_duty: int, state: "_Day", products: dict[FaceKey, "_Product"],
        backroom: "_Backroom | None", heap: list[tuple[float, int, int, int]],
    ) -> None:
        """Free staff on duty take the next faces to refill: refill-only staff first, the till staff last (the first
        of them only when alone on duty)."""
        for member in range(min(on_duty, len(self.free)) - 1, -1, -1):
            if self.free[member] > moment or (member == 0 and on_duty > 1 and self.tills > 0):
                continue
            while self.queue:
                _, since, face = heapq.heappop(self.queue)
                key = self.keys[face]
                if self.waiting.get(key) != since:
                    continue   # already refilled, or a stale entry for a face that has since emptied
                product = products[key]
                if not self.low(state.stock[key], product.full):
                    del self.waiting[key]   # a basket put back lifted it over its refill point
                    continue
                wanted = product.full - state.stock[key]
                units = wanted if backroom is None or key[2] not in backroom.units else min(wanted, backroom.units[key[2]])
                del self.waiting[key]
                if units == 0:
                    if backroom is not None:
                        backroom.take(key[2], wanted, state.day, moment)   # counted short: nothing to bring out
                    self.dry.add(key)
                    continue
                work = self.config.refill_face_sec + self.config.refill_unit_sec * units
                self.working[key] = since
                self.free[member] = moment + work
                self.refilling += work
                heapq.heappush(heap, (moment + work, _FACE_DONE, member, face))
                break


def _clock(hms: str) -> int:
    parts = (hms.split(":") + ["0", "0", "0"])[:3]
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def _hms(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def shelf_stock(store: Store, config: OperationsConfig) -> dict[FaceKey, _Product]:
    """Units of each product on each shelf face at opening: per shelf level carrying it."""
    products: dict[FaceKey, _Product] = {}
    for rack in store.racks:
        for slot in rack.slots:
            for item in slot.items:
                units = config.stock_overrides.get(item.sku, config.stock_per_facing)
                key = (rack.id, slot.face, item.sku)
                product = products.get(key)
                if product is None:
                    products[key] = _Product(item=item, full=units, stats=StockoutStats(
                        sku=item.sku, name=item.name, rack_id=rack.id, rack_name=rack.rack_name, stock=units,
                    ))
                else:
                    product.full += units
                    product.stats.stock += units
    return products


def resolve_shared_store(
    store: Store, results: list[CustomerResult], config: OperationsConfig, *, seed: int,
) -> tuple[list[CustomerResult], OperationsReport]:
    """The shoppers' results replayed in one shared store, and what sharing it did. The input is left as it is."""
    # The input stays as it is: each result gets its own list of events, and an event is copied only when this pass
    # changes it (copying them all took most of the time of a replay, and plans replay a run hundreds of times).
    results = [r.model_copy(update={"timeline": list(r.timeline)}) for r in results]
    copies = _Copies()
    products = shelf_stock(store, config)
    faces: dict[tuple[str, Face], list[FaceKey]] = defaultdict(list)
    for key in products:
        faces[(key[0], key[1])].append(key)
    tills = len(store.counters)
    if config.crew is not None:
        counters = min(tills, config.crew)
    else:
        counters = min(config.open_counters, tills) if config.open_counters is not None and tills else tills
    report = OperationsReport(config=config, counters=counters, counters_in_layout=tills)

    days: dict[Weekday, list[int]] = defaultdict(list)
    for index, result in enumerate(results):
        days[result.day].append(index)
    report.days = len(days)

    checkouts: dict[int, _Checkout] = {}
    hit: set[int] = set()
    open_seconds = 0.0
    busy_seconds = 0.0
    backroom = _backroom(config, products)
    if backroom is not None:
        report.backroom_units = sum(backroom.levels.values())
    for number, day in enumerate(sorted(days)):
        if backroom is not None and number > 0 and config.daily_delivery:
            short = {sku: level for sku, level in backroom.levels.items() if backroom.units[sku] < level}
            backroom.units.update(short)   # the morning delivery tops every backroom up to its level
            report.deliveries += int(bool(short))
        day_checkouts, day_open, day_busy = _play_day(
            store, results, days[day], products, faces, tills, counters, config, report, hit, seed, copies, backroom,
        )
        checkouts.update(day_checkouts)
        open_seconds += day_open
        busy_seconds += day_busy

    for index, checkout in checkouts.items():
        _apply_checkout(results[index], checkout, copies)
    for result in results:
        result.total_spent = sum(e.price * e.quantity for e in result.timeline if e.action == Action.BUY)
        result.leave_time = _hms(_clock(result.arrival_time) + result.duration_sec)

    if backroom is not None:
        report.refill_short_units = sum(s.short_units for s in backroom.stats.values())
        report.backroom = sorted((s for s in backroom.stats.values() if s.short_units),
                                 key=lambda s: (-s.short_units, s.sku))[:_STOCKOUTS_REPORTED]
    report.shoppers_hit = len(hit)
    report.stockout_faces = sum(1 for p in products.values() if p.stats.first_out)
    report.lost_units = sum(p.stats.lost_units for p in products.values())
    report.lost_revenue = sum(p.stats.lost_revenue for p in products.values())
    report.stockouts = sorted(
        (p.stats for p in products.values() if p.stats.first_out or p.stats.lost_units),
        key=lambda s: (-s.lost_revenue, -s.lost_units, -s.minutes_out, s.rack_id, s.sku),
    )[:_STOCKOUTS_REPORTED]
    for stats in report.stockouts:
        stats.minutes_out = round(stats.minutes_out, 1)
    report.till_hours = round(open_seconds / 3600, 2)
    if config.crew is not None:
        report.crew_hours = round(report.crew_hours, 2)
        report.crew_till_hours = round(report.crew_till_hours, 2)
        report.crew_refill_hours = round(report.crew_refill_hours, 2)
        report.refill_wait_min = round(report.refill_wait_min / report.face_refills, 1) if report.face_refills else 0.0
    _queue_summary(report, results, checkouts, config, tills, counters, open_seconds, busy_seconds)
    logger.info(
        f"[shared store] {report.days} day(s), {report.counters} till(s): {report.stockout_faces} faces ran out, "
        f"{report.lost_units} units lost, {report.substituted_units} substituted; {report.queued} shoppers queued, "
        f"avg wait {report.avg_wait_sec:.0f}s, {report.abandoned} left the line"
    )
    return results, report


def _play_day(
    store: Store,
    results: list[CustomerResult],
    indexes: list[int],
    products: dict[FaceKey, _Product],
    faces: dict[tuple[str, Face], list[FaceKey]],
    tills: int,
    counters: int,
    config: OperationsConfig,
    report: OperationsReport,
    hit: set[int],
    seed: int,
    copies: "_Copies",
    backroom: _Backroom | None = None,
) -> tuple[dict[int, _Checkout], float, float]:
    """One day in clock order. Returns each shopper's checkout, and the tills' open and serving seconds.

    With a finite backroom the shelves keep last night's stock and are filled from the backroom before opening and
    at each refill, as far as it goes; without one every day opens with full shelves.

    The tills share one line (first come, first served): a shopper takes the first till that is free and staffed."""
    if not indexes:
        return {}, 0.0, 0.0
    day = results[indexes[0]].day
    state = _Day(day=int(day), stock={key: product.full for key, product in products.items()})
    heap: list[tuple[float, int, int, int]] = []   # (clock second, kind, shopper, timeline index)
    start = math.inf
    end = 0.0
    for index in indexes:
        result = results[index]
        arrival = _clock(result.arrival_time)
        start = min(start, arrival)
        end = max(end, arrival + result.duration_sec)
        for k, event in enumerate(result.timeline):
            if event.action in (Action.BUY, Action.BROWSE) and event.target_rack:
                at = arrival + event.elapsed_sec
                duration = max(1, event.duration)
                state.longest_stop = max(state.longest_stop, duration)
                state.stops.setdefault(event.target_rack, []).append((at, at + duration, index))
            if event.action == Action.BUY:
                heapq.heappush(heap, (arrival + event.elapsed_sec, _PICK, index, k))
            elif event.action == Action.PAY:
                heapq.heappush(heap, (arrival + event.elapsed_sec, _PAY, index, k))
    for stops in state.stops.values():
        stops.sort()
    schedule = store.schedule_for(day)
    opening = schedule.open_hour * 3600 if schedule is not None and schedule.is_open else start // 3600 * 3600
    if backroom is not None and backroom.carry is not None:
        # Overnight the shelves keep what was left and staff fill them from the backroom, as far as it goes.
        for key, product in products.items():
            left = backroom.carry.get(key, product.full)
            state.stock[key] = left + backroom.take(key[2], product.full - left, int(day), opening)
    for key in products:
        if state.stock[key] == 0:   # stocked at zero, or not refilled overnight: out from opening
            _emptied(state, key, products[key], opening)
    crew: _Crew | None = None
    ids: dict[FaceKey, int] = {}
    close_at = schedule.close_hour * 3600 if schedule is not None and schedule.is_open else end
    if config.crew is not None:
        size = max([config.crew, *config.crew_schedule.values()])
        crew = _Crew(config=config, tills=tills, keys=list(products), free=[float(opening)] * size)
        ids = {key: face for face, key in enumerate(crew.keys)}
        state.touched = []
        for key, product in products.items():
            crew.note(key, ids[key], state.stock[key], product.full, opening)
        hour = float(opening)
        while hour < close_at:
            heapq.heappush(heap, (hour, _CREW, -1, -1))   # shifts change on the hour
            hour += 3600
    elif config.restock_every_min is not None:
        step = config.restock_every_min * 60
        moment = opening + step
        while moment < end:
            heapq.heappush(heap, (moment, _RESTOCK, -1, -1))
            moment += step

    def staffed(moment: float) -> int:
        return tills_open(config, tills, counters, int(moment) // 3600 % 24)

    def dispatch(moment: float) -> None:
        if crew is not None and opening <= moment < close_at:
            crew.dispatch(moment, crew_on_duty(config, int(moment) // 3600 % 24), state, products, backroom, heap)

    free = crew.free if crew is not None else [float(opening)] * tills
    busy = 0.0
    checkouts: dict[int, _Checkout] = {}
    last = 0.0
    while heap:
        moment, kind, index, k = heapq.heappop(heap)
        last = max(last, moment)
        if kind == _RESTOCK:
            refilled = False
            for key, product in products.items():
                if state.stock[key] < product.full:
                    moved = (backroom.take(key[2], product.full - state.stock[key], int(day), moment)
                             if backroom is not None else product.full - state.stock[key])
                    if moved:
                        state.stock[key] += moved
                        refilled = True
                        _refilled(state, key, product, moment)
            if refilled:
                report.restocks += 1
        elif kind == _FACE_DONE and crew is not None:
            key = crew.keys[k]
            since = crew.working.pop(key)
            product = products[key]
            wanted = product.full - state.stock[key]
            moved = backroom.take(key[2], wanted, int(day), moment) if backroom is not None else wanted
            if moved > 0:
                state.stock[key] += moved
                _refilled(state, key, product, moment)
            crew.refills += 1
            crew.waited += moment - since
            if backroom is not None and backroom.units.get(key[2], 1) == 0:
                crew.dry.add(key)   # the backroom ran out with this face: nothing more to bring out today
            crew.note(key, k, state.stock[key], product.full, moment)
            heapq.heappush(heap, (moment, _CREW, index, -1))
        elif kind == _CREW:
            dispatch(moment)
        elif kind == _PUT_BACK:
            _put_back(results[index], state, products, moment, copies)
        elif kind == _PICK:
            _pick(results[index], index, k, moment, state, products, faces, config, report, hit, seed, copies)
            if crew is not None and state.touched:
                for key in state.touched:
                    crew.note(key, ids[key], state.stock[key], products[key].full, moment)
                state.touched.clear()
                heapq.heappush(heap, (moment, _CREW, index, -1))
        else:
            result = results[index]
            units = sum(e.quantity for e in result.timeline if e.action == Action.BUY)
            spend = sum(e.price * e.quantity for e in result.timeline if e.action == Action.BUY)
            checkout = _Checkout(pay_index=k, arrived=moment, units=units, spend=spend)
            checkouts[index] = checkout
            if units == 0:
                checkout.nothing_to_pay = True
                continue
            if tills == 0:
                continue
            service = config.checkout_base_sec + config.checkout_item_sec * units
            till, begins = -1, math.inf
            for c in range(min(tills, len(free))):
                starts = _till_starts(c, max(moment, free[c]), staffed)
                if starts < begins:
                    till, begins = c, starts
            wait = begins - moment
            z = random.Random(stable_seed(seed, result.persona_id, int(result.day), "patience")).gauss(0.0, 1.0)
            patience = config.patience_sec * math.exp(config.patience_sd * z)
            if till < 0 or wait > patience:
                checkout.abandoned = True
                checkout.wait = patience
                heapq.heappush(heap, (moment + patience, _PUT_BACK, index, k))
                continue
            checkout.wait = wait
            checkout.service = service
            free[till] = begins + service
            busy += service
            if crew is not None:
                crew.serving += service
                heapq.heappush(heap, (begins + service, _CREW, till, -1))   # free again: back to the shelves
    closing = schedule.close_hour * 3600 if schedule is not None and schedule.is_open else max(end, last)
    closing = max(closing, last)
    if backroom is not None:
        backroom.carry = dict(state.stock)
    for key in list(state.empty_since):
        _refilled(state, key, products[key], closing)
    room = _SPELLS_REPORTED - len(report.empty_spells)
    report.empty_spells.extend(sorted(state.spells, key=lambda s: (s.start, s.rack_id, s.sku))[:max(0, room)])
    open_seconds = 0.0
    hour = float(opening)
    while hour < closing:
        open_seconds += staffed(hour) * (min(closing, hour + 3600) - hour)
        if crew is not None:
            report.crew_hours += crew_on_duty(config, int(hour) // 3600 % 24) * (min(closing, hour + 3600) - hour) / 3600
        hour += 3600
    if crew is not None:
        report.crew_till_hours += crew.serving / 3600
        report.crew_refill_hours += crew.refilling / 3600
        report.face_refills += crew.refills
        report.refill_wait_min += crew.waited / 60   # a total until resolve_shared_store averages it
        report.refill_backlog_max = max(report.refill_backlog_max, crew.backlog)
        report.refills_unfinished += len(crew.waiting)
    return checkouts, open_seconds, busy


def open_hours(store: Store, results: list[CustomerResult]) -> list[str]:
    """The hours ("HH") the store is open on the simulated days, or that shoppers were in it when it keeps no hours."""
    hours: set[int] = set()
    for day in {r.day for r in results}:
        schedule = store.schedule_for(day)
        if schedule is not None and schedule.is_open:
            hours.update(range(schedule.open_hour, schedule.close_hour))
    if not hours:
        for result in results:
            arrival = _clock(result.arrival_time)
            hours.update(range(arrival // 3600, min(24, (arrival + result.duration_sec) // 3600 + 1)))
    return [f"{hour:02d}" for hour in sorted(hours)]


def crew_on_duty(config: OperationsConfig, hour: int) -> int:
    """Crew on duty in an hour of the day: the hour's own number, else the run's (0 without a crew)."""
    if config.crew is None:
        return 0
    return config.crew_schedule.get(f"{hour:02d}", config.crew)


def tills_open(config: OperationsConfig, tills: int, counters: int, hour: int) -> int:
    """Tills staffed in an hour of the day: the hour's own number, else the run's, never more than the layout has.
    With a crew, as many tills as there is crew on duty."""
    if config.crew is not None:
        return min(tills, crew_on_duty(config, hour))
    return min(tills, config.till_schedule.get(f"{hour:02d}", counters))


def _till_starts(till: int, moment: float, staffed: Callable[[float], int]) -> float:
    """The first moment from `moment` on when the till is staffed (within two days; else never)."""
    for _ in range(48):
        if till < staffed(moment):
            return moment
        moment = (int(moment) // 3600 + 1) * 3600
    return math.inf


def _emptied(state: _Day, key: FaceKey, product: _Product, moment: float) -> None:
    if key not in state.empty_since:
        state.empty_since[key] = moment
    if not product.stats.first_out:
        product.stats.first_out = _hms(moment)


def _refilled(state: _Day, key: FaceKey, product: _Product, moment: float) -> None:
    since = state.empty_since.pop(key, None)
    if since is not None:
        product.stats.minutes_out += max(0.0, moment - since) / 60.0
        if moment > since:
            state.spells.append(EmptySpell(day=state.day, rack_id=key[0], face=str(key[1]), sku=key[2],
                                           name=product.item.name, start=round(since), end=round(moment)))


def _crowd(state: _Day, rack: str, moment: float, index: int) -> int:
    """Shoppers stopped at the shelf at that moment, this one included."""
    stops = state.stops.get(rack, [])
    first = bisect.bisect_left(stops, (moment - state.longest_stop,))
    last = bisect.bisect_right(stops, (moment, math.inf, math.inf))
    others = {shopper for began, ends, shopper in stops[first:last] if began <= moment < ends and shopper != index}
    return len(others) + 1


def _pick(
    result: CustomerResult,
    index: int,
    k: int,
    moment: float,
    state: _Day,
    products: dict[FaceKey, _Product],
    faces: dict[tuple[str, Face], list[FaceKey]],
    config: OperationsConfig,
    report: OperationsReport,
    hit: set[int],
    seed: int,
    copies: "_Copies",
) -> None:
    event = result.timeline[k]
    if event.face is None or not event.product_sku:
        return
    key = (event.target_rack, event.face, event.product_sku)
    product = products.get(key)
    if product is None:
        return
    if (config.crowd_limit is not None and event.origin == "impulse"
            and _crowd(state, event.target_rack, moment, index) >= config.crowd_limit
            and random.Random(stable_seed(seed, result.persona_id, int(result.day), event.product_sku, "crowded"))
            .random() < config.crowd_skip):
        # Too many people at the shelf: the shopper moves on without the unplanned pick.
        event = copies.event(result.timeline, k)
        report.crowd_skipped_units += event.quantity
        report.crowd_skipped_revenue += event.quantity * event.price
        event.action = Action.BROWSE
        event.description = _join(event.description, "too crowded at the shelf: moved on")
        return
    wanted = max(1, event.quantity)
    have = state.stock[key]
    if state.touched is not None:
        state.touched.append(key)
    if have >= wanted:
        state.stock[key] = have - wanted
        product.stats.sold_units += wanted
        if state.stock[key] == 0:
            _emptied(state, key, product, moment)
        return

    hit.add(index)
    product.stats.shoppers_missed += 1
    event = copies.event(result.timeline, k)
    if have > 0:
        # Fewer left than the shopper wanted: they take what there is.
        state.stock[key] = 0
        product.stats.sold_units += have
        _emptied(state, key, product, moment)
        _lost(result, product, wanted - have)
        event.quantity = have
        event.description = _join(event.description, f"only {have} left of {wanted} wanted")
        return

    # Keyed by the product, not the step: the same shopper meets the same sold-out product the same way in either
    # layout of a pair, however their route differs.
    rng = random.Random(stable_seed(seed, result.persona_id, int(result.day), event.product_sku, "sold out"))
    if rng.random() < config.substitute_share:
        options = [other for other in faces[(key[0], key[1])] if other != key and state.stock[other] > 0]
        if options:
            price = product.item.price
            choice = min(options, key=lambda o: (abs(products[o].item.price - price), products[o].item.price, o[2]))
            substitute = products[choice]
            taken = min(wanted, state.stock[choice])
            state.stock[choice] -= taken
            if state.touched is not None:
                state.touched.append(choice)
            substitute.stats.sold_units += taken
            if state.stock[choice] == 0:
                _emptied(state, choice, substitute, moment)
            product.stats.substituted_units += taken
            result.substituted_units += taken
            report.substituted_units += taken
            report.substituted_revenue += taken * substitute.item.price
            if taken < wanted:
                _lost(result, product, wanted - taken)
            event.description = _join(event.description, f"took {substitute.item.name}: {product.item.name} was sold out")
            event.product_sku = substitute.item.sku
            event.product_name = substitute.item.name
            event.price = substitute.item.price
            event.quantity = taken
            return
    _lost(result, product, wanted)
    event.action = Action.BROWSE
    event.quantity = 1
    event.description = _join(event.description, f"wanted {product.item.name}: sold out")


def _lost(result: CustomerResult, product: _Product, units: int) -> None:
    product.stats.lost_units += units
    product.stats.lost_revenue += units * product.item.price
    result.lost_units += units


def _put_back(
    result: CustomerResult, state: _Day, products: dict[FaceKey, _Product], moment: float, copies: "_Copies",
) -> None:
    """A shopper left the line: the basket goes back on the shelves."""
    for k, original in enumerate(result.timeline):
        if original.action != Action.BUY:
            continue
        event = copies.event(result.timeline, k)
        if event.face is not None and event.product_sku:
            key = (event.target_rack, event.face, event.product_sku)
            product = products.get(key)
            if product is not None:
                before = state.stock[key]
                state.stock[key] = min(product.full, before + event.quantity)
                product.stats.sold_units = max(0, product.stats.sold_units - event.quantity)
                if before == 0 and state.stock[key] > 0:
                    _refilled(state, key, product, moment)
        event.action = Action.BROWSE
        event.description = _join(event.description, "put back: left the line at the tills")


def _apply_checkout(result: CustomerResult, checkout: _Checkout, copies: "_Copies") -> None:
    """The wait at the tills moves the rest of the visit; a shopper who gave up leaves without paying."""
    timeline = result.timeline
    k = checkout.pay_index
    if k >= len(timeline) or timeline[k].action != Action.PAY:
        return
    pay = copies.event(timeline, k)
    if checkout.nothing_to_pay:
        pay.action = Action.WANDER
        pay.description = _join(pay.description, "nothing left to pay for")
        return
    old = pay.duration
    if checkout.abandoned:
        waited = round(checkout.wait)
        result.queue_wait_sec = waited
        result.left_queue = True
        pay.action = Action.WANDER
        pay.duration = waited
        pay.description = _join(pay.description, f"left the line after {_minutes(waited)} without paying")
        _shift(timeline, k + 1, waited - old, copies)
        return
    waited = round(checkout.wait)
    service = max(1, round(checkout.service)) if checkout.service else old
    result.queue_wait_sec = waited
    if waited:
        _shift(timeline, k, waited, copies)
        if waited >= 30:
            pay.description = _join(pay.description, f"waited {_minutes(waited)} for a till")
    pay.duration = service
    _shift(timeline, k + 1, service - old, copies)


def _shift(timeline: list[TimelineEvent], start: int, seconds: int, copies: "_Copies") -> None:
    if seconds == 0:
        return
    for k in range(start, len(timeline)):
        event = copies.event(timeline, k)
        event.elapsed_sec = max(0, event.elapsed_sec + seconds)


class _Copies:
    """Copy-on-write for the input's events: an event is copied the first time this pass changes it."""

    def __init__(self) -> None:
        self._own: set[int] = set()

    def event(self, timeline: list[TimelineEvent], k: int) -> TimelineEvent:
        event = timeline[k]
        if id(event) not in self._own:
            event = event.model_copy()
            timeline[k] = event
            self._own.add(id(event))
        return event


def _minutes(seconds: int) -> str:
    return f"{seconds} s" if seconds < 60 else f"{seconds / 60:.1f} min"


def _join(description: str, note: str) -> str:
    return f"{description} ({note})" if description else note


def _queue_summary(
    report: OperationsReport,
    results: list[CustomerResult],
    checkouts: dict[int, _Checkout],
    config: OperationsConfig,
    tills: int,
    counters: int,
    open_seconds: float,
    busy_seconds: float,
) -> None:
    queued = [(index, c) for index, c in checkouts.items() if not c.nothing_to_pay and tills > 0]
    report.queued = len(queued)
    waits = sorted(c.wait for _, c in queued)
    if waits:
        report.avg_wait_sec = round(sum(waits) / len(waits), 1)
        report.p90_wait_sec = round(waits[min(len(waits) - 1, math.ceil(0.9 * len(waits)) - 1)], 1)
        report.max_wait_sec = round(waits[-1], 1)
    for _, c in queued:
        if c.abandoned:
            report.abandoned += 1
            report.abandoned_units += c.units
            report.abandoned_revenue += c.spend
    report.counter_utilization = round(busy_seconds / open_seconds, 4) if open_seconds > 0 else 0.0

    hours: dict[str, QueueHour] = {}
    waits_by_hour: dict[str, list[float]] = defaultdict(list)
    for _, c in queued:
        hour = f"{int(c.arrived) // 3600 % 24:02d}"
        stats = hours.setdefault(hour, QueueHour(hour=hour))
        stats.arrivals += 1
        stats.abandoned += int(c.abandoned)
        waits_by_hour[hour].append(c.wait)
    for hour, values in waits_by_hour.items():
        hours[hour].avg_wait_sec = round(sum(values) / len(values), 1)
        hours[hour].max_wait_sec = round(max(values), 1)
    needed = counters_needed([(results[index].day, c.arrived, c.units) for index, c in queued], config)
    for hour, stats in hours.items():
        stats.counters_needed = needed.get(hour, 1)
        stats.counters_open = tills_open(config, tills, counters, int(hour))
        stats.crew_on_duty = crew_on_duty(config, int(hour))
    report.hours = [hours[h] for h in sorted(hours)]
    report.counters_needed = max((h.counters_needed for h in report.hours), default=0)


def counters_needed(
    checkouts: list[tuple[Weekday, float, int]], config: OperationsConfig,
) -> dict[str, int]:
    """Per hour, the fewest tills keeping that hour's average wait within the target, with every shopper who had
    something to pay staying in line (patience set aside, so the advice does not count on shoppers giving up).
    `checkouts`: (day, clock second at the till, units) of each shopper with something to pay."""
    arrivals: dict[Weekday, list[tuple[float, float]]] = defaultdict(list)
    for day, arrived, units in checkouts:
        arrivals[day].append((arrived, config.checkout_base_sec + config.checkout_item_sec * max(1, units)))
    hours: set[str] = set()
    for queue in arrivals.values():
        queue.sort()
        hours.update(f"{int(t) // 3600 % 24:02d}" for t, _ in queue)
    advice: dict[str, int] = {}
    pending = set(hours)
    for tills in range(1, _MAX_COUNTERS_ADVISED + 1):
        if not pending:
            break
        waits: dict[str, list[float]] = defaultdict(list)
        for queue in arrivals.values():
            free = [0.0] * tills
            for moment, service in queue:
                till = min(range(tills), key=lambda c: (free[c], c))
                begins = max(moment, free[till])
                free[till] = begins + service
                waits[f"{int(moment) // 3600 % 24:02d}"].append(begins - moment)
        for hour in list(pending):
            values = waits[hour]
            if sum(values) / len(values) <= config.target_wait_sec:
                advice[hour] = tills
                pending.discard(hour)
    for hour in pending:
        advice[hour] = _MAX_COUNTERS_ADVISED
    return advice
