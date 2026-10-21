"""A customer profile drafted from what the user said about the store, for the create-store form.

The profile is the free text persona generation starts from; a concrete one ("office workers buying lunch between
12 and 1, students after 4, residents for evening top-ups") gives far more varied shoppers than "nearby residents".
"""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

LANGUAGES = {"en": "English", "ko": "Korean", "zh": "Simplified Chinese", "ja": "Japanese", "es": "Spanish", "fr": "French"}


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class _Profile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    profile: str = Field(min_length=20, max_length=900, description="three to five sentences")


PROFILE_PROMPT = """You help a store owner describe their customers so a simulator can generate realistic shoppers.
From what they said about the store, write three to five plain sentences on who shops there: the main groups (age,
occupation, household), when each comes during the opening hours, why they come and what they typically buy, and
roughly how much they spend. Stay consistent with the store type, the place and the hours; do not invent facts about
the specific business (no names, no figures it did not give). Write in {language}."""


async def draft_profile(
    llm: StructuredLLM, *, name: str, description: str, address: str, store_type: str, hours: str, locale: str = "en",
) -> str:
    user = "\n".join(line for line in (
        f"Store: {name.strip()}" if name.strip() else "",
        f"Type: {store_type.strip()}" if store_type.strip() else "",
        f"About it: {description.strip()}" if description.strip() else "",
        f"Location: {address.strip()}" if address.strip() else "",
        f"Opening hours: {hours.strip()}" if hours.strip() else "",
    ) if line) or "No details given."
    out = await llm.generate_structured_async(
        _Profile, PROFILE_PROMPT.format(language=LANGUAGES.get(locale, "English")), user, max_retries=2, seed=0)
    return " ".join(out.profile.split())
