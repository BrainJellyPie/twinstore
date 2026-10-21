"""Exact assignment/SKU matching; missing sales never imply a negative outcome."""

import csv
import hashlib
import io
import re
from decimal import Decimal

from store_emulator.domain.field_pilot import FieldPilot
from store_emulator.domain.field_pos import PilotPosPreview, PosMatch, PosMatchStatus
from store_emulator.engine.marketing.field_pilot import observations_csv

COLUMNS = ["pilot_id", "assignment_id", "transaction_id", "sku", "net_quantity"]
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")


def reconcile_pos(pilot: FieldPilot, data: bytes) -> PilotPosPreview:
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("POS CSV exceeds 2 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Upload a UTF-8 CSV") from exc
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    transactions: dict[str, str] = {}
    seen_items: set[tuple[str, str]] = set()
    groups: dict[str, set[str]] = {}
    units: dict[str, Decimal] = {}
    count = 0
    try:
        header = next(reader, list[str]())
        if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
            raise ValueError("Use pilot_id, assignment_id, transaction_id, sku and net_quantity exactly once")
        for line, values in enumerate(reader, start=2):
            count += 1
            if count > 10000:
                raise ValueError("POS CSV exceeds 10,000 item rows")
            if len(values) != len(header):
                raise ValueError(f"Row {line}: wrong number of columns")
            row = dict(zip(header, values, strict=True))
            if row["pilot_id"] != pilot.pilot_id:
                raise ValueError(f"Row {line}: pilot ID does not match this pilot")
            aid, tid, sku = row["assignment_id"], row["transaction_id"], row["sku"]
            if not TOKEN.fullmatch(tid) or (aid and not TOKEN.fullmatch(aid)):
                raise ValueError(f"Row {line}: use anonymous alphanumeric transaction/assignment tokens (maximum 120 characters)")
            if not sku.strip() or len(sku) > 200 or any(ord(c) < 32 for c in sku):
                raise ValueError(f"Row {line}: SKU must be nonempty text of at most 200 characters without control characters")
            raw = row["net_quantity"]
            if len(raw) > 20 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,6})?", raw):
                raise ValueError(f"Row {line}: net_quantity must be a nonnegative decimal with up to six decimal places")
            quantity = Decimal(raw)
            if quantity > 1_000_000:
                raise ValueError(f"Row {line}: net_quantity exceeds 1,000,000")
            if tid in transactions and transactions[tid] != aid:
                raise ValueError(f"Row {line}: one transaction cannot belong to multiple assignments (including an unlinked row)")
            if (tid, sku) in seen_items:
                raise ValueError(f"Row {line}: duplicate transaction/SKU; aggregate item lines and returns before upload")
            transactions[tid] = aid
            seen_items.add((tid, sku))
            groups.setdefault(aid, set()).add(tid)
            units[aid] = units.get(aid, Decimal(0)) + (quantity if sku == pilot.product.sku else Decimal(0))
    except csv.Error as exc:
        raise ValueError("Malformed POS CSV; keep quoted fields intact") from exc
    if not count:
        raise ValueError("POS CSV must contain at least one item row")

    candidate = pilot.model_copy(deep=True)
    expected = {a.assignment_id: a for a in candidate.assignments}
    matches: list[PosMatch] = []
    proposals = 0
    positive_enrolled: set[str] = set()
    for aid in sorted(groups):
        saved = expected.get(aid)
        status: PosMatchStatus
        if not aid:
            status = "unlinked"
        elif saved is None:
            status = "unknown_assignment"
        elif units[aid] == 0:
            status = "no_target_evidence"
        elif saved.enrolled is not True:
            status = "not_enrolled"
        else:
            positive_enrolled.add(aid)
            if saved.purchased is False:
                status = "conflicting_purchase"
            elif saved.purchased is True:
                status = "already_recorded"
            else:
                status = "proposed_purchase"
                proposals += 1
                saved.purchased = True
        matches.append(PosMatch(assignment_id=aid, transaction_ids=sorted(groups[aid]), target_units=float(units[aid]),
                                status=status, staff_id=saved.staff_id if saved else None,
                                shift_id=saved.shift_id if saved else None, sequence=saved.sequence if saved else None))
    return PilotPosPreview(
        pilot_id=pilot.pilot_id, revision=pilot.revision, target_sku=pilot.product.sku,
        outcome_window=pilot.design.outcome_window, source_sha256=hashlib.sha256(data).hexdigest(), source_rows=count,
        transactions=len(transactions), linked_assignments=sum(aid in expected for aid in groups),
        enrolled_without_evidence=sum(a.enrolled is True and a.assignment_id not in positive_enrolled for a in pilot.assignments),
        proposed_purchases=proposals, matches=matches, candidate_csv=observations_csv(candidate),
        notes=[
            "Only exact assignment IDs and the saved target SKU match. Transactions must be anonymous, unique across stores/dates, finalized, net of returns, and within the saved outcome window. These conditions are not independently verified.",
            "Positive target units can propose purchase=yes only for an already enrolled encounter with an unknown purchase. Known no values are conflicts, never overwritten. Enrollment, delivery, staff, shift, arm and other outcomes remain unchanged.",
            "No matching target sale, zero net units, missing linkage and partial POS coverage never establish purchase=no. Keep unknown outcomes unknown and verify nonpurchases separately using the same capture procedure in both arms.",
            "Within this CSV, one transaction can link to only one assignment. Multiple receipts for one encounter count as one proposed conversion. Duplicate transaction/SKU rows are rejected; aggregate source lines and returns first. No transaction registry is retained, so reuse across separate files or pilots cannot be detected.",
            "Enrolled encounters without positive evidence describes coverage of this file, including previously recorded buyers absent from this extract. It is not the number of missing purchase outcomes or nonbuyers.",
            "This preview does not save observations or raw POS data. Review the proposed full observation sheet before applying it; stale revisions are rejected. Conflicts and unmatched records remain for manual verification.",
            "Matching is not evidence of script effectiveness and does not correct missingness, repeated testing, repeated shoppers or staff/shift confounding. Keep the original fixed sample and stopping rule.",
        ],
    )
