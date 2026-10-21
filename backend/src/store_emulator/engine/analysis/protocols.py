"""Canonical local-history digests and explicit plan differences, not validity scores."""

import csv
import hashlib
import io
import json
from datetime import datetime

from store_emulator.domain.protocols import DataStage, ProtocolChange, ProtocolLedger, ProtocolPlan, ProtocolRevision, ProtocolView, RevisionReview

STAGES: tuple[DataStage, ...] = ("not_collected", "collected_unseen", "results_seen")


def revision_digest(project_id: str, protocol_id: str, revision: ProtocolRevision) -> str:
    payload = {"format_version": "protocol-ledger-v1", "project_id": project_id, "protocol_id": protocol_id,
        **revision.model_dump(mode="json", exclude={"sha256"})}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def record_revision(project_id: str, protocol_id: str, plan: ProtocolPlan, data_stage: DataStage,
                    recorded_at: datetime, reason: str, previous: ProtocolRevision | None) -> ProtocolRevision:
    if previous:
        if STAGES.index(data_stage) < STAGES.index(previous.data_stage):
            raise ValueError("Declared data stage cannot move backward; create a separate protocol for a new study")
        if plan == previous.plan and data_stage == previous.data_stage:
            raise ValueError("No plan or data-stage changes to record")
    revision = ProtocolRevision(revision=previous.revision + 1 if previous else 1, recorded_at=recorded_at,
        reason=reason, data_stage=data_stage, plan=plan.model_copy(deep=True), previous_sha256=previous.sha256 if previous else None, sha256="0" * 64)
    revision.sha256 = revision_digest(project_id, protocol_id, revision)
    return revision


def review_protocol(ledger: ProtocolLedger) -> ProtocolView:
    reviews: list[RevisionReview] = []
    previous: ProtocolRevision | None = None
    for number, revision in enumerate(ledger.revisions, 1):
        if revision.revision != number or revision.previous_sha256 != (previous.sha256 if previous else None):
            raise ValueError("Protocol revision sequence or previous hash is inconsistent")
        if revision.sha256 != revision_digest(ledger.project_id, ledger.protocol_id, revision):
            raise ValueError("Protocol content does not match its recorded hash")
        if previous and STAGES.index(revision.data_stage) < STAGES.index(previous.data_stage):
            raise ValueError("Protocol data-stage history moves backward")
        before: dict[str, str | int] = previous.plan.model_dump() if previous else {}
        after: dict[str, str | int] = revision.plan.model_dump()
        changes = [ProtocolChange(field=key, before=before.get(key), after=value) for key, value in after.items() if before.get(key) != value]
        if previous is None or revision.data_stage != previous.data_stage:
            changes.append(ProtocolChange(field="data_stage", before=previous.data_stage if previous else None, after=revision.data_stage))
        if previous and not changes:
            raise ValueError("Protocol contains an empty amendment")
        reviews.append(RevisionReview(revision=number, changes=changes)); previous = revision
    first, last = ledger.revisions[0], ledger.revisions[-1]
    initial: dict[str, str | int] = first.plan.model_dump()
    current: dict[str, str | int] = last.plan.model_dump()
    return ProtocolView(ledger=ledger, reviews=reviews, head_sha256=last.sha256,
        changed_from_original=[key for key, value in current.items() if initial[key] != value],
        planned_sample_delta=(last.plan.planned_sample_size - first.plan.planned_sample_size)
            if last.plan.analysis_unit == first.plan.analysis_unit and last.plan.evidence_type == first.plan.evidence_type else None,
        revisions_with_results_seen=sum(r.data_stage == "results_seen" for r in ledger.revisions), notes=[
            "This is a local protocol history, not external preregistration, a trusted timestamp, a power calculation or certification of research validity. Recording a plan does not enforce it in a simulation or field pilot.",
            "Data stage is a user declaration, not independently verified. Once results are declared seen, later revisions cannot declare them unseen. First-recorded plans can already be retrospective; inspect the original data stage.",
            "Complete plan snapshots are retained. Differences are against the immediately preceding revision; the original comparison uses plan fields only. Sample delta is planned independent units, not collected observations or guaranteed statistical power. The delta is withheld if the declared analysis unit or evidence source differs from the original. Identical text does not verify that the actual units stayed comparable.",
            "Specify estimands, missing-data handling, repeated analyses/multiplicity, and staff/shift clustering where relevant in the plan. No p-values, confidence intervals or outcome effects are computed here. Synthetic evidence cannot establish actual sales effects.",
            "Hashes verify internal consistency of the retained content and ordering. A person with file access can replace the ledger and recompute all hashes; this is not proof of authenticity, permanence, authorship or pre-result timing. Server clock times are not externally certified.",
            "Keep the JSON export for full snapshots and hashes and the CSV for field differences. Export is bound to the head you viewed. The app has no revision edit/delete endpoint; amendments require the current head and a reason. Limits: 100 protocols per project, 50 revisions per protocol.",
        ])


def protocol_changes_csv(view: ProtocolView) -> str:
    out = io.StringIO(); writer = csv.writer(out)
    writer.writerow(["protocol_id", "project_id", "format_version", "head_sha256", "revision", "recorded_at", "revision_sha256", "previous_sha256", "data_stage", "reason", "field", "before", "after"])
    for revision, review in zip(view.ledger.revisions, view.reviews, strict=True):
        for change in review.changes:
            values: list[object] = [view.ledger.protocol_id, view.ledger.project_id, view.ledger.format_version, view.head_sha256,
                revision.revision, revision.recorded_at.isoformat(), revision.sha256, revision.previous_sha256,
                revision.data_stage, revision.reason, change.field, change.before, change.after]
            writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@", "'")) else v for v in values])
    return out.getvalue()
