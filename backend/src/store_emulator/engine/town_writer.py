"""A neighborhood described in plain words, turned into the generator's `TownSpec` by a language model.

"A busy university street: lots of students, two other convenience stores within a block, a café and a PC room next
door" becomes the university archetype, high density, two rivals and those neighbors. The spec fills the generator
form; the town is generated only when the user asks.
"""

from typing import Protocol

from pydantic import BaseModel, Field

from store_emulator.domain.town import TownArchetype, TownSpec, VenueCategory


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Draft(BaseModel):
    name: str = Field(default="", max_length=60, description="a short name for the neighborhood")
    archetype: TownArchetype
    size_m: float = Field(default=800.0, ge=200.0, le=3000.0, description="side of the area in metres (400 a few blocks, 1500 a district)")
    density: float = Field(default=0.5, ge=0.0, le=1.0, description="how built-up: 0.2 sparse houses, 0.5 typical, 0.9 towers")
    n_competitors: int | None = Field(default=None, ge=0, le=60, description="other convenience stores, when the description says")
    neighbor_categories: list[VenueCategory] = Field(default_factory=list[VenueCategory], max_length=5,
                                                     description="venues right next to our store, when the description says")
    venue_density: float = Field(default=1.0, ge=0.0, le=4.0, description="shops and venues around: 0.5 few, 1 typical, 2 lively")
    rationale: str = Field(default="", max_length=300)


class DescribedTown(BaseModel):
    spec: TownSpec
    rationale: str = ""


TOWN_PROMPT = """You set up a neighborhood generator for a store simulator from a description of the area around the
store. Pick the closest archetype (residential, university, business_district, suburban, station_area, tourist,
mixed) and set size, density, rivals, neighbors and venue density only as the description states or clearly implies;
keep defaults otherwise (800 m, density 0.5, rivals unknown, no neighbors, venue density 1). Give a one-sentence
rationale. Write in English."""


async def describe_town(llm: StructuredLLM, description: str, seed: int = 0) -> DescribedTown:
    draft = await llm.generate_structured_async(_Draft, TOWN_PROMPT, f"Description: {description.strip()}", max_retries=2, seed=0)
    spec = TownSpec(
        archetype=draft.archetype, size_m=round(draft.size_m / 50) * 50 or 800.0, density=round(draft.density, 2),
        n_competitors=draft.n_competitors, neighbor_categories=list(dict.fromkeys(draft.neighbor_categories)),
        venue_density=round(draft.venue_density, 2), seed=seed, name=draft.name.strip(),
    )
    return DescribedTown(spec=spec, rationale=draft.rationale.strip())
