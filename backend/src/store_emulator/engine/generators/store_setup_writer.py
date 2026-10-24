"""The create-store form filled from one description.

"A 24-hour campus convenience store at Chung-Ang University in Seoul, weekdays 7 to 23, mostly students" becomes the
store's name, a short description, the address only when one is given, its type, opening days and hours, and the
store format the starting layout is generated from (one of the listed formats). Nothing is saved; the form shows
every field for the user to check.
"""

from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from store_emulator.engine.generators.profile_writer import LANGUAGES
from store_emulator.engine.prompting import resolve_listed


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Setup(BaseModel):
    name: str = Field(default="", max_length=80, description="the given name, or a plain descriptive one")
    description: str = Field(default="", max_length=400, description="one or two sentences about the store")
    address: str = Field(default="", max_length=200, description="only an address or place the description gives")
    format: str = Field(default="", max_length=80, description="the listed store format that fits, exactly as listed")
    open_days: Literal["7", "weekday", "weekend"] | None = Field(default=None, description="every day, weekdays only or weekends only; null when unspecified")
    open_hour: int | None = Field(default=None, description="0 to 23")
    close_hour: int | None = Field(default=None, description="1 to 24; 24 means midnight")
    currency: Literal["USD", "KRW", "JPY"] | None = Field(default=None, description="from the place, when it is clear")
    rationale: str = Field(default="", max_length=400)

    @field_validator("name", "description", "address", "format", "rationale", mode="before")
    @classmethod
    def _optional_text(cls, value: object) -> object:
        return "" if value is None else value


class StoreSetup(BaseModel):
    name: str = ""
    description: str = ""
    address: str = ""
    store_type: str = ""
    template_id: str = ""
    open_days: Literal["7", "weekday", "weekend"] | None = None
    open_hour: int | None = None
    close_hour: int | None = None
    currency: Literal["USD", "KRW", "JPY"] | None = None
    rationale: str = ""
    warnings: list[str] = []


SETUP_PROMPT = """You fill in a form for a new store in a store simulator from the owner's description. Fill only what
the description says or clearly implies: a short name (theirs if given, otherwise a plain descriptive one such as
"Campus Corner Store"), one or two sentences describing the store
from what the owner said (add no products, prices or facts they did not give), the address only when a place is
given (never invent a street), which listed store format fits best, the opening days
(every day, weekdays or weekends, null when unspecified) and hours (an all-night store is 0 to 24), and the currency when the place makes it
clear (USD, KRW or JPY only). Use empty strings for unspecified text; reserve null for unspecified days, hours and currency.
Write the name and description in {language}; give a short rationale in English."""


def to_setup(draft: _Setup, formats: Sequence[tuple[str, str, str]]) -> StoreSetup:
    """formats: (id, name, store type). The format is resolved by id or name; hours are checked as a pair."""
    warnings: list[str] = []
    by_name: dict[str, set[tuple[str, str]]] = {}
    for fid, name, store_type in formats:
        by_name.setdefault(fid.strip().casefold(), set()).add((fid, store_type))
        by_name.setdefault(name.strip().casefold(), set()).add((fid, store_type))
    template_id = store_type = ""
    if draft.format.strip():
        hit = resolve_listed(draft.format, by_name)
        if hit is None:
            warnings.append(f'No store format "{draft.format}"; choose the starting layout below.')
        elif len(hit) != 1:
            warnings.append(f'More than one store format matches "{draft.format}"; choose the starting layout below.')
        else:
            template_id, store_type = next(iter(hit))
    open_hour, close_hour = draft.open_hour, draft.close_hour
    given = open_hour is not None or close_hour is not None
    valid = open_hour is not None and close_hour is not None and 0 <= open_hour < close_hour <= 24 and open_hour <= 23
    if given and not valid:
        warnings.append("The opening hours could not be read as one daily window (overnight hours are not supported); "
                        "set them below.")
        open_hour = close_hour = None
    return StoreSetup(
        name=draft.name.strip()[:80], description=draft.description.strip()[:400], address=draft.address.strip()[:200],
        store_type=store_type, template_id=template_id, open_days=draft.open_days, open_hour=open_hour,
        close_hour=close_hour, currency=draft.currency, rationale=draft.rationale.strip(), warnings=warnings,
    )


async def draft_store_setup(
    llm: StructuredLLM, text: str, formats: Sequence[tuple[str, str, str, str]], locale: str = "en",
) -> StoreSetup:
    """formats: (id, name, store type, description) of every store format the layout can start from."""
    listing = "\n".join(f"- {name} ({store_type}): {desc}" for _, name, store_type, desc in formats)
    draft = await llm.generate_structured_async(
        _Setup, SETUP_PROMPT.format(language=LANGUAGES.get(locale, "English")),
        f"Store formats:\n{listing}\n\nDescription: {text.strip()}", max_retries=2, seed=0,
    )
    return to_setup(draft, [(fid, name, store_type) for fid, name, store_type, _ in formats])
