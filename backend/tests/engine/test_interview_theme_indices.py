"""Normalizing model-generated labels must preserve each answer's assigned theme."""

import asyncio

import pytest
from pydantic import BaseModel

from store_emulator.engine.interview import code_themes


class ThemeModel:
    def __init__(self, labels: list[str], assignments: list[int]) -> None:
        self.labels = labels
        self.assignments = assignments

    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str, user_prompt: str,
                                                     *, max_retries: int = 1, seed: int | None = None) -> T:
        return response_model.model_validate({"themes": self.labels, "assignments": self.assignments})


@pytest.mark.parametrize("labels,assignments,expected_labels,expected_assignments", [
    (["", " Price ", "Service"], [1, 2, 0, -1, 9], ["Price", "Service", "Other"], [0, 1, 2, 2, 2]),
    ([" ", ""], [0, 1, -1], ["Other"], [0, 0, 0]),
    (["Price", "Other"], [0, 1, 9], ["Price", "Other"], [0, 1, 1]),
    (["Price", " Price "], [0, 1], ["Price"], [0, 0]),
])
def test_cleaned_theme_labels_preserve_assignment_meaning(labels, assignments, expected_labels, expected_assignments):
    result = asyncio.run(code_themes(ThemeModel(labels, assignments), "Why?", ["Answer"] * len(assignments)))
    assert result == (expected_labels, expected_assignments)
