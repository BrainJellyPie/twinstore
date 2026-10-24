"""Stage 3: impulse reactions. Inserts serendipity events for products exposed along the route."""

from store_emulator.domain.behavior import BehaviorCue
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.persona import Persona
from store_emulator.engine.prompting import format_budget, format_price, price_unit_rule
from .prompt_utils import format_cue_prompt

from .stage2_intent import IntentResponse

LEVEL_VISIBILITY_GUIDE = [
    "L3: 눈높이, 가장 잘 보여 선호 강도가 가장 높음",
    "L2: 허리 높이, 그 다음으로 잘 보임",
    "L4: 상단, 보이지만 손이 덜 감",
    "L1: 하단, 목적 구매가 아니면 우선순위가 낮음",
]


class ImpulseResponse(IntentResponse):
    """Additional model shopping actions, with the same engine-field boundary as intent."""


SYSTEM_PROMPT_TEMPLATE = """당신은 매장 고객의 세렌디피티(우연한 발견) 시뮬레이터입니다.
고객이 이미 결정한 동선 위에서, 지나가다가 발견할 수 있는 상품이나 프로모션에 반응하는 추가 행동을 생성하세요.

{price_unit_rule}

규칙:
- 새로 추가할 행동(browse / buy) 만 반환. 방문 순서 배치는 엔진이 자동 처리합니다
- 고객의 성향(충동구매 확률, 탐색 성향)을 반영
- 현실적으로 0~3개 정도의 세렌디피티 이벤트가 적당. 0개도 가능
- action 은 browse 또는 buy 만 사용
- target 은 노출 상품의 접근 타일 좌표를 사용
- **buy 시 product_sku 는 아래 "경로상 노출되는 상품" 목록의 sku 중 하나만 사용**
- buy 시 quantity 는 구매 수량 (기본 1)
- **browse / buy 의 description 은 노출 상품 목록의 상품만 묘사**
- description 은 해당 행동 시점의 상황만 묘사 (이후 행동 참조 금지)
- reasoning은 600자 이하, 각 행동의 description은 400자 이하로 간결하게 작성하고 같은 문장을 반복하지 마세요
- 설명이 없으면 null 대신 빈 문자열("")을 사용하세요
- browse의 product_sku는 빈 문자열(""), quantity는 1로 작성하세요. null을 사용하지 마세요.
- dwell은 0~120초의 정수입니다. 정하지 않은 시간은 null 대신 기본값 0을 사용하세요.

## 언어
- 자유 서술 필드(`reasoning` 및 각 action의 `description`)의 값은 **영어로** 작성하세요.
- 구조적 필드(`action`, `target`, `face`, `dwell`, `product_sku`, `quantity`, `nav`, `area`)는 한국어 prompt 에서 정의된 그대로 유지합니다.
- 영어 표현은 자연스러운 콘텐츠 톤을 유지하세요."""

SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.format(price_unit_rule=price_unit_rule("USD"))


def build_system_prompt(
    max_products: int,
    allow_no_purchase: bool,
    existing_buys: int = 0,
    browse_required_before_buy: bool = False,
    currency: str = "USD",
    *,
    product_codes: bool = False,
    max_quantity: int | None = None,
) -> str:
    """System prompt with pattern-specific constraints applied."""
    constraints: list[str] = []
    if max_quantity is not None:
        constraints.append(f"- buy의 quantity는 1~{max_quantity} 사이의 정수로 작성하세요 (기본 1)")
    if max_products == 0:
        constraints.append("- 이 고객은 구매 의사가 없습니다. buy 이벤트를 추가하지 마세요")
    elif max_products > 0:
        remaining = max(0, max_products - existing_buys)
        constraints.append(f"- 기존 구매 {existing_buys}개 포함, 최대 {max_products}개까지 가능 (추가 가능: {remaining}개)")
    if allow_no_purchase:
        constraints.append("- 이 고객은 아무것도 안 사도 되는 유형입니다")
    if browse_required_before_buy:
        constraints.append("- buy 전에 반드시 같은 rack의 같은 접근 타일에서 browse를 먼저 추가하세요 (browse→buy 세트로 반환)")

    extra = "\n".join(constraints)
    if extra:
        extra = f"\n\n추가 제약:\n{extra}"

    system = SYSTEM_PROMPT_TEMPLATE.format(price_unit_rule=price_unit_rule(currency))
    if product_codes:
        system = system.replace('목록의 sku 중 하나만 사용', '목록의 상품 코드 중 하나만 사용 (상품명이나 임의 코드 금지)')
    return system + extra


def build_user_prompt(
    persona: Persona,
    intent: IntentResponse,
    exposed_products: list[tuple[Rack, Slot, str]],
    day_of_week: str = "",
    address: str = "",
    customer_profile: str = "",
    cue: BehaviorCue | None = None,
    *,
    grid_size: tuple[int, int],
    visibility: dict[str, float] | None = None,
    currency: str = "USD",
    records: dict[str, SlotItem] | None = None,
) -> str:
    """`visibility` (sku → 0–1) comes from the perception model. When given, it already
    accounts for shelf level, distance and facing, so the level heuristic is not repeated."""
    lines: list[str] = []

    lines.append("## 기존 이벤트 시퀀스")
    for i, event in enumerate(intent.actions):
        action_label = event.action or event.nav
        lines.append(f"  [{i}] {action_label}: {event.description}")
    lines.append("")

    lines.append("## 경로상 노출되는 상품")
    if visibility is None:
        lines.append("공통 진열 높이 기준:")
        for guide in LEVEL_VISIBILITY_GUIDE:
            lines.append(f"  - {guide}")
        lines.append("상품별 level만 보고 이 공통 기준을 적용하세요.")
    else:
        lines.append("시인성(0~1)은 고객이 실제 동선에서 그 상품을 봤을 가능성입니다 (진열 높이·거리·방향 반영). 높을수록 눈에 잘 띕니다.")
    record_ids = {(item.sku, item.name, item.price, item.promo): code for code, item in (records or {}).items()}
    rack_codes: dict[str, str] = {}
    lines.append("진열대 표의 R번호는 상품이 놓인 곳입니다. target은 그 진열대의 접근타일을 사용하세요.")
    for rack, _, _ in exposed_products:
        if rack.id in rack_codes:
            continue
        code = f"R{len(rack_codes) + 1}"
        rack_codes[rack.id] = code
        overlay = f" (매대: {rack.rack_decoration_desc})" if rack.rack_decoration_desc else ""
        lines.append(f"  {code}: {rack.rack_name or rack.id}({rack.type}){overlay} @ 접근타일 {sorted(rack.access_tiles(grid_size))[:3]}")
    lines.append("상품 줄: 상품 코드/sku, 이름, 가격, 프로모션, 진열대 R번호, level, 시인성(제공된 경우).")
    for f, slot, sku in exposed_products:
        matched = next((i for i in slot.items if i.sku == sku), None)
        promo = f" [{matched.promo}]" if matched and matched.promo else ""
        name = matched.name if matched else sku
        price = matched.price if matched else 0
        seen = f" 시인성={visibility.get(sku, 0.0):.2f}" if visibility is not None else ""
        code = record_ids.get((sku, name, price, matched.promo if matched else ""), sku)
        lines.append(
            f"  - {code}: {name} {format_price(price, currency)}{promo} | {rack_codes[f.id]} level={slot.level}{seen}"
        )
    lines.append("")

    lines.append("## 고객 성향")
    lines.append(f"  {persona.identity} ({persona.age_group}, {persona.gender}): {persona.behavior_tendency}")
    lines.append(f"  방문 목적: {persona.purpose}")
    if persona.preferred_categories:
        lines.append(f"  선호 카테고리: {', '.join(persona.preferred_categories)}")
    if persona.budget_max > 0:
        lines.append(f"  예산 범위: {format_budget(persona.budget_min, persona.budget_max, currency)}")
    if cue:
        lines.append(f"  현재 상태: {format_cue_prompt(cue)}")
    lines.append("")

    if day_of_week or address or customer_profile:
        lines.append("## 환경")
        if day_of_week:
            lines.append(f"  요일: {day_of_week}")
        if address:
            lines.append(f"  주소: {address}")
        if customer_profile:
            lines.append(f"  Customer profile: {customer_profile}")
        lines.append("")

    lines.append("경로상 노출 상품을 보고, 이 고객이 추가로 반응할 행동을 생성하세요.")
    lines.append("방문 순서는 신경쓰지 마세요. 엔진이 최적 경로로 자동 배치합니다.")
    return "\n".join(lines)
