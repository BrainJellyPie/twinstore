"""Stage 1: behavior-pattern selection. Picks a fitting pattern from persona + time + BehaviorCue."""

from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model, field_validator

from store_emulator.domain.behavior import BehaviorCue, BehaviorPattern
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.engine.prompting import format_budget
from .prompt_utils import format_cue_prompt


class PatternSelectionResponse(BaseModel):
    reasoning: str = Field(default="", max_length=600)
    pattern_id: str = ""
    grammar_override: str = Field(default="", max_length=1200)

    @field_validator("reasoning", mode="before")
    @classmethod
    def _brief_reasoning(cls, value: object) -> object:
        if value is None:
            return ""
        return value[:600] if isinstance(value, str) else value

    @field_validator("grammar_override", mode="before")
    @classmethod
    def _bounded_override(cls, value: object) -> object:
        # An optional rewrite must not overflow stage two. Use the complete
        # built-in grammar instead of executing a partially cut instruction.
        return "" if value is None or (isinstance(value, str) and len(value) > 1200) else value


def pattern_selection_model(patterns: list[BehaviorPattern]) -> type[PatternSelectionResponse]:
    """Bind local grammars to the available IDs, retaining fallback for non-enforcing providers."""
    constraints: dict[str, JsonValue] = {"enum": list(dict.fromkeys(pattern.id for pattern in patterns))}
    return create_model("PatternSelectionResponse", __base__=PatternSelectionResponse,
        __config__=ConfigDict(json_schema_extra={"required": ["pattern_id"]}),
        pattern_id=(str, Field(default_factory=str, json_schema_extra=constraints)))


def build_system_prompt(patterns: list[BehaviorPattern]) -> str:
    catalog_lines: list[str] = []
    for p in patterns:
        catalog_lines.append(f"- **{p.id}** ({p.name}): {p.description}")

    catalog_text = "\n".join(catalog_lines)

    return f"""당신은 매장 고객의 행동 패턴을 선택하는 전문가입니다.
고객 페르소나, 시간대, 개인 상태 정보를 바탕으로 가장 적합한 행동 패턴을 선택하세요.

## 행동 패턴 목록
{catalog_text}

규칙:
- pattern_id는 반드시 위 목록의 id 중 하나여야 합니다
- reasoning에 선택 이유를 한 문장, 600자 이내로 간단히 적으세요
- 고객의 현재 상태와 모순되는 패턴은 피하세요 (예: 동행=혼자인데 사교둘러보기형)
- grammar_override: 선택한 패턴의 기본 행동 문법을 이 고객의 상황에 맞게 미세 조정하고 싶을 때만 사용하세요.
  보통은 비워두세요. 조정 시에도 기본 구조(입장→...→퇴장)는 반드시 유지하세요.
  수정은 1200자 이내로 짧게 작성하고 같은 규칙을 반복하지 마세요. 매장 목록이나 고객 정보를 다시 쓰지 마세요.
- 선택 설명 필드에 내용이 없으면 null 대신 빈 문자열("")을 사용하세요.

## 언어
- 자유 서술 필드(`reasoning`, `grammar_override`)의 값은 **영어로** 작성하세요.
- 구조적 필드(`pattern_id`)는 한국어 prompt 에서 정의된 그대로 유지합니다.
- 영어 표현은 자연스러운 콘텐츠 톤을 유지하세요."""


def build_user_prompt(
    persona: Persona,
    arrival_hour: int,
    store: Store,
    day_of_week: str,
    cue: BehaviorCue,
    address: str = "",
    customer_profile: str = "",
    currency: str = "USD",
) -> str:
    lines: list[str] = []

    lines.append("## 고객 페르소나")
    lines.append(f"- 유형: {persona.identity} ({persona.age_group}, {persona.gender})")
    lines.append(f"- 설명: {persona.description}")
    lines.append(f"- 방문 목적: {persona.purpose}")
    lines.append(f"- 의도: {persona.intent}")
    lines.append(f"- 선호 카테고리: {', '.join(persona.preferred_categories)}")
    lines.append(f"- 예산: {format_budget(persona.budget_min, persona.budget_max, currency)}")
    lines.append(f"- 행동 성향: {persona.behavior_tendency}")
    lines.append("")

    lines.append("## 상황 정보")
    lines.append(f"- 시간: {arrival_hour}시")
    if day_of_week:
        lines.append(f"- 요일: {day_of_week}")
    if address:
        lines.append(f"- 주소: {address}")
    if customer_profile:
        lines.append(f"- Customer profile: {customer_profile}")
    lines.append(f"- 고객 상태: {format_cue_prompt(cue)}")
    lines.append("")

    lines.append("이 고객에게 가장 적합한 행동 패턴을 선택하세요.")
    return "\n".join(lines)


