import asyncio
import logging
import math
import os
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Self

from instructor.core.exceptions import IncompleteOutputException, InstructorRetryException
from pydantic import BaseModel, Field, model_validator

from store_emulator.domain.persona import AGE_GROUPS, GENDERS, AgeGroup, Gender, Persona
from store_emulator.domain.store import DaySchedule, validate_weekly_schedule
from store_emulator.domain.types import AsyncLLMClient, Weekday, WEEKDAY_LABELS, stable_seed
from store_emulator.engine.generators.traffic_profile import TrafficProfile, reshape_hourly_counts
from store_emulator.engine.prompting import budget_example

logger = logging.getLogger(__name__)

type PersonaLabel = Annotated[str, Field(max_length=120)]


# Upper bounds well above what the prompts ask for. Schema-constrained local models (llama.cpp) are held to them, so a
# small model cannot repeat itself for minutes (one listed every hour four times).
class TradeAreaProfile(BaseModel):
    keywords: list[PersonaLabel] = Field(max_length=20)
    identities: list[PersonaLabel] = Field(max_length=40)
    purposes: list[PersonaLabel] = Field(max_length=40)


class HourlyProfile(BaseModel):
    hour: int = Field(ge=0, le=23, strict=True)
    visitor_count: int = Field(ge=0, strict=True)
    person_types: list[PersonaLabel] = Field(max_length=10)


class DailyTrafficResult(BaseModel):
    hourly_profiles: list[HourlyProfile] = Field(max_length=24)

    @model_validator(mode="after")
    def unique_hours(self) -> Self:
        hours = [profile.hour for profile in self.hourly_profiles]
        duplicates = sorted({hour for hour in hours if hours.count(hour) > 1})
        if duplicates:
            raise ValueError(f"Each hour must appear at most once; repeated hours: {duplicates}. Return one visitor count per hour.")
        return self


class GeneratedPersona(BaseModel):
    """What the persona prompt asks for. The rest of a Persona (day, hour, receipt-derived fields) is filled in here:
    asking for no more keeps answers short and gives small models nothing to invent (one filled `category_rates` with
    percentages). Lengths are bounded well above a normal answer, so a local model cannot loop inside a string."""
    identity: PersonaLabel
    age_group: AgeGroup
    gender: Gender
    description: str = Field(max_length=600)
    intent: str = Field(max_length=400)
    purpose: PersonaLabel
    preferred_categories: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list[str], max_length=10)
    budget_min: int = Field(default=0, ge=0, le=9_007_199_254_740_991)
    budget_max: int = Field(default=0, ge=0, le=9_007_199_254_740_991)
    behavior_tendency: str = Field(default="", max_length=300)


class PersonaBatch(BaseModel):
    personas: list[GeneratedPersona] = Field(min_length=1, max_length=12)


@dataclass
class BatchTally:
    """Persona requests across all days: how many were sent, how many failed, and the first failure."""
    requested: int = 0
    failed: int = 0
    first_error: BaseException | None = None


class TooManyBatchesFailed(RuntimeError):
    """Most persona requests failed: the customers that came back would not represent the store."""

    def __init__(self, tally: BatchTally) -> None:
        super().__init__(f"{tally.failed} of {tally.requested} customer requests failed; last error: {tally.first_error}")
        self.tally = tally


@dataclass(frozen=True)
class Pace:
    """How much to ask of the model that answers: customers a day, customers per request, and how many a day a quick
    sample writes (the rest of each day are twins of them)."""
    daily_cap: int
    batch_size: int
    sample_cap: int = 100


@dataclass(frozen=True)
class WriteSize:
    """Customers written in total (all days) and the model requests that takes."""
    per_day: int
    customers: int
    requests: int


@dataclass(frozen=True)
class WritePlan:
    """What writing the customers takes, measured on one request (the probe) before the rest are sent.

    `visitors` are each open day's estimated visitors (weekday → count, at most the population cap). `all` writes
    every one of them; `sample` writes `sample.per_day` a day and fills the rest with twins. The probe wrote
    `probe_customers` customers in `probe_seconds` using `probe_prompt_tokens` + `probe_completion_tokens`
    (`probe_requests` requests, retries included); its customers are kept either way."""
    visitors: dict[int, int]
    all: WriteSize
    sample: WriteSize
    probe_seconds: float
    probe_customers: int
    probe_requests: int
    probe_prompt_tokens: int
    probe_completion_tokens: int


# The answer to a WritePlan: how many customers a day to write (the rest of each day's visitors are twins of them).
type Decide = Callable[[WritePlan], Awaitable[int]]
# Customers written so far and in all, as the batches come back.
type WriteProgress = Callable[[int, int], None]


PROFILE_PROMPT = """당신은 상권 분석 전문가입니다.
주어진 매장 위치와 상권 정보를 바탕으로, 일주일 전체를 아우르는 고객 유형과 방문 목적을 분석하세요.
반드시 매장이 위치한 국가/도시의 실제 고객 특성을 반영하세요.

규칙:
- keywords: 이 지역을 특징짓는 단어 5~10개
  - 각 항목은 120자 이하의 짧은 단어나 구. 긴 설명이나 같은 구절을 반복하지 마세요.

- identities: 이 매장에 **일주일 전체를 통틀어** 방문할 수 있는 고객 유형. 짧은 라벨로 작성.
  - 평일에만 오는 유형 (예: "출근길 직장인", "점심시간 회사원")
  - 주말에만 오는 유형 (예: "주말 가족", "데이트 커플")
  - 매일 오는 유형 (예: "동네 주민", "배달 기사")
  - 특정 요일에 두드러지는 유형 (예: "금요일 회식 후 직장인", "월요일 아침 러너")
  - 최소 15종, 최대 30종. 너무 적으면 요일별 차이가 안 나고, 30종을 넘으면 안 됩니다.
  - 같은 의미의 중복 금지 ("직장인"과 "회사원"은 하나로 통합)

- purposes: 이 매장에서의 **일주일 전체를 통틀어** 가능한 방문 목적. 짧은 라벨로 작성.
  - 평일 특화 목적 (예: "출근 전 커피", "점심 도시락")
  - 주말 특화 목적 (예: "브런치 장보기", "소풍 준비")
  - 시간대별 특화 목적 (예: "야식", "아침식사", "숙취 해소")
  - 매일 공통 목적 (예: "음료 구매", "간식")
  - 최소 15종, 최대 30종. 같은 의미의 중복 금지.

## 언어
- 자유 서술 필드(`keywords`, `identities`, `purposes` 각 항목의 값)는 **영어로** 작성하세요.
- 구조적 필드(enum, id, 좌표, 숫자)는 한국어 prompt 에서 정의된 그대로 유지합니다.
- 영어 표현은 자연스러운 콘텐츠 톤을 유지하세요(예: 짧고 명확한 라벨 형태)."""

DAILY_TRAFFIC_PROMPT = """당신은 상권 분석 전문가입니다.
아래 제공된 identity 풀(고객 유형 목록)을 참고하여, **{day_label}**의 시간대별 방문 트래픽을 예측하세요.

규칙:
- hourly_profiles: 0~23시 전체. 각 시간 H는 H:00–(H+1):00 슬롯을 의미.
  영업 슬롯은 **H ∈ [{open_hour}, {close_hour})** — 즉 H가 {open_hour} 이상 {close_hour} 미만인 슬롯만.
  예: 영업 17~18시면 H=17 슬롯 한 개만 영업, H=18 슬롯은 닫힘.
  영업이 아닌 모든 H는 반드시 visitor_count=0, person_types=[]
- visitor_count: 해당 시간대의 예상 방문객 수 (0 이상 정수).
  하루 총 방문객 수는 매장 입지/규모/상권 특성과 요일에 맞게 합리적으로 추론하여 결정.
  특정 시간대에 몰리는 자연스러운 형상(피크/오프피크/식사시간 등)을 반드시 반영하세요.
- person_types: **반드시 아래 identity 목록의 라벨을 그대로 사용.** {day_label}에 실제로 방문할 유형만 선택
  - 각 항목은 120자 이하. 라벨에 설명을 덧붙이거나 같은 구절을 반복하지 마세요.
  - {day_label}에 맞지 않는 유형은 제외 (예: 주말에 "출근길 직장인" 제외)
  - 시간대별로 적절한 유형만 선택 (예: "야식 손님"은 저녁~심야에만)"""

PERSONA_PROMPT_TEMPLATE = """주어진 시간대+인물유형+지역키워드 조합으로 현실적인 고객 페르소나를 만드세요.
매장이 위치한 국가/도시의 문화, 언어, 소비 패턴을 반영하세요.

규칙:
- 각 페르소나는 반드시 독립적인 개인 1명입니다. 커플, 연인, 친구 쌍 등 관계로 묶인 페르소나를 만들지 마세요. 동행자가 있는 경우에도 "~와 함께 온 사람" 한 명으로만 표현하세요.
- id, day, arrival_hour는 출력하지 마세요. 시스템이 요청 순서에 따라 자동으로 부여합니다.
- identity: 반드시 아래 제공된 identity 목록 중 하나를 그대로 사용 (통계 집계용 라벨)
- age_group: 반드시 다음 중 하나: {age_groups}
- gender: 반드시 다음 중 하나: {genders}
- description: 이 사람의 상황, 성격 1~2문장. 해당 국가의 실제 생활상을 반영. 특정 브랜드명이나 구체적 상품명(예: 바나나맛 우유, 컨디션)을 사용하지 말고, 니즈/카테고리 수준으로 표현 (예: "a sweet dairy beverage", "a hangover-relief drink")
- intent: 매장에서 하고 싶은 것 1문장 (자유 서술). 구체적 상품명 대신 카테고리나 니즈로 표현. 예: "조깅 후 수분 보충할 이온음료를 사고 싶다", "간단한 간식과 음료를 고르고 싶다"
- purpose: 반드시 아래 제공된 purpose 목록 중 하나를 그대로 사용 (통계 집계용 짧은 라벨)
- preferred_categories: 반드시 아래 제공된 카테고리 목록 중에서만 선택. 목록에 없는 카테고리를 임의로 만들지 마세요
- budget_min, budget_max: {budget_rule}
  - 0 이상 9007199254740991 이하의 정수. 한 번의 방문에 현실적인 금액을 사용하고 숫자를 반복하지 마세요. 예산을 정할 수 없으면 0을 사용하세요.
- behavior_tendency: 이동속도/탐색성향/충동구매 한 줄

## 언어
- 자유 서술 필드(`description`, `intent`, `behavior_tendency`)의 값은 **영어로** 작성하세요.
- 구조적 필드(`age_group`, `gender`, `identity`, `purpose`, `preferred_categories`, `budget_min`, `budget_max`)는 프롬프트에서 제공된 라벨/값을 그대로 사용합니다.
- 영어 표현은 자연스러운 콘텐츠 톤을 유지하세요(예: 페르소나 설명은 1-2문장의 짧은 인물 묘사)."""


def persona_prompt(currency: str = "USD") -> str:
    return PERSONA_PROMPT_TEMPLATE.format(
        age_groups=", ".join(AGE_GROUPS),
        genders=", ".join(GENDERS),
        budget_rule=budget_example(currency),
    )


PERSONA_PROMPT = persona_prompt("USD")


async def analyze_location(
    llm: AsyncLLMClient,
    address: str,
    customer_profile: str,
    custom_instruction: str = "",
    *,
    supplemental_summary: str = "",
) -> TradeAreaProfile:
    """spec §4.4 — sole injection point for the supplemental label."""
    user_input = f"Address: {address}\nCustomer profile: {customer_profile}"
    if supplemental_summary:
        user_input += f"\nSupplemental data analysis: {supplemental_summary}"
    if custom_instruction:
        user_input += f"\n추가 지시: {custom_instruction}"
    logger.info(f"[area-analysis] generating profile... ({address})")
    profile = await llm.generate_structured_async(TradeAreaProfile, PROFILE_PROMPT, user_input, max_retries=3)
    logger.info(
        f"[area-analysis] done: {len(profile.keywords)} keywords, "
        f"{len(profile.identities)} identities, {len(profile.purposes)} purposes"
    )
    return profile


async def analyze_daily_traffic(
    llm: AsyncLLMClient,
    address: str,
    customer_profile: str,
    profile: TradeAreaProfile,
    day: Weekday,
    open_hour: int,
    close_hour: int,
) -> list[HourlyProfile]:
    day_label = WEEKDAY_LABELS[day]
    identity_list = "\n".join(f"  - {i}" for i in profile.identities)

    system = DAILY_TRAFFIC_PROMPT.format(
        day_label=day_label, open_hour=open_hour, close_hour=close_hour,
    )
    user_input = (
        f"Address: {address}\nCustomer profile: {customer_profile}\n"
        f"요일: {day_label}\n영업: {open_hour}~{close_hour}시\n\n"
        f"## identity 목록\n{identity_list}"
    )
    logger.info(f"[area-analysis] {day_label} analyzing traffic...")
    result = await llm.generate_structured_async(DailyTrafficResult, system, user_input, max_retries=3)
    # Out-of-hours guard — force zero if the LLM misreads the open-slot range.
    dropped = 0
    for hp in result.hourly_profiles:
        if hp.hour < open_hour or hp.hour >= close_hour:
            if hp.visitor_count > 0 or hp.person_types:
                dropped += hp.visitor_count
                hp.visitor_count = 0
                hp.person_types = []
    if dropped:
        logger.warning(f"[area-analysis] {day_label} dropped {dropped} visitors outside operating hours")
    total = sum(p.visitor_count for p in result.hourly_profiles)
    logger.info(f"[area-analysis] {day_label} traffic analysis done: {total} visitors total (hourly distribution determined)")
    return result.hourly_profiles


async def generate_personas_for_day(
    llm: AsyncLLMClient,
    address: str,
    profile: TradeAreaProfile,
    day: Weekday,
    hourly_profiles: list[HourlyProfile],
    seed: int | None = None,
    custom_instruction: str = "",
    batch_size: int = 10,
    max_concurrent: int = 10,
    categories: list[str] | None = None,
    currency: str = "USD",
    *,
    semaphore: asyncio.Semaphore | None = None,
    tally: BatchTally | None = None,
    on_written: Callable[[int], None] | None = None,
) -> list[Persona]:
    system_prompt = persona_prompt(currency)
    # Local stream per day: days are generated concurrently, so seeding the global
    # `random` module would make them race and repeat the same sequence.
    rng = random.Random(stable_seed(seed, "persona-spec", int(day))) if seed is not None else random.Random()

    day_label = WEEKDAY_LABELS[day]
    profiles_map = {p.hour: p for p in hourly_profiles}
    identity_list = "\n".join(f"  - {i}" for i in profile.identities)
    purpose_list = "\n".join(f"  - {p}" for p in profile.purposes)

    limit = semaphore or asyncio.Semaphore(max_concurrent)
    tasks: list[tuple[list[int], asyncio.Task[list[tuple[GeneratedPersona, int]]]]] = []

    # One spec line per customer, hour by hour; requests take `batch_size` of them in order, across hours, so a quiet
    # hour's one or two customers do not cost a request of their own (a 20-a-day sample over 14 hours took 14).
    specs: list[tuple[int, str]] = []
    for hour, hp in sorted(profiles_map.items()):
        if not hp.person_types or hp.visitor_count <= 0:
            continue
        for _ in range(hp.visitor_count):
            n_types = min(rng.choice([1, 1, 2]), len(hp.person_types))
            types = rng.sample(hp.person_types, n_types)
            n_kw = min(rng.randint(1, 3), len(profile.keywords))
            kws = rng.sample(profile.keywords, n_kw)
            specs.append((hour, f"{hour}시, {'+'.join(types)}, 키워드: {', '.join(kws)}"))
    if specs:
        logger.info(f"[persona] {day_label}: {len(specs)} customers in {-(-len(specs) // batch_size)} requests")

    category_section = ""
    if categories:
        cat_list = "\n".join(f"  - {c}" for c in categories)
        category_section = f"## 카테고리 목록 (preferred_categories는 반드시 이 중에서만 선택)\n{cat_list}\n\n"

    async def _generate_batch(chunk: list[tuple[int, str]], *, recover: bool = True) -> list[tuple[GeneratedPersona, int]]:
        persona_input = (
            f"매장 위치: {address}\n요일: {day_label}\n\n"
            f"## identity 목록 (반드시 이 중 하나 선택)\n{identity_list}\n\n"
            f"## purpose 목록 (반드시 이 중 하나 선택)\n{purpose_list}\n\n"
            f"{category_section}"
            f"아래 {len(chunk)}명의 고객 페르소나를 생성하세요 (순서대로):\n\n"
            + "\n".join(f"[{i}] {line}" for i, (_, line) in enumerate(chunk))
        )
        if custom_instruction:
            persona_input += f"\n\n추가 지시: {custom_instruction}"
        try:
            async with limit:
                batch = await llm.generate_structured_async(PersonaBatch, system_prompt, persona_input, max_retries=3)
        except (IncompleteOutputException, InstructorRetryException) as error:
            cause = (error.failed_attempts[-1].exception
                     if isinstance(error, InstructorRetryException) and error.failed_attempts else error)
            if not recover or len(chunk) < 2 or not isinstance(cause, IncompleteOutputException):
                raise
            logger.info("[persona] %s: splitting a truncated %s-customer request once", day_label, len(chunk))
            middle = len(chunk) // 2
            # Release the shared request slot before either child acquires it.
            first = await _generate_batch(chunk[:middle], recover=False)
            second = await _generate_batch(chunk[middle:], recover=False)
            return first + second
        # Preserve each child's original hours even when a small model returns fewer customers.
        return [(generated, hour) for generated, (hour, _) in zip(batch.personas, chunk)]

    for batch_start in range(0, len(specs), batch_size):
        chunk = specs[batch_start:batch_start + batch_size]
        tasks.append(([hour for hour, _ in chunk], asyncio.create_task(_generate_batch(chunk))))

    all_personas: list[Persona] = []
    for hours, task in tasks:
        size = len(hours)
        if tally is not None:
            tally.requested += 1
        try:
            batch = await task
        except Exception as e:
            logger.error(f"[persona] {day_label} hours {hours[0]}–{hours[-1]} batch generation failed: {e}")
            if tally is not None:
                tally.failed += 1
                tally.first_error = tally.first_error or e
            if on_written is not None:
                on_written(size)   # settled, if not written: twins stand in for them
            continue
        if on_written is not None:
            on_written(size)

        for generated, hour in batch:
            prefix = "F" if generated.gender == "Female" else "M"
            seq = len([p for p in all_personas if p.gender == generated.gender]) + 1
            persona = Persona.model_validate({**generated.model_dump(),
                "id": f"{prefix}{day.value}{seq:03d}", "day": day, "arrival_hour": hour})
            all_personas.append(persona)

    logger.info(f"[persona] {day_label} generated {len(all_personas)} personas")
    return all_personas


async def generate_batched(
    llm: AsyncLLMClient,
    address: str,
    customer_profile: str,
    schedules: list[DaySchedule],
    seed: int | None = None,
    custom_instruction: str = "",
    batch_size: int = 10,
    max_concurrent: int = 10,
    categories: list[str] | None = None,
    *,
    supplemental_summary: str = "",
    currency: str = "USD",
    traffic: TrafficProfile | None = None,
    pace: Callable[[Pace], Pace] | None = None,
    estimates: dict[int, int] | None = None,
    decide: Decide | None = None,
    on_progress: WriteProgress | None = None,
) -> list[Persona]:
    """Personas for every open day. With `traffic` (fitted from the store's own transaction times),
    the model's hourly estimate keeps deciding who comes, but how many come each hour follows the
    data — asked for times, models collapse onto a few stereotyped peaks.

    Each open day gets the visitors the model estimates for it (at most the population cap, 1000). `pace` turns the
    usual pace (customers a day, customers per request) into the one to use; it is asked after the first call, once
    the model that answers is settled (a small model on this computer gets smaller requests). With `decide`, one
    request is written and timed first, and `decide` gets the plan with that measurement and answers how many a day to
    write (every visitor, or a quick sample whose twins fill the rest of the day). `estimates`, when given, receives
    each open day's visitors (weekday 1–7 → visitors); per-day money in reports scales by them."""
    validate_weekly_schedule(schedules)
    profile = await analyze_location(
        llm, address, customer_profile, custom_instruction,
        supplemental_summary=supplemental_summary,
    )

    usual = Pace(daily_cap=_persona_daily_cap_ceiling(), batch_size=batch_size)
    population_cap = _env_int("PERSONA_DAILY_POPULATION", DAILY_POPULATION_CAP)
    settled = pace(usual) if pace is not None else usual
    daily_cap_now, batch_size = max(1, min(settled.daily_cap, population_cap)), max(1, settled.batch_size)
    sample_cap = max(1, min(settled.sample_cap, daily_cap_now))
    open_days = [s for s in schedules if s.is_open]

    # One limit for all days (they run together): 10 requests a day at once came to 70, enough to hit rate limits.
    shared = asyncio.Semaphore(max(1, max_concurrent))
    tally = BatchTally()

    async def _day_visitors(schedule: DaySchedule) -> list[HourlyProfile]:
        hourly = await analyze_daily_traffic(
            llm, address, customer_profile, profile,
            schedule.day, schedule.open_hour, schedule.close_hour,
        )
        hourly = _usable_hourly(hourly, profile, schedule, PLAIN_DAY_VISITORS)
        if traffic is not None:
            hourly = _apply_traffic(hourly, traffic, schedule)
        return _scale_hourly(hourly, population_cap)

    days = list(zip(open_days, await asyncio.gather(*[_day_visitors(s) for s in open_days]), strict=True))
    if estimates is not None:
        for schedule, visitors in days:
            estimates[int(schedule.day)] = sum(h.visitor_count for h in visitors)

    probe: list[Persona] = []
    probe_at: tuple[Weekday, int] | None = None

    def size(cap: int) -> WriteSize:   # requests take batch_size customers of a day, across its hours
        per_day = [sum(h.visitor_count for h in _scale_hourly(visitors, cap) if h.person_types and h.visitor_count > 0)
                   for _, visitors in days]
        requests = 0
        for (schedule, _), n in zip(days, per_day, strict=True):
            if probe_at is not None and probe_at[0] == schedule.day:
                requests += 1
                n = max(0, n - len(probe))
            requests += -(-n // batch_size)
        return WriteSize(per_day=cap, customers=sum(per_day), requests=requests)

    total = size(daily_cap_now).customers
    done = 0

    def written(n: int) -> None:
        nonlocal done
        done += n
        if on_progress is not None:
            on_progress(min(done, total), total)

    def write(day: Weekday, hourly: list[HourlyProfile]) -> Awaitable[list[Persona]]:
        return generate_personas_for_day(
            llm, address, profile, day, hourly,
            seed=seed, custom_instruction=custom_instruction,
            batch_size=batch_size, max_concurrent=max_concurrent,
            categories=categories, currency=currency, semaphore=shared, tally=tally, on_written=written,
        )

    cap = daily_cap_now
    busy = [(schedule, h) for schedule, visitors in days for h in _scale_hourly(visitors, cap)
            if h.person_types and h.visitor_count > 0]
    if decide is not None and busy:
        # One request first, timed: what the rest will take on this model, before asking for all of them.
        schedule, hour = max(busy, key=lambda pair: pair[1].visitor_count)
        n = min(batch_size, hour.visitor_count, sample_cap)
        get_usage = getattr(llm, "get_usage", None)
        before = get_usage() if callable(get_usage) else None
        started = time.monotonic()
        probe = await write(schedule.day, [hour.model_copy(update={"visitor_count": n})])
        seconds = time.monotonic() - started
        after = get_usage() if callable(get_usage) else None
        if not probe and tally.failed:
            raise TooManyBatchesFailed(tally)   # the model cannot write customers: say so now, not after hours
        probe_at = (schedule.day, hour.hour)
        tokens = _usage_delta(before, after)
        plan = WritePlan(
            visitors={int(sched.day): sum(h.visitor_count for h in visitors) for sched, visitors in days},
            all=size(daily_cap_now), sample=size(sample_cap),
            probe_seconds=seconds, probe_customers=len(probe), probe_requests=max(1, tokens[0]),
            probe_prompt_tokens=tokens[1], probe_completion_tokens=tokens[2],
        )
        cap = max(1, min(await decide(plan), daily_cap_now))
        if cap != daily_cap_now:
            total = size(cap).customers
        done = len(probe)

    async def _write_day(schedule: DaySchedule, visitors: list[HourlyProfile]) -> list[Persona]:
        target = _scale_hourly(visitors, cap)
        kept: list[Persona] = []
        if probe_at is not None and probe_at[0] == schedule.day:   # the probe's customers count toward their hour
            kept, probe_hour = probe, probe_at[1]
            target = [h.model_copy(update={"visitor_count": max(0, h.visitor_count - len(kept))})
                      if h.hour == probe_hour else h for h in target]
            # A small sample may allocate fewer customers to this hour than the probe already wrote.
            target = _scale_hourly(target, max(0, cap - len(kept)))
        out = await write(schedule.day, target)
        if kept:
            out = _renumber([*kept, *out], schedule.day)
        return fill_population(out, visitors, schedule.day)

    day_results = await asyncio.gather(*[_write_day(schedule, visitors) for schedule, visitors in days])
    all_personas: list[Persona] = [p for personas in day_results for p in personas]
    if tally.failed * 2 > tally.requested:
        raise TooManyBatchesFailed(tally)
    missing_days = [schedule.day.name for (schedule, visitors), people in zip(days, day_results, strict=True)
                    if any(hour.visitor_count > 0 for hour in visitors) and not people]
    if missing_days:
        raise ValueError(f"No customers were generated for {', '.join(missing_days)} despite positive visitor estimates. "
                         "Every customer request for those days failed or came back empty. Try again, or pick another "
                         "model in Settings → Model providers.")
    if tally.failed:
        logger.warning(f"[persona] {tally.failed} of {tally.requested} requests failed; their visitors are twins")

    logger.info(f"[persona] generated {len(all_personas)} personas total across {len(open_days)} days")
    return all_personas


def _usage_delta(before: object, after: object) -> tuple[int, int, int]:
    """(requests, prompt tokens, completion tokens) between two usage snapshots of the client (zeros without them)."""
    def get(usage: object, name: str) -> int:
        value = getattr(usage, name, 0)
        return value if isinstance(value, int) else 0

    if before is None or after is None:
        return (0, 0, 0)
    return (get(after, "requests") - get(before, "requests"),
            get(after, "prompt_tokens") - get(before, "prompt_tokens"),
            get(after, "completion_tokens") - get(before, "completion_tokens"))


def _renumber(personas: list[Persona], day: Weekday) -> list[Persona]:
    """Ids in order (F1001, F1002, …, M1001, …) for customers written in more than one go on the same day."""
    seq: dict[str, int] = {}
    out: list[Persona] = []
    for p in personas:
        seq[p.gender] = seq.get(p.gender, 0) + 1
        prefix = "F" if p.gender == "Female" else "M"
        out.append(p.model_copy(update={"id": f"{prefix}{day.value}{seq[p.gender]:03d}"}))
    return out


# A day's visitors follow the traffic estimate up to this many; the model writes them all, or a quick sample whose
# twins fill the rest. A plain day — the model gave no usable estimate — has PLAIN_DAY_VISITORS.
DAILY_POPULATION_CAP = 1000
PLAIN_DAY_VISITORS = 300


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def fill_population(written: list[Persona], visitors: list[HourlyProfile], day: Weekday) -> list[Persona]:
    """The day's visitors: the customers the model wrote, and twins of them for the rest of each hour's estimate.

    The model writes every visitor unless the user chose a quick sample (writing them all would take long or cost
    much), and a failed request leaves its customers unwritten. Totals, playback and runs should still see the whole
    day, so each hour gets copies of that hour's customers (of the day's, when the hour has none) under their own ids;
    every copy shops with its own randomness."""
    if not written:
        return written
    by_hour: dict[int, list[Persona]] = {}
    for p in written:
        by_hour.setdefault(p.arrival_hour, []).append(p)
    used = {p.id for p in written}
    seq = {g: sum(1 for p in written if p.gender == g) for g in ("Female", "Male")}
    out = list(written)
    for h in visitors:
        have = by_hour.get(h.hour, [])
        pool = have or written
        for k in range(max(0, h.visitor_count - len(have))):
            src = pool[k % len(pool)]
            prefix = "F" if src.gender == "Female" else "M"
            while True:   # the ids the written customers have (F1001, M1001, …), continued
                seq[src.gender] = seq.get(src.gender, 0) + 1
                twin_id = f"{prefix}{day.value}{seq[src.gender]:03d}"
                if twin_id not in used:
                    break
            used.add(twin_id)
            out.append(src.model_copy(update={"id": twin_id, "arrival_hour": h.hour, "day": day,
                                              "twin_of": src.twin_of or src.id}))
    return out


# Relative visits per hour of a plain convenience-store day (morning, lunch and evening peaks; other hours 2).
_PLAIN_DAY = {7: 4, 8: 6, 9: 4, 11: 4, 12: 7, 13: 6, 17: 5, 18: 7, 19: 6, 20: 5, 21: 4, 22: 3}


def _usable_hourly(hourly: list[HourlyProfile], profile: TradeAreaProfile, schedule: DaySchedule,
                   cap: int) -> list[HourlyProfile]:
    """Hours the persona step can use. Small models sometimes answer an open day with no visitors at all, or with
    visitors but no customer types; both left the day without customers. Hours without types get every identity
    of the trade area (at most 10 an hour, as the schema allows, taking turns so every identity comes); a day
    without visitors gets a plain convenience-store day of `cap` visitors."""
    identities = list(profile.identities) or ["shopper"]
    per_hour = min(10, len(identities))

    def types_for(hour: int) -> list[str]:
        return [identities[(hour * per_hour + k) % len(identities)] for k in range(per_hour)]

    fixed = [h if h.person_types or h.visitor_count <= 0 else h.model_copy(update={"person_types": types_for(h.hour)})
             for h in hourly]
    if sum(h.visitor_count for h in fixed) > 0:
        return fixed
    hours = list(range(schedule.open_hour, schedule.close_hour))
    if not hours:
        return fixed
    logger.warning(f"[area-analysis] {WEEKDAY_LABELS[schedule.day]}: the model gave the open day no visitors; "
                   "using a plain convenience-store day")
    weights = {h: _PLAIN_DAY.get(h, 2) for h in hours}
    total_w = sum(weights.values())
    counts = {h: max(1, round(cap * w / total_w)) for h, w in weights.items()}
    return [HourlyProfile(hour=h, visitor_count=n, person_types=types_for(h)) for h, n in counts.items()]


def _apply_traffic(hourly: list[HourlyProfile], traffic: TrafficProfile, schedule: DaySchedule) -> list[HourlyProfile]:
    """Visitor counts per open hour from the fitted profile; person types from the model's estimate
    (an hour the model left empty borrows the nearest hour's types)."""
    by_hour = {p.hour: p for p in hourly}
    slots = range(schedule.open_hour, schedule.close_hour)
    counts = reshape_hourly_counts({h: by_hour[h].visitor_count if h in by_hour else 0 for h in slots},
                                   traffic, int(schedule.day))
    typed = [p for p in hourly if p.person_types]

    def types_for(h: int) -> list[str]:
        if h in by_hour and by_hour[h].person_types:
            return by_hour[h].person_types
        return min(typed, key=lambda p: abs(p.hour - h)).person_types if typed else []

    return [HourlyProfile(hour=h, visitor_count=n, person_types=types_for(h)) for h, n in counts.items() if n > 0]


def _persona_daily_cap_ceiling() -> int:
    """Customers a day the model writes at most: every estimated visitor (1000), unless PERSONA_DAILY_CAP says less."""
    raw = os.getenv("PERSONA_DAILY_CAP")
    if raw is None:
        return DAILY_POPULATION_CAP
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"[persona] invalid PERSONA_DAILY_CAP={raw!r}; falling back to {DAILY_POPULATION_CAP}")
        return DAILY_POPULATION_CAP
    if value < 10:
        logger.warning(f"[persona] PERSONA_DAILY_CAP={value} below minimum; clamping to 10")
        return 10
    return value


def _scale_hourly(profiles: list[HourlyProfile], cap: int) -> list[HourlyProfile]:
    """Scale hourly visitor_count proportionally so the day has exactly `cap` visitors when it had more.

    Preserves the LLM-emitted shape (peaks, off-peaks). Each hour gets its share rounded down, and the visitors left
    over go to the hours with the largest remainders: rounding every hour on its own lost visitors (a 20-a-day sample
    over 14 quiet hours came to 14, a cap of 1,000 to 994).
    """
    total = sum(max(0, p.visitor_count) for p in profiles)
    if total <= cap:
        return profiles
    exact = [max(0, p.visitor_count) * cap / total for p in profiles]
    counts = [math.floor(e) for e in exact]
    left = cap - sum(counts)
    by_remainder = sorted(range(len(profiles)),
                          key=lambda i: (-(exact[i] - counts[i]), -profiles[i].visitor_count, profiles[i].hour))
    for i in by_remainder[:left]:
        counts[i] += 1
    return [HourlyProfile(hour=p.hour, visitor_count=n, person_types=p.person_types) for p, n in zip(profiles, counts, strict=True)]
