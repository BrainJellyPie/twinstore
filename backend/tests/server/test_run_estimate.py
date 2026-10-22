"""The run dialog's estimate: shoppers counted as the run counts them, model work, time and cost, and the warning."""

import pytest
from fastapi.testclient import TestClient

PID = "proj_67916afd"
SETUP = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # DATA_DIR is relative (".data"), so the test owns a fresh copy
    from store_emulator.server.main import app
    with TestClient(app) as c:  # lifespan seeds the sample project into tmp_path/.data
        yield c


def _estimate(client: TestClient, **body: object) -> dict[str, object]:
    resp = client.post(f"/api/projects/{PID}/runs/estimate", json={"setup_id": SETUP, **body})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_a_rule_based_run_is_quick_and_free(client):
    est = _estimate(client, engine_type="rule_based")
    assert est["model_calls"] == 0 and est["cost_usd"] == 0.0 and est["warn"] is False
    assert est["customers"] > 1000 and est["days"] == 5 and est["per_day"] == round(est["customers"] / 5)   # weekdays only
    capped = _estimate(client, engine_type="rule_based", max_customers=50)
    assert capped["customers"] == 50


def test_a_situations_days_and_the_cap_count_only_shoppers_who_come(client):
    friday = _estimate(client, engine_type="rule_based", scenario_id="payday_friday", max_customers=20)
    assert friday["days"] == 1 and friday["customers"] >= 20   # the cap no longer drops Friday's shoppers


def test_every_llm_shopper_run_of_the_whole_week_warns_with_its_price(client):
    est = _estimate(client, engine_type="pattern_intent_impulse", model="anthropic/claude-haiku-5-5")
    assert est["model"] and est["local"] is False and est["model_calls"] >= 3 * 1000
    assert est["cost_usd"] is not None and est["cost_usd"] > 1 and est["warn"] is True
    small = _estimate(client, engine_type="pattern_intent_impulse", model="anthropic/claude-haiku-5-5", max_customers=10)
    assert small["model_calls"] == 30 and small["warn"] is False


def test_a_vision_run_on_this_computers_model_is_free_but_slow(client):
    est = _estimate(client, engine_type="vlm_glance", model="llamacpp:local", max_customers=300)
    assert est["local"] is True and est["cost_usd"] is None
    assert est["minutes"] >= 10 and est["warn"] is True


def test_an_unknown_layout_is_not_found(client):
    resp = client.post(f"/api/projects/{PID}/runs/estimate", json={"setup_id": "setup_nope", "engine_type": "rule_based"})
    assert resp.status_code == 404


@pytest.mark.parametrize("model", ["anthropic/claude-haiku-5-5", "openai/gpt-6-luna", "gemini/gemini-3.8-flash"])
def test_default_models_are_priced_without_the_online_price_table(monkeypatch, model):
    """Offline, LiteLLM keeps its bundled table, which lacks the newest models: the warning still has a price."""
    import litellm

    from store_emulator.application import estimates

    bundled = {name: entry for name, entry in litellm.model_cost.items()
               if name not in estimates._PRESET_PRICES}  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(litellm, "model_cost", bundled)
    cost = estimates.cost_usd(model, 1_000_000, 100_000)
    assert cost is not None and cost > 0


def test_a_price_the_online_table_brought_is_kept(monkeypatch):
    import litellm

    from store_emulator.application import estimates

    table = dict(litellm.model_cost)
    table["claude-haiku-5-5"] = {"input_cost_per_token": 3e-06, "output_cost_per_token": 0.0,
                                 "litellm_provider": "anthropic", "mode": "chat"}
    monkeypatch.setattr(litellm, "model_cost", table)
    assert estimates.cost_usd("anthropic/claude-haiku-5-5", 1_000_000, 0) == pytest.approx(3.0)
