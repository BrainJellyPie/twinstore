"""Free purchases and repeated customer visits survive channel joins in any order."""

from itertools import permutations

import pytest

from store_emulator.application import channels, online
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.online import OnlineRunRequest, OnlineRunResult, OnlineRunStatus, SessionResult, VisitBrief
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine.online.analysis import summarize
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.shoppers import sample_shoppers


@pytest.mark.parametrize("order", list(permutations(range(3))))
@pytest.mark.parametrize("legacy_paid", [False, True])
def test_free_or_legacy_paid_purchase_and_every_online_visit_are_counted(monkeypatch, order, legacy_paid):
    persona = Persona(id="person", identity="Resident", age_group="30s", gender="Female",
        description="Resident", intent="buy", purpose="Shopping")
    site = build_site("fashion", site_id="web")
    shoppers = sample_shoppers(site, 3, seed=0, missions={"purchase": 1}, mobile_share=.5, personas=[persona])
    sessions = [SessionResult(shopper_id=p.id, site_id=site.id, outcome=outcome, order_total=spent, steps=[])
        for p, outcome, spent in zip(shoppers, ["purchased", "purchased", "left"], [0, 700, 0])]
    report = OnlineRunResult(run_id="online_run", policy="rule", currency="USD",
        shoppers=[shoppers[i] for i in order], variants=[summarize(site, {p.id: p for p in shoppers}, sessions)],
        visits={s.shopper_id: [VisitBrief(outcome=s.outcome, order_total=s.order_total)] for s in sessions})
    view = online.OnlineRunView(status=OnlineRunStatus(run_id=report.run_id, site_ids=[site.id], status="completed",
        request=OnlineRunRequest(site_ids=[site.id], source="project")), result=report)
    customer = CustomerResult(persona_id=persona.id, day=Weekday.MON, arrival_time="12:00:00",
        total_spent=500 if legacy_paid else 0, timeline=[] if legacy_paid else [
            TimelineEvent(elapsed_sec=1, x=1, y=1, action=Action.BUY, product_sku="free", price=0, quantity=1)])
    store = Store(id="store", name="Store", type="convenience", grid_size=(8, 8))
    monkeypatch.setattr(channels, "get_run", lambda *_: view)
    monkeypatch.setattr(channels, "_store_runs", lambda _: [("store_run", "2026-10-25")])
    monkeypatch.setattr(channels, "_load", lambda *_: ({persona.id: customer}, {persona.id: persona}, store, "USD"))
    mix = channels.channel_mix("project", report.run_id)
    assert mix is not None
    assert (mix.customers, mix.both, mix.store_only, mix.online_only, mix.neither) == (1, 1, 0, 0, 0)
    assert mix.online_spend == 700 and mix.store_spend == customer.total_spent
    assert mix.by_age[0].both == mix.by_gender[0].both == 1
