import hashlib
from enum import IntEnum, StrEnum
from typing import Protocol

from pydantic import BaseModel

type Position = tuple[int, int]
type Shape = list[list[int]]

CARDINAL_DIRECTIONS: list[tuple[int, int]] = [(-1, 0), (1, 0), (0, -1), (0, 1)]


class Weekday(IntEnum):
    MON = 1
    TUE = 2
    WED = 3
    THU = 4
    FRI = 5
    SAT = 6
    SUN = 7


WEEKDAY_LABELS: dict[Weekday, str] = {
    Weekday.MON: "월요일",
    Weekday.TUE: "화요일",
    Weekday.WED: "수요일",
    Weekday.THU: "목요일",
    Weekday.FRI: "금요일",
    Weekday.SAT: "토요일",
    Weekday.SUN: "일요일",
}


def stable_seed(*parts: str | int) -> int:
    """Deterministic 63-bit seed derived from `parts`.

    Unlike the built-in `hash()`, the value is stable across processes, so the
    same (run seed, replicate, persona) always maps to the same random stream.
    This is what makes paired layout comparisons use common random numbers.
    """
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0
    cached_requests: int = 0  # served from the on-disk response cache, no provider call

    def __iadd__(self, other: "TokenUsage") -> "TokenUsage":
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.requests += other.requests
        self.cached_requests += other.cached_requests
        return self


class Face(StrEnum):
    N = "N"
    S = "S"
    E = "E"
    W = "W"


FACE_OFFSETS: dict[Face, tuple[int, int]] = {
    Face.N: (0, -1), Face.S: (0, 1), Face.W: (-1, 0), Face.E: (1, 0),
}


class Action(StrEnum):
    ENTER = "enter"
    MOVE = "move"
    BROWSE = "browse"
    BUY = "buy"
    PAY = "pay"
    WANDER = "wander"
    EXIT = "exit"


class AsyncLLMClient(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...
    async def generate_text_async(self, system_prompt: str, user_prompt: str, *, enable_search: bool = False) -> str: ...


class PathFinder(Protocol):
    def find_path(self, walkable_grid: list[list[bool]], start: Position, end: Position) -> list[Position]: ...
