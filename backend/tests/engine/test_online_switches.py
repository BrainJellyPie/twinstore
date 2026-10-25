"""Who a change helps, and the shoppers whose visit ended differently between two stores."""

import asyncio

from store_emulator.domain.online import OnlineShopper, OnlineSite, SessionResult
from store_emulator.engine.online.analysis import paired_deltas, segment_deltas, switches
from store_emulator.engine.online.catalog import build_site
from store_emulator.engine.online.policies import RulePolicy
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers


def _site(**options: object) -> OnlineSite:
    site = build_site("home_kitchen", site_id="sw")
    return site.model_copy(update={"options": site.options.model_copy(update=options)})


def _sessions(site: OnlineSite, shoppers: list[OnlineShopper]) -> list[SessionResult]:
    async def go() -> list[SessionResult]:
        return [await run_session(site, s, RulePolicy(), seed=6, max_steps=30, render=False) for s in shoppers]
    return asyncio.run(go())


def test_switches_and_segments_add_up_to_the_paired_difference() -> None:
    control = _site()
    shoppers = sample_shoppers(control, 160, seed=3, missions={"purchase": 1.0, "browse": 1.0, "gift": 0.5}, mobile_share=0.5)
    base = _sessions(control, shoppers)
    test = _sessions(_site(service_fee=900, guest_checkout=False), shoppers)
    won, lost, changed, rows = switches(base, test)
    pairs = list(zip(base, test, strict=True))
    assert won == sum(a.outcome != "purchased" and b.outcome == "purchased" for a, b in pairs)
    assert lost == sum(a.outcome == "purchased" and b.outcome != "purchased" for a, b in pairs)
    assert lost > won  # a last-step fee and a forced account cost orders
    assert all(r.control_outcome != r.variant_outcome for r in rows)
    assert changed == sum(a.outcome != b.outcome for a, b in pairs) and len(rows) == min(60, changed)
    ordered = [r.control_outcome == "purchased" or r.variant_outcome == "purchased" for r in rows]
    assert ordered == sorted(ordered, reverse=True)  # orders won or lost come first
    lost_row = next(r for r in rows if r.control_outcome == "purchased")
    assert lost_row.control_total > 0 and lost_row.variant_total == 0 and lost_row.variant_thought

    overall = next(d for d in paired_deltas(base, test) if d.metric == "conversion")
    by_id = {s.id: s for s in shoppers}
    segments = segment_deltas(base, test, by_id, seed=1)
    for dimension in ("mission", "device", "age_group", "gender", "vision"):
        part = [s for s in segments if s.dimension == dimension]
        assert sum(s.n for s in part) == len(shoppers)
        weighted = sum(s.conversion_diff * s.n for s in part) / len(shoppers)
        assert abs(weighted - overall.diff) < 1e-3
        for s in part:
            assert s.ci_low is None or s.ci_low <= s.conversion_diff <= (s.ci_high or 0)
    gift = next(s for s in segments if s.dimension == "mission" and s.value == "gift")
    members = [i for i, sh in enumerate(shoppers) if sh.mission == "gift"]
    assert gift.control_conversion == round(sum(base[i].outcome == "purchased" for i in members) / len(members), 4)


def test_identical_stores_have_no_switches() -> None:
    site = _site()
    shoppers = sample_shoppers(site, 40, seed=5, missions={"purchase": 1.0}, mobile_share=0.5)
    sessions = _sessions(site, shoppers)
    assert switches(sessions, _sessions(site, shoppers)) == (0, 0, 0, [])
    assert all(s.conversion_diff == 0 for s in segment_deltas(sessions, sessions, {s.id: s for s in shoppers}))
