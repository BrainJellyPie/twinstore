"""Model routing for synthetic consumers: one model, or an ensemble of several.

Engines talk to `SimLLM`. A single `LiteLLMClient` satisfies it and ignores `route`;
`EnsembleLLMClient` uses `route` (the persona id) to give every customer one consistent
member (mixture), or asks every member (vote, vision glances only).
"""

import asyncio
import random
import threading
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from store_emulator.domain.providers import EnsembleMode
from store_emulator.domain.types import TokenUsage, stable_seed


class SimLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T: ...

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T: ...

    def reset_usage(self) -> None: ...

    def get_usage(self) -> TokenUsage: ...


@dataclass
class _Member:
    name: str
    weight: float
    client: SimLLM


@dataclass(frozen=True)
class MemberAnswer[T: BaseModel]:
    member: str
    answer: T | None
    error: str = ""


class EnsembleLLMClient:
    def __init__(self, members: list[tuple[str, float, SimLLM]], *, mode: EnsembleMode = "mixture", seed: int = 0):
        if not members:
            raise ValueError("an ensemble needs at least one member")
        self.mode: EnsembleMode = mode
        self._seed = seed
        self._members = [_Member(name, weight, client) for name, weight, client in members]
        self._lock = threading.Lock()
        self._assigned: dict[str, str] = {}

    @property
    def member_names(self) -> list[str]:
        return [m.name for m in self._members]

    def member_for(self, route: str | None) -> _Member:
        """Weighted, stable choice: the same route (persona) always gets the same member."""
        rng = random.Random(stable_seed(self._seed, "ensemble", route or ""))
        member = rng.choices(self._members, weights=[m.weight for m in self._members], k=1)[0]
        if route is not None:
            with self._lock:
                self._assigned[route] = member.name
        return member

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        member = self.member_for(route)
        return await member.client.generate_structured_async(
            response_model, system_prompt, user_prompt, max_retries=max_retries, seed=seed, route=route,
        )

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> T:
        member = self.member_for(route)
        return await member.client.generate_structured_with_image_async(
            response_model, system_prompt, user_prompt, image_url, max_retries=max_retries, seed=seed, route=route,
        )

    async def ask_all_with_image[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None,
    ) -> list[MemberAnswer[T]]:
        """Every member answers (concurrently); failures are returned, not raised."""
        async def one(member: _Member) -> MemberAnswer[T]:
            try:
                answer = await member.client.generate_structured_with_image_async(
                    response_model, system_prompt, user_prompt, image_url,
                    max_retries=max_retries, seed=seed, route=route,
                )
                return MemberAnswer(member.name, answer)
            except Exception as e:  # noqa: BLE001 — one member failing must not sink the vote
                return MemberAnswer(member.name, None, f"{type(e).__name__}: {e}"[:300])

        return list(await asyncio.gather(*(one(m) for m in self._members)))

    def reset_usage(self) -> None:
        for m in self._members:
            m.client.reset_usage()
        with self._lock:
            self._assigned = {}

    def get_usage(self) -> TokenUsage:
        total = TokenUsage()
        for m in self._members:
            total += m.client.get_usage()
        return total

    def metadata(self) -> dict[str, object]:
        with self._lock:
            assigned = Counter(self._assigned.values())
        return {
            "mode": self.mode,
            "members": [
                {"name": m.name, "weight": m.weight, "customers": assigned.get(m.name, 0),
                 "usage": m.client.get_usage().model_dump()}
                for m in self._members
            ],
        }
