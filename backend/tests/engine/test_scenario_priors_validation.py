"""Invalid calibration numbers must fail before they affect customer demand."""
import math

import pytest
from pydantic import ValidationError

from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.scenario import Scenario, ScenarioPriors
from store_emulator.engine.scenario import compile_scenario


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", ["need_power", "need_ratio", "size_ratio", "weather_traffic", "temperature_clip"])
def test_nonfinite_scenario_prior_is_rejected_by_simulation_config(field, value):
    values = {
        "need_power": value,
        "need_ratio": {"day:weekday": {"water": value}},
        "size_ratio": {"day:weekday": value},
        "weather_traffic": {"clear": value},
        "temperature_clip": {"water": [0.0, value]},
    }
    with pytest.raises(ValidationError) as error:
        SimulationConfig.model_validate({"scenario_priors": {field: values[field]}})
    assert error.value.errors()[0]["type"] == "finite_number"
    assert error.value.errors()[0]["loc"][:2] == ("scenario_priors", field)


@pytest.mark.parametrize("power", [-1.0, 0.0, 0.5, 1.0, 2.0])
def test_finite_need_powers_scale_situation_ratios_without_changing_hour_ratios(power):
    priors = ScenarioPriors(need_power=power, need_ratio={
        "day:weekday": {"water": 4.0}, "hour:evening": {"water": 2.0},
    })
    effects = compile_scenario(Scenario(), priors)
    assert effects.need_for({"water"}) == pytest.approx(4.0 ** power)
    assert effects.hour_need_for(19, {"water"}) == 2.0


def test_zero_effects_and_negative_event_traffic_remain_valid():
    config = SimulationConfig.model_validate({"scenario_priors": {
        "need_ratio": {"day:weekday": {"water": 0.0}},
        "size_ratio": {"day:weekday": 0.0},
        "weather_traffic": {"clear": 0.0},
        "event_traffic": {"road_construction": -0.2},
    }})
    assert config.scenario_priors is not None
    effects = compile_scenario(Scenario(), config.scenario_priors)
    assert effects.need_for({"water"}) == effects.base_traffic == effects.size == 0.0
    assert config.scenario_priors.event_traffic["road_construction"] == -0.2
