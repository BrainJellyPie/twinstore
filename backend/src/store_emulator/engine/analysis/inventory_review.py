"""Inventory reconciliation and period ratios; no prices or costs are inferred."""

import csv
import hashlib
import io
import re
from decimal import Decimal
from fractions import Fraction

from pydantic import ValidationError

from store_emulator.domain.inventory_review import InventoryFlag, InventoryInput, InventoryPeriod, InventoryReport, InventoryResult, InventoryTotals

QUANTITIES = ["opening_units", "received_units", "sold_units", "returned_units", "other_in_units", "other_out_units", "closing_units"]
MONEY = ["net_sales_minor", "cogs_minor", "opening_cost_minor", "closing_cost_minor"]
COLUMNS = ["sku", *QUANTITIES, *MONEY]


def inventory_template() -> str:
    out = io.StringIO(); csv.writer(out).writerow(COLUMNS)
    return out.getvalue()


def review_inventory(data: bytes, period: InventoryPeriod) -> InventoryReport:
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Inventory CSV exceeds 2 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Upload a UTF-8 CSV") from exc
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    inputs: list[InventoryInput] = []
    seen: set[str] = set()
    try:
        header = next(reader, list[str]())
        if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            raise ValueError("Use every inventory template column exactly once; extra or missing columns are not allowed")
        for line, cells in enumerate(reader, start=2):
            if line > 2001:
                raise ValueError("Inventory CSV exceeds 2,000 SKU rows")
            if len(cells) != len(header):
                raise ValueError(f"Row {line}: wrong number of columns")
            raw = dict(zip(header, cells, strict=True)); parsed: dict[str, object] = {"sku": raw["sku"]}
            for key in QUANTITIES:
                value = raw[key]
                if len(value) > 20 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,3})?", value):
                    raise ValueError(f"Row {line}: {key} needs an explicit nonnegative decimal with up to three decimal places; blank is not zero")
                parsed[key] = Decimal(value)
            for key in MONEY:
                value = raw[key]
                if len(value) > 20 or not re.fullmatch(r"-?[0-9]+", value):
                    raise ValueError(f"Row {line}: {key} needs an explicit integer in currency minor units")
                parsed[key] = int(value)
            try:
                row = InventoryInput.model_validate(parsed)
            except ValidationError as exc:
                raise ValueError(f"Row {line}: invalid SKU or numeric limit; quantities 0–1,000,000, net money ±1,000,000,000,000, inventory cost 0–1,000,000,000,000") from exc
            if row.sku in seen:
                raise ValueError(f"Row {line}: duplicate SKU; aggregate the same SKU for the selected period before upload")
            seen.add(row.sku); inputs.append(row)
    except csv.Error as exc:
        raise ValueError("Malformed inventory CSV; keep quoted fields intact") from exc
    if not inputs:
        raise ValueError("Inventory CSV must contain at least one SKU row")

    results: list[InventoryResult] = []
    for row in inputs:
        supply = row.opening_units + row.received_units + row.other_in_units
        net_sold = row.sold_units - row.returned_units
        expected = supply - net_sold - row.other_out_units
        difference = row.closing_units - expected
        profit = row.net_sales_minor - row.cogs_minor
        average = Fraction(row.opening_cost_minor + row.closing_cost_minor, 2)
        flags: list[InventoryFlag] = []
        if difference: flags.append("stock_mismatch")
        if expected < 0: flags.append("negative_expected_stock")
        if (row.opening_units == 0 and row.opening_cost_minor != 0) or (row.closing_units == 0 and row.closing_cost_minor != 0):
            flags.append("empty_stock_value")
        valid_stock = not flags
        if net_sold < 0: flags.append("net_returns")
        if not supply: flags.append("zero_supply")
        if not average: flags.append("zero_inventory_cost")
        if row.cogs_minor < 0: flags.append("negative_cogs")
        results.append(InventoryResult(inputs=row, expected_closing_units=float(expected), difference_units=float(difference),
            net_sold_units=float(net_sold), reconciled=difference == 0 and expected >= 0, gross_profit_minor=profit,
            average_inventory_cost_minor=float(average),
            net_sell_through=float(net_sold / supply) if valid_stock and supply and net_sold >= 0 else None,
            inventory_turns=float(row.cogs_minor / average) if valid_stock and average and row.cogs_minor >= 0 else None,
            gmroi=float(profit / average) if valid_stock and average else None, flags=flags))
    sales = sum(r.net_sales_minor for r in inputs); cogs = sum(r.cogs_minor for r in inputs)
    average_total = Fraction(sum(r.opening_cost_minor + r.closing_cost_minor for r in inputs), 2)
    withheld = not average_total or any(not r.reconciled or "empty_stock_value" in r.flags for r in results)
    return InventoryReport(period=period, period_days=(period.end_date - period.start_date).days + 1,
        source_sha256=hashlib.sha256(data).hexdigest(), rows=results,
        totals=InventoryTotals(sku_count=len(results), reconciled_skus=sum(r.reconciled for r in results), net_sales_minor=sales,
            cogs_minor=cogs, gross_profit_minor=sales - cogs, average_inventory_cost_minor=float(average_total),
            inventory_turns=float(cogs / average_total) if not withheld and cogs >= 0 else None,
            gmroi=float((sales - cogs) / average_total) if not withheld else None, ratios_withheld=withheld),
        notes=[
            "These are descriptive calculations from operator-supplied records, not audited stock, simulated demand or a causal marketing effect. Use one period, currency, inventory scope and consistent SKU unit throughout. Inputs are not independently verified or converted.",
            "Expected closing = opening + received + customer returns + other in - gross sold - other out. Difference = recorded closing - expected closing. Other out includes transfers, supplier returns and write-offs; other in includes transfers/corrections. Endpoint reconciliation cannot detect every intraperiod shortage or missing transaction.",
            "Net unit sell-through = (sold - customer returns) / (opening + received + other in). This is an explicit period convention, not a receipt-cohort rate. Returns reduce net sales units and are not counted again in supply. Negative net units or zero supply make it unavailable. No unit ratio is combined across different SKUs.",
            "Gross profit = net sales - net COGS, both after applicable returns, discounts and adjustments, excluding tax. Inventory values must be at cost, not retail selling price. Zero stock with nonzero value and stock mismatches withhold ratios. Missing fields are rejected, never filled with zero.",
            "Average inventory cost = (opening value + closing value) / 2, an endpoint approximation that can miss within-period replenishment peaks. Period GMROI = gross profit / average inventory cost; period turnover = net COGS / average inventory cost. Zero average cost is undefined; negative COGS makes turnover unavailable. Negative profit and GMROI are retained.",
            "Portfolio financial ratios divide totals by the sum of average inventory costs, never average SKU ratios. All supplied SKUs remain in totals; a stock/value conflict withholds portfolio ratios instead of silently excluding that SKU. Net-return periods may refer to sales from earlier periods and need separate interpretation.",
            "Ratios cover the selected period only; they are not annualized, confidence intervals or net profit after labor/rent. No universal target, sales forecast, replenishment order or inventory write-back is inferred. Reviews are not saved; export the audit with its source SHA-256 and period.",
        ])


def inventory_csv(report: InventoryReport) -> str:
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(["row_type", "method", "source_sha256", "start_date", "end_date", "currency", "period_days", *COLUMNS,
        "expected_closing_units", "difference_units", "net_sold_units", "reconciled", "gross_profit_minor", "average_inventory_cost_minor",
        "net_sell_through", "inventory_turns", "gmroi", "flags"])
    meta = [report.method, report.source_sha256, report.period.start_date.isoformat(), report.period.end_date.isoformat(), report.period.currency, report.period_days]
    for result in report.rows:
        raw = result.inputs.model_dump()
        values: list[object] = ["sku", *meta, *[raw[k] for k in COLUMNS], result.expected_closing_units, result.difference_units,
            result.net_sold_units, int(result.reconciled), result.gross_profit_minor, result.average_inventory_cost_minor,
            result.net_sell_through, result.inventory_turns, result.gmroi, "|".join(result.flags)]
        writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@", "'")) else v for v in values])
    t = report.totals
    total_flags = ["ratios_withheld"] if t.ratios_withheld else []
    if t.cogs_minor < 0:
        total_flags.append("negative_cogs")
    writer.writerow(["portfolio", *meta, "", *([""] * len(QUANTITIES)), t.net_sales_minor, t.cogs_minor, "", "", "", "", "", "",
        t.gross_profit_minor, t.average_inventory_cost_minor, "", t.inventory_turns, t.gmroi, "|".join(total_flags)])
    return out.getvalue()
