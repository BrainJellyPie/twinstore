"""Model proportions must be valid and remain usable at extreme finite scales."""

import math
import sys
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


@pytest.mark.parametrize("scale", [math.ulp(0.0), 2 * math.ulp(0.0), 1e-320, sys.float_info.min / 4,
                                   sys.float_info.min, 1.0, 1e307])
@pytest.mark.parametrize("ratios", [(1, 1), (1, 3), (3, 1), (1, 2, 3)])
@pytest.mark.parametrize("seed", [0, 7, -11])
def test_weight_scale_preserves_seeded_model_proportions(scale, ratios, seed):
    client = cast(SimLLM, object())
    ordinary = EnsembleLLMClient([(str(i), float(ratio), client) for i, ratio in enumerate(ratios)], seed=seed)
    scaled = EnsembleLLMClient([(str(i), ratio * scale, client) for i, ratio in enumerate(ratios)], seed=seed)
    expected = [ordinary.member_for(f"shopper-{i}").name for i in range(256)]
    picked = [scaled.member_for(f"shopper-{i}").name for i in range(256)]
    assert picked == expected
