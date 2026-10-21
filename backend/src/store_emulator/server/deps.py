import re

from fastapi import HTTPException, Request

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.types import RESOURCE_ID_PATTERN
from store_emulator.application.config import local_config

_config: SimulationConfig | None = None
_RESOURCE_ID = re.compile(RESOURCE_ID_PATTERN)
_PATH_IDS = {"pid", "sid", "run_id", "gid", "cid", "eid", "aid", "jid", "job_id"}


async def validate_resource_paths(request: Request) -> None:
    """Directory-backed IDs are names, never paths relative to a data folder."""
    for name in _PATH_IDS:
        value = request.path_params.get(name)
        if value is not None and (not isinstance(value, str) or not _RESOURCE_ID.fullmatch(value)):
            raise HTTPException(400, f"invalid resource id: {name}")


def get_config() -> SimulationConfig:
    global _config
    if _config is None:
        _config = local_config()
    return _config
