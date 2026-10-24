"""Rival products matched to ours by a language model when their names differ ("Coca-Cola Original 500ml" on the
rival's tag, "Coke 500 ml" in our layout). Only the same product counts: same brand, variant and size."""

from collections.abc import Sequence
from typing import Protocol, Self

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_OURS = 300
MAX_NAME_CHARS = 160


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Pair(BaseModel):
    rival: str = Field(max_length=MAX_NAME_CHARS)
    ours: str = Field(default="", max_length=MAX_NAME_CHARS, description="our product, exactly as listed, or '' when none is the same")

    @field_validator("ours", mode="before")
    @classmethod
    def unmatched(cls, value: object) -> object:
        return "" if value is None else value


class _Pairs(BaseModel):
    pairs: list[_Pair] = Field(default_factory=list[_Pair], max_length=80)


MATCH_PROMPT = """You match products on a rival store's shelf to the same products in our store. A match must be the
same brand, the same variant or flavour and the same size; a similar product is not a match. For each rival product,
give our product's name exactly as listed, or an empty string, not null, when we do not sell that exact product.
Return at most one match per rival product; never assign different products to the same rival name.
For a name longer than 160 characters, copy its first 160 characters only when the prefix identifies one product
in that list. Omit an ambiguous pair; do not guess between products sharing that prefix."""


def _listed_name(raw: str, names: dict[str, str], *, fold: bool) -> str | None:
    key = raw.strip().casefold() if fold else raw
    if not key:
        return None
    if len(raw) == MAX_NAME_CHARS:
        matches = [name for name in names if name.startswith(key)]
        return names[matches[0]] if len(matches) == 1 else None
    return names.get(key)


async def match_products(llm: StructuredLLM, rival_names: Sequence[str], our_names: Sequence[str]) -> dict[str, str]:
    """Rival name → our name, only for pairs the model gives with a name that is really ours."""
    if not rival_names or not our_names:
        return {}
    ours = {n.casefold(): n for n in our_names}
    rivals = {n: n for n in rival_names}

    def resolved_pairs(pairs: list[_Pair]) -> dict[str, str]:
        matched: dict[str, str] = {}
        for pair in pairs:
            rival = _listed_name(pair.rival, rivals, fold=False)
            target = _listed_name(pair.ours, ours, fold=True)
            if rival is None or target is None:
                continue
            if rival in matched and matched[rival] != target:
                raise ValueError("Conflicting matches for the same rival product; return only one listed product per rival name.")
            matched[rival] = target
        return matched

    class MatchedPairs(_Pairs):
        @model_validator(mode="after")
        def consistent_matches(self) -> Self:
            resolved_pairs(self.pairs)
            return self

    listed = "\n".join(f"- {n}" for n in list(our_names)[:MAX_OURS])
    asked = "\n".join(f"- {n}" for n in rival_names[:80])
    out = await llm.generate_structured_async(MatchedPairs, MATCH_PROMPT, f"Our products:\n{listed}\n\nRival products:\n{asked}",
                                              max_retries=2, seed=0)
    return resolved_pairs(out.pairs)
