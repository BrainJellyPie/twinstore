import asyncio
import logging
import math
import os
import random
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Self, cast

from instructor.core.exceptions import IncompleteOutputException, InstructorRetryException
from litellm.exceptions import BadRequestError
from pydantic import BaseModel, ConfigDict, Field, GetJsonSchemaHandler, JsonValue, StringConstraints, ValidationInfo, create_model, field_validator, model_validator
from pydantic_core import CoreSchema

from store_emulator.domain.persona import AGE_GROUPS, GENDERS, AgeGroup, Gender, Persona
from store_emulator.domain.store import DaySchedule, validate_weekly_schedule
from store_emulator.domain.types import AsyncLLMClient, Weekday, WEEKDAY_LABELS, stable_seed
from store_emulator.engine.generators.traffic_profile import TrafficProfile, reshape_hourly_counts
from store_emulator.engine.llm_client import is_context_overflow
from store_emulator.engine.prompting import budget_example, canonical_identifier, minor_unit_scale

logger = logging.getLogger(__name__)

type PersonaLabel = Annotated[str, Field(max_length=120)]

_PROFILE_POOL_SIZES = {"keywords": 8, "identities": 16, "purposes": 16}


def _numbered_profile_schema(schema: dict[str, JsonValue]) -> None:
    properties = cast(dict[str, JsonValue], schema["properties"])
    for field, count in _PROFILE_POOL_SIZES.items():
        keys = [str(i) for i in range(1, count + 1)]
        properties[field] = {
            "type": "object", "additionalProperties": False,
            "required": [key for key in keys],
            "properties": {key: {"type": "string", "maxLength": 120} for key in keys},
        }


# Upper bounds well above what the prompts ask for. Schema-constrained local models (llama.cpp) are held to them, so a
# small model cannot repeat itself for minutes (one listed every hour four times).
class TradeAreaProfile(BaseModel):
    model_config = ConfigDict(json_schema_extra=_numbered_profile_schema)
    keywords: list[PersonaLabel] = Field(max_length=20)
    identities: list[PersonaLabel] = Field(max_length=40, json_schema_extra={"minItems": 1})
    purposes: list[PersonaLabel] = Field(max_length=40, json_schema_extra={"minItems": 1})

    @field_validator("keywords", "identities", "purposes", mode="before")
    @classmethod
    def _ordered_labels(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, dict):
            return value  # Existing providers and canonical caches retain arrays.
        assert info.field_name is not None
        keys = [str(i) for i in range(1, _PROFILE_POOL_SIZES[info.field_name] + 1)]
        values = cast(dict[str, object], value)
        if set(values) != set(keys):
            raise ValueError(f"Fill every numbered {info.field_name} key from 1 to {len(keys)}; do not omit or add keys.")
        return [values[key] for key in keys]

    @field_validator("keywords", "identities", "purposes")
    @classmethod
    def _usable_labels(cls, values: list[str]) -> list[str]:
        # A truthy list of blanks otherwise bypasses the empty-pool fallbacks
        # and becomes an impossible vocabulary for later customer prompts.
        # These are label pools, not weights: repeats must not bias random sampling.
        return list(dict.fromkeys(label.strip() for label in values if label.strip()))


class HourlyProfile(BaseModel):
    hour: int = Field(ge=0, le=23, strict=True)
    visitor_count: int = Field(ge=0, strict=True)
    person_types: list[PersonaLabel] = Field(max_length=10)

    @field_validator("person_types", mode="before")
    @classmethod
    def _empty_hour_types(cls, value: object, info: ValidationInfo) -> object:
        return [] if value is None and info.data.get("visitor_count") == 0 else value

    @field_validator("person_types")
    @classmethod
    def _usable_labels(cls, values: list[str]) -> list[str]:
        # _usable_hourly supplies trade-area types when positive traffic has
        # no usable labels; keep the visitor count so those customers survive.
        return list(dict.fromkeys(label.strip() for label in values if label.strip()))


class DailyTrafficResult(BaseModel):
    hourly_profiles: list[HourlyProfile] = Field(max_length=24)

    @model_validator(mode="after")
    def unique_hours(self) -> Self:
        hours = [profile.hour for profile in self.hourly_profiles]
        duplicates = sorted({hour for hour in hours if hours.count(hour) > 1})
        if duplicates:
            raise ValueError(f"Each hour must appear at most once; repeated hours: {duplicates}. Return one visitor count per hour.")
        return self


def traffic_response_model(open_hour: int, close_hour: int, *, identities: list[str] | None = None) -> type[DailyTrafficResult]:
    """Let the harness assign clock values to the model's ordered open-slot estimates."""
    hours = list(range(open_hour, close_hour))
    keys = [str(i) for i in range(len(hours))]
    choices = list(dict.fromkeys(identities or ["shopper"])) if identities is not None else []

    class SlotTrafficResult(DailyTrafficResult):
        @classmethod
        def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> dict[str, JsonValue]:
            schema = handler(core_schema)
            properties = cast(dict[str, JsonValue], schema["properties"])
            rows = cast(dict[str, JsonValue], properties["hourly_profiles"])
            ref = cast(dict[str, JsonValue], rows["items"])
            # Resolve the registered row, rather than inlining its identity
            # vocabulary 24 times in a plain-JSON provider's prompt.
            row = handler.resolve_ref_schema(ref)
            row_properties = cast(dict[str, JsonValue], row["properties"])
            row_properties.pop("hour")
            row["required"] = ["visitor_count", "person_types"]
            row["additionalProperties"] = False
            if choices:
                types = cast(dict[str, JsonValue], row_properties["person_types"])
                handler.resolve_ref_schema(cast(dict[str, JsonValue], types["items"]))["enum"] = choices
            properties["hourly_profiles"] = {
                "type": "object", "properties": {key: ref for key in keys},
                "required": [key for key in keys], "additionalProperties": False,
            }
            return schema

        @field_validator("hourly_profiles", mode="before")
        @classmethod
        def _assign_hours(cls, value: object) -> object:
            if isinstance(value, dict):
                entries = cast(dict[str, object], value)
                if set(entries) != set(keys):
                    missing = [key for key in keys if key not in entries]
                    unknown = [str(key) for key in entries if key not in keys]
                    raise ValueError(f"Return only these numbered opening slot keys: {keys}. "
                                     f"Missing keys: {missing}; unknown keys: {unknown}. "
                                     "Remove unknown entries. The closing boundary is not another opening slot.")
                value = [entries[key] for key in keys]
                if any(isinstance(row, dict) and "hour" in row for row in value):
                    raise ValueError("Do not combine numbered opening slots with explicit hour fields.")
            if not isinstance(value, list):
                return value
            rows = cast(list[object], value)
            if not rows:
                return rows
            positional = [isinstance(row, dict) and "hour" not in row for row in rows]
            if not any(positional):
                return rows  # Older/non-enforcing providers and cached results retain explicit clocks.
            if not all(positional):
                raise ValueError("Do not mix rows with and without hour. Omit hour from every row and follow the supplied slot order.")
            if len(rows) != len(hours):
                raise ValueError(f"Return one row for each opening-hour slot, in order: {hours}; got {len(rows)} rows.")
            return [{**cast(dict[str, object], row), "hour": hour} for row, hour in zip(rows, hours, strict=True)]

        @field_validator("hourly_profiles")
        @classmethod
        def _supplied_types(cls, rows: list[HourlyProfile]) -> list[HourlyProfile]:
            if not choices:
                return rows
            normalized: list[HourlyProfile] = []
            for row in rows:
                # Inactive legacy rows cannot supply a customer's identity.
                if row.visitor_count <= 0 or row.hour not in hours:
                    normalized.append(row)
                    continue
                labels: list[str] = []
                for value in row.person_types:
                    if value in choices:
                        labels.append(value)
                        continue
                    matches = [label for label in choices if label.casefold() == value.casefold()]
                    if len(matches) != 1:
                        raise ValueError("Choose supplied identity labels for person_types; do not invent different labels.")
                    labels.append(matches[0])
                # Empty lists still use the existing trade-area fallback.
                normalized.append(row.model_copy(update={"person_types": labels}))
            return normalized

    return SlotTrafficResult


class GeneratedPersona(BaseModel):
    """What the persona prompt asks for. The rest of a Persona (day, hour, receipt-derived fields) is filled in here:
    asking for no more keeps answers short and gives small models nothing to invent (one filled `category_rates` with
    percentages). Lengths are bounded well above a normal answer, so a local model cannot loop inside a string."""
    identity: PersonaLabel
    age_group: AgeGroup
    gender: Gender
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
    intent: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
    purpose: PersonaLabel
    preferred_categories: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list[str], max_length=10)
    budget_min: int = Field(default=0, ge=0, le=9_007_199_254_740_991)
    budget_max: int = Field(default=0, ge=0, le=9_007_199_254_740_991)
    behavior_tendency: str = Field(default="", max_length=300)

    @field_validator("age_group", "gender", mode="before")
    @classmethod
    def _canonical_demographic(cls, value: object, info: ValidationInfo) -> object:
        if isinstance(value, str):
            return canonical_identifier(value, AGE_GROUPS if info.field_name == "age_group" else GENDERS)
        return value

    @field_validator("preferred_categories", mode="before")
    @classmethod
    def _empty_preferences(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator("behavior_tendency", mode="before")
    @classmethod
    def _empty_behavior(cls, value: object) -> object:
        return "" if value is None else value

    @model_validator(mode="after")
    def ordered_budget(self) -> Self:
        if self.budget_max > 0 and self.budget_min > self.budget_max:
            raise ValueError("budget_min must not exceed budget_max when the upper limit is positive. "
                             "Use budget_max=0 only for an unspecified upper limit.")
        return self


MAX_PERSONAS_PER_BATCH = 12


class PersonaBatch(BaseModel):
    personas: list[GeneratedPersona] = Field(min_length=1, max_length=MAX_PERSONAS_PER_BATCH)


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


PROFILE_PROMPT = """Analyze the supplied neighborhood and shop description across the whole week.
Return three objects of distinct, short English labels (at most 120 characters each).
Use the numbered keys shown in the schema; put one label in each value. Fill every key exactly once and stop at the last key. Do not output arrays or add more keys:
- keywords: 8 characteristics of the area and shop, using keys "1" through "8".
- identities: 16 kinds of individual PEOPLE who might visit, using keys "1" through "16". A shop, product, or reason to visit is not a person type.
- purposes: 16 things customers want to DO at this shop, using keys "1" through "16". Use short action phrases starting with a verb; a person type is not a purpose.
Reflect the supplied country and city. Include plausible weekday, weekend and time-of-day differences. Do not repeat labels or synonyms to fill a list.
Return field values, not JSON schema definitions.
## 언어
Write keywords, identities and purposes in English."""

DAILY_TRAFFIC_PROMPT = """당신은 상권 분석 전문가입니다.
아래 제공된 identity 풀(고객 유형 목록)을 참고하여, **{day_label}**의 시간대별 방문 트래픽을 예측하세요.

규칙:
- hourly_profiles: an object with the supplied numbered slot keys ("0", "1", ...), not an array.
  영업 슬롯 **H ∈ [{open_hour}, {close_hour})**를 시간순으로 한 번씩 작성.
  각 행은 visitor_count와 person_types만 포함. hour는 출력하지 마세요. 시스템이 순서대로 시간을 부여합니다.
  아래 제공된 슬롯 목록의 각 줄마다 반드시 한 행씩 반환하세요. 방문객이 없는 슬롯도 visitor_count=0, person_types=[]로 포함하세요 (null이 아닌 빈 목록).
  각 H는 H:00–(H+1):00 슬롯입니다. 예: 영업 17~18시면 한 행만 반환하며 이 행은 H=17입니다.
  Return values, not schema definitions. Shape example only:
  {{"hourly_profiles":{{"0":{{"visitor_count":2,"person_types":[]}}}}}}
  Use the actual supplied slots and evidence; the example is not traffic data.
  Do not output properties, $defs, required or type definitions.
- visitor_count: 해당 시간대의 예상 방문객 수 (0 이상 정수).
  하루 총 방문객 수는 매장 입지/규모/상권 특성과 요일에 맞게 합리적으로 추론하여 결정.
  특정 시간대에 몰리는 자연스러운 형상(피크/오프피크/식사시간 등)을 반드시 반영하세요.
- person_types: **반드시 아래 identity 목록의 라벨을 그대로 사용.** {day_label}에 실제로 방문할 유형만 선택
  - 빈 문자열이나 공백뿐인 항목은 넣지 마세요.
  - 각 항목은 120자 이하. 라벨에 설명을 덧붙이거나 같은 구절을 반복하지 마세요.
  - {day_label}에 맞지 않는 유형은 제외 (예: 주말에 "출근길 직장인" 제외)
  - 시간대별로 적절한 유형만 선택 (예: "야식 손님"은 저녁~심야에만)

## 언어
Use the exact supplied identity labels. Do not translate or expand them."""

PERSONA_PROMPT_TEMPLATE = """Create realistic individual customers from the supplied requests, location, customer profile and evidence.
Return a personas array with one individual for each request row, in its exact order. Do not add people or repeat them. People in the same batch must have distinct descriptions and plausible differences in their needs or behavior, even when they share a customer type. Each row is one individual, even if accompanied by others. Do not output id, day or arrival_hour; the application assigns these.
Fields:
- identity and purpose: copy one exact label from the respective supplied list.
- age_group: one of {age_groups}. gender: one of {genders}.
- description: 1–2 sentences about this person's circumstances and character, consistent with their age_group and location.
- intent: one sentence about what this individual wants to do in this shop. Browsing is a valid intent. Both description and intent must contain meaningful text, not blanks.
- preferred_categories: {category_rule}. Use [] if there are none, never null.
- budget_min_major and budget_max_major: {budget_rule}. Keep any budget range supplied in the customer profile. Use nonnegative amounts; do not repeat digits. Use "0" if a budget is unspecified. budget_max_major="0" means no specified upper limit; otherwise the minimum must not exceed the maximum. Do not output budget_min or budget_max; the application fills those stored-unit fields.
- behavior_tendency: a short description of walking pace, browsing or impulse-buying behavior. An age or money amount is not a behavior. Use an empty string if no tendency is given, never null.
Use needs and product categories in descriptions, not brands or specific products. Reflect the country's culture and consumption habits.
## 언어
Write description, intent and behavior_tendency in natural English, even when the input uses another language. Preserve the exact supplied labels for identity, purpose, age_group and gender."""


def persona_prompt(currency: str = "USD", *, listed_categories: bool = False) -> str:
    return PERSONA_PROMPT_TEMPLATE.format(
        age_groups=", ".join(AGE_GROUPS),
        genders=", ".join(GENDERS),
        budget_rule=budget_example(currency),
        category_rule=("반드시 아래 제공된 카테고리 목록 중에서만 선택. 목록에 없는 카테고리를 임의로 만들지 마세요"
                       if listed_categories else
                       "Infer short English category labels from this customer's needs and purchase intent "
                       "(for example tea, snacks or fresh fruit). No category list is supplied. "
                       "Do not use brand or specific product names."),
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
    """Derive customer labels from the supplied profile, evidence and instructions."""
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
    *,
    custom_instruction: str = "",
    supplemental_summary: str = "",
) -> list[HourlyProfile]:
    day_label = WEEKDAY_LABELS[day]
    identity_list = "\n".join(f"  - {i}" for i in (profile.identities or ["shopper"]))

    system = DAILY_TRAFFIC_PROMPT.format(
        day_label=day_label, open_hour=open_hour, close_hour=close_hour,
    )
    user_input = (
        f"Address: {address}\nCustomer profile: {customer_profile}\n"
        f"요일: {day_label}\n영업: {open_hour}~{close_hour}시\n\n"
        f"## identity 목록\n{identity_list}\n\n"
        f"## 영업 슬롯 (각 번호가 hourly_profiles의 키; 정확히 {close_hour - open_hour}개)\n"
        + "\n".join(f"[{i}] {hour:02d}:00–{hour + 1:02d}:00" for i, hour in enumerate(range(open_hour, close_hour)))
    )
    # Labels alone cannot carry quantities, weekday mixes or peak hours from the
    # original evidence. Keep those inputs in this stage and its cache identity.
    if supplemental_summary:
        user_input += f"\nSupplemental data analysis: {supplemental_summary}"
    if custom_instruction:
        user_input += f"\n추가 지시: {custom_instruction}"
    logger.info(f"[area-analysis] {day_label} analyzing traffic...")
    result = await llm.generate_structured_async(
        traffic_response_model(open_hour, close_hour, identities=profile.identities), system, user_input, max_retries=3)
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
    customer_profile: str = "",
    supplemental_summary: str = "",
    sample_offset: int = 0,
    semaphore: asyncio.Semaphore | None = None,
    tally: BatchTally | None = None,
    on_written: Callable[[int], None] | None = None,
) -> list[Persona]:
    system_prompt = persona_prompt(currency, listed_categories=bool(categories))
    batch_size = max(1, min(batch_size, MAX_PERSONAS_PER_BATCH))
    # Local stream per day: days are generated concurrently, so seeding the global
    # `random` module would make them race and repeat the same sequence.
    rng = random.Random(stable_seed(seed, "persona-spec", int(day))) if seed is not None else random.Random()

    day_label = WEEKDAY_LABELS[day]
    profiles_map = {p.hour: p for p in hourly_profiles}
    # Non-enforcing models may return empty pools. Match the traffic fallback
    # instead of requiring the writer to choose from an impossible empty list.
    identities = list(dict.fromkeys(profile.identities or ["shopper"]))
    purposes = list(dict.fromkeys(profile.purposes or ["shopping"]))
    identity_list = "\n".join(f"  - {i}" for i in identities)
    purpose_list = "\n".join(f"  - {p}" for p in purposes)
    identity_choices: dict[str, JsonValue] = {"enum": [*identities]}
    purpose_choices: dict[str, JsonValue] = {"enum": [*purposes]}
    category_choices = list(dict.fromkeys(categories or []))
    scale = minor_unit_scale(currency)

    def budget_schema(schema: dict[str, JsonValue]) -> None:
        # The model copies major amounts; the parsed/cache model keeps minor
        # integers. Explicit new names prevent legacy cache values being scaled twice.
        properties = cast(dict[str, JsonValue], schema["properties"])
        required = cast(list[JsonValue], schema.get("required", []))
        for field in ("budget_min", "budget_max"):
            properties.pop(field)
            properties[field + "_major"] = {
                "type": "string", "maxLength": 19,
                "pattern": r"^[0-9]{1,16}$" if scale == 1 else r"^[0-9]{1,16}(\.[0-9]{1,2})?$",
                "description": f"Amount in {currency.upper()}, before conversion to stored money units.",
            }
        schema["required"] = [*required, "preferred_categories", "budget_min_major", "budget_max_major"]
        if category_choices:
            preferences = cast(dict[str, JsonValue], properties["preferred_categories"])
            preferences["items"] = {"type": "string", "maxLength": 80, "enum": [*category_choices]}

    class LabelledPersona(GeneratedPersona):
        model_config = ConfigDict(json_schema_extra=budget_schema)
        # Keep enums inline: llama.cpp resolves a $ref before its sibling constraints.
        identity: str = Field(max_length=120, json_schema_extra=identity_choices)
        purpose: str = Field(max_length=120, json_schema_extra=purpose_choices)

        @field_validator("preferred_categories")
        @classmethod
        def supplied_categories(cls, values: list[str]) -> list[str]:
            if not category_choices:
                return values
            selected = [canonical_identifier(value, category_choices) for value in values]
            if any(value not in category_choices for value in selected):
                raise ValueError("Choose only supplied category labels for preferred_categories; "
                                 "do not invent or translate labels. Use [] for no preferences.")
            return selected

        @model_validator(mode="before")
        @classmethod
        def major_budgets(cls, value: object) -> object:
            if not isinstance(value, dict):
                return value
            row = cast(dict[str, object], value)
            major = ("budget_min_major", "budget_max_major")
            if not any(field in row for field in major):
                return row  # Existing providers and canonical cached models use minor integers.
            if not all(field in row for field in major) or any(field in row for field in ("budget_min", "budget_max")):
                raise ValueError("Return both budget_min_major and budget_max_major; do not mix major and stored-unit fields.")
            converted = row.copy()
            for field in major:
                amount = converted.pop(field)
                if isinstance(amount, int) and not isinstance(amount, bool):
                    amount = str(amount)  # Plain JSON providers may omit quotes around whole amounts.
                if not isinstance(amount, str) or not re.fullmatch(r"[0-9]{1,16}(\.[0-9]{1,2})?", amount.strip()):
                    raise ValueError(f"{field} must be a nonnegative decimal string, without symbols or exponents.")
                minor = Decimal(amount.strip()) * scale
                if minor != minor.to_integral_value():
                    raise ValueError(f"{field} has a fraction that cannot be stored in {currency.upper()}.")
                converted[field.removesuffix("_major")] = int(minor)
            return converted

        @field_validator("identity", "purpose")
        @classmethod
        def supplied_label(cls, value: str, info: ValidationInfo) -> str:
            choices = identities if info.field_name == "identity" else purposes
            value = value.strip()
            if value in choices:
                return value
            matches = [label for label in choices if label.casefold() == value.casefold()]
            if len(matches) == 1:
                return matches[0]
            raise ValueError(f"Choose one supplied {info.field_name} label; do not leave it blank or invent a different label.")

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

    async def _generate_batch(chunk: list[tuple[int, str]], start: int, *, recover_context: bool = True) -> list[tuple[GeneratedPersona, int]]:
        persona_input = (
            f"매장 위치: {address}\n요일: {day_label}\n\n"
            # Identical hourly specs still represent different people. Include
            # their sample positions even when the provider cannot accept seed.
            f"Generation bookkeeping, not customer traits: sample seed={seed}; "
            f"daily customer positions={start + 1}-{start + len(chunk)}.\n\n"
            f"## identity 목록 (반드시 이 중 하나 선택)\n{identity_list}\n\n"
            f"## purpose 목록 (반드시 이 중 하나 선택)\n{purpose_list}\n\n"
            f"{category_section}"
            f"아래 {len(chunk)}명의 고객 페르소나를 생성하세요 (순서대로):\n\n"
            + "\n".join(f"[{i}] {line}" for i, (_, line) in enumerate(chunk))
        )
        # Category labels and arrival counts cannot carry the source evidence's
        # budgets, needs or preferences. Include it in every batch and cache key,
        # including probe requests and the bounded context/truncation recovery.
        if customer_profile:
            persona_input += f"\n\nCustomer profile: {customer_profile}"
        if supplemental_summary:
            persona_input += f"\nSupplemental data analysis: {supplemental_summary}"
        if custom_instruction:
            persona_input += f"\n\n추가 지시: {custom_instruction}"
        # Bound grammar-capable models to this task; keep the existing short/surplus
        # handling for providers that do not enforce the transmitted JSON schema.
        constraints: dict[str, JsonValue] = {"minItems": len(chunk), "maxItems": len(chunk)}
        batch_schema = create_model("PersonaBatch", __base__=PersonaBatch,
            personas=(list[LabelledPersona], Field(min_length=1, max_length=MAX_PERSONAS_PER_BATCH, json_schema_extra=constraints)))
        try:
            async with limit:
                batch = await llm.generate_structured_async(batch_schema, system_prompt, persona_input, max_retries=3)
        except (IncompleteOutputException, InstructorRetryException, BadRequestError) as error:
            cause = (error.failed_attempts[-1].exception
                     if isinstance(error, InstructorRetryException) and error.failed_attempts else error)
            if len(chunk) < 2 or not (isinstance(cause, IncompleteOutputException)
                                     or (recover_context and is_context_overflow(cause))):
                raise
            logger.info("[persona] %s: splitting an oversized or truncated %s-customer request", day_label, len(chunk))
            middle = len(chunk) // 2
            # Release the shared request slot before either child acquires it.
            # Output truncation can shrink down to one customer (at most 2*n-1
            # tasks for n <= 12). A shared oversized input prefix gets one split.
            # Only return the original batch once every child succeeds.
            first = await _generate_batch(chunk[:middle], start, recover_context=False)
            second = await _generate_batch(chunk[middle:], start + middle, recover_context=False)
            return first + second
        # Preserve each child's original hours even when a small model returns fewer customers.
        return [(generated, hour) for generated, (hour, _) in zip(batch.personas, chunk)]

    for batch_start in range(0, len(specs), batch_size):
        chunk = specs[batch_start:batch_start + batch_size]
        tasks.append(([hour for hour, _ in chunk], asyncio.create_task(_generate_batch(chunk, sample_offset + batch_start))))

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
    daily_cap_now = max(1, min(settled.daily_cap, population_cap))
    batch_size = max(1, min(settled.batch_size, MAX_PERSONAS_PER_BATCH))
    sample_cap = max(1, min(settled.sample_cap, daily_cap_now))
    open_days = [s for s in schedules if s.is_open]

    # One limit for all days (they run together): 10 requests a day at once came to 70, enough to hit rate limits.
    shared = asyncio.Semaphore(max(1, max_concurrent))
    tally = BatchTally()

    async def _day_visitors(schedule: DaySchedule) -> list[HourlyProfile]:
        hourly = await analyze_daily_traffic(
            llm, address, customer_profile, profile,
            schedule.day, schedule.open_hour, schedule.close_hour,
            custom_instruction=custom_instruction, supplemental_summary=supplemental_summary,
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
    probe_positions = 0

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

    def write(day: Weekday, hourly: list[HourlyProfile], *, sample_offset: int = 0) -> Awaitable[list[Persona]]:
        return generate_personas_for_day(
            llm, address, profile, day, hourly,
            seed=seed, custom_instruction=custom_instruction,
            customer_profile=customer_profile, supplemental_summary=supplemental_summary, sample_offset=sample_offset,
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
        probe_positions = n
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
        # A short recovered probe can leave gaps between its child ranges.
        # Reserve the entire request span so later batches cannot reuse a child.
        offset = probe_positions if probe_at is not None and probe_at[0] == schedule.day else 0
        out = await write(schedule.day, target, sample_offset=offset)
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
