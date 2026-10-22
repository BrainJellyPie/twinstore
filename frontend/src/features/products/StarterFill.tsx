import { useI18n } from "@/shared/i18n/i18n";
import { UserMessageError } from "@/shared/i18n/userMessage";
import { RequestError } from "@/shared/components/RequestError";
import { formatMoney } from "@/shared/utils/money";
import { searchText } from "@/shared/utils/searchText";
import { fixtureLabel, fixtureSearchLabels } from "./rackCopyLabels";
import { starterCategoryLabel } from "@/shared/i18n/catalogCategories";
import { starterRackReason } from "./starterRackReason";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import { starterCatalog } from "@/services/queries/starterFill";
import { starterPreview, starterSave } from "@/services/mutations/starterFill";
import type { StarterCatalog, StarterSave } from "@/shared/api/starterFill";
import { autoSelectStarterProducts } from "@/shared/api/starterFill";
import { resolveImageUrl } from "@/shared/api/images";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";

export function StarterFill({ pid, sid }: { pid: string; sid: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return <>
    <Button variant="outline" onClick={() => setOpen(true)}>{t("starterEntry")}</Button>
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
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [revision, setRevision] = useState(0);
  const [reloading, setReloading] = useState(false);
  const reload = () => {
    setReloading(true);
    void catalog.refetch().then((result) => { if (result.isSuccess) setRevision((n) => n + 1); }).finally(() => setReloading(false));
  };
  return <>
    {catalog.isError && <RequestError error={catalog.error}><Button className="h-auto min-h-9 max-w-full whitespace-normal py-2" disabled={reloading} onClick={reload}>{t(catalog.data ? "starterDiscardRetry" : "starterRetry")}</Button></RequestError>}
    {!catalog.data && !catalog.isError && <p role="status">{t("starterLoading")}</p>}
    {catalog.data && <StarterForm key={revision} pid={pid} sid={sid} initial={catalog.data} refreshing={reloading} reload={reload} close={close} mode={mode} setMode={setMode} />}
  </>;
}
function StarterForm({ pid, sid, initial, refreshing, reload, close, mode, setMode }: {
  pid: string; sid: string; initial: StarterCatalog; refreshing: boolean; reload: () => void; close: () => void;
  mode: "auto" | "manual"; setMode: (mode: "auto" | "manual") => void;
}) {
  const { t, locale } = useI18n();
  const [snapshot] = useState(initial);
  const [requirements, setRequirements] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [perSlot, setPerSlot] = useState(2);
  const [selected, setSelected] = useState(new Map<string, string>());
  const [error, setError] = useState<unknown>(null);
  const [prepared, setPrepared] = useState<StarterSave | null>(null);
  const pending = useRef(false);
  const live = useRef(false);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  const preview = useMutation(starterPreview(pid, sid));
  const save = useMutation(starterSave(pid, sid));
  const auto = useMutation({ mutationFn: () => autoSelectStarterProducts(pid, sid, {
    source_sha256: snapshot.source_sha256, currency: snapshot.currency, requirements: requirements.trim(), products_per_slot: perSlot,
  }) });
  const qc = useQueryClient();
  const busy = preview.isPending || save.isPending || auto.isPending || refreshing;
  const locked = busy || !!save.data;
  const eligibleCount = snapshot.racks.filter((r) => !r.reason && r.available_slots > 0).length;
  const terms = searchText(search).split(" ").filter(Boolean);
  const shown = snapshot.racks.filter(r => {
    const text = searchText(`${r.name} ${r.id} ${r.type} ${fixtureSearchLabels(r.type)}`);
    return terms.every(term => text.includes(term));
  }).slice(0, 100);
  const clear = () => { setPrepared(null); preview.reset(); save.reset(); setError(null); };
  const choose = (next: Map<string, string>) => { setSelected(next); clear(); };
  const automatic = async () => {
    if (pending.current) return;
    clear();
    pending.current = true;
    try {
      const body = await auto.mutateAsync();
      if (!live.current) return;
      await preview.mutateAsync(body);
      if (!live.current) return;
      setPrepared({ ...body, request_id: crypto.randomUUID().replace(/-/g, "") });
    } catch (e) { setError(e); }
    finally { pending.current = false; }
  };
  const check = async () => {
    if (pending.current) return;
    clear();
    if (!selected.size || selected.size > 100) { setError(new UserMessageError("starterChooseRacks")); return; }
    if ([...selected.values()].some((key) => !key)) { setError(new UserMessageError("starterChooseCategoryEach")); return; }
    const body = { source_sha256: snapshot.source_sha256, currency: snapshot.currency, products_per_slot: perSlot,
      assignments: [...selected].map(([rack_id, value]) => ({ rack_id, category: value })) };
    pending.current = true;
    try {
      await preview.mutateAsync(body);
      setPrepared({ ...body, request_id: crypto.randomUUID().replace(/-/g, "") });
    } catch (e) { setError(e); } finally { pending.current = false; }
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
  const options = snapshot.categories.map((c) => <option key={c.key} value={c.key}>{t("starterCategoryOption", { category: starterCategoryLabel(c.key, c.label, locale), count: c.products.length })}</option>);
  const sample = snapshot.categories.find((c) => c.key === category);
  return <div className="min-w-0 space-y-3 [overflow-wrap:anywhere] [&_button]:h-auto [&_button]:min-h-9 [&_button]:max-w-full [&_button]:whitespace-normal [&_button]:py-2">
    <p>{t("starterExamples", { editor: t("bulkTitle") })}</p>
    <p>{t("starterEligible")}</p>
    <fieldset disabled={locked} className="flex flex-wrap gap-4 rounded border p-3">
      <legend>{t("starterSelection")}</legend>
      <label><input type="radio" name="starter-mode" checked={mode === "auto"} onChange={() => { setMode("auto"); clear(); }} /> {t("starterAutoMode")}</label>
      <label><input type="radio" name="starter-mode" checked={mode === "manual"} onChange={() => { setMode("manual"); clear(); }} /> {t("starterManualMode")}</label>
    </fieldset>
    {mode === "auto" && <section className="space-y-3 rounded border p-3" aria-label={t("starterAutoRegion")}>
      <p>{t("starterAutoHelp")}</p>
      <label className="block">{t("starterRequirements")}<textarea disabled={locked} value={requirements} onChange={(e) => { setRequirements(Array.from(e.target.value).slice(0, 2000).join("")); clear(); }} className="mt-1 block w-full rounded border p-2" placeholder={t("starterRequirementsHint")} /></label>
      <label className="block">{t("starterPerSection")}<select disabled={locked} className="mt-1 block w-full rounded border p-2" value={perSlot} onChange={(e) => { setPerSlot(Number(e.target.value)); clear(); }}>{[1, 2, 3, 4].map((n) => <option key={n}>{n}</option>)}</select></label>
      <p>{t("starterAvailable", { count: eligibleCount })}</p>
      <Button disabled={locked || eligibleCount < 1 || eligibleCount > 100} onClick={() => void automatic()}>{t(auto.isPending ? "starterChoosing" : preview.isPending ? "copyChecking" : "starterAutoPreview")}</Button>
      <Button variant="outline" disabled={locked} onClick={reload}>{t("starterReload")}</Button>
      {!!error && <p>{t("starterAutoFallback")}</p>}
    </section>}
    {mode === "manual" && <>
    <label className="block">{t("starterSearch")}<input className="mt-1 block w-full min-w-0 max-w-full rounded border p-2" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
    <p>{t("starterShown", { shown: shown.length, selected: selected.size })}</p>
    <fieldset disabled={locked} className="min-w-0 space-y-2 rounded border p-3">
      <legend>{t("starterAssortment")}</legend>
      <label className="block">{t("starterCategoryToApply")}<select className="mt-1 block w-full min-w-0 max-w-full rounded border p-2" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">{t("starterChooseCategory")}</option>{options}</select></label>
      <label className="block">{t("starterPerSection")}<select className="mt-1 block w-full min-w-0 rounded border p-2" value={perSlot} onChange={(e) => { setPerSlot(Number(e.target.value)); clear(); }}>{[1, 2, 3, 4].map((n) => <option key={n}>{n}</option>)}</select></label>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => { const next = new Map(selected); for (const rack of shown) if (!rack.reason && !next.has(rack.id)) next.set(rack.id, category || rack.suggested_category || ""); choose(next); }}>{t("starterSelectShown")}</Button>
        <Button variant="outline" disabled={!category || !selected.size} onClick={() => choose(new Map([...selected.keys()].map((id) => [id, category])))}>{t("starterApplyCategory")}</Button>
        <Button variant="outline" onClick={() => choose(new Map())}>{t("productClearSelection")}</Button>
        <Button variant="outline" onClick={reload}>{t("starterDiscardReload")}</Button>
      </div>
    </fieldset>
    {sample && <details><summary>{t("starterReferenceProducts", { category: starterCategoryLabel(sample.key, sample.label, locale) })}</summary><ul>{sample.products.map((p) => <li key={p.sku}>{p.name} — {formatMoney(p.price, snapshot.currency, { locale })}</li>)}</ul></details>}
    <div className="max-h-[35dvh] overflow-auto rounded border">
      {shown.map((rack) => <div key={rack.id} className="space-y-1 border-b p-2">
        <label><input type="checkbox" aria-label={t("starterSelectRack", { rack: rack.id })} disabled={locked || !!rack.reason} checked={selected.has(rack.id)} onChange={(e) => { const next = new Map(selected); if (e.target.checked) next.set(rack.id, category || rack.suggested_category || ""); else next.delete(rack.id); choose(next); }} /> {rack.name} · {fixtureLabel(rack.type, locale)} · {rack.id}</label>
        {rack.reason ? <p>{starterRackReason(rack, locale)}</p> : <><p>{t("starterSectionsAvailable", { count: rack.available_slots })}</p><select aria-label={t("starterCategoryFor", { rack: rack.id })} disabled={locked || !selected.has(rack.id)} className="max-w-full rounded border p-2" value={selected.get(rack.id) ?? ""} onChange={(e) => { const next = new Map(selected); next.set(rack.id, e.target.value); choose(next); }}><option value="">{t("starterChooseCategory")}</option>{options}</select></>}
      </div>)}
      {!shown.length && <p>{t("starterNoMatch")}</p>}
    </div>
    <p>{t("starterExistingSkus")}</p>
    <Button disabled={locked || !selected.size} onClick={() => void check()}>{t(preview.isPending ? "copyChecking" : "starterPreview")}</Button>
    </>}
    <RequestError error={error} />
    {preview.data && <section aria-label={t("starterPreviewRegion")} className="min-w-0 space-y-2 rounded border p-3">
      <p>{t("starterPreviewSummary", { racks: preview.data.racks.length, placements: preview.data.placements_added, newSkus: preview.data.new_skus, reusedSkus: preview.data.reused_skus })}</p>
      {preview.data.racks.map((rack) => <details key={rack.id}><summary>{t("starterRackSummary", { rack: rack.name, sections: rack.slots_added, placements: rack.placements_added })}</summary><ul>{rack.products.map((p) => <li className="flex items-center gap-2 py-1" key={p.sku}>{p.image_url && <img className="size-14 shrink-0 rounded border object-contain" loading="lazy" src={resolveImageUrl(p.image_url)} alt={p.name} />}<span>{p.name} — {formatMoney(p.price, snapshot.currency, { locale })} {t(rack.reused_skus.includes(p.sku) ? "starterExistingValues" : "starterReference")}</span></li>)}</ul></details>)}
      {prepared && !save.data && <Button disabled={busy} onClick={() => void persist()}>{t(save.isPending ? "starterSaving" : save.isError ? "starterRetrySave" : "starterSave")}</Button>}
    </section>}
    {save.isError && <RequestError error={save.error}><p>{t("copyUncertain")}</p></RequestError>}
    {save.data && <div role="status"><p>{t("starterSaved")}</p><Button onClick={() => { if (save.data) { useSimulationStore.getState().setSelectedSetupId(save.data.setup_id); close(); } }}>{t("starterOpen")}</Button></div>}
    <p className="text-xs">{t("starterAutoClosing")}</p>
  </div>;
}
