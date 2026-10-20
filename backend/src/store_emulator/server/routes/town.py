"""Neighborhood of a project: generate / import, edit venues, demand and synergy."""

from collections.abc import Callable
from typing import Literal, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from store_emulator.application import town as town_service
from store_emulator.application import town_synergy as synergy_service
from store_emulator.application.errors import AppError
from store_emulator.application.scenarios import get_preset
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.application.town_synergy import (
    SynergyJobStatus,
    SynergyJobView,
    SynergyRequest,
)
from store_emulator.domain.town import (
    SynergyRow,
    Town,
    TownDemand,
    TownSpec,
    VenueCategory,
)

from ..deps import get_config

router = APIRouter(prefix="/api/projects", tags=["town"])


class OsmImportRequest(BaseModel):
    address: str | None = Field(default=None, description="Street address or place name (geocoded with Nominatim)")
    lat: float | None = None
    lon: float | None = None
    radius_m: float = Field(default=600.0, ge=150.0, le=2000.0)
    focal_name: str | None = Field(default=None, description="Name of our store on the map, if it exists there")


class VenueRequest(BaseModel):
    category: VenueCategory
    x: float
    y: float
    name: str = ""


def _project_name(pid: str) -> str:
    try:
        meta: object = read_json(metadata_path(pid))
    except (FileNotFoundError, ValueError):
        return ""
    if not isinstance(meta, dict):
        return ""
    name = cast(dict[str, object], meta).get("name", "")
    return name if isinstance(name, str) else ""


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except AppError as e:
        raise HTTPException(e.status_code, str(e)) from e


@router.get("/{pid}/town", summary="The project's neighborhood", response_model=Town)
def get_town(pid: str) -> Town:
    return _call(lambda: town_service.require_town(pid))


@router.put("/{pid}/town", summary="Save an edited neighborhood", response_model=Town)
def put_town(pid: str, town: Town) -> Town:
    return _call(lambda: town_service.save_town(pid, town))


@router.post("/{pid}/town/generate", summary="Generate a synthetic neighborhood", response_model=Town)
def generate_town(pid: str, spec: TownSpec) -> Town:
    """Archetypes: residential, university, business_district, suburban, station_area, tourist, mixed.
    Deterministic for a given seed. Replaces the project's current neighborhood."""
    return _call(lambda: town_service.generate(pid, spec, store_name=_project_name(pid)))


@router.post("/{pid}/town/import-osm", summary="Build the neighborhood from OpenStreetMap", response_model=Town)
def import_osm(pid: str, req: OsmImportRequest) -> Town:
    """Real buildings, shops, cafés, schools, stations and roads around an address (needs internet).
    Residents are estimated from building footprint × floors."""
    return _call(lambda: town_service.import_osm(
        pid, address=req.address, lat=req.lat, lon=req.lon, radius_m=req.radius_m,
        focal_name=req.focal_name or _project_name(pid) or None,
    ))


@router.post("/{pid}/town/venues", summary="What-if: open a venue", response_model=Town)
def add_venue(pid: str, req: VenueRequest) -> Town:
    return _call(lambda: town_service.add_venue(pid, req.category, req.x, req.y, req.name))


@router.delete("/{pid}/town/venues/{venue_id}", summary="What-if: close a venue", response_model=Town)
def delete_venue(pid: str, venue_id: str) -> Town:
    return _call(lambda: town_service.delete_venue(pid, venue_id))


@router.get("/{pid}/town/demand", summary="Daily visitors of our store from the neighborhood", response_model=TownDemand)
def town_demand(
    pid: str, day_type: Literal["weekday", "weekend", "holiday"] = "weekday", scenario_id: str | None = None,
) -> TownDemand:
    scenario = get_preset(scenario_id) if scenario_id else None
    return _call(lambda: town_service.demand(pid, day_type, scenario))


@router.get("/{pid}/town/synergy", summary="Effect of every other venue on our visitors", response_model=list[SynergyRow])
def town_synergy(pid: str, day_type: Literal["weekday", "weekend", "holiday"] = "weekday") -> list[SynergyRow]:
    """Counterfactual: recompute demand without each venue. Positive = complement (it brings us
    customers), negative = competitor. Takes a few seconds."""
    return _call(lambda: town_service.synergy(pid, day_type))


@router.post("/{pid}/town/venues/{venue_id}/synergy-vlm", summary="Start a VLM synergy analysis of one venue",
             response_model=SynergyJobStatus)
def start_vlm_synergy(pid: str, venue_id: str, req: SynergyRequest) -> SynergyJobStatus:
    """Visitor flow with and without the venue from the demand model, and its effect on baskets from
    VLM shoppers simulated twice on the same visitors — with the venue in their trip context ("came
    from the gym next door") and with it removed. Reports Δ visitors/day, Δ spend per visitor and
    Δ conversion (paired, 95% CI), category shifts and Δ revenue/day. Runs in the background; poll
    `GET /town/synergy-jobs/{job_id}`."""
    return _call(lambda: synergy_service.start_vlm_synergy(pid, venue_id, req, get_config()))


@router.get("/{pid}/town/synergy-jobs", summary="VLM synergy jobs", response_model=list[SynergyJobStatus])
def list_synergy_jobs(pid: str, venue_id: str | None = None) -> list[SynergyJobStatus]:
    return synergy_service.list_synergy_jobs(pid, venue_id)


@router.get("/{pid}/town/synergy-jobs/{job_id}", summary="VLM synergy progress and result",
            response_model=SynergyJobView)
def get_synergy_job(pid: str, job_id: str) -> SynergyJobView:
    return _call(lambda: synergy_service.get_synergy_job(pid, job_id))
