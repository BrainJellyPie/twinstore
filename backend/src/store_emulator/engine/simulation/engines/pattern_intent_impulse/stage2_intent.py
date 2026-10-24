"""Stage 2: action-sequence generation. Produces the customer's in-store event sequence from the chosen pattern.

Prompt layout is cache-friendly: everything that is identical for every customer
of a store (instructions + the full rack/product catalog) lives in the system
prompt, and everything customer-specific (pattern, situation, persona) lives in
the user prompt. Providers and local servers with prefix caching (Gemini implicit
caching, OpenAI, vLLM, llama.cpp) then reuse the catalog prefix across customers.
"""

from typing import cast

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.rack import RackType
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.engine.prompting import format_budget, format_price, price_unit_rule
from .prompt_utils import format_cue_prompt

LEVEL_PREFERENCE_GUIDE = [
    "L3: 눈높이로 가장 먼저 인지되는 편",
    "L2: 허리 높이로 그 다음으로 잘 보이는 편",
    "L4: 상단이라 인지는 되지만 손이 덜 가는 편",
    "L1: 하단이라 목적 구매가 아니면 우선순위가 낮은 편",
]


class GeneratedAction(CustomerAction):
    """Model narration is brief; authored and engine-generated domain actions remain unrestricted."""
    description: str = Field(default="", max_length=400)

    @field_validator("description", mode="before")
    @classmethod
    def _brief_description(cls, value: object) -> object:
        if value is None:
            return ""
        return value[:400] if isinstance(value, str) else value


class IntentResponse(BaseModel):
    reasoning: str = Field(default="", max_length=600)
    actions: list[GeneratedAction] = []

    @field_validator("reasoning", mode="before")
    @classmethod
    def _brief_reasoning(cls, value: object) -> object:
        if value is None:
            return ""
        return value[:600] if isinstance(value, str) else value

    @field_validator("actions", mode="before")
    @classmethod
    def _model_actions(cls, value: object, info: ValidationInfo) -> object:
        # SkipJsonSchema hides internal hints from the prompt but still accepts
        # them during validation. Only the engine may select those offer fields.
        if not isinstance(value, (list, tuple)):
            return value
        cleaned: list[object] = []
        for action in cast(list[object] | tuple[object, ...], value):
            if isinstance(action, CustomerAction):
                action = action.model_dump()
            if isinstance(action, dict):
                action = {key: item for key, item in cast(dict[str, object], action).items()
                          if key not in {"origin", "product_block", "product_level"}}
                if info.mode == "json":
                    # A before-validator returns Python containers. Preserve JSON
                    # array → tuple semantics for Instructor's strict validation.
                    for key in ("target", "area"):
                        coordinates = action.get(key)
                        if isinstance(coordinates, list):
                            action[key] = tuple(cast(list[object], coordinates))
            cleaned.append(action)
        return cleaned


def build_system_prompt(store: Store, currency: str = "USD") -> str:
    """Static per store: identical for every customer, so it is a cacheable prefix."""
    return f"""당신은 매장 고객 행동 시뮬레이터입니다.
주어진 매장 정보와 고객 페르소나를 보고, 이 고객이 매장에서 어떤 행동을 할지 이벤트 시퀀스를 생성하세요.
고객별 행동 패턴과 추가 규칙은 사용자 메시지에 주어집니다.

공통 규칙:
- pay는 카운터에서 딱 1회만 발생합니다 (구매 물건이 없으면 생략)
- 시퀀스 순서는 enter → 이동/browse/buy → pay → exit
- 반드시 {{"nav": "leave"}} 으로 종료
- **buy 의 product_sku 는 아래 진열대 목록의 sku 중 하나만 사용**
- **browse / buy 의 description 은 아래 진열대 목록의 상품만 묘사**
- **buy 는 아래 진열대 목록에 적합한 상품이 있을 때만 추가**
- 고객의 예산을 크게 넘는 구매는 하지 않습니다
- reasoning은 600자 이하, 각 행동의 description은 400자 이하로 간결하게 작성하고 같은 문장을 반복하지 마세요
- 설명이 없으면 null 대신 빈 문자열("")을 사용하세요

{price_unit_rule(currency)}

필드 설명:
- action: 행동 유형. enter / move / browse / buy / pay / wander / exit 중 하나
- target: 아래 rack 의 '접근 타일' 좌표 중 하나 [x, y]
- face: 고객이 바라보는 rack 면 (N/S/E/W)
- dwell: 해당 위치 머무는 시간 (초, 최대 120)
- product_sku: buy 시 아래 진열대 목록의 sku 중 하나
- quantity: buy 시 구매 수량 (기본 1. 같은 상품을 여러 개 살 때만 2 이상)
- nav="area" 일 때 area: [x1, y1, x2, y2] 배회 영역
- description: 해당 행동 시점의 상황만 묘사. 진열대 목록의 상품만 다룬다.

## 언어
- 자유 서술 필드(`reasoning` 및 각 action의 `description`)의 값은 **영어로** 작성하세요.
- 구조적 필드(`action`, `target`, `face`, `dwell`, `product_sku`, `quantity`, `nav`, `area`)는 한국어 prompt 에서 정의된 그대로 유지합니다.
- 영어 표현은 자연스러운 콘텐츠 톤을 유지하세요.

{_store_block(store, currency)}"""


def _store_block(store: Store, currency: str) -> str:
    lines: list[str] = []
    lines.append("## 매장 정보")
    lines.append(f"- 유형: {store.type}")
    lines.append(f"- 그리드 크기: {store.grid_size[0]}×{store.grid_size[1]}")
    lines.append("")

    lines.append("## rack 및 상품")
    lines.append("공통 진열 높이 기준:")
    for guide in LEVEL_PREFERENCE_GUIDE:
        lines.append(f"  - {guide}")
    lines.append("같은 카테고리의 대안이 여러 개면 진열 높이 차이를 약하게 참고하되, 명확한 목적 구매는 고객 의도를 우선하세요.")
    lines.append("상품 줄 형식: b<block>/<face> L<level>: 상품명 (sku) 가격 [프로모션]; ...")
    lines.append("")
    for f in store.racks:
        if f.type in {RackType.ENTRANCE, RackType.EXIT}:
            continue
        access = sorted(f.access_tiles(store.grid_size))
        label = f.rack_name or f.id
        lines.append(f"### {f.id} ({f.type}, {label})")
        if f.rack_desc:
            lines.append(f"  설명: {f.rack_desc}")
        if f.rack_decoration_desc:
            lines.append(f"  부착물: {f.rack_decoration_desc}")
        if access:
            lines.append(f"  접근 타일: {access[:6]}{'...' if len(access) > 6 else ''}")
        for slot in f.slots:
            if not slot.items:
                continue
            items = "; ".join(
                f"{item.name} ({item.sku}) {format_price(item.price, currency)}" + (f" [{item.promo}]" if item.promo else "")
                for item in slot.items
            )
            lines.append(f"  - b{slot.block}/{slot.face} L{slot.level}: {items}")
    lines.append("")

    lines.append("## 입구/출구")
    for e in store.entrances:
        lines.append(f"  입구: {e.occupied_positions}")
    for e in store.exits:
        lines.append(f"  출구: {e.occupied_positions}")
    for c in store.counters:
        label = c.rack_name or c.id
        lines.append(f"  카운터: {label}, 결제 타일: {sorted(c.service_access_tiles(store.grid_size))[:4]}")
    return "\n".join(lines)


def build_user_prompt(
    persona: Persona,
    arrival_hour: int,
    concurrent_visitors_in_hour: int,
    day_of_week: str = "",
    cue: BehaviorCue | None = None,
    *,
    pattern: BehaviorPattern,
    grammar_override: str = "",
    currency: str = "USD",
) -> str:
    grammar = grammar_override if grammar_override else pattern.grammar
    lines: list[str] = []

    lines.append(f"## 이 고객의 행동 패턴: {pattern.name}")
    lines.append(grammar)
    lines.append("")
    lines.append("이 고객에게 적용되는 규칙:")
    if pattern.browse_required_before_buy:
        lines.append("- buy 직전에 반드시 같은 rack에서의 browse가 있어야 합니다")
    if pattern.allow_no_purchase:
        lines.append("- 구매 없이 퇴장도 가능합니다. 마음에 드는 상품이 없거나 가격·예산이 맞지 않으면 억지로 구매하지 말고 퇴장하세요")
    lines.append(f"- 한 고객의 구매 상품은 최대 {pattern.max_products}개")
    lines.append("")

    lines.append("## 현재 상황")
    lines.append(f"- 시간: {arrival_hour}시")
    lines.append(f"- 같은 시간대 방문자: 약 {concurrent_visitors_in_hour}명")
    if day_of_week:
        lines.append(f"- 요일: {day_of_week}")
    if cue:
        lines.append(f"- 고객 상태: {format_cue_prompt(cue)}")
    lines.append("")

    lines.append("## 고객 페르소나")
    lines.append(f"- 유형: {persona.identity} ({persona.age_group}, {persona.gender})")
    lines.append(f"- 설명: {persona.description}")
    lines.append(f"- 방문 목적: {persona.purpose}")
    lines.append(f"- 의도: {persona.intent}")
    lines.append(f"- 선호 카테고리: {', '.join(persona.preferred_categories)}")
    lines.append(f"- 예산: {format_budget(persona.budget_min, persona.budget_max, currency)}")
    lines.append(f"- 행동 성향: {persona.behavior_tendency}")
    lines.append("")

    lines.append("이 고객의 매장 내 행동 이벤트 시퀀스를 생성하세요.")
    return "\n".join(lines)
