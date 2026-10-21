import re

from fastapi import HTTPException, Request

from store_emulator.domain.config import SimulationConfig
from store_emulator.application.config import local_config

_config: SimulationConfig | None = None
_PROJECT_ID = re.compile(r"[A-Za-z0-9_-]+")


async def validate_project_path(request: Request) -> None:
    """Project IDs are directory names, never paths relative to the data folder."""
    pid = request.path_params.get("pid")
    if pid is not None and (not isinstance(pid, str) or not _PROJECT_ID.fullmatch(pid)):
        raise HTTPException(400, "invalid project id")


def get_config() -> SimulationConfig:
    global _config
    if _config is None:
        _config = local_config()
    return _config
