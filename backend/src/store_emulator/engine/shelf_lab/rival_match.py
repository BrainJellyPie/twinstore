"""Rival products matched to ours by a language model when their names differ ("Coca-Cola Original 500ml" on the
rival's tag, "Coke 500 ml" in our layout). Only the same product counts: same brand, variant and size."""

from collections.abc import Sequence
from typing import Protocol, Self

from pydantic import BaseModel, Field, model_validator

MAX_OURS = 300


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Pair(BaseModel):
    rival: str = Field(max_length=160)
    ours: str = Field(default="", max_length=160, description="our product, exactly as listed, or '' when none is the same")


class _Pairs(BaseModel):
    pairs: list[_Pair] = Field(default_factory=list[_Pair], max_length=80)


MATCH_PROMPT = """You match products on a rival store's shelf to the same products in our store. A match must be the
same brand, the same variant or flavour and the same size; a similar product is not a match. For each rival product,
give our product's name exactly as listed, or an empty string when we do not sell that exact product.
Return at most one match per rival product; never assign different products to the same rival name."""


async def match_products(llm: StructuredLLM, rival_names: Sequence[str], our_names: Sequence[str]) -> dict[str, str]:
    """Rival name → our name, only for pairs the model gives with a name that is really ours."""
    if not rival_names or not our_names:
        return {}
    ours = {n.casefold(): n for n in our_names}
    asked_set = set(rival_names)

    class MatchedPairs(_Pairs):
        @model_validator(mode="after")
        def consistent_matches(self) -> Self:
            matched: dict[str, str] = {}
            for pair in self.pairs:
                target = ours.get(pair.ours.strip().casefold())
                if pair.rival not in asked_set or target is None:
                    continue
                if pair.rival in matched and matched[pair.rival] != target:
                    raise ValueError("Conflicting matches for the same rival product; return only one listed product per rival name.")
                matched[pair.rival] = target
            return self

    listed = "\n".join(f"- {n}" for n in list(our_names)[:MAX_OURS])
    asked = "\n".join(f"- {n}" for n in rival_names[:80])
    out = await llm.generate_structured_async(MatchedPairs, MATCH_PROMPT, f"Our products:\n{listed}\n\nRival products:\n{asked}",
                                              max_retries=2, seed=0)
    return {p.rival: ours[p.ours.strip().casefold()] for p in out.pairs
            if p.rival in asked_set and p.ours.strip().casefold() in ours}
