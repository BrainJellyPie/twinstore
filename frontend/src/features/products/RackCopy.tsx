import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import { rackCopyOptions } from "@/services/queries/rackCopy";
import { rackCopyPreview, rackCopySave } from "@/services/mutations/rackCopy";
import type { RackCopySave } from "@/shared/api/rackCopy";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { priceText } from "./productDrafts";

export function RackCopy({ pid, sid }: { pid: string; sid: string }) {
  const [open, setOpen] = useState(false);
  return <><Button variant="outline" onClick={() => setOpen(true)}>Reuse shelf products</Button>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="flex max-h-[90dvh] flex-col overflow-y-auto p-4 sm:max-w-4xl sm:p-7">
      <DialogTitle>Reuse shelf products</DialogTitle>
      <DialogDescription>Copy a finished assortment to compatible empty shelves, then save a new layout.</DialogDescription>
      {open && <CopySession key={`${pid}:${sid}`} pid={pid} sid={sid} close={() => setOpen(false)} />}
    </DialogContent></Dialog></>;
}
function CopySession({ pid, sid, close }: { pid: string; sid: string; close: () => void }) {
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
    if (selected.size > 100) { setError("Choose at most 100 destination racks."); return; }
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
    <p>Use products already placed in this layout. Names, prices, promotions, image links, levels and item order are copied exactly. These are placements, not physical stock quantities. No model is called.</p>
    <p>Destinations must be completely empty, the same fixture type and footprint, with every copied side accessible. N/S/E/W sides stay the same; this does not rotate an assortment or drop products to fit.</p>
    <fieldset disabled={locked} className="min-w-0 space-y-3">
      <label className="block">Copy products from<select className="mt-1 block w-full min-w-0 rounded border p-2" value={source} onChange={e => { setSource(e.target.value); choose(new Set()); }}>
        <option value="">Choose a stocked shelf or fridge</option>
        {options.data?.sources.map(r => <option key={r.id} value={r.id} disabled={!!r.reason}>{r.name} · {r.id} · {r.placements} placements{r.reason ? ` — ${r.reason}` : ""}</option>)}
      </select></label>
      <Button variant="outline" onClick={() => { choose(new Set()); void options.refetch(); }}>Discard choices and reload shelves</Button>
      <label className="block">Search destination shelves<input className="mt-1 block w-full min-w-0 rounded border p-2" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <p>{shown.length} destinations shown (up to 100). {selected.size} selected across all filters.</p>
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={!current || !source} onClick={() => choose(new Set([...selected, ...shown.filter(r => !r.reason).map(r => r.id)]))}>Select shown compatible shelves</Button><Button variant="outline" onClick={() => choose(new Set())}>Clear selection</Button></div>
      <div className="max-h-[30dvh] overflow-auto rounded border">
        {shown.map(r => <div key={r.id} className="border-b p-2"><label><input type="checkbox" aria-label={`Copy to rack ${r.id}`} disabled={!!r.reason} checked={selected.has(r.id)} onChange={e => { const next = new Set(selected); if (e.target.checked) next.add(r.id); else next.delete(r.id); choose(next); }} /> {r.name} · {r.type} · {r.id}</label><p>{r.reason ?? `${r.placements} placements will be copied here.`}</p></div>)}
      </div>
    </fieldset>
    {options.isFetching && <p role="status">Checking shelves…</p>}
    {options.isError && <p role="alert">{options.error.message} <Button disabled={busy} onClick={() => void options.refetch()}>Retry shelves</Button></p>}
    {current && !options.data?.sources.length && <p>Place products on a shelf first using the editor, starter products or a reviewed shelf photo.</p>}
    {source && current && !targets.some(r => !r.reason) && <p>No compatible empty destination. Add a matching shelf in Step 1, or choose another source.</p>}
    {error && <p role="alert">{error}</p>}
    <Button disabled={locked || !current || !selected.size} onClick={() => void check()}>Preview shelf copies</Button>
    {prepared && !previewCurrent && !busy && !save.data && !save.isError && <p role="alert">The layout changed. Preview again before saving.</p>}
    {preview.data && prepared && (previewCurrent || save.isPending || save.isError || save.data) && <section aria-label="Shelf copy preview" className="space-y-2 rounded border p-3">
      <p>From {preview.data.source_name}: {preview.data.targets.length} destinations, {preview.data.placements_added} added placements.</p>
      <ul>{preview.data.targets.map(r => <li key={r.id}>{r.name} · {r.id}: {r.placements} placements</li>)}</ul>
      <details open><summary>Review exact products and shelf sections</summary>{preview.data.slots.map(s => <div key={`${s.block}:${s.face}:${s.level}`}><p>Block {s.block + 1} · {s.face} · level {s.level}</p><ol>{s.items.map((p, i) => <li key={i}>{p.name} · {p.sku} · {priceText(p.price, prepared.currency)} {prepared.currency}{p.regular_price ? ` · regular price ${priceText(p.regular_price, prepared.currency)} ${prepared.currency}` : ""}{p.promo ? ` · ${p.promo}` : ""}{p.image_url ? " · image retained" : " · no image"}</li>)}</ol></div>)}</details>
      {prepared && !save.data && <Button disabled={busy} onClick={() => void persist()}>{save.isPending ? "Saving shelf copies…" : save.isError ? "Retry saving shelf copies" : "Save layout with shelf copies"}</Button>}
    </section>}
    {save.isError && <p role="alert">{save.error.message} The save may have completed. Retry the same request or check Layouts before starting again.</p>}
    {save.data && <div role="status"><p>Shelf copies saved. Original and previously stocked racks are unchanged.</p><Button onClick={() => { if (save.data) { useSimulationStore.getState().setSelectedSetupId(save.data.setup_id); close(); } }}>Open copied layout</Button></div>}
    <p className="text-xs">Closing discards unsaved choices; an accepted save can finish after closing. Return to the original in Layouts to undo the saved variant.</p>
  </div>;
}
