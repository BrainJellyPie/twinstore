"""Identify an attempted vision phase with no usable model responses."""

from typing import cast


def unanswered_vision_phase(metadata: dict[str, object]) -> str:
    planning = cast(dict[str, object], metadata["planning"]) if isinstance(metadata.get("planning"), dict) else {}
    for label, source, calls_key, errors_key in (
        ("shelf glances", metadata, "glances", "errors"),
        ("entrance plans", planning, "plans", "plan_errors"),
    ):
        calls, errors = source.get(calls_key), source.get(errors_key)
        if isinstance(calls, int) and calls > 0 and isinstance(errors, int) and errors >= calls:
            return label
    return ""
