"""Product reporting includes externally landed views as well as internal clicks."""

import asyncio
from collections import Counter
import random

import pytest

from store_emulator.domain.online import ActionKind
from store_emulator.engine.online.analysis import summarize
from store_emulator.engine.online.policies import Choice, Memory, StepView
from store_emulator.engine.online.session import run_session
from store_emulator.engine.online.shoppers import sample_shoppers
from tests.engine.test_online_arrivals import _site


@pytest.mark.parametrize("arrival", ["direct", "search_engine", "social"])
@pytest.mark.parametrize("open_another", [False, True])
def test_product_rows_account_for_the_landing_and_subsequent_views(arrival, open_another):
    site = _site()
    shopper = sample_shoppers(site, 1, seed=4, missions={"purchase": 1.0}, mobile_share=0)[0].model_copy(update={"arrival": arrival})

    class Browse:
        async def choose(self, site, shopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
            if open_another and not memory.steps:
                control = next(c for c in view.page.active if c.action.kind == ActionKind.OPEN_PRODUCT)
                return Choice(control)
            return Choice(view.page.leave)

    session = asyncio.run(run_session(site, shopper, Browse(), seed=4, max_steps=3, render=False))
    expected = Counter(session.viewed_products)
    assert sum(expected.values()) == int(arrival != "direct") + int(open_another)
    report = summarize(site, {shopper.id: shopper}, [session])
    assert {row.product_id: row.views for row in report.products} == dict(expected)
    assert sum(row.adds for row in report.products) == 0
    assert report.actions.get("open_product", 0) == int(open_another)


def test_repeated_views_remain_counts_and_do_not_become_unique_reach():
    site = _site()
    shopper = sample_shoppers(site, 1, seed=4, missions={"replenish": 1.0}, mobile_share=0)[0].model_copy(update={"arrival": "search_engine"})

    class Leave:
        async def choose(self, site, shopper, view: StepView, memory: Memory, rng: random.Random) -> Choice:
            return Choice(view.page.leave)

    session = asyncio.run(run_session(site, shopper, Leave(), seed=4, max_steps=1, render=False))
    # The recorded views, not clicks, are the source for a repeated product exposure.
    repeated = session.model_copy(update={"viewed_products": session.viewed_products * 3})
    report = summarize(site, {shopper.id: shopper}, [repeated])
    assert len(report.products) == 1 and report.products[0].views == 3
