"""Import device-extracted, anonymous tracks. Only aggregate reports are persisted."""

import csv
import io
from pathlib import Path

from pydantic import ValidationError

from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import now_iso, read_json
from store_emulator.application.storage.runs import load_run_results, load_run_store
from store_emulator.domain.movement import MovementReport, TrackPoint
from store_emulator.engine.analysis.movement import movement_report

MAX_TRACK_BYTES = 10 * 1024 * 1024
MAX_TRACK_SAMPLES = 100_000


def parse_tracks(data: bytes) -> list[TrackPoint]:
    if len(data) > MAX_TRACK_BYTES:
        raise ValueError("Track CSV is too large (maximum 10 MB).")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ValueError("Track CSV must use UTF-8 encoding.") from e
    reader = csv.DictReader(io.StringIO(text))
    required = {"track_id", "x", "y", "timestamp_sec"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("Track CSV needs columns: track_id,x,y,timestamp_sec.")
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("Track CSV contains duplicate column names.")
    points: list[TrackPoint] = []
    for row in reader:
        if len(points) >= MAX_TRACK_SAMPLES:
            raise ValueError(f"Track CSV exceeds {MAX_TRACK_SAMPLES:,} samples.")
        try:
            points.append(TrackPoint.model_validate({
                "track_id": (row.get("track_id") or "").strip(), "x": row.get("x"), "y": row.get("y"),
                "timestamp_sec": row.get("timestamp_sec"),
            }))
        except ValidationError as e:
            raise ValueError(f"Invalid track sample on CSV line {reader.line_num}: use an anonymous track ID, integer x/y and finite nonnegative seconds.") from e
    return points


def score_movement(base: Path, data: bytes, *, max_gap_seconds: float) -> MovementReport:
    store = load_run_store(base)
    try:
        points = parse_tracks(data)
        report = movement_report(points, load_run_results(base), store.grid_size, max_gap_seconds=max_gap_seconds)
    except (ValueError, csv.Error) as e:
        raise AppError(str(e), 400) from e
    walkable = store.walkable_grid()
    blocked = sum(1 for p in points if not walkable[p.y][p.x])
    if blocked:
        report.notes.append(f"{blocked} samples fall on non-walkable fixture cells. Check camera-to-grid alignment before interpreting differences.")
    report.created_at = now_iso()
    return report


def read_movement(base: Path) -> MovementReport | None:
    path = base / "output" / "movement.json"
    return MovementReport.model_validate(read_json(path)) if path.exists() else None
