import random

from pydantic import BaseModel

from store_emulator.domain.persona import Persona
from store_emulator.domain.types import Weekday, stable_seed


class CustomerEntry(BaseModel):
    persona_id: str
    day: Weekday
    arrival_time: str  # "HH:MM:SS"
    hour: int


def generate_customers(personas: list[Persona], seed: int = 0) -> list[CustomerEntry]:
    """Assign each persona a minute/second within its arrival hour.

    Each persona draws from its own stream keyed by (seed, persona id), so the
    arrival time of a persona does not depend on which other personas are in
    the run or on the store layout — and never touches the global `random` state.
    """
    entries: list[CustomerEntry] = []
    for persona in personas:
        rng = random.Random(stable_seed(seed, "arrival", persona.id))
        hour = persona.arrival_hour
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)
        entries.append(CustomerEntry(
            persona_id=persona.id,
            day=persona.day,
            arrival_time=f"{hour:02d}:{minute:02d}:{second:02d}",
            hour=hour,
        ))

    entries.sort(key=lambda e: (e.day, e.arrival_time))
    return entries
