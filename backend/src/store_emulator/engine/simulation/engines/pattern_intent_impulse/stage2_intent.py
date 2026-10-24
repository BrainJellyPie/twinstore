"""Stage 2: action-sequence generation. Produces the customer's in-store event sequence from the chosen pattern.

Prompt layout is cache-friendly: everything that is identical for every customer
of a store (instructions + the full rack/product catalog) lives in the system
prompt, and everything customer-specific (pattern, situation, persona) lives in
the user prompt. Providers and local servers with prefix caching (Gemini implicit
caching, OpenAI, vLLM, llama.cpp) then reuse the catalog prefix across customers.
"""

import hashlib
import json
from typing import ClassVar, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, create_model, field_validator

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.rack import Rack, RackType, Slot, SlotItem
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, PathFinder, Position
from store_emulator.engine.prompting import format_budget, format_price, price_unit_rule
from store_emulator.engine.routing.route_builder import entrance_position, face_access_tile
from store_emulator.engine.routing.store_lookup import resolve_buy_placement
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

    @field_validator("dwell", mode="before")
    @classmethod
    def _unspecified_dwell(cls, value: object) -> object:
        return 0 if value is None else value

    @field_validator("description", mode="before")
    @classmethod
    def _brief_description(cls, value: object) -> object:
        if value is None:
            return ""
        return value[:400] if isinstance(value, str) else value


class IntentResponse(BaseModel):
    actions_optional: ClassVar[bool] = False
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
                if action.get("action") != Action.BUY:
                    for key, default in (("product_sku", ""), ("quantity", 1)):
                        if key in action and action[key] is None:
                            action[key] = default
                if info.mode == "json":
                    # A before-validator returns Python containers. Preserve JSON
                    # array → tuple semantics for Instructor's strict validation.
                    for key in ("target", "area"):
                        coordinates = action.get(key)
                        if isinstance(coordinates, list):
                            action[key] = tuple(cast(list[object], coordinates))
            cleaned.append(action)
        return cleaned


class CatalogSelection(BaseModel):
    codes: list[str] = []


def catalog_selection_model(records: dict[str, SlotItem], maximum: int, *, required: bool = False) -> type[CatalogSelection]:
    mapping = {code: item.sku for code, item in records.items()}
    digest = hashlib.sha256(json.dumps(mapping, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    constraints: dict[str, JsonValue] = {"items": {"type": "string", "enum": list(records)}} if records else {}

    class BoundedCatalogSelection(CatalogSelection):
        model_config = ConfigDict(json_schema_extra={"$comment": f"catalog-sku-map:{digest}"})

        @field_validator("codes")
        @classmethod
        def _known_codes(cls, values: list[str]) -> list[str]:
            unknown = sorted(set(values) - records.keys())
            if unknown:
                raise ValueError(f"Unknown product codes: {unknown}. Copy codes from the supplied catalog.")
            return list(dict.fromkeys(values))

    limit = min(maximum, len(records))
    codes = (Field(max_length=limit, json_schema_extra=constraints) if required else
             Field(default_factory=list[str], max_length=limit, json_schema_extra=constraints))
    return create_model("BoundedCatalogSelection", __base__=BoundedCatalogSelection, codes=(list[str], codes))


def build_catalog_selection_prompt(store: Store, records: dict[str, SlotItem], maximum: int, currency: str) -> str:
    lines = ["## 후보 상품 선택",
        f"매장 유형: {store.type}. 아래는 매장의 전체 상품 목록입니다.",
        f"고객의 목적, 행동 패턴, 예산을 고려해 구매하거나 자세히 살펴볼 후보를 최대 {maximum}개 고르세요.",
        "최종 구매 및 동선은 다음 단계에서 정합니다. 여러 필요를 고려하되 관심 상품이 없으면 빈 목록을 반환하세요.",
        "codes 목록은 반드시 포함하세요. 관심 상품이 없으면 codes: []를 명시하세요.",
        "codes에는 목록의 상품 코드만 순서대로 넣으세요. 같은 코드를 반복하거나 새 코드를 만들지 마세요.",
        price_unit_rule(currency), ""]
    lines.extend(f"{code}: {item.name} {format_price(item.price, currency)}" + (f" [{item.promo}]" if item.promo else "")
                 for code, item in records.items())
    return "\n".join(lines)


def catalog_records(store: Store) -> dict[str, SlotItem]:
    """One short reference per visible offer; identical repeated placements share the record."""
    offers: dict[tuple[str, str, int, str], SlotItem] = {}
    skus = {item.sku for rack in store.racks for slot in rack.slots for item in slot.items}
    for rack in store.racks:
        if rack.type in {RackType.ENTRANCE, RackType.EXIT}:
            continue
        for slot in rack.slots:
            for item in slot.items:
                offers.setdefault((item.sku, item.name, item.price, item.promo), item)
    prefix = "@P"
    while any(f"{prefix}{index}" in skus for index in range(1, len(offers) + 1)):
        prefix = "@" + prefix
    return {f"{prefix}{index}": item for index, item in enumerate(offers.values(), 1)}


def catalog_response_model[T: IntentResponse](base: type[T], records: dict[str, SlotItem], *,
                                              max_quantity: int | None = None) -> type[T]:
    """Keep offer references in cached answers until the engine binds their exact placement."""
    mapping = {code: item.sku for code, item in records.items()}
    digest = hashlib.sha256(json.dumps(mapping, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    constraints: dict[str, JsonValue] = {"enum": ["", *mapping]}
    quantity_bounds: dict[str, JsonValue] = ({"minimum": 1, "maximum": max_quantity}
                                            if max_quantity is not None else {})

    class CatalogAction(GeneratedAction):
        product_sku: str = Field(default="", json_schema_extra=constraints)
        # Guide constrained decoding; non-enforcing providers still use the
        # executor's existing clamping rather than invalidating the whole visit.
        quantity: int = Field(default=1, json_schema_extra=quantity_bounds)

    return create_model(base.__name__, __base__=base,
        __config__=ConfigDict(json_schema_extra={"$comment": f"catalog-offer-codes-v2:{digest}"}),
        actions=(list[CatalogAction], Field(default_factory=list[CatalogAction]) if base.actions_optional else Field()))


def decode_catalog_response[T: IntentResponse](base: type[T], response: IntentResponse,
                                              records: dict[str, SlotItem], store: Store, *,
                                              exposed: list[tuple[Rack, Slot, str]] | None = None,
                                              pathfinder: PathFinder | None = None) -> T:
    """Bind model codes to real offers after stripping all model-supplied internal hints."""
    result = base.model_validate(response.model_dump())
    grid = store.walkable_grid()
    allowed = ({(rack.id, slot.block, slot.face, slot.level, sku) for rack, slot, sku in exposed}
               if exposed is not None else None)
    start = entrance_position(store)
    reachable: dict[Position, bool] = {}

    def accessible(rack: Rack, slot: Slot) -> bool:
        tile = face_access_tile(rack, slot.face, store.grid_size, grid, block=slot.block)
        if tile is None:
            return False
        if pathfinder is None:
            return True
        if tile not in reachable:
            path = pathfinder.find_path(grid, start, tile)
            reachable[tile] = tile == start or bool(path and path[-1] == tile)
        return reachable[tile]

    for action in result.actions:
        item = records.get(action.product_sku)
        if item is None and allowed is not None:
            # The exposure stage presents one anchor offer per SKU. A provider
            # ignoring the code grammar must still buy that observed offer.
            item = next((item for item in records.values() if item.sku == action.product_sku), None)
        if item is None and allowed is None and pathfinder is not None and action.action == Action.BUY:
            # A canonical SKU still selects its legacy offer by stance first.
            # Only an identical offer may supply a reachable alternative copy.
            placement = resolve_buy_placement(store, target=action.target, face=action.face, sku=action.product_sku)
            if placement is not None:
                item = next((item for item in placement[1].items if item.sku == action.product_sku), None)
        if item is None:
            continue  # Canonical SKUs from non-grammar providers keep legacy stance resolution.
        if action.action != Action.BUY:
            action.product_sku = item.sku
            continue
        racks: list[Rack] = []
        for rack in store.racks:
            slots = [slot for slot in rack.slots
                     if (candidate := next((i for i in slot.items if i.sku == item.sku), None)) is not None
                     and (allowed is None or (rack.id, slot.block, slot.face, slot.level, item.sku) in allowed)
                     and (candidate.name, candidate.price, candidate.promo) == (item.name, item.price, item.promo)
                     and not any(lock.block == slot.block and lock.face == slot.face for lock in rack.locked_faces)
                     and accessible(rack, slot)]
            if slots:
                racks.append(rack.model_copy(update={"slots": slots}))
        placement = resolve_buy_placement(store.model_copy(update={"racks": racks}),
                                          target=action.target, face=action.face, sku=item.sku)
        if placement is None:
            action.product_sku = ""  # The invalid-buy guard drops it, never substitutes another offer.
            continue
        rack, slot = placement
        action.product_sku = item.sku
        action.target = face_access_tile(rack, slot.face, store.grid_size, grid, block=slot.block)
        action.face = slot.face
        action.product_block, action.product_level = slot.block, slot.level
    return result


def build_system_prompt(store: Store, currency: str = "USD", *, records: dict[str, SlotItem] | None = None,
                        focused: bool = False, max_quantity: int | None = None) -> str:
    """Static per store: identical for every customer, so it is a cacheable prefix."""
    scope = ("## 후보 상품 범위\n전체 상품을 검토해 고른 고객별 후보만 아래 상품 목록에 표시합니다. "
             "다른 상품도 매장에 있으며 모든 진열대와 이동 공간은 그대로입니다. "
             "이 단계에서는 표시된 후보로만 구매를 계획하세요.\n\n") if focused else ""
    quantity_rule = (f"1~{max_quantity} 사이의 정수, 기본 1" if max_quantity is not None
                     else "기본 1. 같은 상품을 여러 개 살 때만 2 이상")
    return f"""당신은 매장 고객 행동 시뮬레이터입니다.
주어진 매장 정보와 고객 페르소나를 보고, 이 고객이 매장에서 어떤 행동을 할지 이벤트 시퀀스를 생성하세요.
고객별 행동 패턴과 추가 규칙은 사용자 메시지에 주어집니다.

공통 규칙:
- actions 필드는 반드시 포함하세요. 행동이 없으면 빈 배열 []을 명시하고 필드를 생략하지 마세요.
- pay는 카운터에서 딱 1회만 발생합니다 (구매 물건이 없거나 매장에 카운터가 없으면 생략)
- 시퀀스 순서는 enter → 이동/browse/buy → pay → exit
- 반드시 {{"nav": "leave"}} 으로 종료
- **buy 의 product_sku 는 아래 상품 목록의 짧은 상품 코드 중 하나만 사용**
- **browse / buy 의 description 은 아래 진열대 목록의 상품만 묘사**
- **buy 는 아래 진열대 목록에 적합한 상품이 있을 때만 추가**
- 고객의 예산을 크게 넘는 구매는 하지 않습니다
- reasoning은 600자 이하, 각 행동의 description은 400자 이하로 간결하게 작성하고 같은 문장을 반복하지 마세요
- 설명이 없으면 null 대신 빈 문자열("")을 사용하세요
- buy가 아닌 행동의 product_sku는 빈 문자열(""), quantity는 1로 작성하세요. null을 사용하지 마세요.

{price_unit_rule(currency)}

필드 설명:
- action: 행동 유형. enter / move / browse / buy / pay / wander / exit 중 하나
- target: 아래 rack 의 '접근 타일' 좌표 중 하나 [x, y]
- face: 고객이 바라보는 rack 면 (N/S/E/W)
- dwell: 해당 위치 머무는 시간 (초, 0~120). 정하지 않은 시간은 null 대신 기본값 0을 사용
- product_sku: buy 시 아래 상품 목록의 코드 (예: @P1). 상품명이나 임의의 코드를 쓰지 마세요
- quantity: buy 시 구매 수량 ({quantity_rule})
- nav="area" 일 때 area: [x1, y1, x2, y2] 배회 영역
- description: 해당 행동 시점의 상황만 묘사. 진열대 목록의 상품만 다룬다.

## 언어
- 자유 서술 필드(`reasoning` 및 각 action의 `description`)의 값은 **영어로** 작성하세요.
- 구조적 필드(`action`, `target`, `face`, `dwell`, `product_sku`, `quantity`, `nav`, `area`)는 한국어 prompt 에서 정의된 그대로 유지합니다.
- 영어 표현은 자연스러운 콘텐츠 톤을 유지하세요.

{scope}{_store_block(store, currency, catalog_records(store) if records is None else records)}"""


def _store_block(store: Store, currency: str, records: dict[str, SlotItem]) -> str:
    lines: list[str] = []
    lines.append("## 매장 정보")
    lines.append(f"- 유형: {store.type}")
    lines.append(f"- 그리드 크기: {store.grid_size[0]}×{store.grid_size[1]}")
    lines.append("")

    lines.append("## 상품 목록 (코드: 상품명 가격 [프로모션])")
    for code, item in records.items():
        lines.append(f"  {code}: {item.name} {format_price(item.price, currency)}" + (f" [{item.promo}]" if item.promo else ""))
    record_ids = {(item.sku, item.name, item.price, item.promo): code for code, item in records.items()}
    lines.append("")
    lines.append("## rack 및 진열 위치")
    lines.append("공통 진열 높이 기준:")
    for guide in LEVEL_PREFERENCE_GUIDE:
        lines.append(f"  - {guide}")
    lines.append("같은 카테고리의 대안이 여러 개면 진열 높이 차이를 약하게 참고하되, 명확한 목적 구매는 고객 의도를 우선하세요.")
    lines.append("진열 줄 형식: b<block>/<face> L<level>: 상품 코드 목록. 여러 위치가 있으면 각 위치에 같은 상품들이 있습니다.")
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
        stock: dict[tuple[str, ...], list[str]] = {}
        for slot in f.slots:
            if not slot.items:
                continue
            codes = tuple(record_ids[key] for item in slot.items
                          if (key := (item.sku, item.name, item.price, item.promo)) in record_ids)
            if not codes:
                continue
            stock.setdefault(codes, []).append(f"b{slot.block}/{slot.face} L{slot.level}")
        for codes, positions in stock.items():
            lines.append(f"  - {', '.join(positions)}: {', '.join(codes)}")
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
