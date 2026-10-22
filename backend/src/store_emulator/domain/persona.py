from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .types import Weekday

type AgeGroup = Literal["10s", "20s", "30s", "40s", "50s", "60s+"]
type Gender = Literal["Male", "Female"]

AGE_GROUPS: list[AgeGroup] = ["10s", "20s", "30s", "40s", "50s", "60s+"]
GENDERS: list[Gender] = ["Male", "Female"]


class Persona(BaseModel):
    id: str
    day: Weekday = Weekday.MON
    identity: str
    age_group: AgeGroup
    gender: Gender
    description: str
    intent: str
    purpose: str
    arrival_hour: int = 12  # 0–23 (not enforced by a Field constraint)
    preferred_categories: list[str] = []
    budget_min: int = Field(default=0, ge=0)  # unit: project currency's minor units
    budget_max: int = Field(default=0, ge=0)  # 0 = no budget limit
    behavior_tendency: str = ""
    # Different items this trip is for (e.g. drawn from the store's own receipts). 0 = the engine
    # decides from the behavior pattern; > 0 = engines plan this many and size the trip to it.
    basket_size: int = 0
    # Product categories those items come from (e.g. from the same receipt). Real trips often take
    # several products of one kind; asked for 6 items, models otherwise pick 6 categories.
    # 0 = unconstrained.
    basket_kinds: int = 0
    # Share of this shopper's past trips that included each category (e.g. from loyalty data). Vision
    # planners are told which of them the household has run out of this trip: a seeded draw per
    # category at its rate. A model asked for one trip otherwise buys every staple every time (milk on
    # 73 % of trips against 43 % on real receipts). Empty = no such draw.
    category_rates: dict[str, Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]] = {}
    # Products this shopper habitually buys (names as on the shelf), e.g. from their purchase history.
    # The VLM planner sees them; the rule planner picks one of them first with probability habit_prob.
    usual_products: list[str] = []
    # The written customer this visitor copies ("" = written by the model or taken from data). A day is written as a
    # sample of its estimated visitors and filled with twins; model-based runs sample written customers first.
    twin_of: str = ""

    @property
    def budget_label(self) -> str:
        return f"{self.budget_min}¢~{self.budget_max}¢"
