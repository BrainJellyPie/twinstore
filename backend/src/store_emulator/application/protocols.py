"""Atomic, bounded local protocol histories with optimistic concurrency."""

from datetime import datetime, timezone
from pathlib import Path
import re

from filelock import FileLock, Timeout

from store_emulator.application.errors import AppError
from store_emulator.application.shelf_lab import _check_id  # pyright: ignore[reportPrivateUsage]
from store_emulator.application.storage.io import DATA_DIR, write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.protocols import AmendProtocol, CreateProtocol, ProtocolLedger, ProtocolListing, ProtocolSummary, ProtocolView
from store_emulator.engine.analysis.protocols import protocol_changes_csv, record_revision, review_protocol

MAX_BYTES = 4 * 1024 * 1024


def _root(pid: str) -> Path:
    _check_id(pid, "project id")
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)
    return Path(DATA_DIR) / pid / "marketing" / "protocols"


def _path(pid: str, protocol_id: str) -> Path:
    if not re.fullmatch(r"protocol_[0-9a-f]{32}", protocol_id):
        raise AppError("Invalid protocol ID", 400)
    return _root(pid) / f"{protocol_id}.json"


def get_protocol(pid: str, protocol_id: str) -> ProtocolView:
    path = _path(pid, protocol_id)
    try:
        with path.open("rb") as source:
            data = source.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Oversized protocol history")
        ledger = ProtocolLedger.model_validate_json(data)
        if ledger.project_id != pid or ledger.protocol_id != protocol_id:
            raise ValueError("Protocol identity mismatch")
        return review_protocol(ledger)
    except FileNotFoundError as exc:
        raise AppError("Protocol not found", 404) from exc
    except ValueError as exc:
        raise AppError("Protocol history is invalid or inconsistent; preserve the file and restore a verified copy", 409) from exc
    except OSError as exc:
        raise AppError("Unable to read protocol history", 500) from exc


def list_protocols(pid: str) -> ProtocolListing:
    items: list[ProtocolSummary] = []; unavailable: list[str] = []
    paths = sorted(_root(pid).glob("protocol_*.json"))
    if len(paths) > 100:
        raise AppError("Protocol directory exceeds the supported 100-record limit", 409)
    for path in paths:
        try:
            view = get_protocol(pid, path.stem)
        except AppError as exc:
            if exc.status_code not in (400, 404, 409): raise
            unavailable.append(path.stem); continue
        latest = view.ledger.revisions[-1]
        items.append(ProtocolSummary(protocol_id=view.ledger.protocol_id, title=latest.plan.title, revision=latest.revision,
            data_stage=latest.data_stage, evidence_type=latest.plan.evidence_type, updated_at=latest.recorded_at))
    return ProtocolListing(protocols=sorted(items, key=lambda item: (item.updated_at, item.protocol_id), reverse=True), unavailable_ids=unavailable)


def _save(path: Path, ledger: ProtocolLedger) -> ProtocolView:
    view = review_protocol(ledger)
    if len(ledger.model_dump_json(indent=2).encode()) > MAX_BYTES:
        raise AppError("Protocol history exceeds 4 MB; shorten the new amendment", 422)
    write_json(path, ledger.model_dump(mode="json"))
    return view


def create_protocol(pid: str, req: CreateProtocol) -> ProtocolView:
    root = _root(pid); protocol_id = f"protocol_{req.request_id}"
    try:
        root.mkdir(parents=True, exist_ok=True)
        with FileLock(root / ".update.lock", timeout=0):
            path = _path(pid, protocol_id)
            if path.exists():
                view = get_protocol(pid, protocol_id); first = view.ledger.revisions[0]
                if first.plan != req.plan or first.data_stage != req.data_stage:
                    raise AppError("This creation request ID already belongs to a different plan; reload the list", 409)
                return view
            if len(list(root.glob("protocol_*.json"))) >= 100:
                raise AppError("A project supports at most 100 protocols", 409)
            revision = record_revision(pid, protocol_id, req.plan, req.data_stage, datetime.now(timezone.utc), "Initial plan", None)
            return _save(path, ProtocolLedger(format_version="protocol-ledger-v1", project_id=pid, protocol_id=protocol_id, revisions=[revision]))
    except Timeout as exc:
        raise AppError("Another protocol update is in progress; reload and retry", 409) from exc
    except OSError as exc:
        raise AppError("Unable to save protocol; reload the list before retrying", 500) from exc


def amend_protocol(pid: str, protocol_id: str, req: AmendProtocol) -> ProtocolView:
    path = _path(pid, protocol_id)
    if not path.exists():
        raise AppError("Protocol not found", 404)
    try:
        with FileLock(path.parent / ".update.lock", timeout=0):
            view = get_protocol(pid, protocol_id)
            if view.head_sha256 != req.expected_head:
                raise AppError("Protocol changed in another session; reload the saved version before amending", 409)
            if len(view.ledger.revisions) >= 50:
                raise AppError("A protocol supports at most 50 revisions", 409)
            try:
                revision = record_revision(pid, protocol_id, req.plan, req.data_stage, datetime.now(timezone.utc), req.reason, view.ledger.revisions[-1])
            except ValueError as exc:
                raise AppError(str(exc), 422) from exc
            view.ledger.revisions.append(revision)
            return _save(path, view.ledger)
    except Timeout as exc:
        raise AppError("Another protocol update is in progress; reload and retry", 409) from exc
    except OSError as exc:
        raise AppError("Unable to save amendment; reload the saved version before retrying", 500) from exc


def export_protocol(pid: str, protocol_id: str, head: str, csv: bool) -> str:
    view = get_protocol(pid, protocol_id)
    if view.head_sha256 != head:
        raise AppError("Protocol changed since the displayed version; reload before export", 409)
    return protocol_changes_csv(view) if csv else view.model_dump_json(indent=2)
