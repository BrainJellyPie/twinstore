import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/shared/components/ui/dialog";
import { libraryPhotosOptions } from "@/services/queries/libraryPhotos";
import { libraryPhotosPreview, libraryPhotosSave } from "@/services/mutations/libraryPhotos";
import type { PhotoSave } from "@/shared/api/libraryPhotos";
import { resolveImageUrl } from "@/shared/api/images";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";

export function LibraryPhotos({ pid, sid }: { pid: string; sid: string }) {
  const [open, setOpen] = useState(false);
  return <><Button variant="outline" onClick={() => setOpen(true)}>Use library photos</Button>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="flex max-h-[90dvh] flex-col overflow-y-auto p-4 sm:max-w-4xl sm:p-7">
      <DialogTitle>Use library photos</DialogTitle>
      <DialogDescription>Connect uploaded packshots to shelf products and save a separate layout.</DialogDescription>
      {open && <PhotoSession key={`${pid}:${sid}`} pid={pid} sid={sid} close={() => setOpen(false)} />}
    </DialogContent></Dialog></>;
}
function PhotoSession({ pid, sid, close }: { pid: string; sid: string; close: () => void }) {
  const [search, setSearch] = useState("");
  const [photoSearch, setPhotoSearch] = useState("");
  const [choices, setChoices] = useState(new Map<string, string>());
  const [replace, setReplace] = useState(false);
  const [prepared, setPrepared] = useState<PhotoSave | null>(null);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const options = useQuery(libraryPhotosOptions(pid, sid));
  const preview = useMutation(libraryPhotosPreview(pid, sid));
  const save = useMutation(libraryPhotosSave(pid, sid));
  const qc = useQueryClient();
  const busy = options.isFetching || preview.isPending || save.isPending;
  const locked = busy || !!save.data;
  const assets = options.data?.assets ?? [];
  const products = options.data?.products ?? [];
  const visibleAssets = assets.filter(a => `${a.name} ${a.sku} ${a.asset_id}`.toLocaleLowerCase().includes(photoSearch.toLocaleLowerCase())).slice(0, 100);
  const shown = products.filter(p => `${p.sku} ${p.names.join(" ")}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).slice(0, 100);
  const selected = [...choices.entries()].filter(([, aid]) => aid);
  const current = !options.isError && prepared?.source_sha256 === options.data?.source_sha256 && prepared?.assignments.every(a => assets.some(asset => asset.asset_id === a.asset_id && asset.version === a.version));
  const clear = () => { setPrepared(null); preview.reset(); save.reset(); setError(""); };
  const choose = (next: Map<string, string>) => { setChoices(next); clear(); };
  const suggest = () => {
    const next = new Map(choices);
    for (const p of shown) {
      const matches = assets.filter(a => a.sku === p.sku);
      if (matches.length === 1 && (replace || !p.image_urls.length)) next.set(p.sku, matches[0]!.asset_id);
    }
    choose(next);
  };
  const check = async () => {
    if (pending.current || !options.data || options.isError || !selected.length) return;
    clear();
    if (selected.length > 100) { setError("Choose at most 100 products per batch."); return; }
    const assignments = selected.flatMap(([sku, aid]) => { const asset = assets.find(a => a.asset_id === aid); return asset ? [{ sku, asset_id: aid, version: asset.version }] : []; });
    if (assignments.length !== selected.length) { setError("A selected photo disappeared. Reload the library."); return; }
    const body = { source_sha256: options.data.source_sha256, assignments, replace_existing: replace };
    pending.current = true;
    try { await preview.mutateAsync(body); setPrepared({ ...body, request_id: crypto.randomUUID().replace(/-/g, "") }); }
    catch (e) { setError((e as Error).message); } finally { pending.current = false; }
  };
  const persist = async () => {
    if (pending.current || !prepared || (!current && !save.isError)) return;
    pending.current = true;
    try {
      await save.mutateAsync(prepared);
      void qc.invalidateQueries({ queryKey: queryKeys.setups(pid) });
      void qc.invalidateQueries({ queryKey: queryKeys.project(pid), exact: true });
    } catch { /* Keep the request identity when acknowledgement is uncertain. */ }
    finally { pending.current = false; }
  };
  return <div className="min-w-0 space-y-3 [overflow-wrap:anywhere] [&_button]:h-auto [&_button]:min-h-9 [&_button]:max-w-full [&_button]:whitespace-normal [&_button]:py-2">
    <p>Reuse images uploaded in Market → Products. No model runs here. Existing SKU links are suggestions to review, not verified product identification. Names, prices, positions and stock information stay unchanged.</p>
    <fieldset disabled={locked || options.isError} className="min-w-0 space-y-3">
      <label className="block"><input type="checkbox" checked={replace} onChange={e => { setReplace(e.target.checked); choose(new Map()); }} /> Allow replacing existing images in the new layout</label>
      <label className="block">Search shelf products<input className="mt-1 block w-full rounded border p-2" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <label className="block">Search library photos<input className="mt-1 block w-full rounded border p-2" value={photoSearch} onChange={e => setPhotoSearch(e.target.value)} /></label>
      <p>{visibleAssets.length} photos in each menu (up to 100), plus its selected photo. Search to find other photos.</p>
      <p>{shown.length} products shown (up to 100). {selected.length} selected across all filters.</p>
      <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={suggest}>Use unique links for shown products</Button><Button variant="outline" onClick={() => choose(new Map())}>Clear photo choices</Button></div>
      <div className="max-h-[35dvh] overflow-auto rounded border">{shown.map(p => {
        const asset = assets.find(a => a.asset_id === choices.get(p.sku));
        const matches = assets.filter(a => a.sku === p.sku).length;
        const menuAssets = asset && !visibleAssets.includes(asset) ? [asset, ...visibleAssets] : visibleAssets;
        return <div key={p.sku} className="space-y-1 border-b p-2">
          <p>{p.names.join(" / ")} · {p.sku} · {p.placements} placements{p.image_urls.length ? " · existing image" : " · no image"}</p>
          <label className="block">Photo for {p.sku}<select className="block w-full min-w-0 rounded border p-2" disabled={!replace && !!p.image_urls.length} value={choices.get(p.sku) ?? ""} onChange={e => choose(new Map(choices).set(p.sku, e.target.value))}>
            <option value="">Keep current image</option>{menuAssets.map(a => <option key={a.asset_id} value={a.asset_id}>{a.name} · {a.asset_id}{a.sku ? ` · linked to ${a.sku}` : " · unlinked"}</option>)}
          </select></label>
          {matches > 1 && <p>Multiple photos link to this SKU. Choose one explicitly.</p>}
          {asset && <img className="h-20 max-w-full object-contain" src={resolveImageUrl(asset.image_url)} alt={`Selected photo for ${p.sku}`} />}
        </div>;
      })}</div>
    </fieldset>
    <Button variant="outline" disabled={locked} onClick={() => { choose(new Map()); void options.refetch(); }}>Reload products and photos</Button>
    {options.isFetching && <p role="status">Loading products and photos…</p>}
    {options.isError && <p role="alert">{options.error.message}</p>}
    {options.data && !assets.length && <p>No library photos yet. Open Market → Products and upload packshots, then return here and reload. Optional pack reading there uses a model; this workflow does not.</p>}
    {options.data && !products.length && <p>Place products first using starter products or a reviewed shelf photo.</p>}
    {error && <p role="alert">{error}</p>}
    <Button disabled={locked || options.isError || !selected.length} onClick={() => void check()}>Preview product photos</Button>
    {prepared && !current && !busy && !save.data && !save.isError && <p role="alert">Products or photos changed. Preview again before saving.</p>}
    {preview.data && prepared && (current || save.isPending || save.isError || save.data) && <section aria-label="Product photo preview" className="space-y-3 rounded border p-3">
      <p>{preview.data.changes.length} products · {preview.data.changed_placements} placements. Only the new layout gets these images.</p>
      {preview.data.changes.map(p => <div key={p.sku}><p>{p.names.join(" / ")} · {p.sku}: {p.asset_name}</p><div className="flex flex-wrap gap-3"><div>Before{p.image_urls.length ? p.image_urls.map(url => <img key={url} className="h-24 max-w-full object-contain" src={resolveImageUrl(url)} alt={`Current photo for ${p.sku}`} />) : <p>No image</p>}</div><div>After<img className="h-24 max-w-full object-contain" src={resolveImageUrl(p.image_url)} alt={`Saved photo for ${p.sku}`} /></div></div></div>)}
      {!save.data && <Button disabled={busy} onClick={() => void persist()}>{save.isPending ? "Saving photos…" : save.isError ? "Retry saving photo layout" : "Save layout with photos"}</Button>}
    </section>}
    {save.isError && <p role="alert">{save.error.message} The save may have completed. Retry the same request or check Layouts.</p>}
    {save.data && <div role="status"><p>Photo layout saved. Original layout and library images are preserved.</p><Button onClick={() => { if (save.data) { useSimulationStore.getState().setSelectedSetupId(save.data.setup_id); close(); } }}>Open photo layout</Button></div>}
    <p className="text-xs">Saved photos survive library deletion. Return to the original layout to undo. Closing discards unsaved choices; an accepted save may finish after closing. Up to 500 library photos and 100 selected SKUs; 64 MB per batch.</p>
  </div>;
}
