"""Read-only, source-bound reviews of minimal paired experiment snapshots."""

import hashlib
from pathlib import Path

from pydantic import ValidationError

from store_emulator.application.errors import AppError
from store_emulator.application.shelf_lab import _check_id  # pyright: ignore[reportPrivateUsage]
from store_emulator.application.storage.io import DATA_DIR
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.factorial import FactorialReport, FactorialRequest, FactorialSource, PairedSnapshot
from store_emulator.domain.marketing import JobStatus
from store_emulator.engine.marketing.factorial import analyze_factorial, factorial_csv, factorial_source


def _load(pid: str, eid: str) -> tuple[PairedSnapshot, str] | str:
    _check_id(pid, "project id")
    _check_id(eid, "experiment id")
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)
    folder = Path(DATA_DIR) / pid / "marketing" / "experiments" / eid
    try:
        status = JobStatus.model_validate_json((folder / "status.json").read_bytes())
    except FileNotFoundError as exc:
        raise AppError("Experiment not found", 404) from exc
    except ValidationError as exc:
        raise AppError("Experiment status is invalid", 409) from exc
    if status.job_id != eid or status.kind != "experiment":
        raise AppError("Experiment identity does not match its saved location", 409)
    if status.status != "completed":
        return "Complete the experiment before reviewing its paired outcomes."
    try:
        with (folder / "paired-outcomes.json").open("rb") as file:
            data = file.read(8 * 1024 * 1024 + 1)
    except FileNotFoundError:
        return "Paired outcomes were not retained for this run. Legacy aggregate reports cannot reconstruct pairs. Use a new A/B run with supported outcomes."
    if len(data) > 8 * 1024 * 1024:
        raise AppError("Paired snapshot exceeds 8 MB", 409)
    try:
        snapshot = PairedSnapshot.model_validate_json(data)
    except ValidationError as exc:
        raise AppError("Paired snapshot is invalid; no outcomes were inferred", 409) from exc
    if snapshot.experiment_id != eid:
        raise AppError("Paired snapshot belongs to another experiment", 409)
    return snapshot, hashlib.sha256(data).hexdigest()


def source(pid: str, eid: str) -> FactorialSource:
    loaded = _load(pid, eid)
    if isinstance(loaded, str):
        return FactorialSource(available=False, reason=loaded)
    return factorial_source(*loaded)


def preview(pid: str, eid: str, req: FactorialRequest) -> FactorialReport:
    loaded = _load(pid, eid)
    if isinstance(loaded, str):
        raise AppError(loaded, 409)
    snapshot, digest = loaded
    if digest != req.source_sha256:
        raise AppError("Paired source changed; reload the source and review again before export", 409)
    try:
        return analyze_factorial(snapshot, req)
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc


def export(pid: str, eid: str, req: FactorialRequest) -> str:
    return factorial_csv(preview(pid, eid, req))
