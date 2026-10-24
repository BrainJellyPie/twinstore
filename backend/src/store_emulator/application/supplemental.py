"""Supplemental data handling — v2 schema-aware 2-pass pipeline (prototype-aligned).

spec: docs/superpowers/specs/2026-05-13-supplemental-v2-pipeline.md (rev 5)

Decision (2026-05-13): mirror the prototype
`parastore-persona-generator-v2/core/step0_analyzer.py` content-generation
behavior as closely as possible. The defenses added by Option B / spec rev 4
(invalid heuristic, time-like column-name heuristic, Stage 1/3 size caps)
were dropped because they bypassed the prototype's own validation.

Retained backend-infra adaptations:
- LiteLLMClient instead of Gemini File API (application-layer abstraction).
- Column name str normalization (guarantees Stage 2/3 contract: list[str]).
- CSV Unicode BOM handling and Korean Excel encoding, with common spreadsheet delimiters.
- Response truncation (SUPPLEMENTAL_SUMMARY_MAX_CHARS) to bound metadata storage.
- Race-safe metadata write is the caller's responsibility (`_run_async_pipeline`).
"""

from __future__ import annotations

import io
import json
import logging
import re
from datetime import date, datetime
from datetime import time as ClockTime
from functools import lru_cache
from typing import Any, cast
from xml.etree.ElementTree import fromstring
from zipfile import ZipFile

import pandas as pd  # type: ignore[reportMissingTypeStubs]
from dateutil.parser import parse as parse_date
from pydantic import BaseModel

from store_emulator.domain.types import AsyncLLMClient
from store_emulator.engine.llm_client import final_answer_text
from store_emulator.engine.generators.traffic_profile import (
    TrafficProfile,
    fit_traffic_profile,
)
from store_emulator.application.workbooks import validate_xlsx_budget
from store_emulator.application.customer_csv import validate_customer_csv

logger = logging.getLogger(__name__)

SUPPLEMENTAL_MAX_BYTES = 10 * 1024 * 1024
SUPPLEMENTAL_SUMMARY_MAX_CHARS = 2000
SUPPLEMENTAL_ALLOWED_EXTS: set[str] = {".csv", ".xlsx"}
STAGE2_MAX_RETRIES = 3

# Deterministic sheet name used for CSV inputs (single sheet).
_CSV_SHEET_NAME = "data"


# spec §3.2 — Stage 2 response model
class SheetColumns(BaseModel):
    sheet_name: str
    columns: list[str]


class SelectedColumns(BaseModel):
    selected_columns: list[SheetColumns]


_STAGE2_SYSTEM_PROMPT = (
    "다음은 상권 분석, 고객 행동 패턴 분석 및 페르소나 도출을 위한 엑셀 데이터의\n"
    "메타데이터와 상위 5행 샘플 데이터입니다. 이 데이터를 기반으로, 분석에 가장\n"
    "핵심적이고 유의미한 컬럼들을 시트별로 선택해 주세요. 불필요한 단순 ID,\n"
    "연속 번호, 의미 없는 컬럼은 제외하세요. 응답은 SelectedColumns 스키마를\n"
    "따릅니다."
)


# Stage 1 — schema + metadata + sample (spec §3.1)


def _ext(filename: str) -> str:
    if not filename:
        return ""
    dot = filename.rfind(".")
    if dot == -1:
        return ""
    return filename[dot:].lower()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Cast every column to str. On collision, keep the first (parastore contract)."""
    seen: set[str] = set()
    keep_idx: list[int] = []
    new_labels: list[str] = []
    raw_cols: list[object] = list(df.columns)  # type: ignore[reportUnknownArgumentType]
    for i, col in enumerate(raw_cols):
        s = str(col)
        if s in seen:
            continue
        seen.add(s)
        keep_idx.append(i)
        new_labels.append(s)
    out = cast(pd.DataFrame, df.iloc[:, keep_idx].copy())  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    out.columns = new_labels  # type: ignore[reportUnknownMemberType]
    return out


def read_customer_workbook(data: bytes, *, preserve_identifiers: bool = False) -> dict[str, pd.DataFrame]:
    """Use the customer-generation reader for preflight, before creating a project or calling a model."""
    issues = validate_xlsx_budget(data, collect_cell_issues=True)
    worksheet_parts: list[str] = []
    try:
        # openpyxl silently drops missing worksheet parts while reading the
        # surviving sheets. Do not turn an incomplete upload into partial evidence.
        with ZipFile(io.BytesIO(data)) as archive:
            manifest = fromstring(archive.read("[Content_Types].xml"))
            parts = set(archive.namelist())
            for part in manifest:
                if part.get("ContentType", "").endswith(".worksheet+xml"):
                    name = part.get("PartName", "").lstrip("/")
                    if name not in parts:
                        raise ValueError("A declared worksheet is missing from the workbook")
                    worksheet_parts.append(name)
        result = pd.read_excel(  # type: ignore[reportUnknownMemberType]
            io.BytesIO(data), sheet_name=None, engine="openpyxl",
            dtype=object if preserve_identifiers else None, keep_default_na=not preserve_identifiers,
        )
    except Exception as exc:
        raise ValueError("Customer Excel workbook could not be read. Open it in a spreadsheet app and save it "
                         "as an unencrypted XLSX file, then try again.") from exc
    if any(issues.get(part) for part in worksheet_parts):
        raise ValueError("Customer Excel workbook contains spreadsheet errors or formulas without saved results. "
                         "Recalculate and save it in a spreadsheet app, or export its values as CSV, then upload again.")
    out: dict[str, pd.DataFrame] = {}
    items: list[tuple[object, object]] = list(result.items())  # type: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    for key, frame in items:
        if isinstance(frame, pd.DataFrame):
            out[str(key)] = frame
    if not any(frame.shape[1] for frame in out.values()):
        raise ValueError("Customer Excel workbook is empty or has no column header.")
    return out


def _load_frames(bytes_: bytes, ext: str, *, preserve_identifiers: bool = False) -> dict[str, pd.DataFrame]:
    """csv → single sheet ``"data"``; xlsx → sheet_name=None dict. Empty dict on failure."""
    if ext == ".csv":
        try:
            text, delimiter = validate_customer_csv(bytes_)
            df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=object if preserve_identifiers else None,
                             keep_default_na=not preserve_identifiers)  # type: ignore[reportUnknownMemberType]
            if not isinstance(df.index, pd.RangeIndex):  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                return {}
        except Exception:
            return {}
        return {_CSV_SHEET_NAME: df}

    if ext == ".xlsx":
        try:
            return read_customer_workbook(bytes_, preserve_identifiers=preserve_identifiers)
        except Exception:
            return {}

    return {}


def _build_sheet_metadata(df: pd.DataFrame) -> dict[str, object]:
    """spec §3.1 — per-sheet metadata."""
    cols_info: dict[str, object] = {}
    cols: list[object] = list(df.columns)  # type: ignore[reportUnknownArgumentType]
    for col in cols:
        series = df[col]  # type: ignore[reportUnknownVariableType]
        cols_info[str(col)] = {
            "dtype": str(series.dtype),  # type: ignore[reportUnknownMemberType]
            "null_ratio": float(series.isnull().mean()),  # type: ignore[reportUnknownMemberType]
            "unique_count": int(series.nunique(dropna=True)),  # type: ignore[reportUnknownMemberType]
        }
    return {
        "total_rows": int(df.shape[0]),
        "total_columns": int(df.shape[1]),
        "columns_info": cols_info,
    }


def _build_sheet_sample(df: pd.DataFrame) -> list[dict[str, str]]:
    """spec §3.1 — top-5 row sample, all values cast to str (no truncation, prototype-aligned)."""
    head = df.head(5)
    rows: list[dict[str, str]] = []
    records: list[object] = head.to_dict(orient="records")  # type: ignore[reportUnknownMemberType, reportAssignmentType]
    for rec in records:
        if not isinstance(rec, dict):
            continue
        row: dict[str, str] = {}
        items: list[tuple[object, object]] = list(rec.items())  # type: ignore[reportUnknownArgumentType]
        for k, v in items:
            row[str(k)] = str(v)
        rows.append(row)
    return rows


def _stage1_extract(
    bytes_: bytes,
    ext: str,
) -> tuple[dict[str, pd.DataFrame], dict[str, object], dict[str, object]]:
    """bytes → (effective_frames, metadata, sample_data). On failure: ({}, {}, {}).

    Prototype-aligned: no invalid heuristic, no size cap, every sheet passes through.
    Only column names are str-normalized (parastore contract).
    """
    raw_frames = _load_frames(bytes_, ext)
    if not raw_frames:
        return ({}, {}, {})

    effective_frames: dict[str, pd.DataFrame] = {}
    metadata: dict[str, object] = {}
    sample_data: dict[str, object] = {}

    for sheet_name, df in raw_frames.items():
        normalized = _normalize_columns(df)
        effective_frames[sheet_name] = normalized
        metadata[sheet_name] = _build_sheet_metadata(normalized)
        sample_data[sheet_name] = _build_sheet_sample(normalized)

    if not effective_frames:
        return ({}, {}, {})

    return (effective_frames, metadata, sample_data)


# Stage 2 — LLM column selection (spec §3.2)


def _build_stage2_user_input(
    metadata: dict[str, object],
    sample_data: dict[str, object],
) -> str:
    """spec §3.2 user_input — [메타데이터] / [샘플 데이터] blocks."""
    md = json.dumps(metadata, ensure_ascii=False, indent=2)
    sd = json.dumps(sample_data, ensure_ascii=False, indent=2)
    return f"[메타데이터]\n{md}\n\n[샘플 데이터]\n{sd}"


def _effective_columns_fallback(
    effective_frames: dict[str, pd.DataFrame],
) -> dict[str, list[str]]:
    """All effective columns across every effective sheet (used as fallback)."""
    out: dict[str, list[str]] = {}
    for sheet_name, df in effective_frames.items():
        cols: list[object] = list(df.columns)  # type: ignore[reportUnknownArgumentType]
        out[sheet_name] = [str(c) for c in cols]
    return out


async def _stage2_select_columns(
    llm: AsyncLLMClient,
    effective_frames: dict[str, pd.DataFrame],
    metadata: dict[str, object],
    sample_data: dict[str, object],
) -> dict[str, list[str]]:
    """spec §3.2 — LLM call + response normalization + fallback.

    Returns sheet → effective columns list (all str).
    """
    user_input = _build_stage2_user_input(metadata, sample_data)
    try:
        selection = await llm.generate_structured_async(
            SelectedColumns,
            _STAGE2_SYSTEM_PROMPT,
            user_input,
            max_retries=STAGE2_MAX_RETRIES,
        )
    except Exception:
        logger.warning(
            "[supplemental] stage2 LLM call failed; falling back to effective columns.",
            exc_info=True,
        )
        return _effective_columns_fallback(effective_frames)

    effective_cols_by_sheet: dict[str, list[str]] = {}
    effective_cols_set_by_sheet: dict[str, set[str]] = {}
    for sheet_name, df in effective_frames.items():
        cols_raw: list[object] = list(df.columns)  # type: ignore[reportUnknownArgumentType]
        cols_str = [str(c) for c in cols_raw]
        effective_cols_by_sheet[sheet_name] = cols_str
        effective_cols_set_by_sheet[sheet_name] = set(cols_str)

    result: dict[str, list[str]] = {}
    for entry in selection.selected_columns:
        sheet_name = entry.sheet_name
        if sheet_name not in effective_cols_set_by_sheet:
            continue
        if sheet_name in result:
            continue
        valid_cols_set = effective_cols_set_by_sheet[sheet_name]
        seen: set[str] = set()
        normalized_cols: list[str] = []
        for col in entry.columns:
            if col == "":
                continue
            if col not in valid_cols_set:
                continue
            if col in seen:
                continue
            seen.add(col)
            normalized_cols.append(col)
        if not normalized_cols:
            result[sheet_name] = list(effective_cols_by_sheet[sheet_name])
        else:
            result[sheet_name] = normalized_cols

    for sheet_name, cols_str in effective_cols_by_sheet.items():
        if sheet_name not in result:
            result[sheet_name] = list(cols_str)

    return result


# Stage 3 — deterministic aggregation (spec §3.3)


def _is_time_like_column(df: pd.DataFrame, col: str) -> bool:
    """Prototype-aligned: only check datetime64 dtype. No column-name heuristic."""
    series = df[col]  # type: ignore[reportUnknownVariableType]
    return bool(pd.api.types.is_datetime64_any_dtype(series))  # type: ignore[reportUnknownMemberType]


def _column_stats_block(df: pd.DataFrame, col: str) -> str:
    """Build the stats block for a single column (spec §3.3, prototype-aligned)."""
    series = df[col]  # type: ignore[reportUnknownVariableType]
    if bool(series.isnull().all()):  # type: ignore[reportUnknownMemberType]
        return f"[Column: {col} (All NaN)]\n"

    if pd.api.types.is_datetime64_any_dtype(series):  # type: ignore[reportUnknownMemberType]
        ts_min = series.min()  # type: ignore[reportUnknownMemberType]
        ts_max = series.max()  # type: ignore[reportUnknownMemberType]
        return (
            f"[Column: {col} ({series.dtype})]\n"  # type: ignore[reportUnknownMemberType]
            f"  기간: {ts_min} ~ {ts_max}\n"
        )

    if pd.api.types.is_numeric_dtype(series):  # type: ignore[reportUnknownMemberType]
        desc = series.describe().round(2)  # type: ignore[reportUnknownMemberType]
        desc_dict = desc.to_dict()  # type: ignore[reportUnknownMemberType]
        return (
            f"[Column: {col} ({series.dtype})]\n"  # type: ignore[reportUnknownMemberType]
            f"  요약 통계: {desc_dict}\n"
        )

    vc = series.value_counts(dropna=True).head(10)  # type: ignore[reportUnknownMemberType]
    vc_dict: dict[str, int] = {}
    items: list[tuple[object, object]] = list(vc.items())  # type: ignore[reportUnknownArgumentType, reportUnknownMemberType]
    for k, v in items:
        vc_dict[str(k)] = int(v)  # type: ignore[reportUnknownArgumentType]
    return (
        f"[Column: {col} ({series.dtype})]\n"  # type: ignore[reportUnknownMemberType]
        f"  상위 10개 빈도: {vc_dict}\n"
    )


def _maybe_hourly_groupby_block(df: pd.DataFrame, columns: list[str]) -> str:
    """Hourly mean across numeric columns when a time-like column (datetime64) is
    present, at least one numeric column exists, and hour.nunique() > 1.

    Prototype-aligned: time-likeness is dtype-only; fires only when the
    hour-of-day axis is itself meaningful.
    """
    try:
        first_time_col: str | None = None
        for c in columns:
            if c in df.columns and _is_time_like_column(df, c):  # type: ignore[reportUnknownArgumentType]
                first_time_col = c
                break
        if first_time_col is None:
            return ""
        time_series = df[first_time_col]  # type: ignore[reportUnknownVariableType]
        hours = time_series.dt.hour  # type: ignore[reportUnknownMemberType]
        if int(hours.nunique(dropna=True)) <= 1:  # type: ignore[reportUnknownMemberType]
            return ""
        numeric_cols: list[str] = []
        for c in columns:
            if c == first_time_col:
                continue
            if c not in df.columns:  # type: ignore[reportUnknownArgumentType]
                continue
            if _is_time_like_column(df, c):
                continue
            if pd.api.types.is_numeric_dtype(df[c]):  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                numeric_cols.append(c)
        if not numeric_cols:
            return ""
        df_numeric = cast(pd.DataFrame, df[numeric_cols])  # type: ignore[reportUnknownArgumentType]
        grouped = df_numeric.groupby(hours).mean().round(2)  # type: ignore[reportUnknownMemberType]
        grouped_dict = grouped.to_dict(orient="index")  # type: ignore[reportUnknownMemberType]
        return f"[그룹화 통계]\n시간대별 주요 수치 평균: {grouped_dict}\n"
    except Exception:
        return ""


def _aggregate_sheet(
    sheet_name: str,
    df: pd.DataFrame,
    columns: list[str],
) -> str:
    """Build the stats text for a single sheet (prototype-aligned: no cap)."""
    df_cols_set = {str(c) for c in df.columns}  # type: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    use_cols = [c for c in columns if c in df_cols_set]
    if not use_cols:
        return ""

    header = (
        f"--- Sheet: {sheet_name} ---\n"
        f"Selected Columns: {', '.join(use_cols)}\n"
    )
    parts: list[str] = [header, "\n"]

    groupby_block = _maybe_hourly_groupby_block(df, use_cols)
    if groupby_block:
        parts.append(groupby_block)
        parts.append("\n")

    column_blocks: list[str] = []
    for c in use_cols:
        try:
            column_blocks.append(_column_stats_block(df, c))
        except Exception:
            logger.warning(
                "[supplemental] stage3 column stat failed; skipping.",
                extra={"sheet": sheet_name, "column": c},
                exc_info=True,
            )
            continue

    if not column_blocks and not groupby_block:
        return ""

    parts.extend(column_blocks)
    return "".join(parts)


def _stage3_aggregate(
    effective_frames: dict[str, pd.DataFrame],
    selected_columns_by_sheet: dict[str, list[str]],
) -> str:
    """spec §3.3 — build per-sheet stats text and concatenate (prototype-aligned: no cap)."""
    sheet_texts: list[str] = []
    for sheet_name, df in effective_frames.items():
        columns = selected_columns_by_sheet.get(sheet_name)
        if not columns:
            continue
        try:
            text = _aggregate_sheet(sheet_name, df, columns)
        except Exception:
            logger.warning(
                "[supplemental] stage3 sheet aggregation failed; skipping.",
                extra={"sheet": sheet_name},
                exc_info=True,
            )
            continue
        if text:
            sheet_texts.append(text)

    if not sheet_texts:
        return ""
    return "\n".join(sheet_texts)


# Stage 4 — final LLM summary (spec §3.4)


_STAGE4_SYSTEM_PROMPT = (
    "다음은 특정 상점의 고객 및 매출, 혹은 상권에 대한 데이터의 통계적 요약본입니다.\n"
    "이 상점을 방문하는 고객의 행동 패턴, 매장 특성, 주 방문 목적 등 시간대별 방문객 "
    "수를 추정하고 고객 페르소나를 생성하는 데 필요한 핵심 정보만 추출해 주세요.\n\n"
    "[지침]\n"
    "1. 불필요한 서론, 인사말, 결론은 생략하고 핵심 내용만 바로 출력하세요.\n"
    "2. 다음 3가지 항목으로 나누어 마크다운 불릿 포인트(-) 형태로 작성하세요:\n"
    "   - 상권 및 입지 특성 요약\n"
    "   - 시간대/요일별 방문 특이사항\n"
    "   - 주 고객층 및 행동 특성\n"
    "3. 각 항목은 최대 3문장 이내로 매우 간결하게 작성하세요.\n"
    "4. 제공된 데이터 요약본에 수치 등이 명확하게 나와있을 경우, 이를 분석하여 "
    "대략적인 분포를 명시하세요.\n"
    "5. 만약 제공된 데이터가 완전히 깨져 있거나 상권 분석/고객 페르소나 도출과 "
    "무관하여 도저히 분석할 수 없는 경우, 억지로 분석하지 말고 '데이터 부족 "
    "및 분석 불가'를 명확히 선언하세요.\n\n"
    "## 언어\n"
    "- 출력 마크다운 본문 전체를 **영어로** 작성하세요.\n"
    "- 항목 헤더(상권 및 입지 특성 요약 등)도 영어로 번역하여 출력하세요.\n"
    "- 구조적 요소(마크다운 불릿 `-`, 숫자, 통계 수치)는 그대로 유지합니다.\n"
    "- 영어 표현은 자연스러운 비즈니스 분석 톤을 유지하세요."
)


async def _stage4_final_summary(
    llm: AsyncLLMClient,
    compressed_text: str,
) -> str:
    """spec §3.4 — LLM text completion. Empty after .strip() returns ""; truncated to SUPPLEMENTAL_SUMMARY_MAX_CHARS."""
    user_input = f"[데이터 요약본]\n{compressed_text}"
    response = await llm.generate_text_async(_STAGE4_SYSTEM_PROMPT, user_input)
    stripped = final_answer_text(response).strip()
    if not stripped:
        return ""
    return stripped[:SUPPLEMENTAL_SUMMARY_MAX_CHARS]


async def summarize_supplemental(
    bytes_: bytes,
    filename: str,
    llm: AsyncLLMClient,
) -> str:
    """csv/xlsx bytes → pandas → 4-stage pipeline → prose summary. Returns "" on failure.

    spec rev 5 §3. Prototype-aligned: no invalid heuristic, no cap.
    """
    if not bytes_ or not filename:
        return ""
    ext = _ext(filename)
    if ext not in SUPPLEMENTAL_ALLOWED_EXTS:
        return ""
    try:
        effective_frames, metadata, sample_data = _stage1_extract(bytes_, ext)
        if not effective_frames:
            return ""
        selected_columns_by_sheet = await _stage2_select_columns(
            llm, effective_frames, metadata, sample_data,
        )
        compressed_text = _stage3_aggregate(
            effective_frames, selected_columns_by_sheet,
        )
        if not compressed_text:
            return ""
        return await _stage4_final_summary(llm, compressed_text)
    except Exception:
        logger.warning(
            "[supplemental] pipeline failed; returning empty.",
            exc_info=True,
        )
        return ""


# ── Visit times from a POS export ──────────────────────────────────────────

_ID_SUFFIXES = ("", "id", "no", "num", "number", "code", "번호", "아이디", "코드")
_BASKET_COLUMNS = {root + suffix for root in ("transaction", "trans", "basket", "receipt", "order", "ticket", "invoice", "거래", "영수증", "주문")
                   for suffix in _ID_SUFFIXES}
_RECEIPT_SCOPE_COLUMNS = {root + suffix for root in ("store", "shop", "branch", "register", "terminal", "till", "pos", "매장", "점포", "지점", "단말기", "계산대")
                          for suffix in _ID_SUFFIXES}
_DATE_COLUMNS = {"date", "transactiondate", "transdate", "orderdate", "receiptdate", "salesdate", "visitdate", "businessdate",
                 "날짜", "일자", "거래일자", "거래일", "주문일자", "주문일", "영업일자", "방문일자"}
_TIME_COLUMNS = {"time", "timestamp", "transactiontime", "transtime", "ordertime", "receipttime", "salestime", "visittime",
                 "시간", "시각", "거래시간", "거래시각", "주문시간", "주문시각", "방문시간", "방문시각"}
_VISIT_TIMESTAMP_COLUMNS = _DATE_COLUMNS | _TIME_COLUMNS | {
    root + suffix for root in ("", "transaction", "trans", "order", "receipt", "sales", "visit", "purchase", "invoice")
    for suffix in ("datetime", "timestamp")
} | {"일시", "거래일시", "주문일시", "방문일시", "판매일시", "결제일시"}
_CLOCK_ONLY = re.compile(r"\s*\d{1,2}(?::\d{2}(?::\d{2}(?:\.\d+)?)?(?:\s*[ap]m)?|\s*[ap]m)"
                         r"(?:\s*(?:Z|[+-]\d{2}:?\d{2}))?\s*", re.IGNORECASE)
MIN_TRAFFIC_VISITS = 200


def _local_timestamps(values: list[object]) -> list[pd.Timestamp | None]:
    try:
        parsed = cast(pd.DatetimeIndex, pd.to_datetime(values, errors="coerce", format="mixed"))  # type: ignore[reportUnknownMemberType]
        stamps = cast(list[pd.Timestamp], parsed.tolist())  # type: ignore[reportUnknownMemberType]  # pandas omits the scalar type
    except ValueError:
        # Mixed offsets/naive values cannot share one pandas timezone. Keep the exported local clock.
        stamps = [cast(pd.Timestamp, pd.to_datetime(value, errors="coerce")) for value in values]  # type: ignore[reportUnknownMemberType]
    return [None if stamp is pd.NaT else stamp.tz_localize(None) for stamp in stamps]


def _visit_times_from_frame(df: pd.DataFrame) -> list[tuple[int, int]]:
    """(weekday 1–7, hour) of each visit in a table with a timestamp column, one per basket when a
    transaction/receipt ID column exists. Use the earliest valid clock in each date/store/register-scoped receipt.
    Empty when no column parses as date-times with a time of day."""
    table = cast(Any, df)
    columns = cast(list[object], list(table.columns))
    labels = {col: "".join(char for char in str(col).casefold() if char.isalnum()) for col in columns}
    best: list[pd.Timestamp | None] | None = None
    best_score = (-1, 0.0)
    dates: list[list[str | None]] = []
    clocks: list[list[str | None]] = []

    @lru_cache(maxsize=4096)
    def text_evidence(text: str) -> tuple[bool, bool]:
        # Missing components must not borrow pandas' current/default calendar.
        # Keep repeated receipt lines cheap without retaining upload data globally.
        try:
            first = parse_date(text, default=datetime(2000, 1, 1, 3))
            # Separate days by more than a week so a weekday cannot resolve both
            # defaults to the same invented day in a partially specified month.
            second = parse_date(text, default=datetime(2004, 3, 20, 17))
        except (ValueError, OverflowError):
            return False, False
        return first.date() == second.date(), first.hour == second.hour

    for col in columns:
        if labels[col] in _BASKET_COLUMNS or labels[col] in _RECEIPT_SCOPE_COLUMNS:
            continue
        series = table[col]
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):  # type: ignore[reportUnknownMemberType]
            continue  # epoch numbers are not taken for timestamps
        values = cast(list[object], series.tolist())
        evidence = [text_evidence(value) if isinstance(value, str) else (isinstance(value, date), False)
                    for value in values]
        clock_only = [isinstance(value, ClockTime) or (isinstance(value, str) and _CLOCK_ONLY.fullmatch(value) is not None)
                      for value in values]
        if labels[col] in _TIME_COLUMNS and sum(clock_only) / max(1, len(values)) >= 0.8:
            clock_values = _local_timestamps([str(value) if is_clock else None for value, is_clock in zip(values, clock_only, strict=True)])
            clocks.append([stamp.strftime("%H:%M:%S.%f") if stamp is not None else None for stamp in clock_values])
        parsed = _local_timestamps([value if has_date else None
                                    for value, (has_date, _) in zip(values, evidence, strict=True)])
        valid = [stamp for stamp in parsed if stamp is not None]
        ok = len(valid) / max(1, len(values))
        # Only source text can explicitly say midnight. A date-only Excel cell is also a midnight datetime.
        explicit_times = sum(has_date and has_time for has_date, has_time in evidence) / max(1, len(values))
        has_time = ok > 0 and (sum((stamp.hour, stamp.minute, stamp.second, stamp.microsecond) != (0, 0, 0, 0)
                                  for stamp in valid) / len(valid) > 0.5 or
                              explicit_times > 0.5)
        # Account creation/update timestamps may be complete but are not the receipt's visit time.
        # A mostly complete column must not turn its date-only text rows into midnight visits.
        timed = [stamp if not isinstance(value, str) or has_clock else None
                 for stamp, value, (_, has_clock) in zip(parsed, values, evidence, strict=True)]
        score = (int(labels[col] in _VISIT_TIMESTAMP_COLUMNS), sum(stamp is not None for stamp in timed) / max(1, len(values)))
        if ok >= 0.8 and has_time and score > best_score:
            best, best_score = timed, score
        elif ok >= 0.8 and not has_time and labels[col] in _DATE_COLUMNS:
            dates.append([stamp.date().isoformat() if stamp is not None else None for stamp in parsed])
    for date_values in dates:
        for clock_values in clocks:
            combined = _local_timestamps([f"{date} {clock}" if date is not None and clock is not None else None
                                          for date, clock in zip(date_values, clock_values, strict=True)])
            ok = sum(stamp is not None for stamp in combined) / max(1, len(combined))
            score = (1, ok)  # Both components have recognized visit date/time labels.
            if ok >= 0.8 and score > best_score:
                best, best_score = combined, score
    if best is None:
        return []
    frame = cast(Any, pd.DataFrame({"ts": best}))
    basket = next((c for c in columns if labels[c] in _BASKET_COLUMNS), None)
    if basket is not None:
        frame["basket"] = table[basket].astype("string").str.strip().replace("", pd.NA).to_numpy()
        frame["date"] = frame.ts.dt.date
        identity = ["date", "basket"]
        for index, col in enumerate(c for c in columns if labels[c] in _RECEIPT_SCOPE_COLUMNS):
            key = f"scope_{index}"
            frame[key] = table[col].astype("string").str.strip().replace("", pd.NA).to_numpy()
            identity.append(key)
        # Product-line sort order must not change the hour assigned to a receipt.
        frame = frame.dropna(subset=["ts", "basket"]).groupby(identity, sort=False, dropna=False, as_index=False)["ts"].min()
    ts = frame.ts.dropna()
    days = cast(list[int], (ts.dt.dayofweek + 1).astype(int).tolist())
    hours = cast(list[int], ts.dt.hour.astype(int).tolist())
    return list(zip(days, hours, strict=True))


def traffic_from_supplemental(bytes_: bytes, filename: str) -> TrafficProfile | None:
    """A weekday × hour traffic profile fitted from a POS export (csv/xlsx with a timestamp column),
    or None when the file has no usable timestamps or fewer than MIN_TRAFFIC_VISITS visits."""
    ext = _ext(filename)
    if not bytes_ or ext not in SUPPLEMENTAL_ALLOWED_EXTS:
        return None
    try:
        visits = [v for df in _load_frames(bytes_, ext, preserve_identifiers=True).values()
                  for v in _visit_times_from_frame(_normalize_columns(df))]
    except Exception:
        logger.warning("[supplemental] timestamp scan failed", exc_info=True)
        return None
    if len(visits) < MIN_TRAFFIC_VISITS:
        return None
    return fit_traffic_profile(visits, source=f"{filename}: {len(visits)} visits")
