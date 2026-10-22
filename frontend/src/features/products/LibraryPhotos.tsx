import { useI18n } from "@/shared/i18n/i18n";
import { UserMessageError } from "@/shared/i18n/userMessage";
import { RequestError } from "@/shared/components/RequestError";
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
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return <><Button variant="outline" onClick={() => setOpen(true)}>{t("photosTitle")}</Button>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="flex max-h-[90dvh] flex-col overflow-y-auto p-4 sm:max-w-4xl sm:p-7">
      <DialogTitle>{t("photosTitle")}</DialogTitle>
      <DialogDescription>{t("photosDescription")}</DialogDescription>
      {open && <PhotoSession key={`${pid}:${sid}`} pid={pid} sid={sid} close={() => setOpen(false)} />}
    </DialogContent></Dialog></>;
}
function PhotoSession({ pid, sid, close }: { pid: string; sid: string; close: () => void }) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [photoSearch, setPhotoSearch] = useState("");
  const [choices, setChoices] = useState(new Map<string, string>());
  const [replace, setReplace] = useState(false);
  const [prepared, setPrepared] = useState<PhotoSave | null>(null);
  const [error, setError] = useState<unknown>(null);
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
  const clear = () => { setPrepared(null); preview.reset(); save.reset(); setError(null); };
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
    if (selected.length > 100) { setError(new UserMessageError("photosTooMany")); return; }
    const assignments = selected.flatMap(([sku, aid]) => { const asset = assets.find(a => a.asset_id === aid); return asset ? [{ sku, asset_id: aid, version: asset.version }] : []; });
    if (assignments.length !== selected.length) { setError(new UserMessageError("photosMissingSelection")); return; }
    const body = { source_sha256: options.data.source_sha256, assignments, replace_existing: replace };
    pending.current = true;
    try { await preview.mutateAsync(body); setPrepared({ ...body, request_id: crypto.randomUUID().replace(/-/g, "") }); }
    catch (e) { setError(e); } finally { pending.current = false; }
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
    <p>{t("photosHelp")}</p>
    <fieldset disabled={locked || options.isError} className="min-w-0 space-y-3">
      <label className="block"><input type="checkbox" checked={replace} onChange={e => { setReplace(e.target.checked); choose(new Map()); }} />{t("photosReplace")}</label>
      <label className="block">{t("photosSearchProducts")}<input className="mt-1 block w-full rounded border p-2" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <label className="block">{t("photosSearchLibrary")}<input className="mt-1 block w-full rounded border p-2" value={photoSearch} onChange={e => setPhotoSearch(e.target.value)} /></label>
      <p>{t("photosMenuCount", { count: visibleAssets.length })}</p>
      <p>{t("photosProductCount", { shown: shown.length, selected: selected.length })}</p>
      <div className="flex flex-wrap gap-2"><Button variant="outline" onClick={suggest}>{t("photosSuggest")}</Button><Button variant="outline" onClick={() => choose(new Map())}>{t("photosClear")}</Button></div>
      <div className="max-h-[35dvh] overflow-auto rounded border">{shown.map(p => {
        const asset = assets.find(a => a.asset_id === choices.get(p.sku));
        const matches = assets.filter(a => a.sku === p.sku).length;
        const menuAssets = asset && !visibleAssets.includes(asset) ? [asset, ...visibleAssets] : visibleAssets;
        return <div key={p.sku} className="space-y-1 border-b p-2">
          <p>{p.names.join(" / ")} · {p.sku} · {t("productPlacements", { count: p.placements })} · {t(p.image_urls.length ? "photosExisting" : "photosNone")}</p>
          <label className="block">{t("photosForSku", { sku: p.sku })}<select className="block w-full min-w-0 rounded border p-2" disabled={!replace && !!p.image_urls.length} value={choices.get(p.sku) ?? ""} onChange={e => choose(new Map(choices).set(p.sku, e.target.value))}>
            <option value="">{t("photosKeep")}</option>{menuAssets.map(a => <option key={a.asset_id} value={a.asset_id}>{a.name} · {a.asset_id} · {a.sku ? t("photosLinked", { sku: a.sku }) : t("photosUnlinked")}</option>)}
          </select></label>
          {matches > 1 && <p>{t("photosAmbiguous")}</p>}
          {asset && <img className="h-20 max-w-full object-contain" src={resolveImageUrl(asset.image_url)} alt={t("photosSelectedAlt", { sku: p.sku })} />}
        </div>;
      })}</div>
    </fieldset>
    <Button variant="outline" disabled={locked} onClick={() => { choose(new Map()); void options.refetch(); }}>{t("photosReload")}</Button>
    {options.isFetching && <p role="status">{t("photosLoading")}</p>}
    {options.isError && <RequestError error={options.error} />}
    {options.data && !assets.length && <p>{t("photosEmptyLibrary")}</p>}
    {options.data && !products.length && <p>{t("photosEmptyProducts")}</p>}
    <RequestError error={error} />
    <Button disabled={locked || options.isError || !selected.length} onClick={() => void check()}>{t("photosPreview")}</Button>
    {prepared && !current && !busy && !save.data && !save.isError && <p role="alert">{t("photosStale")}</p>}
    {preview.data && prepared && (current || save.isPending || save.isError || save.data) && <section aria-label={t("photosPreviewTitle")} className="space-y-3 rounded border p-3">
      <p>{t("photosPreviewCount", { products: preview.data.changes.length, placements: preview.data.changed_placements })}</p>
      {preview.data.changes.map(p => <div key={p.sku}><p>{p.names.join(" / ")} · {p.sku}: {p.asset_name}</p><div className="flex flex-wrap gap-3"><div>{t("productBefore")}{p.image_urls.length ? p.image_urls.map(url => <img key={url} className="h-24 max-w-full object-contain" src={resolveImageUrl(url)} alt={t("photosCurrentAlt", { sku: p.sku })} />) : <p>{t("productNoImage")}</p>}</div><div>{t("productAfter")}<img className="h-24 max-w-full object-contain" src={resolveImageUrl(p.image_url)} alt={t("photosSavedAlt", { sku: p.sku })} /></div></div></div>)}
      {!save.data && <Button disabled={busy} onClick={() => void persist()}>{t(save.isPending ? "photosSaving" : save.isError ? "photosRetrySave" : "photosSave")}</Button>}
    </section>}
    {save.isError && <RequestError error={save.error}><p>{t("photosSaveUncertain")}</p></RequestError>}
    {save.data && <div role="status"><p>{t("photosSaved")}</p><Button onClick={() => { if (save.data) { useSimulationStore.getState().setSelectedSetupId(save.data.setup_id); close(); } }}>{t("photosOpen")}</Button></div>}
    <p className="text-xs">{t("photosLimits")}</p>
  </div>;
}
