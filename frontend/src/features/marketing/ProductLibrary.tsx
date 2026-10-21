// Product image library: drop package shots (a photo on a plain background is cut out automatically), name them,
// tag the brand and link each to a product of the layout. Linked images become "new package" variants in A/B
// tests and stimuli in concept tests; Shelf Lab uses the same library.

import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, ImagePlus, Link2, Loader2, Scissors, Trash2 } from "lucide-react";

import * as api from "@/shared/api/client";
import type { PackageAsset } from "@/shared/api/client";
import { marketingKeys } from "@/shared/api/marketing";
import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/utils/cn";

import { usePackages } from "./hooks";
import type { Product } from "./products";

export function ProductDrop({ projectId, compact = false, onUploaded }: { projectId: string; compact?: boolean; onUploaded?: (a: PackageAsset[]) => void }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [cutOut, setCutOut] = useState(true);
  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      const out: PackageAsset[] = [];
      for (const f of files) {
        out.push(await api.uploadPackage(projectId, f, { name: f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "), remove_background: cutOut }));
      }
      return out;
    },
    onSuccess: async (assets) => {
      await qc.invalidateQueries({ queryKey: marketingKeys.packages(projectId) });
      onUploaded?.(assets);
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
          <span className="block text-sm font-semibold">{upload.isPending ? "Uploading…" : "Drop product images"}</span>
          <span className="block text-xs text-muted-foreground">PNG, JPEG or WebP · several at once · packshots or phone photos</span>
        </span>
        <input ref={input} type="file" multiple accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
      </button>
      <label className="flex items-center gap-2 px-1 text-xs text-muted-foreground">
        <input type="checkbox" checked={cutOut} onChange={(e) => setCutOut(e.target.checked)} />
        Remove a plain background
      </label>
      {upload.error && <p className="text-xs text-destructive">{upload.error.message}</p>}
    </div>
  );
}

export function ProductLibrary({ projectId, products }: { projectId: string; products: Product[] }) {
  const packages = usePackages(projectId);
  const list = packages.data ?? [];
  return (
    <div className="space-y-4">
      <ProductDrop projectId={projectId} />
      {list.length === 0 ? (
        <p className="px-1 text-sm text-muted-foreground">
          No product images yet. Add the packs you want to test — current packs, redesigns, competitor packs — then link each one to
          the product it replaces on the shelf.
        </p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(13.5rem,1fr))] gap-3">
          {list.map((p) => <ProductCard key={p.asset_id} projectId={projectId} asset={p} products={products} />)}
        </div>
      )}
    </div>
  );
}

function ProductCard({ projectId, asset, products }: { projectId: string; asset: PackageAsset; products: Product[] }) {
  const qc = useQueryClient();
  const [name, setName] = useState(asset.name);
  const [brand, setBrand] = useState(asset.brand ?? "");
  const [confirm, setConfirm] = useState(false);
  const save = useMutation({
    mutationFn: (update: { name?: string; brand?: string; sku?: string }) => api.updatePackage(projectId, asset.asset_id, update),
    onSuccess: () => qc.invalidateQueries({ queryKey: marketingKeys.packages(projectId) }),
  });
  const del = useMutation({
    mutationFn: () => api.deletePackage(projectId, asset.asset_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: marketingKeys.packages(projectId) }),
  });
  const linked = products.find((p) => p.sku === asset.sku);
  return (
    <div className="group overflow-hidden rounded-2xl border bg-card">
      <div className="relative flex h-40 items-center justify-center bg-[conic-gradient(var(--muted)_25%,transparent_0_50%,var(--muted)_0_75%,transparent_0)] bg-[length:16px_16px] p-3">
        <img src={api.packageUrl(projectId, asset.asset_id)} alt={asset.name} className="max-h-full max-w-full object-contain drop-shadow-[0_8px_14px_rgb(0_0_0/0.22)]" />
        {asset.cut_out && (
          <span className="absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-[0.65rem] text-white">
            <Scissors className="size-3" /> cut out
          </span>
        )}
        <button
          type="button"
          onClick={() => (confirm ? del.mutate() : setConfirm(true))}
          onBlur={() => setConfirm(false)}
          className={cn("absolute top-2 right-2 inline-flex items-center gap-1 rounded-full px-2 py-1 text-[0.68rem] transition-opacity",
            confirm ? "bg-destructive text-white" : "bg-black/55 text-white opacity-0 group-hover:opacity-100 focus-visible:opacity-100")}
          aria-label={`Delete ${asset.name}`}
        >
          <Trash2 className="size-3" /> {confirm ? "Delete?" : ""}
        </button>
      </div>
      <div className="space-y-1.5 p-2.5">
        <Input value={name} onChange={(e) => setName(e.target.value)} onBlur={() => name.trim() && name !== asset.name && save.mutate({ name: name.trim() })}
          className="h-8 text-sm font-medium" aria-label="Name" />
        <Input value={brand} onChange={(e) => setBrand(e.target.value)} onBlur={() => brand !== (asset.brand ?? "") && save.mutate({ brand: brand.trim() })}
          placeholder="Brand" className="h-8 text-xs" aria-label="Brand" />
        <label className="flex items-center gap-1.5">
          <Link2 className={cn("size-3.5 shrink-0", linked ? "text-primary" : "text-muted-foreground")} aria-hidden />
          <select
            value={asset.sku ?? ""}
            onChange={(e) => save.mutate({ sku: e.target.value })}
            className="h-8 min-w-0 flex-1 rounded-lg border bg-card/60 px-1.5 text-xs"
            aria-label="Shown on the shelf as"
          >
            <option value="">Not on the shelf</option>
            {products.map((p) => <option key={p.sku} value={p.sku}>{p.name} · {p.sku}</option>)}
            {asset.sku && !linked && <option value={asset.sku}>{asset.sku} (not in this layout)</option>}
          </select>
          {save.isSuccess && !save.isPending && <Check className="size-3.5 text-positive" aria-label="Saved" />}
        </label>
        <div className="num text-[0.68rem] text-muted-foreground">{asset.width}×{asset.height}px{asset.brand ? ` · ${asset.brand}` : ""}</div>
      </div>
    </div>
  );
}
