import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import { productCatalog } from "@/services/queries/productEdits";
import { productPreview, productSave } from "@/services/mutations/productEdits";
import type { ProductCatalog, ProductEditsSave, ProductRow } from "@/shared/api/productEdits";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { draftEdits, priceText, type RowDraft } from "./productDrafts";

export function ProductBulkEditor({ pid, sid }: { pid: string; sid: string }) {
  const [open, setOpen] = useState(false);
  return <>
    <Button variant="outline" onClick={() => setOpen(true)}>Edit products together</Button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="flex max-h-[90dvh] flex-col overflow-y-auto sm:max-w-5xl">
        <DialogTitle>Edit products together</DialogTitle>
        <DialogDescription>Search placed products, review changes and save a new layout. The original stays unchanged.</DialogDescription>
        {open && <ProductSession key={`${pid}:${sid}`} pid={pid} sid={sid} onClose={() => setOpen(false)} />}
      </DialogContent>
    </Dialog>
  </>;
}
function ProductSession({ pid, sid, onClose }: { pid: string; sid: string; onClose: () => void }) {
  const catalog = useQuery(productCatalog(pid, sid));
  const [reload, setReload] = useState(0);
  const [reloading, setReloading] = useState(false);
  const reloadProducts = () => {
    setReloading(true);
    void catalog.refetch().then((result) => { if (result.isSuccess) setReload((v) => v + 1); }).finally(() => setReloading(false));
  };
  return <>
    {catalog.isError && <p role="alert">{catalog.error.message}<Button disabled={reloading} onClick={reloadProducts}>{catalog.data ? "Discard edits and retry products" : "Retry products"}</Button></p>}
    {!catalog.data && !catalog.isError && <div role="status">Loading current products…</div>}
    {catalog.data && <ProductForm key={reload} pid={pid} sid={sid} initial={catalog.data} refreshing={reloading} onClose={onClose} onReload={reloadProducts} />}
  </>;
}
function ProductForm({ pid, sid, initial, refreshing, onReload, onClose }: {
  pid: string; sid: string; initial: ProductCatalog; refreshing: boolean; onReload: () => void; onClose: () => void;
}) {
  const [snapshot] = useState(initial);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(new Set<string>());
  const [drafts, setDrafts] = useState(new Map<string, RowDraft>());
  const [history, setHistory] = useState<Map<string, RowDraft>[]>([]);
  const [bulkPrice, setBulkPrice] = useState("");
  const [bulkPromo, setBulkPromo] = useState("");
  const [error, setError] = useState("");
  const [prepared, setPrepared] = useState<ProductEditsSave | null>(null);
  const busyRef = useRef(false);
  const preview = useMutation(productPreview(pid, sid));
  const save = useMutation(productSave(pid, sid));
  const qc = useQueryClient();
  const busy = preview.isPending || save.isPending;
  const locked = busy || !!save.data || refreshing;
  const filtered = snapshot.products.filter((row) => [row.sku, ...row.names, ...row.racks].some((v) => v.toLocaleLowerCase().includes(search.toLocaleLowerCase())));
  const shown = filtered.slice(0, 100);
  const editable = (row: ProductRow) => !!row.sku.trim() && row.sku.length <= 200;
  const clearPreview = () => { preview.reset(); save.reset(); setPrepared(null); setError(""); };
  const change = (next: Map<string, RowDraft>) => {
    setHistory((old) => [...old.slice(-19), drafts]);
    setDrafts(next); clearPreview();
  };
  const patch = (sku: string, value: RowDraft) => {
    const next = new Map(drafts); next.set(sku, { ...next.get(sku), ...value }); change(next);
  };
  const bulk = (value: RowDraft) => {
    const next = new Map(drafts);
    for (const sku of selected) next.set(sku, { ...next.get(sku), ...value });
    try { draftEdits(next, snapshot.currency); change(next); } catch (e) { setError((e as Error).message); }
  };
  const check = async () => {
    if (busyRef.current) return;
    clearPreview();
    try {
      const edits = draftEdits(drafts, snapshot.currency);
      if (!edits.length) throw new Error("Change at least one product field first.");
      const body = { source_sha256: snapshot.source_sha256, currency: snapshot.currency, edits };
      busyRef.current = true;
      const report = await preview.mutateAsync(body);
      if (report.changes.length) setPrepared({ ...body, request_id: crypto.randomUUID().replace(/-/g, "") });
    } catch (e) { setError((e as Error).message); } finally { busyRef.current = false; }
  };
  const persist = async () => {
    if (!prepared || busyRef.current) return;
    busyRef.current = true;
    try {
      await save.mutateAsync(prepared);
      void qc.invalidateQueries({ queryKey: queryKeys.setups(pid) });
      void qc.invalidateQueries({ queryKey: queryKeys.project(pid), exact: true });
    } catch { /* Keep the identical request for an uncertain-save retry. */ }
    finally { busyRef.current = false; }
  };
  const variants = (items: string[]) => items.slice(0, 5).join(" | ") + (items.length > 5 ? ` | … (${items.length} variants)` : "");
  const values = (row: ProductRow) => `${variants(row.names)} · ${variants(row.prices.map((n) => priceText(n, snapshot.currency)))} ${snapshot.currency} · ${variants(row.promos.map((p) => p || "(no promotion)"))}`;
  return <div className="min-w-0 space-y-3">
    <p>All placements of an exact SKU change together, including placements hidden by search. Mixed values are shown separately. SKU, positions, images and regular prices stay unchanged. Enter your own prices; template prices are examples.</p>
    <label className="block">Search products or racks<input className="ml-2 rounded border p-2" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
    <p>{shown.length} of {filtered.length} matches shown (up to 100). {selected.size} selected across all filters. {drafts.size} SKUs edited.</p>
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" disabled={locked} onClick={() => setSelected(new Set([...selected, ...shown.filter(editable).map((r) => r.sku)]))}>Select shown</Button>
      <Button variant="outline" disabled={locked} onClick={() => setSelected(new Set())}>Clear selection</Button>
      <Button variant="outline" disabled={locked || !history.length} onClick={() => { const last = history[history.length - 1]; if (last) { setDrafts(last); setHistory(history.slice(0, -1)); clearPreview(); } }}>Undo last edit</Button>
      <Button variant="outline" disabled={locked || !drafts.size} onClick={() => change(new Map())}>Reset unsaved edits</Button>
      <Button variant="outline" disabled={locked} onClick={onReload}>Discard edits and reload products</Button>
    </div>
    <fieldset disabled={locked} className="flex flex-wrap items-end gap-2 rounded border p-3">
      <legend>Apply to selected SKUs</legend>
      <label>Price ({snapshot.currency})<input aria-label="Selected product price" inputMode="decimal" maxLength={100} className="block rounded border p-2" value={bulkPrice} onChange={(e) => setBulkPrice(e.target.value)} /></label>
      <Button variant="outline" disabled={!selected.size} onClick={() => bulk({ price: bulkPrice })}>Set selected prices</Button>
      <label>Promotion<input aria-label="Selected product promotion" maxLength={200} className="block rounded border p-2" value={bulkPromo} onChange={(e) => setBulkPromo(e.target.value)} /></label>
      <Button variant="outline" disabled={!selected.size} onClick={() => bulk({ promo: bulkPromo })}>Set selected promotions</Button>
      <span>Empty promotion clears it. Prices round to the currency minor unit.</span>
    </fieldset>
    <div className="max-h-[40dvh] overflow-auto rounded border">
      <table className="w-full text-left text-sm"><thead><tr><th>Select / SKU</th><th>Name</th><th>Price ({snapshot.currency})</th><th>Promotion</th><th>Placements</th></tr></thead><tbody>
        {shown.map((row) => { const draft = drafts.get(row.sku); return <tr key={row.sku} className="border-t align-top">
          <td className="p-2"><label><input type="checkbox" aria-label={`Select ${row.sku}`} disabled={locked || !editable(row)} checked={selected.has(row.sku)} onChange={(e) => { const next = new Set(selected); if (e.target.checked) next.add(row.sku); else next.delete(row.sku); setSelected(next); }} /> {row.sku || "Missing SKU"}</label></td>
          <td className="p-2"><input aria-label={`Name for ${row.sku}`} disabled={locked || !editable(row)} maxLength={200} className="w-44 rounded border p-1" value={draft?.name ?? (row.names.length === 1 ? row.names[0] : "")} placeholder="Mixed names — unchanged" onChange={(e) => patch(row.sku, { name: e.target.value })} /><p className="max-w-52 break-words text-xs">{row.names.slice(0, 5).join(" | ")}</p></td>
          <td className="p-2"><input aria-label={`Price for ${row.sku}`} disabled={locked || !editable(row)} inputMode="decimal" maxLength={100} className="w-32 rounded border p-1" value={draft?.price ?? (row.prices.length === 1 ? priceText(row.prices[0]!, snapshot.currency) : "")} placeholder="Mixed — unchanged" onChange={(e) => patch(row.sku, { price: e.target.value })} /><p className="text-xs">{row.prices.slice(0, 5).map((n) => priceText(n, snapshot.currency)).join(" | ")}</p></td>
          <td className="p-2"><input aria-label={`Promotion for ${row.sku}`} disabled={locked || !editable(row)} maxLength={200} className="w-36 rounded border p-1" value={draft?.promo ?? (row.promos.length === 1 ? row.promos[0] : "")} placeholder="Mixed — unchanged" onChange={(e) => patch(row.sku, { promo: e.target.value })} /></td>
          <td className="p-2">{row.placements}<p className="max-w-40 break-words text-xs">{row.racks.slice(0, 5).join(", ")}</p></td>
        </tr>; })}
      </tbody></table>
      {!shown.length && <p>No matching products. Create stocked shelves or change your search.</p>}
    </div>
    {error && <p role="alert">{error}</p>}
    <Button disabled={locked || !drafts.size} onClick={() => void check()}>{preview.isPending ? "Checking changes…" : "Preview product changes"}</Button>
    {preview.data && <section aria-label="Product change preview" className="space-y-2 rounded border p-3">
      <p>{preview.data.changes.length} SKUs / {preview.data.changed_placements} placements will change. Zero changes do not create a draft.</p>
      <ul className="max-h-56 overflow-auto">{preview.data.changes.map((c) => <li key={c.before.sku} className="break-words border-b p-2"><strong>{c.before.sku}</strong><p>Before: {values(c.before)}</p><p>After: {values(c.after)}</p></li>)}</ul>
      {prepared && !save.data && <Button disabled={busy || refreshing} onClick={() => void persist()}>{save.isPending ? "Saving product draft…" : save.isError ? "Retry saving product draft" : "Save as new product draft"}</Button>}
    </section>}
    {save.isError && <p role="alert">{save.error.message} An uncertain save may have completed. Retry the same save before changing edits, or check Layouts after leaving.</p>}
    {save.data && <div role="status"><p>Product draft saved. The original layout is unchanged; return to it from Layouts to undo the saved variant.</p><Button onClick={() => { if (save.data) { useSimulationStore.getState().setSelectedSetupId(save.data.setup_id); onClose(); } }}>Open edited layout</Button></div>}
    <p className="text-xs">Undo keeps the last 20 local edits. Closing discards unsaved inputs; an accepted save can finish after you leave. No model is called.</p>
  </div>;
}
