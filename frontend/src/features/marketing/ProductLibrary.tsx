// Product image library: drop package shots (a photo on a plain background is cut out automatically), name them,
// tag the brand and link each to a product of the layout. Linked images become "new package" variants in A/B
// tests and stimuli in concept tests; Shelf Lab uses the same library.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, ImagePlus, Link2, Loader2, Scissors, Sparkles, Trash2 } from "lucide-react";

import * as api from "@/shared/api/client";
import type { PackageAsset } from "@/shared/api/client";
import { marketingKeys } from "@/shared/api/marketing";
import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import { NeedsModel } from "@/features/settings/NeedsModel";

import { usePackages } from "./hooks";
import type { Product } from "./products";

export function ProductDrop({ projectId, compact = false, onUploaded, setupId }: {
  projectId: string; compact?: boolean; onUploaded?: (a: PackageAsset[]) => void;
  /** Layout whose products a read pack may be linked to. */
  setupId?: string;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [cutOut, setCutOut] = useState(true);
  const [readPacks, setReadPacks] = useState(true);
  const [unread, setUnread] = useState(0);
  const [failures, setFailures] = useState<{ name: string; message: string }[]>([]);
  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      const out: PackageAsset[] = [];
      const failed: { name: string; message: string }[] = [];
      let unreadable = 0;
      // One file at a time; a rejected file is reported and the rest still upload.
      for (const f of files) {
        let asset: PackageAsset;
        try {
          asset = await api.uploadPackage(projectId, f, { name: f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "), remove_background: cutOut });
        } catch (e) {
          failed.push({ name: f.name, message: e instanceof Error ? e.message : String(e) });
          continue;
        }
        if (readPacks) {
          // The printed name beats the file name; a pack the model cannot read keeps the file name.
          try { asset = (await api.readPackage(projectId, asset.asset_id, { setup_id: setupId })).asset; } catch { unreadable += 1; }
        }
        out.push(asset);
      }
      setUnread(unreadable);
      setFailures(failed);
      return out;
    },
    onSettled: async (assets) => {
      await qc.invalidateQueries({ queryKey: marketingKeys.packages(projectId) });
      if (assets?.length) onUploaded?.(assets);
    },
  });
  const pick = (list: FileList | null) => {
    const files = Array.from(list ?? []).filter((f) => f.type.startsWith("image/"));
    if (files.length) upload.mutate(files);
  };
  return (
    <div className="space-y-1.5">
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files); }}
        className={cn(
          "flex w-full items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-foreground/15 text-left transition-colors",
          compact ? "px-3 py-3" : "px-5 py-6",
          drag ? "border-primary bg-primary/5" : "hover:border-primary/60",
        )}
      >
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-foreground/[0.05]">
          {upload.isPending ? <Loader2 className="size-5 animate-spin" /> : <ImagePlus className="size-5" />}
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-semibold">{upload.isPending ? (readPacks ? t("mkUploadingReading") : t("mkUploading")) : t("mkDropImages")}</span>
          <span className="block text-xs text-muted-foreground">{t("mkDropHint")}</span>
        </span>
        <input ref={input} type="file" multiple accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
      </button>
      <div className="flex flex-wrap gap-x-4 gap-y-1 px-1 text-xs text-muted-foreground">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cutOut} onChange={(e) => setCutOut(e.target.checked)} />
          {t("mkRemoveBackground")}
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={readPacks} onChange={(e) => setReadPacks(e.target.checked)} />
          {t("mkNamePacks")}
        </label>
      </div>
      {upload.error && <p role="alert" className="text-xs text-destructive">{upload.error.message}</p>}
      {failures.length > 0 && !upload.isPending && (
        <div role="alert" className="px-1 text-xs text-destructive">
          <p>{failures.length === 1 ? t("mkOneUploadFailed") : t("mkUploadsFailed", { count: failures.length })}</p>
          <ul className="list-disc pl-4">
            {failures.map((f, i) => <li key={i} className="break-words"><span className="font-medium">{f.name}</span>: {f.message}</li>)}
          </ul>
        </div>
      )}
      {unread > 0 && !upload.isPending && (
        <p className="text-xs text-muted-foreground">{t(unread > 1 ? "mkUnreadMany" : "mkUnreadOne", { count: unread })}</p>
      )}
      {/* Reading a pack takes a model; with none set up, say how to get one (nothing shows once one answers). */}
      {unread > 0 && !upload.isPending && <NeedsModel purpose="assist" />}
    </div>
  );
}

export function ProductLibrary({ projectId, products, setupId }: { projectId: string; products: Product[]; setupId?: string }) {
  const { t } = useI18n();
  const packages = usePackages(projectId);
  const list = packages.data ?? [];
  // A deleted card held focus; it moves to the drop zone at the top of the library.
  const drop = useRef<HTMLDivElement>(null);
  const focusDrop = () => drop.current?.querySelector("button")?.focus();
  return (
    <div className="space-y-4">
      <div ref={drop}><ProductDrop projectId={projectId} setupId={setupId} /></div>
      {list.length === 0 ? (
        <p className="px-1 text-sm text-muted-foreground">{t("mkNoImages")}</p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(13.5rem,1fr))] gap-3">
          {list.map((p) => <ProductCard key={`${projectId}:${p.asset_id}`} projectId={projectId} asset={p} products={products} setupId={setupId} onDeleted={focusDrop} />)}
        </div>
      )}
    </div>
  );
}

function ProductCard({ projectId, asset, products, setupId, onDeleted }: {
  projectId: string; asset: PackageAsset; products: Product[]; setupId?: string; onDeleted: () => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [nameDraft, setNameDraft] = useState<string | null>(null);
  const [brandDraft, setBrandDraft] = useState<string | null>(null);
  const name = nameDraft ?? asset.name;
  const brand = brandDraft ?? asset.brand ?? "";
  // Saved values follow reads and refetches; unfinished edits remain until their own save is acknowledged.
  useEffect(() => { setNameDraft((current) => current?.trim() === asset.name ? null : current); }, [asset.name]);
  useEffect(() => { setBrandDraft((current) => current?.trim() === (asset.brand ?? "") ? null : current); }, [asset.brand]);
  const read = useMutation({
    mutationFn: () => api.readPackage(projectId, asset.asset_id, { setup_id: setupId }),
    onSuccess: () => qc.invalidateQueries({ queryKey: marketingKeys.packages(projectId) }),
  });
  const [confirm, setConfirm] = useState(false);
  const save = useMutation({
    mutationFn: (update: { name?: string; brand?: string; sku?: string }) => api.updatePackage(projectId, asset.asset_id, update),
    onSuccess: () => qc.invalidateQueries({ queryKey: marketingKeys.packages(projectId) }),
  });
  const del = useMutation({
    mutationFn: () => api.deletePackage(projectId, asset.asset_id),
    onSuccess: onDeleted,
    onSettled: () => qc.invalidateQueries({ queryKey: marketingKeys.packages(projectId) }),
  });
  const linked = products.find((p) => p.sku === asset.sku);
  return (
    <div className="group overflow-hidden rounded-2xl border bg-card">
      <div className="relative flex h-40 items-center justify-center bg-[conic-gradient(var(--muted)_25%,transparent_0_50%,var(--muted)_0_75%,transparent_0)] bg-[length:16px_16px] p-3">
        <img src={api.packageUrl(projectId, asset.asset_id)} alt={asset.name} className="max-h-full max-w-full object-contain drop-shadow-[0_8px_14px_rgb(0_0_0/0.22)]" />
        {asset.cut_out && (
          <span className="absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-[0.7rem] text-white">
            <Scissors className="size-3" /> {t("mkCutOut")}
          </span>
        )}
        <button
          type="button"
          onClick={() => (confirm ? del.mutate() : setConfirm(true))}
          onBlur={() => setConfirm(false)}
          className={cn("absolute top-2 right-2 inline-flex items-center gap-1 rounded-full px-2 py-1 text-[0.68rem] transition-opacity",
            confirm ? "bg-destructive text-white dark:text-neutral-950" : "bg-black/55 text-white opacity-0 group-hover:opacity-100 focus-visible:opacity-100 [@media(hover:none)]:opacity-100")}
          aria-label={confirm ? t("mkDeleteConfirm") : t("mkDeleteJob", { name: asset.name })}
        >
          <Trash2 className="size-3" /> {confirm ? t("mkDeleteConfirm") : ""}
        </button>
      </div>
      <div className="space-y-1.5 p-2.5">
        <Input value={name} onChange={(e) => setNameDraft(e.target.value === asset.name ? null : e.target.value)} onBlur={() => name.trim() && name !== asset.name && save.mutate({ name: name.trim() })}
          className="h-8 text-sm font-medium" aria-label={t("mkName")} />
        <Input value={brand} onChange={(e) => setBrandDraft(e.target.value === (asset.brand ?? "") ? null : e.target.value)} onBlur={() => brand !== (asset.brand ?? "") && save.mutate({ brand: brand.trim() })}
          placeholder={t("mkBrand")} className="h-8 text-xs" aria-label={t("mkBrand")} />
        <label className="flex items-center gap-1.5">
          <Link2 className={cn("size-3.5 shrink-0", linked ? "text-primary" : "text-muted-foreground")} aria-hidden />
          <select
            value={asset.sku ?? ""}
            onChange={(e) => save.mutate({ sku: e.target.value })}
            className="h-8 min-w-0 flex-1 rounded-lg border bg-card/60 px-1.5 text-xs"
            aria-label={t("mkShownAs")}
          >
            <option value="">{t("mkNotOnShelf")}</option>
            {products.map((p) => <option key={p.sku} value={p.sku}>{p.name} · {p.sku}</option>)}
            {asset.sku && !linked && <option value={asset.sku}>{t("mkNotInLayout", { sku: asset.sku })}</option>}
          </select>
          {save.isSuccess && !save.isPending && <Check className="size-3.5 text-positive" aria-label={t("studioSaved")} />}
        </label>
        <div className="flex items-center justify-between gap-2">
          <span className="num text-[0.68rem] text-muted-foreground">{asset.width}×{asset.height}px{asset.brand ? ` · ${asset.brand}` : ""}</span>
          <button type="button" onClick={() => read.mutate()} disabled={read.isPending}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[0.7rem] text-muted-foreground hover:bg-foreground/[0.05] hover:text-foreground disabled:opacity-50"
            title={t("mkReadPackTitle")}>
            {read.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />} {t("mkReadPack")}
          </button>
        </div>
        {read.data && (
          <p className="text-[0.68rem] text-muted-foreground">
            {read.data.reading.size && `${read.data.reading.size} · `}{read.data.reading.category}
            {read.data.linked ? t("mkLinkedToShelf") : ""}
          </p>
        )}
        {read.error && <p role="alert" className="text-[0.68rem] text-destructive">{read.error.message}</p>}
        {save.error && <p role="alert" className="text-[0.68rem] text-destructive">{save.error.message}</p>}
        {del.error && <p role="alert" className="text-[0.68rem] text-destructive">{del.error.message}</p>}
      </div>
    </div>
  );
}
