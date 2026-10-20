import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from store_emulator.application.storage.generations import recover_running_generations
from store_emulator.application.storage.seed import seed_sample_projects
from store_emulator.application.storage.setups import recover_running_setups
from .routes import simulate, projects, setups, util, images, providers

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s %(message)s")
# Silence noisy third-party loggers (raw request/response, completion calls, etc.).
for _lib in ("LiteLLM", "litellm", "instructor", "httpx", "httpcore"):
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
    recovered_gens = recover_running_generations()
    if recovered_gens > 0:
        logger.info(f"server start: marked {recovered_gens} in-progress generations as failed")
    yield


app = FastAPI(
    lifespan=lifespan,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulate.router)
app.include_router(simulate.engines_router)
app.include_router(projects.router)
app.include_router(setups.router)
app.include_router(util.router)
app.include_router(images.router)
app.include_router(providers.router)


@app.get("/api/health", tags=["system"], summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok"}
