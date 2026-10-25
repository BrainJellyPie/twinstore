"""Ads on an online store: where each campaign shows, and what it did.

Per campaign and store variant: impressions (pages it was on), reach (visits that saw it), clicks and click-through
rate, post-click conversions (a visit that clicked the ad and ordered the advertised product), view-through
conversions (saw it, did not click, ordered the product anyway), revenue from post-click conversions, cost (per click
or per thousand impressions) and return on ad spend.

Attributed numbers show what an ad was credited with, not what it caused. Against a store without the ad, shopped
by the same people, `ad_lifts` gives the incremental effect: extra units of the advertised product, the change in
total revenue and in revenue from everything else (cannibalization or halo), and incremental return on ad spend.
Either store of a comparison may be the one with the ad.
"""

from store_emulator.domain.online import AdCampaign, AdLift, AdPlacement, AdRow, OnlineSite, SessionResult


def active_ads(site: OnlineSite, placement: AdPlacement) -> list[AdCampaign]:
    """Running campaigns of one placement whose product the store still sells."""
    return [ad for ad in site.ads if ad.active and ad.placement == placement and site.product(ad.product_id) is not None]


def ad_cost(ad: AdCampaign, impressions: int, clicks: int) -> int:
    return ad.cost * clicks if ad.pricing == "cpc" else round(ad.cost * impressions / 1000)


def _units(sessions: list[SessionResult], product_id: str) -> tuple[int, int]:
    """(units, revenue) of one product over the orders of these sessions."""
    units = revenue = 0
    for session in sessions:
        for line in session.order:
            if line.product_id == product_id:
                units += line.quantity
                revenue += line.price * line.quantity
    return units, revenue


def ad_rows(site: OnlineSite, sessions: list[SessionResult]) -> list[AdRow]:
    rows: list[AdRow] = []
    for ad in site.ads:
        if not ad.active:
            continue
        product = site.product(ad.product_id)
        impressions = clicks = reach = click_conversions = view_conversions = attributed = 0
        for session in sessions:
            shown = sum(1 for step in session.steps if ad.id in step.ads)
            clicked = sum(1 for step in session.steps if step.choice is not None and step.choice.ad_id == ad.id)
            impressions += shown
            clicks += clicked
            reach += shown > 0
            bought = [line for line in session.order if line.product_id == ad.product_id]
            if bought and clicked:
                click_conversions += 1
                attributed += sum(line.price * line.quantity for line in bought)
            elif bought and shown:
                view_conversions += 1
        units, _ = _units(sessions, ad.product_id)
        cost = ad_cost(ad, impressions, clicks)
        rows.append(AdRow(
            ad_id=ad.id, name=ad.name, placement=ad.placement, product_id=ad.product_id,
            product_name=product.name if product else ad.product_id, impressions=impressions, reach=reach,
            clicks=clicks, ctr=round(clicks / impressions, 4) if impressions else 0.0,
            click_conversions=click_conversions, view_conversions=view_conversions, attributed_revenue=attributed,
            units_sold=units, cost=cost, roas=round(attributed / cost, 2) if cost else None,
        ))
    return rows


def ad_lifts(control_site: OnlineSite, control: list[SessionResult], control_rows: list[AdRow],
             variant_site: OnlineSite, variant: list[SessionResult], variant_rows: list[AdRow]) -> list[AdLift]:
    """Every ad running in only one of the two stores, against the other store on the same shoppers. An ad running in
    both adds nothing between them. With several such ads, the change in total revenue belongs to all of them
    together."""
    control_running = {ad.id for ad in control_site.ads if ad.active}
    variant_running = {ad.id for ad in variant_site.ads if ad.active}
    lifts: list[AdLift] = []
    for site, with_ad, without, rows, elsewhere in ((variant_site, variant, control, variant_rows, control_running),
                                                    (control_site, control, variant, control_rows, variant_running)):
        total_with = sum(s.order_total for s in with_ad)
        total_without = sum(s.order_total for s in without)
        cost_of = {row.ad_id: row.cost for row in rows}
        for ad in site.ads:
            if not ad.active or ad.id in elsewhere:
                continue
            units_with, revenue_with = _units(with_ad, ad.product_id)
            units_without, revenue_without = _units(without, ad.product_id)
            cost = cost_of.get(ad.id, 0)
            revenue_diff = total_with - total_without
            lifts.append(AdLift(
                ad_id=ad.id, name=ad.name, site_id=site.id, product_id=ad.product_id, units_without=units_without,
                units_with=units_with, units_diff=units_with - units_without, revenue_diff=revenue_diff,
                other_revenue_diff=(total_with - revenue_with) - (total_without - revenue_without), cost=cost,
                iroas=round(revenue_diff / cost, 2) if cost else None,
            ))
    return lifts
