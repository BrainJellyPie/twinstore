"""An optimization set up from the goal the manager writes.

"More impulse sales, but keep the fridges and the cashier wall where they are, at most five changes" becomes the
optimizer's own settings: the objective, what may change (shelf contents, rack positions or both), how many moves
the result may differ by, which shelves stay locked (shelves of the layout, by name) and the smallest gain worth
keeping. Nothing starts; the settings fill the dialog.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from store_emulator.domain.optimize import OptimizeObjective, OptimizeScope
from store_emulator.domain.store import Store
from store_emulator.engine.prompting import resolve_listed


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Goal(BaseModel):
    objective: Literal["revenue_per_visitor", "total_revenue", "conversion_rate", "impulse_revenue",
                       "units_per_visitor", "walking_distance"] = "revenue_per_visitor"
    scope: Literal["planogram", "placement", "both"] = "planogram"
    max_moves: int | None = Field(default=None, description="how many changes the result may make, 1 to 50")
    keep_fridges_on_walls: bool | None = None
    locked_shelves: list[str] = Field(default_factory=list[str], max_length=20,
                                      description="listed shelves that must not change, exactly as listed")
    min_improvement_percent: float | None = Field(default=None, description="smallest gain worth keeping, in percent")
    rationale: str = Field(default="", max_length=400)

    @field_validator("rationale", mode="before")
    @classmethod
    def _optional_rationale(cls, value: object) -> object:
        return "" if value is None else value


class OptimizeGoal(BaseModel):
    objective: OptimizeObjective
    scope: OptimizeScope
    max_moves: int | None = None
    keep_fridges_on_walls: bool | None = None
    lock_rack_ids: list[str] = []
    locked: list[str] = []            # the locked shelves by name, as resolved
    min_improvement: float | None = None   # a fraction, as the optimizer takes it
    rationale: str = ""
    warnings: list[str] = []


GOAL_PROMPT = """You set up a store-layout optimizer from a manager's goal. Choose:
- objective: revenue_per_visitor, total_revenue, conversion_rate (share who buy), impulse_revenue (unplanned buys),
  units_per_visitor, or walking_distance (shorter walks; minimized);
- scope: planogram (move products between shelves and levels; fixtures stay), placement (move whole fixtures; their
  products travel with them), or both;
- max_moves only when the goal limits how much may change; keep_fridges_on_walls true or false only when the goal
  says so; locked_shelves: listed shelves the goal says must not change, exactly as listed; min_improvement_percent
  only when the goal names a smallest gain worth keeping;
- a short rationale; use an empty string, not null, when none is given.
Write in English."""


def to_goal(draft: _Goal, store: Store) -> OptimizeGoal:
    """Locked shelves resolved to rack ids (an ambiguous name is not guessed); bounds checked."""
    warnings: list[str] = []
    by_name: dict[str, set[str]] = {}
    for rack in store.racks:
        if rack.rack_name.strip():
            by_name.setdefault(rack.rack_name.strip().casefold(), set()).add(rack.id)
    locked_ids: list[str] = []
    locked_names: list[str] = []
    for asked in draft.locked_shelves:
        ids = resolve_listed(asked, by_name)
        if ids is None:
            warnings.append(f'No shelf "{asked}" in this layout; nothing was locked for it.')
            continue
        for rid in sorted(ids):
            if rid not in locked_ids:
                locked_ids.append(rid)
        locked_names.append(asked.strip())
    max_moves = draft.max_moves
    if max_moves is not None and not 1 <= max_moves <= 50:
        warnings.append(f"{max_moves} moves is outside 1 to 50; the move limit was left as it was.")
        max_moves = None
    gain = draft.min_improvement_percent
    if gain is not None and not 0 <= gain <= 100:
        warnings.append(f"A {gain:g} % minimum gain is outside 0 to 100; it was left as it was.")
        gain = None
    minimum = None if gain is None else gain / 100
    if gain is not None and gain > 0 and minimum == 0:
        warnings.append("The minimum gain is too small to represent; it was left as it was.")
        minimum = None
    return OptimizeGoal(
        objective=OptimizeObjective(draft.objective), scope=OptimizeScope(draft.scope), max_moves=max_moves,
        keep_fridges_on_walls=draft.keep_fridges_on_walls, lock_rack_ids=locked_ids, locked=locked_names,
        min_improvement=minimum, rationale=draft.rationale.strip(),
        warnings=warnings,
    )


async def read_goal(llm: StructuredLLM, text: str, store: Store) -> OptimizeGoal:
    shelves = list(dict.fromkeys(r.rack_name for r in store.racks if r.rack_name.strip()))
    draft = await llm.generate_structured_async(
        _Goal, GOAL_PROMPT, f"Shelves: {', '.join(shelves)}\n\nGoal: {text.strip()}", max_retries=2, seed=0)
    return to_goal(draft, store)
