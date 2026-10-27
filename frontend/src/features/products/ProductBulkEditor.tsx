import { useI18n } from "@/shared/i18n/i18n";
import { UserMessageError } from "@/shared/i18n/userMessage";
import { RequestError } from "@/shared/components/RequestError";
import { formatMoney } from "@/shared/utils/money";
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
import { focusOnMount } from "@/shared/utils/focusOnMount";

export function ProductBulkEditor({ pid, sid }: { pid: string; sid: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return <>
    <Button variant="outline" onClick={() => setOpen(true)}>{t("bulkTitle")}</Button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="flex max-h-[90dvh] flex-col overflow-y-auto sm:max-w-5xl">
        <DialogTitle>{t("bulkTitle")}</DialogTitle>
        <DialogDescription>{t("bulkDescription")}</DialogDescription>
        {open && <ProductSession key={`${pid}:${sid}`} pid={pid} sid={sid} onClose={() => setOpen(false)} />}
      </DialogContent>
    </Dialog>
  </>;
}
function ProductSession({ pid, sid, onClose }: { pid: string; sid: string; onClose: () => void }) {
  const { t } = useI18n();
  const catalog = useQuery(productCatalog(pid, sid));
  const [reload, setReload] = useState(0);
  const [reloading, setReloading] = useState(false);
  const reloadProducts = () => {
    setReloading(true);
    void catalog.refetch().then((result) => { if (result.isSuccess) setReload((v) => v + 1); }).finally(() => setReloading(false));
  };
  return <>
    {catalog.isError && <RequestError error={catalog.error}><Button disabled={reloading} onClick={reloadProducts}>{t(catalog.data ? "bulkDiscardRetry" : "bulkRetry")}</Button></RequestError>}
    {!catalog.data && !catalog.isError && <div role="status">{t("bulkLoading")}</div>}
    {catalog.data && <ProductForm key={reload} pid={pid} sid={sid} initial={catalog.data} refreshing={reloading} onClose={onClose} onReload={reloadProducts} />}
  </>;
}
function ProductForm({ pid, sid, initial, refreshing, onReload, onClose }: {
  pid: string; sid: string; initial: ProductCatalog; refreshing: boolean; onReload: () => void; onClose: () => void;
}) {
  const { t, locale } = useI18n();
  const [snapshot] = useState(initial);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(new Set<string>());
  const [drafts, setDrafts] = useState(new Map<string, RowDraft>());
  const [history, setHistory] = useState<Map<string, RowDraft>[]>([]);
  const [bulkPrice, setBulkPrice] = useState("");
  const [bulkPromo, setBulkPromo] = useState("");
  const [error, setError] = useState<unknown>(null);
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
  const clearPreview = () => { preview.reset(); save.reset(); setPrepared(null); setError(null); };
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
    try { draftEdits(next, snapshot.currency); change(next); } catch (e) { setError(e); }
  };
  const check = async () => {
    if (busyRef.current) return;
    clearPreview();
    try {
      const edits = draftEdits(drafts, snapshot.currency);
      if (!edits.length) throw new UserMessageError("bulkNoEdits");
      const body = { source_sha256: snapshot.source_sha256, currency: snapshot.currency, edits };
      busyRef.current = true;
      const report = await preview.mutateAsync(body);
      if (report.changes.length) setPrepared({ ...body, request_id: crypto.randomUUID().replace(/-/g, "") });
    } catch (e) { setError(e); } finally { busyRef.current = false; }
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
  const variants = (items: string[]) => items.slice(0, 5).join(" | ") + (items.length > 5 ? ` | … (${t("productVariants", { count: items.length })})` : "");
  const values = (row: ProductRow) => `${variants(row.names)} · ${variants(row.prices.map((n) => formatMoney(n, snapshot.currency, { locale })))} · ${variants(row.promos.map((p) => p || t("productNoPromo")))}`;
  return <div className="min-w-0 space-y-3 [overflow-wrap:anywhere] [&_button]:h-auto [&_button]:min-h-9 [&_button]:max-w-full [&_button]:whitespace-normal [&_button]:py-2">
    <p>{t("bulkHelp")}</p>
    <label className="block">{t("bulkSearch")}<input className="ml-2 rounded border p-2" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
    <p>{t("bulkCounts", { shown: shown.length, matches: filtered.length, selected: selected.size, edited: drafts.size })}</p>
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" disabled={locked} onClick={() => setSelected(new Set([...selected, ...shown.filter(editable).map((r) => r.sku)]))}>{t("bulkSelectShown")}</Button>
      <Button variant="outline" disabled={locked} onClick={() => setSelected(new Set())}>{t("productClearSelection")}</Button>
      <Button variant="outline" disabled={locked || !history.length} onClick={() => { const last = history[history.length - 1]; if (last) { setDrafts(last); setHistory(history.slice(0, -1)); clearPreview(); } }}>{t("bulkUndo")}</Button>
      <Button variant="outline" disabled={locked || !drafts.size} onClick={() => change(new Map())}>{t("bulkReset")}</Button>
      <Button variant="outline" disabled={locked} onClick={onReload}>{t("bulkReload")}</Button>
    </div>
    <fieldset disabled={locked} className="flex flex-wrap items-end gap-2 rounded border p-3">
      <legend>{t("bulkSelected")}</legend>
      <label>{t("productPriceCurrency", { currency: snapshot.currency })}<input aria-label={t("bulkPrice")} inputMode="decimal" maxLength={100} className="block rounded border p-2" value={bulkPrice} onChange={(e) => setBulkPrice(e.target.value)} /></label>
      <Button variant="outline" disabled={!selected.size} onClick={() => bulk({ price: bulkPrice })}>{t("bulkSetPrices")}</Button>
      <label>{t("productPromotion")}<input aria-label={t("bulkPromo")} maxLength={200} className="block rounded border p-2" value={bulkPromo} onChange={(e) => setBulkPromo(e.target.value)} /></label>
      <Button variant="outline" disabled={!selected.size} onClick={() => bulk({ promo: bulkPromo })}>{t("bulkSetPromos")}</Button>
      <span>{t("bulkPriceHint")} {t("bulkDecimalHint")}</span>
    </fieldset>
    <div role="region" aria-label={t("bulkTable")} tabIndex={0} className="max-h-[40dvh] overflow-auto rounded border">
      <table className="w-full min-w-[40rem] text-left text-sm"><thead><tr><th>{t("bulkSelectSku")}</th><th>{t("productName")}</th><th>{t("productPriceCurrency", { currency: snapshot.currency })}</th><th>{t("productPromotion")}</th><th>{t("productPlacementColumn")}</th></tr></thead><tbody>
        {shown.map((row) => { const draft = drafts.get(row.sku); return <tr key={row.sku} className="border-t align-top">
          <td className="p-2"><label><input type="checkbox" aria-label={t("productSelectSku", { sku: row.sku })} disabled={locked || !editable(row)} checked={selected.has(row.sku)} onChange={(e) => { const next = new Set(selected); if (e.target.checked) next.add(row.sku); else next.delete(row.sku); setSelected(next); }} /> {row.sku || t("productMissingSku")}</label></td>
          <td className="p-2"><input aria-label={t("productNameFor", { sku: row.sku })} disabled={locked || !editable(row)} maxLength={200} className="w-44 rounded border p-1" value={draft?.name ?? (row.names.length === 1 ? row.names[0] : "")} placeholder={t("productMixedNames")} onChange={(e) => patch(row.sku, { name: e.target.value })} /><p className="max-w-52 break-words text-xs">{row.names.slice(0, 5).join(" | ")}</p></td>
          <td className="p-2"><input aria-label={t("productPriceFor", { sku: row.sku })} disabled={locked || !editable(row)} inputMode="decimal" maxLength={100} className="w-32 rounded border p-1" value={draft?.price ?? (row.prices.length === 1 ? priceText(row.prices[0]!, snapshot.currency) : "")} placeholder={t("productMixedValues")} onChange={(e) => patch(row.sku, { price: e.target.value })} /><p className="text-xs">{row.prices.slice(0, 5).map((n) => formatMoney(n, snapshot.currency, { locale })).join(" | ")}</p></td>
          <td className="p-2"><input aria-label={t("productPromoFor", { sku: row.sku })} disabled={locked || !editable(row)} maxLength={200} className="w-36 rounded border p-1" value={draft?.promo ?? (row.promos.length === 1 ? row.promos[0] : "")}
            placeholder={draft?.promo === undefined && row.promos.length > 1 ? t("productMixedValues") : t("productNoPromo")} onChange={(e) => patch(row.sku, { promo: e.target.value })} /></td>
          <td className="p-2">{new Intl.NumberFormat(locale).format(row.placements)}<p className="max-w-40 break-words text-xs">{row.racks.slice(0, 5).join(", ")}</p></td>
        </tr>; })}
      </tbody></table>
      {!shown.length && <p>{t("bulkEmpty")}</p>}
    </div>
    <RequestError error={error} />
    <Button disabled={locked || !drafts.size} onClick={() => void check()}>{t(preview.isPending ? "bulkChecking" : "bulkPreview")}</Button>
    {preview.data && <section aria-label={t("bulkPreviewTitle")} className="space-y-2 rounded border p-3">
      <p>{t("bulkPreviewCount", { skus: preview.data.changes.length, placements: preview.data.changed_placements })}</p>
      <ul className="max-h-56 overflow-auto">{preview.data.changes.map((c) => <li key={c.before.sku} className="break-words border-b p-2"><strong>{c.before.sku}</strong><p>{t("productBeforeValues", { values: values(c.before) })}</p><p>{t("productAfterValues", { values: values(c.after) })}</p></li>)}</ul>
      {prepared && !save.data && <Button disabled={busy || refreshing} onClick={() => void persist()}>{t(save.isPending ? "bulkSaving" : save.isError ? "bulkRetrySave" : "bulkSave")}</Button>}
    </section>}
    {save.isError && <RequestError error={save.error}><p>{t("bulkSaveUncertain")}</p></RequestError>}
    {save.data && <div ref={focusOnMount} tabIndex={-1} role="status" className="outline-offset-2"><p>{t("bulkSaved")}</p><Button onClick={() => { if (save.data) { useSimulationStore.getState().setSelectedSetupId(save.data.setup_id); onClose(); } }}>{t("bulkOpen")}</Button></div>}
    <p className="text-xs">{t("bulkLimits")}</p>
  </div>;
}
