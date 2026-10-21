"""Model proportions must be valid and remain usable at extreme finite scales."""

from typing import cast

import pytest
from pydantic import ValidationError

from store_emulator.domain.providers import EnsembleMember
from store_emulator.engine.llm_router import EnsembleLLMClient, SimLLM


@pytest.mark.parametrize("weight", [float("inf"), float("-inf"), float("nan"), 0.0, -1.0])
def test_invalid_model_weight_is_rejected_before_routing(weight):
    with pytest.raises(ValidationError):
        EnsembleMember(model="custom:model", weight=weight)


@pytest.mark.parametrize("weight", [float("inf"), float("-inf"), float("nan"), 0.0, -1.0])
def test_direct_router_rejects_invalid_weights(weight):
    client = cast(SimLLM, object())
    with pytest.raises(ValueError, match="weight"):
        EnsembleLLMClient([("A", weight, client), ("B", 1.0, client)])


def test_large_finite_weights_keep_their_relative_proportions():
    client = cast(SimLLM, object())
    ordinary = EnsembleLLMClient([("A", 3.0, client), ("B", 1.0, client)], seed=7)
    large = EnsembleLLMClient([("A", 1.5e308, client), ("B", 5e307, client)], seed=7)
    expected = [ordinary.member_for(f"shopper-{i}").name for i in range(500)]
    picked = [large.member_for(f"shopper-{i}").name for i in range(500)]
    assert picked == expected
    assert 0.65 < picked.count("A") / len(picked) < 0.85
