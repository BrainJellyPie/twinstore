import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { protocolAmend, protocolCreate, protocolExport } from "@/services/mutations/protocols";
import { protocolQuery, protocolsQuery } from "@/services/queries/protocols";
import type { DataStage, ProtocolPlan, ProtocolView } from "@/shared/api/protocols";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

type Translate = ReturnType<typeof useI18n>["t"];
const STAGES: [DataStage, MessageKey][] = [["not_collected", "mkStageNotCollected"], ["collected_unseen", "mkStageCollectedUnseen"], ["results_seen", "mkStageResultsSeen"]];
const stageLabel = (stage: DataStage, t: Translate) => t(STAGES.find(([value]) => value === stage)![1]);
const TEXT_FIELDS = [
  ["question", "mkFieldQuestion", "mkFieldQuestionHint"],
  ["population", "mkFieldPopulation", "mkFieldPopulationHint"],
  ["design", "mkFieldDesign", "mkFieldDesignHint"],
  ["primary_outcome", "mkFieldOutcome", "mkFieldOutcomeHint"],
  ["analysis_unit", "mkFieldUnit", "mkFieldUnitHint"],
  ["exclusions_and_missing", "mkFieldExclusions", "mkFieldExclusionsHint"],
  ["stopping_rule", "mkFieldStopping", "mkFieldStoppingHint"],
  ["analysis_plan", "mkFieldAnalysis", "mkFieldAnalysisHint"],
] as const;
const OTHER_FIELDS: Record<string, MessageKey> = {
  title: "mkProtocolFieldTitle", evidence_type: "mkProtocolFieldEvidence", planned_sample_size: "mkProtocolFieldSample", data_stage: "mkProtocolFieldStage",
};
/** Plan field keys from the saved history, shown with the labels used in the form. */
function fieldLabel(field: string, t: Translate): string {
  const text = TEXT_FIELDS.find(([key]) => key === field);
  if (text) return t(text[1]);
  return Object.prototype.hasOwnProperty.call(OTHER_FIELDS, field) ? t(OTHER_FIELDS[field]!) : field;
}
const emptyPlan: ProtocolPlan = { title: "", evidence_type: "synthetic", question: "", population: "", design: "", primary_outcome: "", analysis_unit: "", planned_sample_size: 0, exclusions_and_missing: "", stopping_rule: "", analysis_plan: "" };
function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = filename;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function Protocols({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const [selected, setSelected] = useState("");
  const list = useQuery(protocolsQuery(projectId));
  return <section aria-label={t("mkProtocolsAria")} className="space-y-4">
    <h2 className="text-lg font-semibold">{t("mkProtocolsTitle")}</h2>
    <p className="text-sm">{t("mkProtocolsIntro")}</p>
    <div className="flex flex-wrap gap-2"><Button onClick={() => setSelected(`new:${crypto.randomUUID().replace(/-/g, "")}`)}>{t("mkNewProtocol")}</Button>
      <Button variant="outline" disabled={list.isFetching} onClick={() => void list.refetch()}>{t("mkReloadProtocols")}</Button></div>
    {list.isFetching && <p role="status">{t("mkLoadingProtocols")}</p>}
    {list.error && <p role="alert">{list.error.message}</p>}
    {list.data?.unavailable_ids.length ? <p role="alert">{t("mkUnreadableHistories", { ids: list.data.unavailable_ids.join(", ") })}</p> : null}
    <div className="flex max-h-48 flex-wrap gap-2 overflow-auto">{list.data?.protocols.map((p) => <Button key={p.protocol_id} variant={selected === p.protocol_id ? "default" : "outline"} className="h-auto max-w-full whitespace-normal break-words text-left" onClick={() => setSelected(p.protocol_id)}>{t("mkProtocolItem", { title: p.title, revision: String(p.revision), stage: stageLabel(p.data_stage, t) })}</Button>)}</div>
    {selected.startsWith("new:") ? <ProtocolEditor key={`${projectId}:${selected}`} projectId={projectId} requestId={selected.slice(4)} onCreated={setSelected} />
      : selected ? <ProtocolDetail key={`${projectId}:${selected}`} projectId={projectId} id={selected} /> : <p className="text-sm text-muted-foreground">{t("mkChooseProtocol")}</p>}
  </section>;
}

function ProtocolDetail({ projectId, id }: { projectId: string; id: string }) {
  const { t } = useI18n();
  const query = useQuery(protocolQuery(projectId, id));
  return <div className="space-y-3">
    <Button variant="outline" disabled={query.isFetching} onClick={() => void query.refetch()}>{t("mkReloadSaved")}</Button>
    {query.isFetching ? <p role="status">{t("mkLoadingHistory")}</p> : query.error ? <p role="alert">{query.error.message}</p>
      : query.data ? <ProtocolEditor key={query.data.head_sha256} projectId={projectId} view={query.data} onAmended={() => void query.refetch()} /> : null}
  </div>;
}

function ProtocolEditor({ projectId, view, requestId = "", onCreated, onAmended }: { projectId: string; view?: ProtocolView; requestId?: string; onCreated?: (id: string) => void; onAmended?: () => void }) {
  const { t } = useI18n();
  const latest = view ? view.ledger.revisions[view.ledger.revisions.length - 1] : undefined;
  const [plan, setPlan] = useState<ProtocolPlan>(latest?.plan ?? emptyPlan);
  const [sample, setSample] = useState(latest ? String(latest.plan.planned_sample_size) : "");
  const [stage, setStage] = useState<DataStage | "">(latest?.data_stage ?? ""); const [reason, setReason] = useState("");
  const qc = useQueryClient(); const id = view?.ledger.protocol_id ?? "";
  const create = useMutation(protocolCreate(projectId, qc)); const amend = useMutation(protocolAmend(projectId, id, qc));
  const audit = useMutation(protocolExport(projectId, id));
  const busy = create.isPending || amend.isPending || audit.isPending;
  const submitted = { ...plan, planned_sample_size: Number(sample) };
  const changed = !latest || JSON.stringify(submitted) !== JSON.stringify(latest.plan) || stage !== latest.data_stage;
  const dirty = changed || reason !== "";
  const valid = stage !== "" && plan.title.trim() && TEXT_FIELDS.every(([key]) => plan[key].trim()) && /^\d+$/.test(sample) && Number(sample) >= 1 && Number(sample) <= 1_000_000 && (!view || reason.trim());
  const error = create.error?.message || amend.error?.message || audit.error?.message;
  return <div className="space-y-4 rounded-2xl border bg-card p-4 text-sm">
    <h3 className="font-semibold">{view ? t("mkAmendTitle", { revision: String(latest!.revision) }) : t("mkRecordTitle")}</h3>
    <p className="text-xs text-muted-foreground">{t("mkProtocolIntro")}</p>
    <fieldset disabled={busy} className="space-y-3">
      <label className="block">{t("mkProtocolTitle")}<Input maxLength={120} value={plan.title} onChange={(e) => setPlan({ ...plan, title: e.target.value })} /></label>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label>{t("mkEvidenceSource")}<select aria-label={t("mkEvidenceSource")} className="block w-full rounded border bg-background p-2" value={plan.evidence_type} onChange={(e) => setPlan({ ...plan, evidence_type: e.target.value as ProtocolPlan["evidence_type"] })}><option value="synthetic">{t("mkEvidenceSynthetic")}</option><option value="observed">{t("mkEvidenceObserved")}</option></select></label>
        <label>{t("mkDeclaredStage")}<select aria-label={t("mkDeclaredStage")} className="block w-full rounded border bg-background p-2" value={stage} onChange={(e) => setStage(e.target.value as DataStage)}><option value="" disabled>{t("mkChooseStage")}</option>{STAGES.map(([value, label], index) => <option key={value} value={value} disabled={!!latest && index < STAGES.findIndex(([s]) => s === latest.data_stage)}>{t(label)}</option>)}</select></label>
      </div>
      <p className="text-xs">{t("mkStageHint")}</p>
      {TEXT_FIELDS.map(([key, label, hint]) => <label key={key} className="block">{t(label)}<textarea aria-label={t(label)} className="mt-1 block min-h-20 w-full rounded border bg-background p-2" maxLength={1500} value={plan[key]} onChange={(e) => setPlan({ ...plan, [key]: e.target.value })} /><span className="text-xs text-muted-foreground">{t(hint)}</span></label>)}
      <label className="block">{t("mkPlannedUnits")}<Input type="number" min={1} max={1_000_000} step={1} value={sample} onChange={(e) => setSample(e.target.value)} /></label>
      <p className="text-xs">{t("mkPlannedUnitsHint")}</p>
      {view && <label className="block">{t("mkAmendReason")}<textarea aria-label={t("mkAmendReason")} className="mt-1 block min-h-20 w-full rounded border bg-background p-2" maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} /></label>}
    </fieldset>
    <Button disabled={!valid || !changed || busy || (latest?.revision ?? 0) >= 50} onClick={() => {
      if (!stage) return;
      if (view) amend.mutate({ expected_head: view.head_sha256, plan: submitted, data_stage: stage, reason }, { onSuccess: () => onAmended?.() });
      else create.mutate({ request_id: requestId, plan: submitted, data_stage: stage }, { onSuccess: (result) => onCreated?.(result.ledger.protocol_id) });
    }}>{view ? t("mkRecordAmendment") : t("mkRecordOriginal")}</Button>
    {busy && <p role="status">{t("mkProcessingProtocol")}</p>}
    {error && <p role="alert" className="text-destructive">{t("mkUncertainSave", { error })}</p>}
    {view && <>
      <p>{t("mkRevisionStats", { revisions: view.ledger.revisions.length, seen: view.revisions_with_results_seen, delta: view.planned_sample_delta ?? t("studioUnavailable") })}</p>
      {view.planned_sample_delta == null && <p>{t("mkDeltaUnavailable")}</p>}
      <p>{t("mkFieldsDiffering", { fields: view.changed_from_original.map((field) => fieldLabel(field, t)).join(", ") || t("studioNone"), stage: stageLabel(view.ledger.revisions[0]!.data_stage, t) })}</p>
      <p className="break-all text-xs">{t("mkHeadSha", { sha: view.head_sha256 })}</p>
      <div className="flex flex-wrap gap-2">{(["json", "csv"] as const).map((format) => <Button key={format} variant="outline" disabled={busy || dirty} onClick={() => audit.mutate({ head: view.head_sha256, format }, { onSuccess: (blob) => save(blob, `${id}.${format}`) })}>{format === "json" ? t("mkExportJson") : t("mkExportChangesCsv")}</Button>)}</div>
      {dirty && <p className="text-xs">{t("mkSaveBeforeExport")}</p>}
      <div className="space-y-2">{view.ledger.revisions.map((revision, index) => <details key={revision.sha256} className="rounded border p-2"><summary className="cursor-pointer">{t("mkRevisionSummary", { revision: String(revision.revision), at: revision.recorded_at, stage: stageLabel(revision.data_stage, t), count: view.reviews[index]!.changes.length })}</summary>
        <p className="my-2 whitespace-pre-wrap break-words">{t("mkReasonValue", { value: revision.reason })}</p><div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">{t("mkChangesCaption")}</caption><thead><tr className="text-left"><th>{t("mkColField")}</th><th>{t("mkColBefore")}</th><th>{t("mkColAfter")}</th></tr></thead><tbody>{view.reviews[index]!.changes.map((c) => <tr key={c.field} className="border-t align-top"><th className="py-2 text-left">{fieldLabel(c.field, t)}</th><td className="max-w-sm whitespace-pre-wrap break-words p-2">{c.before ?? t("mkNotRecorded")}</td><td className="max-w-sm whitespace-pre-wrap break-words p-2">{c.after}</td></tr>)}</tbody></table></div></details>)}</div>
      <details><summary className="cursor-pointer">{t("studioMethodLimitations")}</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{view.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </>}
  </div>;
}
