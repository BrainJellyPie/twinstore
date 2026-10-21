import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { protocolAmend, protocolCreate, protocolExport } from "@/services/mutations/protocols";
import { protocolQuery, protocolsQuery } from "@/services/queries/protocols";
import type { DataStage, ProtocolPlan, ProtocolView } from "@/shared/api/protocols";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

const STAGES: [DataStage, string][] = [["not_collected", "Data not collected"], ["collected_unseen", "Data collected; results unseen"], ["results_seen", "Results already seen"]];
const stageLabel = (stage: DataStage) => STAGES.find(([value]) => value === stage)![1];
const TEXT_FIELDS = [
  ["question", "Research question / hypothesis", "State the question and whether the planned work is exploratory."],
  ["population", "Population and sampling", "Define eligible people, stores or synthetic personas and how they are sampled."],
  ["design", "Design and assignment", "Define conditions, assignment and staff/shift blocking where relevant."],
  ["primary_outcome", "Primary outcome and window", "Specify the metric, units, denominator and observation window."],
  ["analysis_unit", "Independent analysis unit", "Person, session, staff/shift block or store? Explain repeated observations and clustering."],
  ["exclusions_and_missing", "Exclusions and missing data", "Define exclusions and handling of missing records before inspecting results."],
  ["stopping_rule", "Stopping and interim review rule", "Define the fixed horizon or stopping rule, including repeated looks."],
  ["analysis_plan", "Analysis and multiplicity plan", "Specify comparisons, uncertainty, multiple testing and relevant model/version settings."],
] as const;
const emptyPlan: ProtocolPlan = { title: "", evidence_type: "synthetic", question: "", population: "", design: "", primary_outcome: "", analysis_unit: "", planned_sample_size: 0, exclusions_and_missing: "", stopping_rule: "", analysis_plan: "" };
function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = filename;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function Protocols({ projectId }: { projectId: string }) {
  const [selected, setSelected] = useState("");
  const list = useQuery(protocolsQuery(projectId));
  return <section aria-label="Research protocols" className="space-y-4">
    <h2 className="text-lg font-semibold">Research protocols and amendments</h2>
    <p className="text-sm">Record the original plan and explain later changes. This local history is not external preregistration or proof that results were unseen. Synthetic studies do not establish actual sales effects.</p>
    <div className="flex flex-wrap gap-2"><Button onClick={() => setSelected(`new:${crypto.randomUUID().replace(/-/g, "")}`)}>New protocol</Button>
      <Button variant="outline" disabled={list.isFetching} onClick={() => void list.refetch()}>Reload protocol list</Button></div>
    {list.isFetching && <p role="status">Loading protocol list…</p>}
    {list.error && <p role="alert">{list.error.message}</p>}
    {list.data?.unavailable_ids.length ? <p role="alert">Some saved histories cannot be read or verified. Preserve the files and restore a verified copy: {list.data.unavailable_ids.join(", ")}</p> : null}
    <div className="flex max-h-48 flex-wrap gap-2 overflow-auto">{list.data?.protocols.map((p) => <Button key={p.protocol_id} variant={selected === p.protocol_id ? "default" : "outline"} className="h-auto max-w-full whitespace-normal break-words text-left" onClick={() => setSelected(p.protocol_id)}>{p.title} · r{p.revision} · {stageLabel(p.data_stage)}</Button>)}</div>
    {selected.startsWith("new:") ? <ProtocolEditor key={`${projectId}:${selected}`} projectId={projectId} requestId={selected.slice(4)} onCreated={setSelected} />
      : selected ? <ProtocolDetail key={`${projectId}:${selected}`} projectId={projectId} id={selected} /> : <p className="text-sm text-muted-foreground">Choose a saved protocol or record a new plan. Up to 100 protocols per project, 50 revisions per protocol. No model calls.</p>}
  </section>;
}

function ProtocolDetail({ projectId, id }: { projectId: string; id: string }) {
  const query = useQuery(protocolQuery(projectId, id));
  return <div className="space-y-3">
    <Button variant="outline" disabled={query.isFetching} onClick={() => void query.refetch()}>Reload saved version (discard draft)</Button>
    {query.isFetching ? <p role="status">Loading saved history…</p> : query.error ? <p role="alert">{query.error.message}</p>
      : query.data ? <ProtocolEditor key={query.data.head_sha256} projectId={projectId} view={query.data} onAmended={() => void query.refetch()} /> : null}
  </div>;
}

function ProtocolEditor({ projectId, view, requestId = "", onCreated, onAmended }: { projectId: string; view?: ProtocolView; requestId?: string; onCreated?: (id: string) => void; onAmended?: () => void }) {
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
    <h3 className="font-semibold">{view ? `Amend saved protocol · revision ${latest!.revision}` : "Record an original research plan"}</h3>
    <p className="text-xs text-muted-foreground">All fields are required. Describe the intended rules; the app records them but does not enforce them on runs or judge their scientific adequacy. Avoid personal details or secrets. Submitted saves can complete after you leave this view; reload the list to check.</p>
    <fieldset disabled={busy} className="space-y-3">
      <label className="block">Protocol title<Input maxLength={120} value={plan.title} onChange={(e) => setPlan({ ...plan, title: e.target.value })} /></label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label>Evidence source<select aria-label="Evidence source" className="block w-full rounded border bg-background p-2" value={plan.evidence_type} onChange={(e) => setPlan({ ...plan, evidence_type: e.target.value as ProtocolPlan["evidence_type"] })}><option value="synthetic">Synthetic / simulated</option><option value="observed">Observed / real-world</option></select></label>
        <label>Declared data stage<select aria-label="Declared data stage" className="block w-full rounded border bg-background p-2" value={stage} onChange={(e) => setStage(e.target.value as DataStage)}><option value="" disabled>Choose declared stage</option>{STAGES.map(([value, label], index) => <option key={value} value={value} disabled={!!latest && index < STAGES.findIndex(([s]) => s === latest.data_stage)}>{label}</option>)}</select></label>
      </div>
      <p className="text-xs">Data stage is your declaration. It cannot move backward. A local timestamp and hash do not prove a plan was written before results were known.</p>
      {TEXT_FIELDS.map(([key, label, hint]) => <label key={key} className="block">{label}<textarea aria-label={label} className="mt-1 block min-h-20 w-full rounded border bg-background p-2" maxLength={1500} value={plan[key]} onChange={(e) => setPlan({ ...plan, [key]: e.target.value })} /><span className="text-xs text-muted-foreground">{hint}</span></label>)}
      <label className="block">Planned independent units<Input type="number" min={1} max={1_000_000} step={1} value={sample} onChange={(e) => setSample(e.target.value)} /></label>
      <p className="text-xs">This records your sample target, not a power calculation or actual observations. Account for staff/shift dependence and repeated measurements in the analysis plan.</p>
      {view && <label className="block">Amendment reason<textarea aria-label="Amendment reason" className="mt-1 block min-h-20 w-full rounded border bg-background p-2" maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} /></label>}
    </fieldset>
    <Button disabled={!valid || !changed || busy || (latest?.revision ?? 0) >= 50} onClick={() => {
      if (!stage) return;
      if (view) amend.mutate({ expected_head: view.head_sha256, plan: submitted, data_stage: stage, reason }, { onSuccess: () => onAmended?.() });
      else create.mutate({ request_id: requestId, plan: submitted, data_stage: stage }, { onSuccess: (result) => onCreated?.(result.ledger.protocol_id) });
    }}>{view ? "Record amendment" : "Record original plan"}</Button>
    {busy && <p role="status">Processing protocol request…</p>}
    {error && <p role="alert" className="text-destructive">{error} Reload the saved version or list before retrying an uncertain save.</p>}
    {view && <>
      <p>Recorded revisions: {view.ledger.revisions.length} · Revisions declaring results seen: {view.revisions_with_results_seen} · Planned-unit change from original: {view.planned_sample_delta ?? "Unavailable"}.</p>
      {view.planned_sample_delta == null && <p>The sample delta is unavailable because the analysis unit or evidence source differs from the original.</p>}
      <p>Plan fields differing from original: {view.changed_from_original.join(", ") || "None"}. Original declared stage: {stageLabel(view.ledger.revisions[0]!.data_stage)}.</p>
      <p className="break-all text-xs">Current head SHA-256: {view.head_sha256}</p>
      <div className="flex flex-wrap gap-2">{(["json", "csv"] as const).map((format) => <Button key={format} variant="outline" disabled={busy || dirty} onClick={() => audit.mutate({ head: view.head_sha256, format }, { onSuccess: (blob) => save(blob, `${id}.${format}`) })}>Export saved {format === "json" ? "history JSON" : "changes CSV"}</Button>)}</div>
      {dirty && <p className="text-xs">Save the amendment or reload the saved version before exporting. Unsaved edits are not in the history.</p>}
      <div className="space-y-2">{view.ledger.revisions.map((revision, index) => <details key={revision.sha256} className="rounded border p-2"><summary className="cursor-pointer">Revision {revision.revision} · {revision.recorded_at} · {stageLabel(revision.data_stage)} · {view.reviews[index]!.changes.length} recorded fields</summary>
        <p className="my-2 whitespace-pre-wrap break-words">Reason: {revision.reason}</p><div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">Changes from preceding revision (original records all fields)</caption><thead><tr className="text-left"><th>Field</th><th>Before</th><th>After</th></tr></thead><tbody>{view.reviews[index]!.changes.map((c) => <tr key={c.field} className="border-t align-top"><th className="py-2 text-left">{c.field}</th><td className="max-w-sm whitespace-pre-wrap break-words p-2">{c.before ?? "Not recorded"}</td><td className="max-w-sm whitespace-pre-wrap break-words p-2">{c.after}</td></tr>)}</tbody></table></div></details>)}</div>
      <details><summary className="cursor-pointer">Method and limitations</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{view.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </>}
  </div>;
}
