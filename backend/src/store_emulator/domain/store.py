from typing import Final

from pydantic import BaseModel, Field, model_validator

from .layout_options import StoreDesign
from .rack import Rack, RackType, PASSTHROUGH_TYPES, Slot
from .types import Position, Weekday


# Allowed range for a store grid side length. Clamped during the normalize step after LLM store generation.
GRID_MIN_SIDE: Final[int] = 8
GRID_MAX_SIDE: Final[int] = 16


class DaySchedule(BaseModel):
    """Per-weekday operating hours. Open window is the half-open interval `[open_hour, close_hour)` — only hours H with open_hour <= H < close_hour are open."""
    day: Weekday
    is_open: bool = True
    open_hour: int = Field(default=9, ge=0, le=24)
    close_hour: int = Field(default=18, ge=0, le=24)

    @model_validator(mode="after")
    def _validate_open_close(self) -> "DaySchedule":
        if self.is_open and self.open_hour >= self.close_hour:
            raise ValueError(
                f"open_hour({self.open_hour}) must be less than close_hour({self.close_hour}) "
                f"(overnight operating hours are not yet supported)"
            )
        return self


class Store(BaseModel):
    id: str
    name: str
    type: str
    design_theme: StoreDesign = "classic"
    # Legacy stores inherit the server/run currency until explicitly recorded.
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    grid_size: Position  # (width, height)
    weekly_schedule: list[DaySchedule] = []
    racks: list[Rack] = []

    def schedule_for(self, day: Weekday) -> DaySchedule | None:
        for s in self.weekly_schedule:
            if s.day == day:
                return s
        return None

    @property
    def open_days(self) -> list[DaySchedule]:
        return [s for s in self.weekly_schedule if s.is_open]

    def walkable_grid(self) -> list[list[bool]]:
        w, h = self.grid_size
        grid = [[True] * w for _ in range(h)]
        for f in self.racks:
            if f.type in PASSTHROUGH_TYPES:
                continue
            for x, y in f.occupied_positions:
                if 0 <= x < w and 0 <= y < h:
                    grid[y][x] = False
        return grid

    def rack_at(self, x: int, y: int) -> Rack | None:
        for f in self.racks:
            if (x, y) in f.occupied_positions:
                return f
        return None

    @property
    def entrances(self) -> list[Rack]:
        return [f for f in self.racks if f.type == RackType.ENTRANCE]

    @property
    def exits(self) -> list[Rack]:
        return [f for f in self.racks if f.type == RackType.EXIT]

    @property
    def counters(self) -> list[Rack]:
        return [f for f in self.racks if f.type == RackType.COUNTER]

    @property
    def product_racks(self) -> list[Rack]:
        return [f for f in self.racks if f.slots]

    @property
    def all_slots(self) -> list[tuple[Rack, Slot]]:
        return [(f, s) for f in self.racks for s in f.slots]
