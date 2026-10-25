"""Model routing for synthetic consumers: one model, or an ensemble of several.

Engines talk to `SimLLM`. A single `LiteLLMClient` satisfies it and ignores `route`;
`EnsembleLLMClient` uses `route` (the persona id) to give every customer one consistent
member (mixture), or asks every member (vote, vision glances only).
"""

import asyncio
import math
import random
import sys
import threading
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from instructor.core.exceptions import IncompleteOutputException, InstructorRetryException
from pydantic import BaseModel

from store_emulator.domain.providers import EnsembleMode
from store_emulator.domain.types import TokenUsage, stable_seed


class SimLLM(Protocol):
    """`max_tokens` overrides the configured completion cap for one call (None = configured)."""

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T: ...

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T: ...

    def reset_usage(self) -> None: ...

    def get_usage(self) -> TokenUsage: ...


def _cap(max_tokens: int | None) -> dict[str, int]:
    """Forward a per-call token cap only when set, so clients without the keyword keep working."""
    return {} if max_tokens is None else {"max_tokens": max_tokens}


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
        if any(not math.isfinite(weight) or weight <= 0 for _, weight, _ in members):
            raise ValueError("ensemble weights must be finite and greater than zero")
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
        weights = [m.weight for m in self._members]
        total = sum(weights)
        # Subnormal totals round the random draw and bias otherwise equal weights.
        if not math.isfinite(total) or total < sys.float_info.min:
            largest = max(weights)
            weights = [weight / largest for weight in weights]
        member = rng.choices(self._members, weights=weights, k=1)[0]
        if route is not None:
            with self._lock:
                self._assigned[route] = member.name
        return member

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        member = self.member_for(route)
        return await member.client.generate_structured_async(
            response_model, system_prompt, user_prompt, max_retries=max_retries, seed=seed, route=route,
            **_cap(max_tokens),
        )

    async def generate_structured_with_image_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
    ) -> T:
        member = self.member_for(route)
        return await member.client.generate_structured_with_image_async(
            response_model, system_prompt, user_prompt, image_url, max_retries=max_retries, seed=seed, route=route,
            **_cap(max_tokens),
        )

    async def ask_all_with_image[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, image_url: str | None,
        *, max_retries: int = 1, seed: int | None = None, route: str | None = None, max_tokens: int | None = None,
        retry_max_tokens: int | None = None,
    ) -> list[MemberAnswer[T]]:
        """Every member answers (concurrently); failures are returned, not raised.
        With `image_url` None the question is asked as text only. An optional second
        output budget retries only a member whose terminal completion was truncated."""
        async def one(member: _Member) -> MemberAnswer[T]:
            budgets = (max_tokens,) if retry_max_tokens is None else (max_tokens, retry_max_tokens)
            for attempt, budget in enumerate(budgets):
                try:
                    if image_url is None:
                        answer = await member.client.generate_structured_async(
                            response_model, system_prompt, user_prompt,
                            max_retries=max_retries, seed=seed, route=route, **_cap(budget),
                        )
                    else:
                        answer = await member.client.generate_structured_with_image_async(
                            response_model, system_prompt, user_prompt, image_url,
                            max_retries=max_retries, seed=seed, route=route, **_cap(budget),
                        )
                    return MemberAnswer(member.name, answer)
                except Exception as e:  # noqa: BLE001 — one member failing must not sink the vote
                    cause = (e.failed_attempts[-1].exception
                             if isinstance(e, InstructorRetryException) and e.failed_attempts else e)
                    if attempt == 0 and retry_max_tokens is not None and isinstance(cause, IncompleteOutputException):
                        continue
                    return MemberAnswer(member.name, None, f"{type(e).__name__}: {e}"[:300])
            raise AssertionError("unreachable")

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
