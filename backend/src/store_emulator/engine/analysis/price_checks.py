"""Exact, descriptive full-outer comparison of two supplied observation sources."""

import csv
import hashlib
import io
import re
from datetime import date

from store_emulator.domain.price_checks import CheckFlag, PriceCheck, PriceCheckReport, PriceCheckScope, PriceCheckTotals, PriceObservation

COLUMNS = ["check_id", "sku", "pack_reference", "checked_on", "currency", "price_minor", "terms"]
MAX_BYTES = 2 * 1024 * 1024


def price_check_template() -> str:
    out = io.StringIO(); csv.writer(out).writerow(COLUMNS)
    return out.getvalue()


def _parse(data: bytes, source: str) -> dict[str, PriceObservation]:
    if len(data) > MAX_BYTES:
        raise ValueError(f"{source} CSV exceeds 2 MB")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    except UnicodeDecodeError as exc:
        raise ValueError(f"{source}: use UTF-8 CSV") from exc
    observations: dict[str, PriceObservation] = {}
    try:
        header = next(reader, list[str]())
        if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            raise ValueError(f"{source}: use each template column exactly once, without extras")
        for line, cells in enumerate(reader, 2):
            if line > 2001:
                raise ValueError(f"{source} CSV exceeds 2,000 rows")
            if len(cells) != len(header):
                raise ValueError(f"{source} row {line}: wrong number of columns")
            raw = dict(zip(header, cells, strict=True))
            try:
                if len(raw["price_minor"]) > 13 or not re.fullmatch(r"[0-9]+", raw["price_minor"]):
                    raise ValueError("Explicit nonnegative integer required")
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw["checked_on"]):
                    raise ValueError("Use YYYY-MM-DD")
                observation = PriceObservation.model_validate({**raw, "checked_on": date.fromisoformat(raw["checked_on"]), "price_minor": int(raw["price_minor"])})
            except ValueError as exc:
                raise ValueError(f"{source} row {line}: invalid value; check IDs, date, currency, integer price and terms") from exc
            if observation.check_id in observations:
                raise ValueError(f"{source} row {line}: duplicate check_id; resolve duplicate checks before upload")
            observations[observation.check_id] = observation
    except csv.Error as exc:
        raise ValueError(f"{source}: malformed CSV; preserve quoted fields") from exc
    return observations


def review_price_checks(label_data: bytes, checkout_data: bytes, scope: PriceCheckScope) -> PriceCheckReport:
    labels = _parse(label_data, "Label"); checkouts = _parse(checkout_data, "Checkout")
    if not labels and not checkouts:
        raise ValueError("Supply at least one observation across the two files")
    rows: list[PriceCheck] = []
    for check_id in sorted(labels.keys() | checkouts.keys()):
        label = labels.get(check_id); checkout = checkouts.get(check_id)
        flags: list[CheckFlag] = []
        if label is None: flags.append("missing_label")
        if checkout is None: flags.append("missing_checkout")
        if label is not None and checkout is not None:
            if label.sku != checkout.sku: flags.append("sku_mismatch")
            if label.pack_reference != checkout.pack_reference: flags.append("pack_mismatch")
            if label.currency != checkout.currency: flags.append("currency_mismatch")
        present = [r for r in (label, checkout) if r is not None]
        if any(r.checked_on != scope.audit_date for r in present): flags.append("outside_audit_date")
        if any(r.terms != "public" for r in present): flags.append("terms_unverified")
        gap = checkout.price_minor - label.price_minor if not flags and label is not None and checkout is not None else None
        rows.append(PriceCheck(check_id=check_id, label=label, checkout=checkout, flags=flags, difference_minor=gap,
            relation="unavailable" if gap is None else "checkout_higher" if gap > 0 else "checkout_lower" if gap < 0 else "equal"))
    currencies = sorted({r.label.currency for r in rows if r.difference_minor is not None and r.label is not None})
    totals: list[PriceCheckTotals] = []
    for currency in currencies:
        differences = [r.difference_minor for r in rows if r.label is not None and r.label.currency == currency and r.difference_minor is not None]
        positive = sum(d for d in differences if d > 0); negative = sum(d for d in differences if d < 0)
        totals.append(PriceCheckTotals(currency=currency, comparable=len(differences), higher=sum(d > 0 for d in differences),
            lower=sum(d < 0 for d in differences), equal=sum(d == 0 for d in differences), positive_difference_minor=positive,
            negative_difference_minor=negative, net_difference_minor=positive + negative))
    digest = hashlib.sha256(scope.model_dump_json().encode())
    for data in (label_data, checkout_data):
        digest.update(len(data).to_bytes(8, "big")); digest.update(data)
    return PriceCheckReport(scope=scope, source_sha256=digest.hexdigest(), label_count=len(labels), checkout_count=len(checkouts),
        excluded_count=sum(bool(r.flags) for r in rows), rows=rows, totals=totals, notes=[
            "Descriptive review of supplied checks, not independently verified prices, a representative store error rate, legal compliance, refunds, lost revenue or causal sales effects.",
            "Join by exact case-sensitive check_id. Repeated SKU checks are allowed and are not independent customers or samples. Missing sides stay unavailable, never zero; duplicates within either source are rejected.",
            "Comparable pairs require identical SKU, full package reference and currency, both on the declared audit date with public terms. Matching identifiers do not prove equivalent items or timing. Verify channel, package, tax, deposit and observation time yourself.",
            "Use full payable item/package prices in integer currency minor units (USD cents, KRW won), including explicit zero for free items. No basket, weighted-goods, multibuy, member or coupon calculations. Unknown and conditional terms are excluded.",
            "Difference = checkout minus label. Positive and negative sums are shown separately so opposite discrepancies do not disappear in the net sum. Totals describe one price difference per comparable check, not transaction volumes or customer losses. Currencies are never converted or pooled.",
            "No models, significance tests, employee/shift comparisons or automatic price writes. Repeated reviews and selected samples do not establish statistical evidence. Retain original files and export; review is not saved. Digest binds both byte streams and scope but does not authenticate observations.",
        ])


def price_check_csv(report: PriceCheckReport) -> str:
    out = io.StringIO(); writer = csv.writer(out)
    fields = ["row_type", "method", "source_sha256", "store_ref", "audit_date", "check_id", *[f"{side}_{c}" for side in ("label", "checkout") for c in COLUMNS if c != "check_id"], "flags", "relation", "difference_minor", *PriceCheckTotals.model_fields]
    writer.writerow(fields)
    meta: dict[str, object] = {"method": report.method, "source_sha256": report.source_sha256, **report.scope.model_dump(mode="json")}
    records: list[dict[str, object]] = []
    for row in report.rows:
        record: dict[str, object] = {**meta, "row_type": "check", "check_id": row.check_id, "flags": "|".join(row.flags), "relation": row.relation, "difference_minor": row.difference_minor}
        for side, observation in (("label", row.label), ("checkout", row.checkout)):
            if observation is not None:
                record.update({f"{side}_{k}": v for k, v in observation.model_dump(mode="json").items() if k != "check_id"})
        records.append(record)
    records.extend({**meta, "row_type": "currency_total", **total.model_dump()} for total in report.totals)
    for record in records:
        values: list[object] = []
        for field in fields:
            value = record.get(field, "")
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "'")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return out.getvalue()
