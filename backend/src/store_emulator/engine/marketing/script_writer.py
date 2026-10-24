"""An alternative staff script drafted from the current one, for a paired script test.

The draft keeps the offer (product, price, promotion) and uses only the verified facts given, so the test compares
wording rather than a different deal or an invented claim.
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class ScriptDraft(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=40, description="a short label for the approach, e.g. 'Value first'")
    script: str = Field(min_length=1, max_length=1200, description="the exact words staff say")
    differs_by: str = Field(default="", max_length=240, description="in one sentence, what this wording changes")

    @field_validator("differs_by", mode="before")
    @classmethod
    def _optional_difference(cls, value: object) -> object:
        return "" if value is None else value


SCRIPT_PROMPT = """You write in-store staff scripts for a paired test against the current script. Write one
alternative that a shopper would hear from an employee: natural, polite, short enough to say in one breath or two,
easy to decline. Keep the same product, price and promotion as given; use only the verified facts listed (no health,
quality or origin claims beyond them); no pressure, no false scarcity. Change the approach, not the offer: follow the
direction when one is given, otherwise pick the one change most likely to help a shopper decide.
Use an empty string, not null, when no differs_by explanation is given. Write in English."""


async def draft_script(
    llm: StructuredLLM, *, product: str, offer: str, context: str, facts: str, current: str, direction: str = "",
) -> ScriptDraft:
    user = "\n".join(line for line in (
        f"Product: {product}. Offer on the shelf: {offer}.",
        f"Encounter: {context.strip()}",
        f"Verified facts: {facts.strip() or 'none given; use none'}",
        f"Current script: {current.strip() or '(none yet; write a first script)'}",
        f"Direction: {direction.strip()}" if direction.strip() else "",
    ) if line)
    draft = await llm.generate_structured_async(ScriptDraft, SCRIPT_PROMPT, user, max_retries=2, seed=0)
    return draft.model_copy(update={"script": " ".join(draft.script.split())[:1200], "name": draft.name.strip()[:40]})
