import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import { starterCatalog } from "@/services/queries/starterFill";
import { starterPreview, starterSave } from "@/services/mutations/starterFill";
import type { StarterCatalog, StarterSave } from "@/shared/api/starterFill";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { useI18n } from "@/shared/i18n/i18n";
import { priceText } from "./productDrafts";

export function StarterFill({ pid, sid }: { pid: string; sid: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return <>
    <Button variant="outline" onClick={() => setOpen(true)}>{t("starterTitle")}</Button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="flex max-h-[90dvh] flex-col overflow-y-auto p-4 sm:max-w-4xl sm:p-7">
        <DialogTitle>{t("starterTitle")}</DialogTitle>
        <DialogDescription>{t("starterDescription")}</DialogDescription>
        {open && <StarterSession key={`${pid}:${sid}`} pid={pid} sid={sid} close={() => setOpen(false)} />}
      </DialogContent>
    </Dialog>
  </>;
}
function StarterSession({ pid, sid, close }: { pid: string; sid: string; close: () => void }) {
  const { t } = useI18n();
  const catalog = useQuery(starterCatalog(pid, sid));
  const [revision, setRevision] = useState(0);
  const [reloading, setReloading] = useState(false);
  const reload = () => {
    setReloading(true);
    void catalog.refetch().then((result) => { if (result.isSuccess) setRevision((n) => n + 1); }).finally(() => setReloading(false));
  };
  return <>
    {catalog.isError && <p role="alert">{catalog.error.message}<Button className="h-auto min-h-9 max-w-full whitespace-normal py-2" disabled={reloading} onClick={reload}>{catalog.data ? t("starterDiscardRetry") : t("starterRetry")}</Button></p>}
    {!catalog.data && !catalog.isError && <p role="status">{t("starterLoading")}</p>}
    {catalog.data && <StarterForm key={revision} pid={pid} sid={sid} initial={catalog.data} refreshing={reloading} reload={reload} close={close} />}
  </>;
}
function StarterForm({ pid, sid, initial, refreshing, reload, close }: {
  pid: string; sid: string; initial: StarterCatalog; refreshing: boolean; reload: () => void; close: () => void;
}) {
  const { t } = useI18n();
  const [snapshot] = useState(initial);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [perSlot, setPerSlot] = useState(2);
  const [selected, setSelected] = useState(new Map<string, string>());
  const [error, setError] = useState("");
  const [prepared, setPrepared] = useState<StarterSave | null>(null);
  const pending = useRef(false);
  const preview = useMutation(starterPreview(pid, sid));
  const save = useMutation(starterSave(pid, sid));
  const qc = useQueryClient();
  const busy = preview.isPending || save.isPending || refreshing;
  const locked = busy || !!save.data;
  const shown = snapshot.racks.filter((r) => `${r.name} ${r.id} ${r.type}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).slice(0, 100);
  const clear = () => { setPrepared(null); preview.reset(); save.reset(); setError(""); };
  const choose = (next: Map<string, string>) => { setSelected(next); clear(); };
  const check = async () => {
    if (pending.current) return;
    clear();
    if (!selected.size || selected.size > 100) { setError(t("starterChooseRacks")); return; }
    if ([...selected.values()].some((key) => !key)) { setError(t("starterChooseCategoryEach")); return; }
    const body = { source_sha256: snapshot.source_sha256, currency: snapshot.currency, products_per_slot: perSlot,
      assignments: [...selected].map(([rack_id, value]) => ({ rack_id, category: value })) };
    pending.current = true;
    try {
      await preview.mutateAsync(body);
      setPrepared({ ...body, request_id: crypto.randomUUID().replace(/-/g, "") });
    } catch (e) { setError((e as Error).message); } finally { pending.current = false; }
  };
  const persist = async () => {
    if (!prepared || pending.current) return;
    pending.current = true;
    try {
      await save.mutateAsync(prepared);
      void qc.invalidateQueries({ queryKey: queryKeys.setups(pid) });
      void qc.invalidateQueries({ queryKey: queryKeys.project(pid), exact: true });
    } catch { /* Keep the same prepared request for retry. */ }
    finally { pending.current = false; }
  };
  const options = snapshot.categories.map((c) => <option key={c.key} value={c.key}>{t("starterCategoryOption", { category: c.label, count: c.products.length })}</option>);
  const sample = snapshot.categories.find((c) => c.key === category);
  return <div className="min-w-0 space-y-3 [overflow-wrap:anywhere] [&_button]:h-auto [&_button]:min-h-9 [&_button]:max-w-full [&_button]:whitespace-normal [&_button]:py-2">
    <p>{t("starterExamples")}</p>
    <p>{t("starterEligible")}</p>
    <label className="block">{t("starterSearch")}<input className="mt-1 block w-full min-w-0 max-w-full rounded border p-2" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
    <p>{t("starterShown", { shown: shown.length, selected: selected.size })}</p>
    <fieldset disabled={locked} className="min-w-0 space-y-2 rounded border p-3">
      <legend>{t("starterAssortment")}</legend>
      <label className="block">{t("starterCategoryToApply")}<select className="mt-1 block w-full min-w-0 max-w-full rounded border p-2" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">{t("starterChooseCategory")}</option>{options}</select></label>
      <label className="block">{t("starterPerSection")}<select className="mt-1 block w-full min-w-0 rounded border p-2" value={perSlot} onChange={(e) => { setPerSlot(Number(e.target.value)); clear(); }}>{[1, 2, 3, 4].map((n) => <option key={n}>{n}</option>)}</select></label>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => { const next = new Map(selected); for (const rack of shown) if (!rack.reason && !next.has(rack.id)) next.set(rack.id, category || rack.suggested_category || ""); choose(next); }}>{t("starterSelectShown")}</Button>
        <Button variant="outline" disabled={!category || !selected.size} onClick={() => choose(new Map([...selected.keys()].map((id) => [id, category])))}>{t("starterApplyCategory")}</Button>
        <Button variant="outline" onClick={() => choose(new Map())}>{t("productsClearSelection")}</Button>
        <Button variant="outline" onClick={reload}>{t("starterDiscardReload")}</Button>
      </div>
    </fieldset>
    {sample && <details><summary>{t("starterReferenceProducts", { category: sample.label })}</summary><ul>{sample.products.map((p) => <li key={p.sku}>{p.name} — {priceText(p.price, snapshot.currency)} {snapshot.currency}</li>)}</ul></details>}
    <div className="max-h-[35dvh] overflow-auto rounded border">
      {shown.map((rack) => <div key={rack.id} className="space-y-1 border-b p-2">
        <label><input type="checkbox" aria-label={t("starterSelectRack", { rack: rack.id })} disabled={locked || !!rack.reason} checked={selected.has(rack.id)} onChange={(e) => { const next = new Map(selected); if (e.target.checked) next.set(rack.id, category || rack.suggested_category || ""); else next.delete(rack.id); choose(next); }} /> {rack.name} · {rack.type} · {rack.id}</label>
        {rack.reason ? <p>{rack.reason}</p> : <><p>{t("starterSectionsAvailable", { count: rack.available_slots })}</p><select aria-label={t("starterCategoryFor", { rack: rack.id })} disabled={locked || !selected.has(rack.id)} className="max-w-full rounded border p-2" value={selected.get(rack.id) ?? ""} onChange={(e) => { const next = new Map(selected); next.set(rack.id, e.target.value); choose(next); }}><option value="">{t("starterChooseCategory")}</option>{options}</select></>}
      </div>)}
      {!shown.length && <p>{t("starterNoMatch")}</p>}
    </div>
    <p>{t("starterExistingSkus")}</p>
    {error && <p role="alert">{error}</p>}
    <Button disabled={locked || !selected.size} onClick={() => void check()}>{preview.isPending ? t("productsCheckingShelves") : t("starterPreview")}</Button>
    {preview.data && <section aria-label={t("starterPreviewRegion")} className="min-w-0 space-y-2 rounded border p-3">
      <p>{t("starterPreviewSummary", { racks: preview.data.racks.length, placements: preview.data.placements_added, newSkus: preview.data.new_skus, reusedSkus: preview.data.reused_skus })}</p>
      {preview.data.racks.map((rack) => <details key={rack.id}><summary>{t("starterRackSummary", { rack: rack.name, sections: rack.slots_added, placements: rack.placements_added })}</summary><ul>{rack.products.map((p) => <li key={p.sku}>{p.name} — {priceText(p.price, snapshot.currency)} {snapshot.currency} {rack.reused_skus.includes(p.sku) ? t("starterExistingValues") : t("starterReference")}</li>)}</ul></details>)}
      {prepared && !save.data && <Button disabled={busy} onClick={() => void persist()}>{save.isPending ? t("starterSaving") : save.isError ? t("starterRetrySave") : t("starterSave")}</Button>}
    </section>}
    {save.isError && <p role="alert">{save.error.message} {t("starterUncertainSave")}</p>}
    {save.data && <div role="status"><p>{t("starterSaved")}</p><Button onClick={() => { if (save.data) { useSimulationStore.getState().setSelectedSetupId(save.data.setup_id); close(); } }}>{t("starterOpen")}</Button></div>}
    <p className="text-xs">{t("starterClosing")}</p>
  </div>;
}
