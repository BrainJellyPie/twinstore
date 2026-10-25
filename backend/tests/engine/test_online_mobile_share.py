"""The configured device mix must include real mobile-only and desktop-only panels."""

import pytest

from store_emulator.domain.online import OnlineRunRequest
from store_emulator.domain.persona import AGE_GROUPS, Persona
from store_emulator.engine.online.shoppers import sample_shoppers
from tests.engine.test_online_store import _site


@pytest.mark.parametrize("age", AGE_GROUPS)
@pytest.mark.parametrize("share,device", [(0.0, "desktop"), (1.0, "mobile")])
def test_project_customers_of_every_age_respect_device_mix_endpoints(age, share, device):
    site = _site("senior_care")
    persona = Persona(id="customer", identity="Local resident", age_group=age, gender="Female",
                      description="A regular customer", purpose="Shopping", intent="Buy household supplies")
    original = persona.model_dump()
    shoppers = sample_shoppers(site, 80, seed=19, missions={"purchase": 1}, mobile_share=share, personas=[persona])
    assert {s.device for s in shoppers} == {device}
    assert {s.persona_id for s in shoppers} == {persona.id}
    assert persona.model_dump() == original


@pytest.mark.parametrize("share,device", [(0.0, "desktop"), (1.0, "mobile")])
def test_generated_panel_respects_the_validated_run_request(share, device):
    site = _site("senior_care")
    request = OnlineRunRequest(site_ids=[site.id], mobile_share=share, shoppers=500, seed=8)
    shoppers = sample_shoppers(site, request.shoppers, seed=request.seed, missions=request.missions,
                               mobile_share=request.mobile_share)
    assert {s.device for s in shoppers} == {device}
    assert {s.age_group for s in shoppers} == set(AGE_GROUPS)
    assert shoppers == sample_shoppers(site, request.shoppers, seed=request.seed, missions=request.missions,
                                       mobile_share=request.mobile_share)


def test_device_mix_changes_monotonically_without_changing_other_sampled_traits():
    site = _site()
    panels = [sample_shoppers(site, 500, seed=7, missions={"purchase": 1}, mobile_share=share)
              for share in (0, 0.25, 0.55, 0.9, 1)]
    counts = [sum(s.device == "mobile" for s in panel) for panel in panels]
    assert counts[0] == 0 and counts[-1] == 500
    assert all(a < b for a, b in zip(counts, counts[1:]))
    baseline = [s.model_dump(exclude={"device", "description"}) for s in panels[0]]
    for panel in panels[1:]:
        assert [s.model_dump(exclude={"device", "description"}) for s in panel] == baseline


def test_age_preferences_still_affect_a_mixed_panel():
    site = _site()
    counts = []
    for age in ("20s", "60s+"):
        persona = Persona(id="customer", identity="Resident", age_group=age, gender="Male",
                          description="A regular customer", purpose="Shopping", intent="Buy supplies")
        shoppers = sample_shoppers(site, 500, seed=9, missions={"purchase": 1}, mobile_share=0.55, personas=[persona])
        counts.append(sum(s.device == "mobile" for s in shoppers))
    assert 0 < counts[1] < counts[0] < 500
