import math
import random

from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Position, Weekday, stable_seed

from .route_builder import JourneyStep, entrance_position
from .store_lookup import rack_id_at, resolve_buy_placement


def build_timeline(
    persona_id: str,
    day: Weekday,
    arrival_time: str,
    journey: list[JourneyStep],
    store: Store,
    block_move_sec: float = 3,
    rng: random.Random | None = None,
    max_quantity: int = 6,
) -> CustomerResult:
    # Wander glances are the only randomness here; default to a stream keyed by the
    # customer so timelines are reproducible even when callers pass no rng.
    rng = rng or random.Random(stable_seed("timeline", persona_id, arrival_time))
    timeline: list[TimelineEvent] = []
    # Time runs as a float (fractional seconds per tile, diagonal steps of √2 tiles); events carry it
    # rounded to whole seconds.
    t = 0.0

    entrance = entrance_position(store)
    first_pos = journey[0].path[0] if journey and journey[0].path else entrance
    timeline.append(TimelineEvent(elapsed_sec=0, x=first_pos[0], y=first_pos[1], action=Action.ENTER))

    for step in journey:
        action_type = _resolve_action(step.action.action)

        # wander — constant-speed move with pause rhythm in front of racks.
        is_wander = step.action.nav == "area" and action_type == Action.WANDER
        if is_wander:
            wander_start = step.path[0] if step.path else _last_pos(step, timeline)
            timeline.append(TimelineEvent(
                elapsed_sec=round(t), x=wander_start[0], y=wander_start[1],
                action=Action.WANDER,
                description=step.action.description,
            ))

            rack_tiles = _rack_access_tiles(store)
            # The next journey leg starts at this path's endpoint. Reserve its
            # walking time before adding glances so pauses cannot truncate it.
            walking = sum(_step_sec(a, b, block_move_sec) for a, b in zip(step.path, step.path[1:]))
            budget = max(0.0, step.action.dwell - walking)

            for prev_pos, pos in zip(step.path, step.path[1:], strict=False):
                dt = _step_sec(prev_pos, pos, block_move_sec)
                t += dt
                timeline.append(TimelineEvent(elapsed_sec=round(t), x=pos[0], y=pos[1], action=Action.MOVE))

                if budget > 0 and pos in rack_tiles and rng.random() < _WANDER_GLANCE_PROB:
                    pause = min(budget, rng.randint(_WANDER_GLANCE_MIN, _WANDER_GLANCE_MAX))
                    timeline.append(TimelineEvent(
                        elapsed_sec=round(t), x=pos[0], y=pos[1],
                        action=Action.WANDER, duration=round(pause),
                    ))
                    t += pause
                    budget -= pause

            if budget > 0:
                t += budget
            continue
        else:
            for prev_pos, pos in zip(step.path, step.path[1:], strict=False):
                t += _step_sec(prev_pos, pos, block_move_sec)
                timeline.append(TimelineEvent(elapsed_sec=round(t), x=pos[0], y=pos[1], action=Action.MOVE))

        current_pos = _last_pos(step, timeline)

        # enter: merge the description into the very first event only.
        if action_type == Action.ENTER:
            if step.action.description:
                timeline[0].description = step.action.description
            t += _resolve_dwell(step, store)
            continue

        if step.action.nav == "leave":
            timeline.append(TimelineEvent(
                elapsed_sec=round(t), x=current_pos[0], y=current_pos[1], action=Action.EXIT,
            ))
            break

        target = step.action.target
        face = step.action.face
        te = TimelineEvent(
            elapsed_sec=round(t), x=current_pos[0], y=current_pos[1],
            action=action_type,
            target_rack=rack_id_at(store, target, face) if target else "",
            face=face,
            description=step.action.description,
            product_sku=step.action.product_sku,
            origin=step.action.origin if action_type in (Action.BROWSE, Action.BUY) else "",
        )
        if action_type == Action.BUY:
            te.quantity = max(1, min(max_quantity, step.action.quantity))

        if action_type == Action.PAY:
            for counter in store.counters:
                if current_pos in counter.service_access_tiles(store.grid_size):
                    te.target_rack = counter.id
                    break

        if action_type == Action.BUY and step.action.product_sku:
            placement = resolve_buy_placement(
                store,
                target=target,
                face=face,
                sku=step.action.product_sku,
                block=step.action.product_block, level=step.action.product_level,
            )
            if placement is not None:
                rack, slot = placement
                matched = next((i for i in slot.items if i.sku == step.action.product_sku), None)
                if matched is not None:
                    te.product_name = matched.name
                    te.price = matched.price
                # SKU + stance pin the placement exactly; override the
                # coordinate-based guess that may have picked a contested neighbour.
                te.target_rack = rack.id
                te.face = slot.face
                te.product_block = slot.block
                te.product_level = slot.level

        # A pick continues a stop only at the same resolved rack and face. Adjacent shelves can
        # share an access tile, and the SKU may correct an ambiguous coordinate-based rack guess.
        last = timeline[-1]
        continues = (action_type == Action.BUY and last.action == Action.BROWSE and len(step.path) <= 1
                     and (last.x, last.y) == current_pos and bool(te.target_rack)
                     and last.target_rack == te.target_rack and last.face == te.face)
        dwell = _resolve_dwell(step, store, floor=not continues, rack_id=te.target_rack)
        te.duration = dwell
        timeline.append(te)
        t += dwell

    total_spent = sum(e.price * e.quantity for e in timeline if e.action == Action.BUY)
    total_elapsed = timeline[-1].elapsed_sec if timeline else 0

    return CustomerResult(
        persona_id=persona_id,
        day=day,
        arrival_time=arrival_time,
        leave_time=_add_seconds(arrival_time, total_elapsed),
        timeline=timeline,
        total_spent=total_spent,
    )


def _step_sec(a: Position, b: Position, block_move_sec: float) -> float:
    """Walking time of one grid step: a tile, or √2 tiles on a diagonal."""
    return block_move_sec * (math.sqrt(2.0) if a[0] != b[0] and a[1] != b[1] else 1.0)


def _last_pos(step: JourneyStep, timeline: list[TimelineEvent]) -> Position:
    """Return the step's path endpoint; fall back to the previous timeline position."""
    if step.path:
        return step.path[-1]
    if timeline:
        return (timeline[-1].x, timeline[-1].y)
    return (0, 0)


def _resolve_action(action: Action | None) -> Action:
    return action if action is not None else Action.BROWSE


_GLOBAL_MAX_DWELL = 300  # Max allowed dwell (seconds) when rack lookup fails.
_WANDER_GLANCE_PROB = 0.5  # Probability of pausing in front of a rack.
_WANDER_GLANCE_MIN = 2  # Min rack-front pause (seconds).
_WANDER_GLANCE_MAX = 4  # Max rack-front pause (seconds).


def _resolve_dwell(step: JourneyStep, store: Store, *, floor: bool = True, rack_id: str = "") -> int:
    dwell = step.action.dwell
    target = step.action.target
    rack = next((r for r in store.racks if r.id == rack_id), None) if rack_id else None
    if rack is None and target is not None:
        rack = store.rack_at(target[0], target[1])
        if rack is None:
            for f in store.racks:
                if target in f.access_tiles(store.grid_size):
                    rack = f
                    break
    if rack:
        dwell = max(rack.dwell_min if floor else 1, min(rack.dwell_max, dwell))
    else:
        dwell = min(_GLOBAL_MAX_DWELL, dwell)
    return max(1, dwell)


def _rack_access_tiles(store: Store) -> set[Position]:
    """Access tiles for racks that carry products."""
    tiles: set[Position] = set()
    for rack in store.product_racks:
        tiles |= rack.access_tiles(store.grid_size)
    return tiles


def _add_seconds(time_str: str, seconds: int) -> str:
    parts = time_str.split(":")
    if len(parts) < 3:
        parts = ["0", "0", "0"]
    total = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) + seconds
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
