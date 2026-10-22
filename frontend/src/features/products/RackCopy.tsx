import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import { rackCopyOptions } from "@/services/queries/rackCopy";
import { rackCopyPreview, rackCopySave } from "@/services/mutations/rackCopy";
import type { RackCopySave } from "@/shared/api/rackCopy";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { useI18n } from "@/shared/i18n/i18n";
import { priceText } from "./productDrafts";

export function RackCopy({ pid, sid }: { pid: string; sid: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return <><Button variant="outline" onClick={() => setOpen(true)}>{t("copyTitle")}</Button>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="flex max-h-[90dvh] flex-col overflow-y-auto p-4 sm:max-w-4xl sm:p-7">
      <DialogTitle>{t("copyTitle")}</DialogTitle>
      <DialogDescription>{t("copyDescription")}</DialogDescription>
      {open && <CopySession key={`${pid}:${sid}`} pid={pid} sid={sid} close={() => setOpen(false)} />}
    </DialogContent></Dialog></>;
}
function CopySession({ pid, sid, close }: { pid: string; sid: string; close: () => void }) {
  const { t } = useI18n();
  const [source, setSource] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(new Set<string>());
  const [prepared, setPrepared] = useState<RackCopySave | null>(null);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const options = useQuery(rackCopyOptions(pid, sid, source));
  const preview = useMutation(rackCopyPreview(pid, sid));
  const save = useMutation(rackCopySave(pid, sid));
  const qc = useQueryClient();
  const busy = options.isFetching || preview.isPending || save.isPending;
  const locked = busy || !!save.data;
  const current = options.data?.source_rack_id === (source || null) && !options.isError && !options.isPlaceholderData;
  const previewCurrent = current && prepared?.source_sha256 === options.data?.source_sha256 && prepared?.currency === options.data?.currency;
  const targets = current ? options.data?.targets ?? [] : [];
  const shown = targets.filter(r => `${r.name} ${r.id} ${r.type}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).slice(0, 100);
  const clear = () => { setPrepared(null); preview.reset(); save.reset(); setError(""); };
  const choose = (next: Set<string>) => { setSelected(next); clear(); };
  const check = async () => {
    if (pending.current || !options.data || !current || !source || !selected.size) return;
    clear();
    if (selected.size > 100) { setError(t("copyAtMost")); return; }
    const body = { source_sha256: options.data.source_sha256, currency: options.data.currency, source_rack_id: source, target_rack_ids: [...selected] };
    pending.current = true;
    try { await preview.mutateAsync(body); setPrepared({ ...body, request_id: crypto.randomUUID().replace(/-/g, "") }); }
    catch (e) { setError((e as Error).message); } finally { pending.current = false; }
  };
  const persist = async () => {
    if (!prepared || pending.current || (!previewCurrent && !save.isError)) return;
    pending.current = true;
    try {
      await save.mutateAsync(prepared);
      void qc.invalidateQueries({ queryKey: queryKeys.setups(pid) });
      void qc.invalidateQueries({ queryKey: queryKeys.project(pid), exact: true });
    } catch { /* Retain the prepared identity after an uncertain response. */ }
    finally { pending.current = false; }
  };
  return <div className="min-w-0 space-y-3 [overflow-wrap:anywhere] [&_button]:h-auto [&_button]:min-h-9 [&_button]:max-w-full [&_button]:whitespace-normal [&_button]:py-2">
    <p>{t("copyIntro")}</p>
    <p>{t("copyRules")}</p>
    <fieldset disabled={locked} className="min-w-0 space-y-3">
      <label className="block">{t("copyFrom")}<select className="mt-1 block w-full min-w-0 rounded border p-2" value={source} onChange={e => { setSource(e.target.value); choose(new Set()); }}>
        <option value="">{t("copyChooseSource")}</option>
        {options.data?.sources.map(r => <option key={r.id} value={r.id} disabled={!!r.reason}>{r.name} · {r.id} · {t("copyPlacements", { count: r.placements })}{r.reason ? ` — ${r.reason}` : ""}</option>)}
      </select></label>
      <Button variant="outline" onClick={() => { choose(new Set()); void options.refetch(); }}>{t("copyDiscardReload")}</Button>
      <label className="block">{t("copySearch")}<input className="mt-1 block w-full min-w-0 rounded border p-2" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <p>{t("copyShown", { shown: shown.length, selected: selected.size })}</p>
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={!current || !source} onClick={() => choose(new Set([...selected, ...shown.filter(r => !r.reason).map(r => r.id)]))}>{t("copySelectShown")}</Button><Button variant="outline" onClick={() => choose(new Set())}>{t("productsClearSelection")}</Button></div>
      <div className="max-h-[30dvh] overflow-auto rounded border">
        {shown.map(r => <div key={r.id} className="border-b p-2"><label><input type="checkbox" aria-label={t("copyToRack", { rack: r.id })} disabled={!!r.reason} checked={selected.has(r.id)} onChange={e => { const next = new Set(selected); if (e.target.checked) next.add(r.id); else next.delete(r.id); choose(next); }} /> {r.name} · {r.type} · {r.id}</label><p>{r.reason ?? t("copyWillCopy", { count: r.placements })}</p></div>)}
      </div>
    </fieldset>
    {options.isFetching && <p role="status">{t("productsCheckingShelves")}</p>}
    {options.isError && <p role="alert">{options.error.message} <Button disabled={busy} onClick={() => void options.refetch()}>{t("copyRetryShelves")}</Button></p>}
    {current && !options.data?.sources.length && <p>{t("copyNoSources")}</p>}
    {source && current && !targets.some(r => !r.reason) && <p>{t("copyNoTargets")}</p>}
    {error && <p role="alert">{error}</p>}
    <Button disabled={locked || !current || !selected.size} onClick={() => void check()}>{t("copyPreview")}</Button>
    {prepared && !previewCurrent && !busy && !save.data && !save.isError && <p role="alert">{t("copyLayoutChanged")}</p>}
    {preview.data && prepared && (previewCurrent || save.isPending || save.isError || save.data) && <section aria-label={t("copyPreviewRegion")} className="space-y-2 rounded border p-3">
      <p>{t("copyPreviewSummary", { source: preview.data.source_name, targets: preview.data.targets.length, placements: preview.data.placements_added })}</p>
      <ul>{preview.data.targets.map(r => <li key={r.id}>{r.name} · {r.id}: {t("copyPlacements", { count: r.placements })}</li>)}</ul>
      <details open><summary>{t("copyReviewProducts")}</summary>{preview.data.slots.map(s => <div key={`${s.block}:${s.face}:${s.level}`}><p>{t("copySlot", { block: s.block + 1, face: s.face, level: s.level })}</p><ol>{s.items.map((p, i) => <li key={i}>{p.name} · {p.sku} · {priceText(p.price, prepared.currency)} {prepared.currency}{p.regular_price ? ` · ${t("copyRegularPrice", { price: `${priceText(p.regular_price, prepared.currency)} ${prepared.currency}` })}` : ""}{p.promo ? ` · ${p.promo}` : ""} · {p.image_url ? t("copyImageRetained") : t("copyNoImage")}</li>)}</ol></div>)}</details>
      {prepared && !save.data && <Button disabled={busy} onClick={() => void persist()}>{save.isPending ? t("copySaving") : save.isError ? t("copyRetrySave") : t("copySave")}</Button>}
    </section>}
    {save.isError && <p role="alert">{save.error.message} {t("copyUncertainSave")}</p>}
    {save.data && <div role="status"><p>{t("copySaved")}</p><Button onClick={() => { if (save.data) { useSimulationStore.getState().setSelectedSetupId(save.data.setup_id); close(); } }}>{t("copyOpen")}</Button></div>}
    <p className="text-xs">{t("copyClosing")}</p>
  </div>;
}
