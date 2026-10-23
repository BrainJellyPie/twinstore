"""Validated project customers shared by simulation and study input readers."""

from pydantic import TypeAdapter, ValidationError

from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import read_json
from store_emulator.application.storage.setups import personas_path
from store_emulator.domain.persona import Persona, validate_persona_ids

_POPULATION = TypeAdapter(list[Persona])


def read_personas(project_id: str) -> list[Persona]:
    path = personas_path(project_id)
    if not path.exists():
        return []
    try:
        return validate_persona_ids(_POPULATION.validate_python(read_json(path)))
    except ValueError as error:
        if isinstance(error, ValidationError):
            first = error.errors(include_input=False)[0]
            location = ".".join(str(part) for part in first["loc"]) or "customers"
            reason = f"{location}: {first['msg']}"
        else:
            reason = str(error)
        raise AppError(f"Saved customers in {project_id}/personas.json are invalid ({reason}). "
                       "Restore the file or regenerate customers before retrying.", 400) from error
