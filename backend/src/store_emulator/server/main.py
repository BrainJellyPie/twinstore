import logging
import math
import mimetypes
import ipaddress
import os
import re
import threading
from os import PathLike
from pathlib import Path
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send
from fastapi.middleware.cors import CORSMiddleware

from store_emulator.application.capture import recover_interrupted_captures
from store_emulator.application.storage.generations import recover_running_generations
from store_emulator.application.storage.io import DamagedFile
from store_emulator.application.storage.jobs import recover_interrupted_jobs
from store_emulator.application.storage.seed import seed_sample_projects
from store_emulator.application.storage.setups import recover_running_setups
from store_emulator.application.marketing import recover_running_jobs
from store_emulator.application.local_vlm import manager as local_vlm
from store_emulator.application.providers import check_keys, cloud_providers_with_key
from .deps import validate_resource_paths
from .routes import catalog_images
from .routes import assist, simulate, projects, setups, util, images, providers, scenarios, town, optimize, templates, capture, shelf_lab, floorplan, vision_inputs, system, marketing, interview, field_pilot, inventory_review, unit_prices, protocols, price_checks, product_edits, starter_fill, rack_copy, library_photos

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s %(message)s")
# Silence noisy third-party loggers (raw request/response, completion calls, etc.).
# The OpenAI SDK (used for local and OpenAI-compatible servers) logs every request body at DEBUG, images included.
for _lib in ("LiteLLM", "litellm", "instructor", "httpx", "httpcore", "openai", "anthropic", "PIL", "urllib3",
             "multipart", "python_multipart", "aiohttp"):
    logging.getLogger(_lib).setLevel(logging.WARNING)


class _StatusPollFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "/status " not in msg and "/health " not in msg


logging.getLogger("uvicorn.access").addFilter(_StatusPollFilter())

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    seeded = seed_sample_projects()
    if seeded > 0:
        logger.info(f"server start: seeded {seeded} sample project(s)")
    recovered_setups = recover_running_setups()
    if recovered_setups > 0:
        logger.info(f"server start: recovered {recovered_setups} running setups to draft")
    recovered_captures = recover_interrupted_captures()
    if recovered_captures > 0:
        logger.info(f"server start: marked {recovered_captures} interrupted captures as failed")
    recovered_jobs = recover_interrupted_jobs()
    if recovered_jobs > 0:
        logger.info(f"server start: marked {recovered_jobs} interrupted background jobs as failed")
    recovered_gens = recover_running_generations()
    if recovered_gens > 0:
        logger.info(f"server start: marked {recovered_gens} in-progress generations as failed")
    recovered_marketing = recover_running_jobs()
    if recovered_marketing > 0:
        logger.info(f"server start: marked {recovered_marketing} interrupted marketing jobs as failed")
    launched = os.environ.get("TWINSTORE_LOCAL_VLM_AUTO") == "1"   # opened from an app icon
    if not cloud_providers_with_key():
        # The local model the user chose before, or one already on this computer: never a download nobody asked for.
        if launched:
            local_vlm().auto_start()
        logger.warning("server start: no model API key set — vision shoppers need a key or the local model "
                       "(see /api/system/models)")
    elif launched:
        threading.Thread(target=_check_keys, name="key-check", daemon=True).start()
    yield
    local_vlm().stop()


def _check_keys() -> None:
    """A key a provider turns down counts as none: when that leaves no key, a local model the user set up starts right
    away rather than after the first failed request."""
    try:
        turned_down = check_keys()
    except Exception:  # noqa: BLE001 — the check only saves time; requests still move on by themselves
        logger.warning("server start: could not check the model API keys", exc_info=True)
        return
    if turned_down:
        logger.warning(f"server start: {', '.join(turned_down)} turned the API key down (not valid or revoked); "
                       "replace it in Settings → Model providers")
        if not cloud_providers_with_key():
            local_vlm().auto_start()


app = FastAPI(
    lifespan=lifespan,
    dependencies=[Depends(validate_resource_paths)],
    title="Store Emulator API",
    description=(
        "Block-grid store simulator API. "
        "Create store → place items → generate personas → run simulation → fetch results. "
        "Customers are simulated by the pattern_intent_impulse LLM engine or the rule_based baseline. "
        "Runs are reproducible (seeded) and comparable (paired A/B with confidence intervals)."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=[
        {"name": "simulate", "description": "Run / inspect simulations. Async execution; poll for status."},
        {"name": "projects", "description": "Project CRUD."},
        {"name": "setups", "description": "Setup CRUD — store layout + slots. Clone, slot upload, generation polling."},
        {"name": "util", "description": "Stateless utilities — validation against arbitrary store JSON, etc."},
        {"name": "system", "description": "System status check."},
    ],
)

@app.exception_handler(RequestValidationError)
async def validation_error_response(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Python's JSON parser accepts nonfinite numbers; echoed validation inputs must still be valid JSON.
    detail = jsonable_encoder(exc.errors(), custom_encoder={
        float: lambda value: value if math.isfinite(value) else str(value),
        bytes: lambda value: value.decode("utf-8", errors="replace"),
    })
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(DamagedFile)
async def damaged_file_response(_request: Request, exc: DamagedFile) -> JSONResponse:
    # Says which file instead of "Internal Server Error"; lists leave such a file out and show the rest.
    logger.warning(f"{exc} ({exc.path})")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# Web pages that may use the API: those on this computer — the app itself (from this server or through the launcher)
# and the development UI (http://localhost:5173 calling http://localhost:8000) — and any TWINSTORE_ALLOWED_ORIGINS
# names (comma-separated). Any other site the user visits must not read the stores or change the model settings.
LOOPBACK_ORIGIN = r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d{1,5})?"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _same_address(origin: str, host: str | None) -> bool:
    """The page came from this server reached by its IP address (another device on the network, with
    `launcher.py --host 0.0.0.0`). A name is not enough: a site can point its own name at this computer."""
    parts = urlsplit(origin)
    if host is None or parts.netloc != host or parts.hostname is None:
        return False
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        return False
    return True


class RefuseOtherSites:
    """CORS only hides the answer from other pages: a POST without a body, or a form, is sent from any web page
    without asking first. A change (any method but GET, HEAD and OPTIONS) is refused when the request names an origin
    that is not allowed, or names none while the browser marks it cross-site."""

    def __init__(self, app: ASGIApp, extra: list[str]) -> None:
        self.app = app
        self.extra = frozenset(extra)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in _SAFE_METHODS:
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            if (origin is None and headers.get("sec-fetch-site") == "cross-site") or (
                    origin is not None and re.fullmatch(LOOPBACK_ORIGIN, origin) is None and origin not in self.extra
                    and not _same_address(origin, headers.get("host"))):
                refused = JSONResponse({"detail": "TwinStore accepts changes only from its own pages"}, status_code=403)
                await refused(scope, receive, send)
                return
        await self.app(scope, receive, send)


def guard_origins(target: FastAPI) -> None:
    listed = os.environ.get("TWINSTORE_ALLOWED_ORIGINS", "").split(",")
    extra = [origin.strip().rstrip("/") for origin in listed if origin.strip()]
    target.add_middleware(CORSMiddleware, allow_origins=extra, allow_origin_regex=LOOPBACK_ORIGIN, allow_methods=["*"],
                          allow_headers=["*"])
    target.add_middleware(RefuseOtherSites, extra=extra)


guard_origins(app)

app.include_router(simulate.router)
app.include_router(simulate.engines_router)
app.include_router(projects.router)
app.include_router(setups.router)
app.include_router(product_edits.router)
app.include_router(starter_fill.router)
app.include_router(rack_copy.router)
app.include_router(library_photos.router)
app.include_router(util.router)
app.include_router(images.router)
app.include_router(catalog_images.router)
app.include_router(providers.router)
app.include_router(scenarios.router)
app.include_router(town.router)
app.include_router(optimize.router)
app.include_router(templates.router)
app.include_router(capture.router)
app.include_router(shelf_lab.router)
app.include_router(floorplan.router)
app.include_router(vision_inputs.router)
app.include_router(system.router)
app.include_router(marketing.router)
app.include_router(interview.router)
app.include_router(field_pilot.router)
app.include_router(inventory_review.router)
app.include_router(unit_prices.router)
app.include_router(protocols.router)
app.include_router(price_checks.router)
app.include_router(assist.router)


@app.get("/api/health", tags=["system"], summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Built web UI (one-click mode) ──────────────────────────────────────────────
# When `frontend/dist` exists (built by the launcher or shipped in a release zip), the API server
# also serves the UI, so the whole app runs on a single port with no Node.js at run time.

def _frontend_dist() -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("PARASTORE_FRONTEND_DIST"):
        candidates.append(Path(os.environ["PARASTORE_FRONTEND_DIST"]))
    candidates.append(Path(__file__).resolve().parents[4] / "frontend" / "dist")
    return next((c.resolve() for c in candidates if (c / "index.html").is_file()), None)


# Windows takes file types from the registry, where .js is sometimes "text/plain": browsers then refuse the UI's
# module scripts and the page stays blank. The UI's own types are set here.
for _ext, _type in ((".js", "text/javascript"), (".mjs", "text/javascript"), (".css", "text/css"),
                    (".svg", "image/svg+xml"), (".json", "application/json"), (".wasm", "application/wasm"),
                    (".woff2", "font/woff2"), (".webp", "image/webp")):
    mimetypes.add_type(_type, _ext)

class _ImmutableAssets(StaticFiles):
    """The built UI's scripts and styles: their names carry a hash of their content, so a name never changes meaning."""

    def file_response(self, full_path: PathLike[str] | str, stat_result: os.stat_result, scope: Scope,
                      status_code: int = 200) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def mount_web_ui(target: FastAPI, dist: Path) -> None:
    """Serves the built UI from `dist`. Its page is asked for again on every visit, so a browser never keeps the last
    version's page after an update (that page loads the last version's scripts, which the new one does not have: a
    blank page or the old app); its hashed scripts and styles never change and are kept."""
    if (dist / "assets").is_dir():
        target.mount("/assets", _ImmutableAssets(directory=dist / "assets"), name="ui-assets")

    @target.get("/{path:path}", include_in_schema=False)
    async def web_ui(path: str) -> FileResponse:  # pyright: ignore[reportUnusedFunction]  (the decorator registers it)
        """Static files of the UI, and index.html for client-side routes (/projects/…, /settings)."""
        if path.startswith("api/") or path == "api":
            raise HTTPException(404, "not found")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist in candidate.parents and candidate.name != "index.html":
            return FileResponse(candidate, headers={"Cache-Control": "no-cache"})
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})


_DIST = _frontend_dist()
if _DIST is not None:
    mount_web_ui(app, _DIST)
