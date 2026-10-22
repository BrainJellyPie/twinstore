import asyncio
import logging
import os
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, Field

from store_emulator.domain.persona import AGE_GROUPS, GENDERS, AgeGroup, Gender, Persona
from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import AsyncLLMClient, Weekday, WEEKDAY_LABELS, stable_seed
from store_emulator.engine.generators.traffic_profile import TrafficProfile, reshape_hourly_counts
from store_emulator.engine.prompting import budget_example

logger = logging.getLogger(__name__)


# Upper bounds well above what the prompts ask for. Schema-constrained local models (llama.cpp) are held to them, so a
# small model cannot repeat itself for minutes (one listed every hour four times).
class TradeAreaProfile(BaseModel):
    keywords: list[str] = Field(max_length=20)
    identities: list[str] = Field(max_length=40)
    purposes: list[str] = Field(max_length=40)


class HourlyProfile(BaseModel):
    hour: int
    visitor_count: int
    person_types: list[str] = Field(max_length=10)


class DailyTrafficResult(BaseModel):
    hourly_profiles: list[HourlyProfile] = Field(max_length=24)


class GeneratedPersona(BaseModel):
    """What the persona prompt asks for. The rest of a Persona (day, hour, receipt-derived fields) is filled in here:
    asking for no more keeps answers short and gives small models nothing to invent (one filled `category_rates` with
    percentages). Lengths are bounded well above a normal answer, so a local model cannot loop inside a string."""
    id: str = Field(default="", max_length=40)
    identity: str = Field(max_length=120)
    age_group: AgeGroup
    gender: Gender
    description: str = Field(max_length=600)
    intent: str = Field(max_length=400)
    purpose: str = Field(max_length=120)
    preferred_categories: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list[str], max_length=10)
    budget_min: int = Field(default=0, ge=0)
    budget_max: int = Field(default=0, ge=0)
    behavior_tendency: str = Field(default="", max_length=300)


class PersonaBatch(BaseModel):
    personas: list[GeneratedPersona] = Field(max_length=12)


@dataclass(frozen=True)
class Pace:
    """How much to ask of the model that answers: customers a day, and customers per request."""
    daily_cap: int
    batch_size: int


PROFILE_PROMPT = """당신은 상권 분석 전문가입니다.
주어진 매장 위치와 상권 정보를 바탕으로, 일주일 전체를 아우르는 고객 유형과 방문 목적을 분석하세요.
반드시 매장이 위치한 국가/도시의 실제 고객 특성을 반영하세요.

규칙:
- keywords: 이 지역을 특징짓는 단어 5~10개

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
  - {day_label}에 맞지 않는 유형은 제외 (예: 주말에 "출근길 직장인" 제외)
  - 시간대별로 적절한 유형만 선택 (예: "야식 손님"은 저녁~심야에만)"""

PERSONA_PROMPT_TEMPLATE = """주어진 시간대+인물유형+지역키워드 조합으로 현실적인 고객 페르소나를 만드세요.
매장이 위치한 국가/도시의 문화, 언어, 소비 패턴을 반영하세요.

규칙:
- 각 페르소나는 반드시 독립적인 개인 1명입니다. 커플, 연인, 친구 쌍 등 관계로 묶인 페르소나를 만들지 마세요. 동행자가 있는 경우에도 "~와 함께 온 사람" 한 명으로만 표현하세요.
- id: 아무 값이나 넣으세요 (시스템이 자동 채번합니다)
- identity: 반드시 아래 제공된 identity 목록 중 하나를 그대로 사용 (통계 집계용 라벨)
- age_group: 반드시 다음 중 하나: {age_groups}
- gender: 반드시 다음 중 하나: {genders}
- description: 이 사람의 상황, 성격 1~2문장. 해당 국가의 실제 생활상을 반영. 특정 브랜드명이나 구체적 상품명(예: 바나나맛 우유, 컨디션)을 사용하지 말고, 니즈/카테고리 수준으로 표현 (예: "a sweet dairy beverage", "a hangover-relief drink")
- intent: 매장에서 하고 싶은 것 1문장 (자유 서술). 구체적 상품명 대신 카테고리나 니즈로 표현. 예: "조깅 후 수분 보충할 이온음료를 사고 싶다", "간단한 간식과 음료를 고르고 싶다"
- purpose: 반드시 아래 제공된 purpose 목록 중 하나를 그대로 사용 (통계 집계용 짧은 라벨)
- preferred_categories: 반드시 아래 제공된 카테고리 목록 중에서만 선택. 목록에 없는 카테고리를 임의로 만들지 마세요
- budget_min, budget_max: {budget_rule}
- behavior_tendency: 이동속도/탐색성향/충동구매 한 줄

## 언어
- 자유 서술 필드(`description`, `intent`, `behavior_tendency`)의 값은 **영어로** 작성하세요.
- 구조적 필드(`id`, `age_group`, `gender`, `identity`, `purpose`, `preferred_categories`, `budget_min`, `budget_max`)는 프롬프트에서 제공된 라벨/값을 그대로 사용합니다.
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
) -> list[Persona]:
    system_prompt = persona_prompt(currency)
    # Local stream per day: days are generated concurrently, so seeding the global
    # `random` module would make them race and repeat the same sequence.
    rng = random.Random(stable_seed(seed, "persona-spec", int(day))) if seed is not None else random.Random()

    day_label = WEEKDAY_LABELS[day]
    profiles_map = {p.hour: p for p in hourly_profiles}
    identity_list = "\n".join(f"  - {i}" for i in profile.identities)
    purpose_list = "\n".join(f"  - {p}" for p in profile.purposes)

    semaphore = asyncio.Semaphore(max_concurrent)
    tasks: list[tuple[int, asyncio.Task[PersonaBatch]]] = []

    async def _generate_batch(prompt: str) -> PersonaBatch:
        async with semaphore:
            return await llm.generate_structured_async(PersonaBatch, system_prompt, prompt, max_retries=3)

    for hour, hp in sorted(profiles_map.items()):
        if not hp.person_types or hp.visitor_count <= 0:
            continue

        logger.info(f"[persona] {day_label} hour {hour} slot ({hp.visitor_count} visitors) LLM generation start")

        for batch_start in range(0, hp.visitor_count, batch_size):
            current_size = min(batch_size, hp.visitor_count - batch_start)
            spec_lines: list[str] = []
            for i in range(current_size):
                n_types = min(rng.choice([1, 1, 2]), len(hp.person_types))
                types = rng.sample(hp.person_types, n_types)
                n_kw = min(rng.randint(1, 3), len(profile.keywords))
                kws = rng.sample(profile.keywords, n_kw)
                spec_lines.append(f"[{i}] {hour}시, {'+'.join(types)}, 키워드: {', '.join(kws)}")

            category_section = ""
            if categories:
                cat_list = "\n".join(f"  - {c}" for c in categories)
                category_section = f"## 카테고리 목록 (preferred_categories는 반드시 이 중에서만 선택)\n{cat_list}\n\n"

            persona_input = (
                f"매장 위치: {address}\n요일: {day_label}\n\n"
                f"## identity 목록 (반드시 이 중 하나 선택)\n{identity_list}\n\n"
                f"## purpose 목록 (반드시 이 중 하나 선택)\n{purpose_list}\n\n"
                f"{category_section}"
                f"아래 {current_size}명의 고객 페르소나를 생성하세요:\n\n"
                + "\n".join(spec_lines)
            )
            if custom_instruction:
                persona_input += f"\n\n추가 지시: {custom_instruction}"

            task = asyncio.create_task(_generate_batch(persona_input))
            tasks.append((hour, task))

    all_personas: list[Persona] = []
    for hour, task in tasks:
        try:
            batch = await task
        except Exception as e:
            logger.error(f"[persona] {day_label} hour {hour} batch generation failed: {e}")
            continue

        for generated in batch.personas:
            persona = Persona.model_validate(generated.model_dump())
            prefix = "F" if persona.gender == "Female" else "M"
            seq = len([p for p in all_personas if p.gender == persona.gender]) + 1
            persona.id = f"{prefix}{day.value}{seq:03d}"
            persona.day = day
            persona.arrival_hour = hour
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
) -> list[Persona]:
    """Personas for every open day. With `traffic` (fitted from the store's own transaction times),
    the model's hourly estimate keeps deciding who comes, but how many come each hour follows the
    data — asked for times, models collapse onto a few stereotyped peaks.

    `pace` turns the usual pace (customers a day, customers per request) into the one to use; it is asked after
    the first call, once the model that answers is settled (a small model on this computer is asked for less)."""
    profile = await analyze_location(
        llm, address, customer_profile, custom_instruction,
        supplemental_summary=supplemental_summary,
    )

    usual = Pace(daily_cap=_persona_daily_cap_ceiling(), batch_size=batch_size)
    settled = pace(usual) if pace is not None else usual
    daily_cap_now, batch_size = max(1, settled.daily_cap), max(1, settled.batch_size)
    open_days = [s for s in schedules if s.is_open]

    async def _process_day(schedule: DaySchedule) -> list[Persona]:
        hourly = await analyze_daily_traffic(
            llm, address, customer_profile, profile,
            schedule.day, schedule.open_hour, schedule.close_hour,
        )
        hourly = _usable_hourly(hourly, profile, schedule, daily_cap_now)
        if traffic is not None:
            hourly = _apply_traffic(hourly, traffic, schedule)
        hourly = _scale_hourly(hourly, daily_cap_now)
        return await generate_personas_for_day(
            llm, address, profile, schedule.day, hourly,
            seed=seed, custom_instruction=custom_instruction,
            batch_size=batch_size, max_concurrent=max_concurrent,
            categories=categories, currency=currency,
        )

    day_results = await asyncio.gather(*[_process_day(s) for s in open_days])
    all_personas: list[Persona] = [p for personas in day_results for p in personas]

    logger.info(f"[persona] generated {len(all_personas)} personas total across {len(open_days)} days")
    return all_personas


# Relative visits per hour of a plain convenience-store day (morning, lunch and evening peaks; other hours 2).
_PLAIN_DAY = {7: 4, 8: 6, 9: 4, 11: 4, 12: 7, 13: 6, 17: 5, 18: 7, 19: 6, 20: 5, 21: 4, 22: 3}


def _usable_hourly(hourly: list[HourlyProfile], profile: TradeAreaProfile, schedule: DaySchedule,
                   cap: int) -> list[HourlyProfile]:
    """Hours the persona step can use. Small models sometimes answer an open day with no visitors at all, or with
    visitors but no customer types; both left the day without customers. Hours without types get every identity
    of the trade area; a day without visitors gets a plain convenience-store day of `cap` visitors."""
    identities = list(profile.identities) or ["shopper"]
    fixed = [h if h.person_types or h.visitor_count <= 0 else h.model_copy(update={"person_types": identities})
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
    return [HourlyProfile(hour=h, visitor_count=n, person_types=identities) for h, n in counts.items()]


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
    raw = os.getenv("PERSONA_DAILY_CAP")
    if raw is None:
        return 100
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"[persona] invalid PERSONA_DAILY_CAP={raw!r}; falling back to 100")
        return 100
    if value < 10:
        logger.warning(f"[persona] PERSONA_DAILY_CAP={value} below minimum; clamping to 10")
        return 10
    return value


def _scale_hourly(profiles: list[HourlyProfile], cap: int) -> list[HourlyProfile]:
    """Scale hourly visitor_count proportionally so the daily sum never exceeds cap.

    Preserves the LLM-emitted shape (peaks, off-peaks). If rounding pushes the
    total over cap, peel 1 off the busiest bucket until the sum fits — cap is
    a strict ceiling.
    """
    total = sum(p.visitor_count for p in profiles)
    if total <= cap:
        return profiles
    ratio = cap / total
    scaled: list[HourlyProfile] = [
        HourlyProfile(
            hour=p.hour,
            visitor_count=max(0, round(p.visitor_count * ratio)),
            person_types=p.person_types,
        )
        for p in profiles
    ]
    excess = sum(p.visitor_count for p in scaled) - cap
    while excess > 0:
        i = max(range(len(scaled)), key=lambda idx: scaled[idx].visitor_count)
        if scaled[i].visitor_count == 0:
            break
        scaled[i].visitor_count -= 1
        excess -= 1
    return scaled
