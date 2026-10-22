"""Exact numeric thresholds and valid arrival clocks for shopper search."""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import pytest
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.store import Store
from store_emulator.engine.shopper_filter import _Filter, apply_filter

STORE = Store(id="s", name="Store", type="convenience", grid_size=(8, 8))
def customer(pid, spent=0, arrival="15:00:00"):
    return CustomerResult(persona_id=pid, day=1, arrival_time=arrival, total_spent=spent)

@pytest.mark.parametrize("currency,scale", [("USD",100),("EUR",100),("usd",100),("KRW",1),("JPY",1),("VND",1),("CLP",1),("ISK",1),("HUF",1),("TWD",1),("IDR",1)])
@pytest.mark.parametrize("threshold", [0, 5e-324, 1e-8, .004, .005, .015, .5, 1.005, 1.015, 1.5, 2.675])
def test_spending_limits_are_true_inclusive_inequalities(currency, scale, threshold):
    exact=Decimal(str(threshold))*scale
    low=int(exact.to_integral_value(rounding=ROUND_FLOOR)); high=int(exact.to_integral_value(rounding=ROUND_CEILING))
    amounts=sorted({max(0,low-1),low,high,high+1})
    customers={str(n):customer(str(n),n) for n in amounts}
    minimum=apply_filter(_Filter(label="Minimum",min_spent=threshold),customers,{},STORE,currency)
    maximum=apply_filter(_Filter(label="Maximum",max_spent=threshold),customers,{},STORE,currency)
    assert set(minimum.persona_ids)=={str(n) for n in amounts if Decimal(n)>=exact}
    assert set(maximum.persona_ids)=={str(n) for n in amounts if Decimal(n)<=exact}

@pytest.mark.parametrize("invalid", ["", "unknown", "24:01:00", "24:59", "15:60:00", "15:00:61", "15:00:garbage", "15:00:00:extra", "²:00", "99:00", "-1:00"])
@pytest.mark.parametrize("field", ["arrived_after","arrived_before"])
def test_unknown_or_invalid_arrival_cannot_satisfy_a_time_condition(invalid,field):
    customers={"bad":customer("bad",arrival=invalid),"valid":customer("valid")}
    value="14:00" if field=="arrived_after" else "16:00"
    result=apply_filter(_Filter.model_validate({"label":"Known times",field:value}),customers,{},STORE,"USD")
    assert result.persona_ids==["valid"]

@pytest.mark.parametrize("field",["min_spent","max_spent"])
def test_large_finite_spend_does_not_overflow_float_multiplication(field):
    customers={"free":customer("free")}
    result=apply_filter(_Filter.model_validate({"label":"Large threshold",field:1e308}),customers,{},STORE,"USD")
    assert result.persona_ids==([] if field=="min_spent" else ["free"])

@pytest.mark.parametrize("field",["arrived_after","arrived_before"])
@pytest.mark.parametrize("invalid",["24:01","15:00:bad","²:00"])
def test_invalid_filter_time_is_reported_without_crashing(field,invalid):
    result=apply_filter(_Filter.model_validate({"label":"Invalid time",field:invalid}),{"valid":customer("valid")},{},STORE,"USD")
    assert result.warnings and result.persona_ids==["valid"]


@pytest.mark.parametrize("field",["min_spent","max_spent","min_minutes","max_minutes"])
@pytest.mark.parametrize("value",[float("inf"),float("-inf"),float("nan")])
def test_nonfinite_numeric_conditions_are_rejected(field,value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        _Filter.model_validate({"label":"Nonfinite",field:value})

@pytest.mark.parametrize("field,value,expected",[
    ("arrived_after","15:00:30",["after","boundary"]),
    ("arrived_before","15:00:30",["before"]),
    ("arrived_after","00:00",["after","before","boundary"]),
    ("arrived_before","24:00",["after","before","boundary"]),
])
def test_arrival_boundaries_preserve_seconds_and_endpoint_rules(field,value,expected):
    customers={pid:customer(pid,arrival=time) for pid,time in [("before","15:00:29"),("boundary","15:00:30"),("after","15:00:31")]}
    result=apply_filter(_Filter.model_validate({"label":"Boundary",field:value}),customers,{},STORE,"USD")
    assert result.persona_ids==expected
    assert value in result.criteria[0]
