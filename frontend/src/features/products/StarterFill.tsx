import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import { starterCatalog } from "@/services/queries/starterFill";
import { starterPreview, starterSave } from "@/services/mutations/starterFill";
import type { StarterCatalog, StarterSave } from "@/shared/api/starterFill";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { priceText } from "./productDrafts";

export function StarterFill({ pid, sid }: { pid: string; sid: string }) {
  const [open, setOpen] = useState(false);
  return <>
    <Button variant="outline" onClick={() => setOpen(true)}>Fill empty shelves</Button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="flex max-h-[90dvh] flex-col overflow-y-auto p-4 sm:max-w-4xl sm:p-7">
        <DialogTitle>Fill empty shelves</DialogTitle>
        <DialogDescription>Place starter products on existing empty shelves and fridges. Review first, then save a new layout.</DialogDescription>
        {open && <StarterSession key={`${pid}:${sid}`} pid={pid} sid={sid} close={() => setOpen(false)} />}
      </DialogContent>
    </Dialog>
  </>;
}
function StarterSession({ pid, sid, close }: { pid: string; sid: string; close: () => void }) {
  const catalog = useQuery(starterCatalog(pid, sid));
  const [revision, setRevision] = useState(0);
  const [reloading, setReloading] = useState(false);
  const reload = () => {
    setReloading(true);
    void catalog.refetch().then((result) => { if (result.isSuccess) setRevision((n) => n + 1); }).finally(() => setReloading(false));
  };
  return <>
    {catalog.isError && <p role="alert">{catalog.error.message}<Button className="h-auto min-h-9 max-w-full whitespace-normal py-2" disabled={reloading} onClick={reload}>{catalog.data ? "Discard choices and retry" : "Retry starter options"}</Button></p>}
    {!catalog.data && !catalog.isError && <p role="status">Loading starter options…</p>}
    {catalog.data && <StarterForm key={revision} pid={pid} sid={sid} initial={catalog.data} refreshing={reloading} reload={reload} close={close} />}
  </>;
}
function StarterForm({ pid, sid, initial, refreshing, reload, close }: {
  pid: string; sid: string; initial: StarterCatalog; refreshing: boolean; reload: () => void; close: () => void;
}) {
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
    if (!selected.size || selected.size > 100) { setError("Choose 1–100 empty racks."); return; }
    if ([...selected.values()].some((key) => !key)) { setError("Choose a category for every selected rack."); return; }
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
  const options = snapshot.categories.map((c) => <option key={c.key} value={c.key}>{c.label} ({c.products.length} products)</option>);
  const sample = snapshot.categories.find((c) => c.key === category);
  return <div className="min-w-0 space-y-3 [overflow-wrap:anywhere] [&_button]:h-auto [&_button]:min-h-9 [&_button]:max-w-full [&_button]:whitespace-normal [&_button]:py-2">
    <p>Generic products and reference prices are examples, not your actual stock or shelf prices. KRW/JPY references use fixed illustrative conversions, not live FX. Review prices after saving in Edit products together.</p>
    <p>Only completely empty racks are eligible. Geometry, signs, stocked racks and images stay unchanged. Each accessible, unlocked face receives products on four levels. Tables and checkout counters are excluded.</p>
    <label className="block">Search shelves<input className="mt-1 block w-full min-w-0 max-w-full rounded border p-2" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
    <p>{shown.length} racks shown (up to 100). {selected.size} selected across all filters.</p>
    <fieldset disabled={locked} className="min-w-0 space-y-2 rounded border p-3">
      <legend>Starter assortment</legend>
      <label className="block">Category to apply<select className="mt-1 block w-full min-w-0 max-w-full rounded border p-2" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">Choose a category</option>{options}</select></label>
      <label className="block">Products per shelf section<select className="mt-1 block w-full min-w-0 rounded border p-2" value={perSlot} onChange={(e) => { setPerSlot(Number(e.target.value)); clear(); }}>{[1, 2, 3, 4].map((n) => <option key={n}>{n}</option>)}</select></label>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => { const next = new Map(selected); for (const rack of shown) if (!rack.reason && !next.has(rack.id)) next.set(rack.id, category || rack.suggested_category || ""); choose(next); }}>Select shown empty racks</Button>
        <Button variant="outline" disabled={!category || !selected.size} onClick={() => choose(new Map([...selected.keys()].map((id) => [id, category])))}>Apply category to selected racks</Button>
        <Button variant="outline" onClick={() => choose(new Map())}>Clear selection</Button>
        <Button variant="outline" onClick={reload}>Discard choices and reload</Button>
      </div>
    </fieldset>
    {sample && <details><summary>Reference products in {sample.label}</summary><ul>{sample.products.map((p) => <li key={p.sku}>{p.name} — {priceText(p.price, snapshot.currency)} {snapshot.currency}</li>)}</ul></details>}
    <div className="max-h-[35dvh] overflow-auto rounded border">
      {shown.map((rack) => <div key={rack.id} className="space-y-1 border-b p-2">
        <label><input type="checkbox" aria-label={`Select rack ${rack.id}`} disabled={locked || !!rack.reason} checked={selected.has(rack.id)} onChange={(e) => { const next = new Map(selected); if (e.target.checked) next.set(rack.id, category || rack.suggested_category || ""); else next.delete(rack.id); choose(next); }} /> {rack.name} · {rack.type} · {rack.id}</label>
        {rack.reason ? <p>{rack.reason}</p> : <><p>{rack.available_slots} shelf sections available.</p><select aria-label={`Category for ${rack.id}`} disabled={locked || !selected.has(rack.id)} className="max-w-full rounded border p-2" value={selected.get(rack.id) ?? ""} onChange={(e) => { const next = new Map(selected); next.set(rack.id, e.target.value); choose(next); }}><option value="">Choose a category</option>{options}</select></>}
      </div>)}
      {!shown.length && <p>No matching shelves. Add shelves or fridges and an entrance in Step 1, or change the search.</p>}
    </div>
    <p>Existing exact SKUs reuse their current names, prices and images. Mixed existing values must be resolved first. Matching names alone never merge products.</p>
    {error && <p role="alert">{error}</p>}
    <Button disabled={locked || !selected.size} onClick={() => void check()}>{preview.isPending ? "Checking shelves…" : "Preview starter products"}</Button>
    {preview.data && <section aria-label="Starter product preview" className="min-w-0 space-y-2 rounded border p-3">
      <p>{preview.data.racks.length} racks · {preview.data.placements_added} placements · {preview.data.new_skus} new SKUs · {preview.data.reused_skus} reused SKUs.</p>
      {preview.data.racks.map((rack) => <details key={rack.id}><summary>{rack.name}: {rack.slots_added} sections, {rack.placements_added} placements — review products</summary><ul>{rack.products.map((p) => <li key={p.sku}>{p.name} — {priceText(p.price, snapshot.currency)} {snapshot.currency}{rack.reused_skus.includes(p.sku) ? " (existing SKU values)" : " (reference)"}</li>)}</ul></details>)}
      {prepared && !save.data && <Button disabled={busy} onClick={() => void persist()}>{save.isPending ? "Saving starter draft…" : save.isError ? "Retry saving starter draft" : "Save stocked layout"}</Button>}
    </section>}
    {save.isError && <p role="alert">{save.error.message} An uncertain save may have completed. Retry the same request or check Layouts before starting again.</p>}
    {save.data && <div role="status"><p>Starter draft saved. The source layout is unchanged.</p><Button onClick={() => { if (save.data) { useSimulationStore.getState().setSelectedSetupId(save.data.setup_id); close(); } }}>Open stocked layout</Button></div>}
    <p className="text-xs">Closing discards unsaved choices. An accepted save can finish after closing. Return to the original in Layouts to undo a saved variant. No model is called.</p>
  </div>;
}
