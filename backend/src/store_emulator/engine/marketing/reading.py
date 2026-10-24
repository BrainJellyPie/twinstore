"""A model's reading of a finished study: the reasons respondents gave, coded into themes, and a commentary on the
report's numbers that ties them together.

The report's numbers stay the report's own; the reading only adds words. Themes are counted over the answers that
were coded (and, for paired studies, per arm), so a share always says what it is a share of.
"""

import json
from collections.abc import Sequence
from html import escape
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from store_emulator.engine.interview import code_themes

MAX_REASONS = 160        # answers sent to theme coding (the first ones, in respondent order)
MAX_REASON_CHARS = 300
MAX_REPORT_CHARS = 16_000
EXAMPLES_PER_THEME = 2
EXAMPLE_CHARS = 150


class StructuredLLM(Protocol):
    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str,
        *, max_retries: int = 1, seed: int | None = None,
    ) -> T: ...


class Reason(BaseModel):
    """One open answer and the arm or group it came from ("" when the study has none)."""
    text: str
    group: str = ""


class ReasonTheme(BaseModel):
    label: str
    count: int
    share: float                                  # of the coded answers
    by_group: dict[str, int] = {}                 # answers per arm or group, for paired studies
    examples: list[str] = []


class StudyReading(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = ""
    interpretation: str = ""
    next_steps: str = ""
    themes_question: str = ""
    themes: list[ReasonTheme] = []
    answers_coded: int = 0
    groups: list[str] = []
    model: str = ""
    created_at: str = ""


class _Commentary(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: str = Field(min_length=1, max_length=900, description=(
        "the finding a manager acts on, in two or three plain sentences; at most two figures"))
    interpretation: str = Field(
        max_length=1400, description="why it may have happened: hypotheses tied to the numbers and to the reasons given")
    next_steps: str = Field(max_length=1000, description="what to test or do next, concretely")


COMMENTARY_PROMPT = """You are a market research analyst writing the commentary of a {study} for a brand or category
manager. The respondents are synthetic shoppers (personas answering through a language model). Use only the numbers in
the report (JSON) and the coded reasons below; do not invent figures, products or causes you cannot support from them.
When a difference's 95 % interval includes zero, or a group is small, say so plainly instead of calling a winner.
Refer to products and options by their names. Always provide a nonblank summary of what the report shows.
Write in English: short plain paragraphs, no headings, no markdown."""


def compact_report(report: BaseModel, exclude: set[str]) -> str:
    """The report as compact JSON without respondent-level lists, cut to a size a model reads well."""
    text = json.dumps(report.model_dump(mode="json", exclude=exclude), ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= MAX_REPORT_CHARS else text[:MAX_REPORT_CHARS] + "…(truncated)"


async def code_reasons(llm: StructuredLLM, question: str, reasons: Sequence[Reason]) -> tuple[list[ReasonTheme], int, list[str]]:
    """Themes of the open answers (empty below four answers), the number coded, and the groups seen."""
    kept = [Reason(text=r.text.strip()[:MAX_REASON_CHARS], group=r.group) for r in reasons if r.text.strip()][:MAX_REASONS]
    groups = list(dict.fromkeys(r.group for r in kept if r.group))
    if len(kept) < 4:
        return [], 0, groups
    labels, coded = await code_themes(llm, question, [r.text for r in kept])
    themes: list[ReasonTheme] = []
    for k, label in enumerate(labels):
        members = [r for r, c in zip(kept, coded, strict=False) if c == k]
        if not members:
            continue
        by_group = {g: sum(1 for r in members if r.group == g) for g in groups}
        examples = [_clip(x) for x in sorted(dict.fromkeys(r.text for r in members), key=len)[:EXAMPLES_PER_THEME]]
        themes.append(ReasonTheme(label=label, count=len(members), share=round(len(members) / len(kept), 4),
                                  by_group=by_group, examples=examples))
    themes.sort(key=lambda t: (t.label == "Other", -t.count))
    return themes, len(kept), groups


def _clip(text: str, limit: int = EXAMPLE_CHARS) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return f"{cut}…"


def _themes_text(question: str, themes: Sequence[ReasonTheme], coded: int) -> str:
    if not themes:
        return ""
    lines = [f'Reasons respondents gave ("{question}"), coded into themes over {coded} answers:']
    for t in themes:
        split = ", ".join(f"{g}: {n}" for g, n in t.by_group.items())
        lines.append(f"- {t.label}: {t.count} ({t.share:.0%}){f'; by arm {split}' if split else ''}"
                     + (f'; e.g. "{t.examples[0]}"' if t.examples else ""))
    return "\n".join(lines)


async def read_study(
    llm: StructuredLLM, study: str, report_json: str, question: str, reasons: Sequence[Reason],
) -> StudyReading:
    """Themes first (they inform the commentary), then the commentary on the numbers and the themes."""
    themes, coded, groups = await code_reasons(llm, question, reasons)
    user = f"Report:\n{report_json}\n\n{_themes_text(question, themes, coded)}".strip()
    commentary = await llm.generate_structured_async(
        _Commentary, COMMENTARY_PROMPT.format(study=study), user, max_retries=2, seed=0,
    )
    return StudyReading(summary=commentary.summary, interpretation=commentary.interpretation,
                        next_steps=commentary.next_steps, themes_question=question if themes else "",
                        themes=themes, answers_coded=coded, groups=groups)


def reading_html(reading: StudyReading | None) -> str:
    """The reading as a labelled block for the print-ready reports."""
    if reading is None or not (reading.summary or reading.themes):
        return ""
    e = escape
    paragraphs = "".join(f"<p>{e(t)}</p>" for t in (reading.summary, reading.interpretation, reading.next_steps) if t)
    rows = "".join(
        f"<tr><td><b>{e(t.label)}</b>{''.join(f'<br><span class=note>“{e(x)}”</span>' for x in t.examples)}</td>"
        f"<td class=n>{t.count}</td><td class=n>{t.share:.0%}</td>"
        + "".join(f"<td class=n>{t.by_group.get(g, 0)}</td>" for g in reading.groups) + "</tr>"
        for t in reading.themes
    )
    table = (f"<h3>Why they answered that way <span class='note'>· {reading.answers_coded} answers coded into themes</span></h3>"
             f"<table><tr><th>Theme</th><th>Answers</th><th>Share</th>{''.join(f'<th>{e(g)}</th>' for g in reading.groups)}</tr>{rows}</table>"
             if rows else "")
    return (f"<div class='ai'><small>Commentary and themes written by {e(reading.model or 'a language model')} "
            f"from the numbers and answers in this report</small>{paragraphs}{table}</div>")
