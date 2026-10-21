// Storefront appeal: a photo of a shop front, rated like a passer-by would (sign, entrance, window,
// upkeep), sets that venue's pull in the demand model — ours or a rival's.

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Camera, Loader2, Store } from "lucide-react";

import * as api from "@/shared/api/client";
import type { StorefrontResult, Town } from "@/shared/api/client";
import { cn } from "@/shared/utils/cn";

import { VENUE_LABELS } from "./townStyle";

const SCORES = [
  ["signage", "Sign"],
  ["entrance", "Entrance"],
  ["window", "Window"],
  ["upkeep", "Upkeep"],
] as const;

export function StorefrontCard({ projectId, town, onTown }: { projectId: string; town: Town; onTown: (t: Town) => void }) {
  const focal = town.venues.find((v) => v.id === town.focal_venue_id);
  const rivals = town.venues.filter((v) => !v.is_focal && (v.category === "convenience" || v.category === "supermarket"));
  const [venueId, setVenueId] = useState(town.focal_venue_id);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<StorefrontResult | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const rate = useMutation({
    mutationFn: (file: File) => api.rateStorefront(projectId, venueId, file),
    onSuccess: (r) => {
      setResult(r);
      onTown(r.town);
    },
  });
  const pick = (file: File | undefined) => {
    if (!file) return;
    setPreview(URL.createObjectURL(file));
    rate.mutate(file);
  };
  const appeal = result?.venue_id === venueId ? result.appeal : null;
  const delta = appeal && result ? appeal.attractiveness / result.previous_attractiveness - 1 : 0;

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <Store className="size-4 text-heat-2" />
        <h3 className="font-medium">Storefront appeal</h3>
      </div>
      <p className="text-xs text-muted-foreground">A street photo of a shop front sets how strongly it pulls passers-by in the demand model.</p>
      <select className="h-9 w-full rounded-xl border bg-card/60 px-2.5 text-xs" value={venueId} onChange={(e) => { setVenueId(e.target.value); setResult(null); setPreview(null); }}>
        {focal && <option value={focal.id}>Our store · {focal.name}</option>}
        {rivals.map((v) => <option key={v.id} value={v.id}>Rival · {v.name} ({VENUE_LABELS[v.category]})</option>)}
      </select>
      <button type="button" onClick={() => input.current?.click()}
        className="relative flex h-32 w-full items-center justify-center overflow-hidden rounded-2xl border border-dashed border-foreground/15 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground">
        {preview ? <img src={preview} alt="Storefront" className="absolute inset-0 h-full w-full object-cover" /> : null}
        <span className={cn("relative flex items-center gap-1.5 rounded-full px-3 py-1.5", preview && "glass text-foreground")}>
          {rate.isPending ? <Loader2 className="size-4 animate-spin" /> : <Camera className="size-4" />}
          {rate.isPending ? "Rating…" : preview ? "Another photo" : "Upload a storefront photo"}
        </span>
      </button>
      <input ref={input} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
      {rate.error && <p className="text-xs text-destructive">{rate.error instanceof Error ? rate.error.message : String(rate.error)}</p>}
      {appeal && (
        <div className="space-y-2 rounded-2xl border border-glass-border bg-foreground/[0.02] p-3">
          <div className="flex items-end justify-between">
            <div>
              <div className="eyebrow">Appeal</div>
              <div className="num text-3xl font-medium tracking-[-0.05em]">{appeal.overall.toFixed(1)}<span className="text-base text-muted-foreground">/10</span></div>
            </div>
            <div className="text-right text-xs">
              <div className="text-muted-foreground">pull {result!.previous_attractiveness.toFixed(2)} → <span className="num font-semibold text-foreground">{appeal.attractiveness.toFixed(2)}</span></div>
              <div className={cn("num font-semibold", delta >= 0 ? "text-positive" : "text-negative")}>{delta >= 0 ? "+" : ""}{Math.round(delta * 100)}%</div>
            </div>
          </div>
          {SCORES.map(([key, label]) => (
            <div key={key} className="flex items-center gap-2 text-xs">
              <span className="w-16 text-muted-foreground">{label}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-foreground/10">
                <div className="aurora-gradient h-full rounded-full" style={{ width: `${appeal[key] * 10}%` }} />
              </div>
              <span className="num w-7 text-right">{appeal[key].toFixed(0)}</span>
            </div>
          ))}
          <p className="text-[0.72rem] text-muted-foreground">{appeal.method === "vlm" ? `${appeal.model}: ` : ""}{appeal.reasons}</p>
        </div>
      )}
    </section>
  );
}
