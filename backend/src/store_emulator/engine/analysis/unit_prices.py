"""Exact unit normalization and eligibility-aware observed offer comparisons."""

import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction

from pydantic import ValidationError

from store_emulator.domain.unit_prices import ObservedOffer, OfferReview, PriceBasis, PriceComparison, PriceFlag, PriceScope, UnitPriceReport

COLUMNS = ["offer_id", "comparison_group", "retailer", "observed_on", "currency", "pack_count", "quantity_per_pack", "unit", "price_minor", "availability", "terms"]
UNITS: dict[str, tuple[PriceBasis, Fraction]] = {"g": ("kg", Fraction(1, 1000)), "kg": ("kg", Fraction(1)), "ml": ("l", Fraction(1, 1000)), "l": ("l", Fraction(1)), "item": ("item", Fraction(1))}


def _decimal(value: Fraction) -> str:
    with localcontext() as ctx:
        ctx.prec = 50
        return format(Decimal(value.numerator) / Decimal(value.denominator), ".12g")


def unit_price_template() -> str:
    out = io.StringIO(); csv.writer(out).writerow(COLUMNS)
    return out.getvalue()


def review_unit_prices(data: bytes, scope: PriceScope) -> UnitPriceReport:
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Offer CSV exceeds 2 MB")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    except UnicodeDecodeError as exc:
        raise ValueError("Upload a UTF-8 CSV") from exc
    rows: list[OfferReview] = []
    seen: set[tuple[str, str]] = set()
    groups: dict[tuple[str, str, PriceBasis], list[OfferReview]] = defaultdict(list)
    try:
        header = next(reader, list[str]())
        if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            raise ValueError("Use every offer template column exactly once, without extra columns")
        for line, cells in enumerate(reader, 2):
            if line > 2001:
                raise ValueError("Offer CSV exceeds 2,000 rows")
            if len(cells) != len(header):
                raise ValueError(f"Row {line}: wrong number of columns")
            raw = dict(zip(header, cells, strict=True)); parsed: dict[str, object] = dict(raw)
            for key in ("pack_count", "price_minor"):
                if len(raw[key]) > 16 or not re.fullmatch(r"[0-9]+", raw[key]):
                    raise ValueError(f"Row {line}: {key} needs an explicit nonnegative integer")
                parsed[key] = int(raw[key])
            if len(raw["quantity_per_pack"]) > 16 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,3})?", raw["quantity_per_pack"]):
                raise ValueError(f"Row {line}: quantity_per_pack needs a positive decimal with up to three decimal places")
            parsed["quantity_per_pack"] = Decimal(raw["quantity_per_pack"])
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw["observed_on"]):
                    raise ValueError("Use YYYY-MM-DD")
                parsed["observed_on"] = date.fromisoformat(raw["observed_on"])
                offer = ObservedOffer.model_validate(parsed)
            except (ValidationError, ValueError) as exc:
                raise ValueError(f"Row {line}: invalid offer value; check identifiers, date, currency, units (item requires whole counts), status and template limits") from exc
            identity = (offer.retailer, offer.offer_id)
            if identity in seen:
                raise ValueError(f"Row {line}: duplicate retailer/offer ID; choose one observation per offer before upload")
            seen.add(identity)
            basis, scale = UNITS[offer.unit]
            quantity = Fraction(offer.quantity_per_pack) * offer.pack_count * scale
            rate = Fraction(offer.price_minor) / quantity
            flags: list[PriceFlag] = []
            age = (scope.as_of - offer.observed_on).days
            if age < 0: flags.append("future")
            elif age > scope.max_age_days: flags.append("stale")
            if offer.availability == "out_of_stock": flags.append("out_of_stock")
            elif offer.availability == "unknown": flags.append("unknown_availability")
            if offer.terms == "conditional": flags.append("conditional_offer")
            row = OfferReview(inputs=offer, basis=basis, quantity_in_basis=_decimal(quantity), unit_price_minor=_decimal(rate), unit_price_exact=str(rate), flags=flags)
            rows.append(row); groups[(offer.comparison_group, offer.currency, basis)].append(row)
    except csv.Error as exc:
        raise ValueError("Malformed offer CSV; keep quoted fields intact") from exc
    if not rows:
        raise ValueError("Offer CSV needs at least one row")
    if not any(row.inputs.retailer == scope.focal_retailer for row in rows):
        raise ValueError("Focal retailer must exactly match a supplied retailer ID")
    comparisons: list[PriceComparison] = []
    for (group, currency, basis), offers in sorted(groups.items()):
        focal = [r for r in offers if not r.flags and r.inputs.retailer == scope.focal_retailer]
        competitors = [r for r in offers if not r.flags and r.inputs.retailer != scope.focal_retailer]
        own_min = min((Fraction(r.unit_price_exact) for r in focal), default=None)
        other_min = min((Fraction(r.unit_price_exact) for r in competitors), default=None)
        gap = own_min - other_min if own_min is not None and other_min is not None else None
        comparisons.append(PriceComparison(comparison_group=group, currency=currency, basis=basis,
            focal_count=len(focal), competitor_count=len(competitors), competitor_retailers=len({r.inputs.retailer for r in competitors}),
            focal_min_minor=_decimal(own_min) if own_min is not None else None,
            competitor_min_minor=_decimal(other_min) if other_min is not None else None,
            gap_minor=_decimal(gap) if gap is not None else None, gap_exact=str(gap) if gap is not None else None,
            gap_percent=_decimal(100 * gap / other_min) if gap is not None and other_min else None,
            relation="unavailable" if gap is None else "equal" if gap == 0 else "above" if gap > 0 else "below",
            focal_offer_ids=sorted(r.inputs.offer_id for r in focal if Fraction(r.unit_price_exact) == own_min),
            competitor_offers=sorted((r.inputs.retailer, r.inputs.offer_id) for r in competitors if Fraction(r.unit_price_exact) == other_min)))
    return UnitPriceReport(scope=scope, source_sha256=hashlib.sha256(data).hexdigest(), rows=rows, comparisons=comparisons, notes=[
        "Observed operator-supplied offers, not verified live prices, a market census, demand forecasts or causal sales effects. A missing offer does not establish absence from a retailer's assortment.",
        "Comparison groups assert comparable products/quality and consistent tax, deposit, delivery and channel treatment. The operator must check these assumptions. IDs are exact and case-sensitive; no fuzzy product matching or currency conversion.",
        "Total quantity = pack_count × quantity_per_pack, normalized to kg, l or item. price_minor is the total payable price for that complete bundle, not a per-pack price. No automatic promotion or membership arithmetic.",
        "Only in-stock public offers observed on/before as_of and no more than max_age_days old qualify. Conditional/member/coupon offers, unknown availability, stale and future observations remain in the audit but are excluded from comparisons.",
        "Each group/currency/basis compares the lowest eligible focal offer with the lowest eligible competitor offer. Counts and all exact ties are shown; this is a selected observed minimum, not a typical price or optimal price recommendation.",
        "Gap = focal minimum - competitor minimum. Percent gap = 100 × gap / competitor minimum; undefined when that minimum is zero. Missing sides remain unavailable, not zero. Exact rational comparisons precede 12-significant-digit display rounding; audit includes exact rates and gaps.",
        "No model calls, p-values, employee/shift pooling, automatic price changes or town-demand calibration. Changing the scope is descriptive filtering. Reviews are not saved; retain the original CSV and audit with source hash and scope.",
    ])


def unit_price_csv(report: UnitPriceReport) -> str:
    out = io.StringIO(); writer = csv.writer(out)
    comparison_columns = ["focal_count", "competitor_count", "competitor_retailers", "focal_min_minor", "competitor_min_minor", "gap_minor", "gap_exact", "gap_percent", "relation", "focal_offer_ids", "competitor_offers"]
    columns = ["row_type", "method", "source_sha256", "focal_retailer", "as_of", "max_age_days", *COLUMNS, "basis", "quantity_in_basis", "unit_price_minor", "unit_price_exact", "flags", *comparison_columns]
    writer.writerow(columns)
    meta: dict[str, object] = {"method": report.method, "source_sha256": report.source_sha256, **report.scope.model_dump(mode="json")}
    records: list[dict[str, object]] = []
    for row in report.rows:
        records.append({**meta, "row_type": "offer", **row.inputs.model_dump(mode="json"), "basis": row.basis,
            "quantity_in_basis": row.quantity_in_basis, "unit_price_minor": row.unit_price_minor, "unit_price_exact": row.unit_price_exact, "flags": "|".join(row.flags)})
    for c in report.comparisons:
        records.append({**meta, "row_type": "comparison", **c.model_dump(), "focal_offer_ids": json.dumps(c.focal_offer_ids, ensure_ascii=False), "competitor_offers": json.dumps(c.competitor_offers, ensure_ascii=False)})
    label_columns = {"focal_retailer", "offer_id", "comparison_group", "retailer"}
    for record in records:
        values: list[object] = []
        for key in columns:
            value = record.get(key, "")
            if key in label_columns and isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "'")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return out.getvalue()
