"""Locally recorded research plans and full amendment history."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from store_emulator.application import protocols
from store_emulator.application.errors import AppError
from store_emulator.domain.protocols import AmendProtocol, CreateProtocol, ProtocolListing, ProtocolView

router = APIRouter(prefix="/api/projects/{pid}/protocols", tags=["research protocols"])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.get("", response_model=ProtocolListing)
def list_protocols(pid: str) -> ProtocolListing:
    return _call(lambda: protocols.list_protocols(pid))


@router.post("", response_model=ProtocolView)
def create_protocol(pid: str, req: CreateProtocol) -> ProtocolView:
    return _call(lambda: protocols.create_protocol(pid, req))


@router.get("/{protocol_id}", response_model=ProtocolView)
def get_protocol(pid: str, protocol_id: str) -> ProtocolView:
    return _call(lambda: protocols.get_protocol(pid, protocol_id))


@router.post("/{protocol_id}/amendments", response_model=ProtocolView)
def amend_protocol(pid: str, protocol_id: str, req: AmendProtocol) -> ProtocolView:
    return _call(lambda: protocols.amend_protocol(pid, protocol_id, req))


@router.get("/{protocol_id}/export.json")
def export_json(pid: str, protocol_id: str, head: Annotated[str, Query(pattern=r"^[0-9a-f]{64}$")]) -> PlainTextResponse:
    text = _call(lambda: protocols.export_protocol(pid, protocol_id, head, False))
    return PlainTextResponse(text, media_type="application/json", headers={"Content-Disposition": 'attachment; filename="research-protocol.json"'})


@router.get("/{protocol_id}/changes.csv")
def export_csv(pid: str, protocol_id: str, head: Annotated[str, Query(pattern=r"^[0-9a-f]{64}$")]) -> PlainTextResponse:
    text = _call(lambda: protocols.export_protocol(pid, protocol_id, head, True))
    return PlainTextResponse(text, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="protocol-changes.csv"'})
