// Storefront appeal: a photo of a shop front, rated like a passer-by would (sign, entrance, window,
// upkeep), sets that venue's pull in the demand model — ours or a rival's.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, Loader2, Store } from "lucide-react";

import * as api from "@/shared/api/client";
import type { StorefrontResult, Town } from "@/shared/api/client";
import { cn } from "@/shared/utils/cn";
import { queryKeys } from "@/shared/queries/keys";
import { useI18n } from "@/shared/i18n/i18n";
import { richText } from "@/shared/i18n/richText";

import { VENUE_LABELS } from "./townStyle";
import { formatPercent, formatDecimal } from "@/shared/utils/money";

const SCORES = [
  ["signage", "areaScoreSign"],
  ["entrance", "areaScoreEntrance"],
  ["window", "areaScoreWindow"],
  ["upkeep", "areaScoreUpkeep"],
] as const;

export function StorefrontCard({ projectId, town, onTown }: { projectId: string; town: Town; onTown: (t: Town) => void }) {
  const [selected, setSelected] = useState(town.focal_venue_id);
  const eligible = town.venues.filter((v) => v.id === town.focal_venue_id || (!v.is_focal && (v.category === "convenience" || v.category === "supermarket")));
  const venueId = eligible.some((v) => v.id === selected) ? selected : eligible[0]?.id ?? "";
  return <StorefrontRating key={JSON.stringify([projectId, town.id, venueId])} projectId={projectId} town={town}
    venueId={venueId} onVenueChange={setSelected} onTown={onTown} />;
}

function StorefrontRating({ projectId, town, venueId, onVenueChange, onTown }: {
  projectId: string; town: Town; venueId: string; onVenueChange: (id: string) => void; onTown: (t: Town) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const focal = town.venues.find((v) => v.id === town.focal_venue_id);
  const rivals = town.venues.filter((v) => !v.is_focal && (v.category === "convenience" || v.category === "supermarket"));
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<StorefrontResult | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const mounted = useRef(false);
  const currentTown = useRef(town);
  const pending = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { currentTown.current = town; }, [town]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const rate = useMutation({
    mutationFn: ({ file }: { file: File; snapshot: Town }) => api.rateStorefront(projectId, venueId, file),
    onSuccess: (r, { snapshot }) => {
      if (!mounted.current) return;
      if (currentTown.current !== snapshot) {
        void qc.invalidateQueries({ queryKey: queryKeys.town(projectId) });
        return;
      }
      setResult(r);
      onTown(r.town);
    },
    onSettled: () => { pending.current = false; },
  });
  const pick = (file: File | undefined) => {
    if (!file || !venueId || pending.current) return;
    pending.current = true;
    setResult(null);
    setPreview(URL.createObjectURL(file));
    rate.mutate({ file, snapshot: town });
  };
  const appeal = result?.venue_id === venueId ? result.appeal : null;
  const delta = appeal && result ? appeal.attractiveness / result.previous_attractiveness - 1 : 0;

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <Store className="size-4 text-heat-2" />
        <h3 className="font-medium">{t("areaStorefrontTitle")}</h3>
      </div>
      <p className="text-xs text-muted-foreground">{t("areaStorefrontHint")}</p>
      <select className="h-9 w-full rounded-xl border bg-card/60 px-2.5 text-xs" aria-label={t("areaStorefrontVenue")} value={venueId} disabled={rate.isPending || !venueId} onChange={(e) => onVenueChange(e.target.value)}>
        {focal && <option value={focal.id}>{t("areaStorefrontOurs", { name: focal.name })}</option>}
        {rivals.map((v) => <option key={v.id} value={v.id}>{t("areaStorefrontRival", { name: v.name, category: t(VENUE_LABELS[v.category]) })}</option>)}
      </select>
      <button type="button" disabled={rate.isPending || !venueId} onClick={() => input.current?.click()}
        className="relative flex h-32 w-full items-center justify-center overflow-hidden rounded-2xl border border-dashed border-foreground/15 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground">
        {preview ? <img src={preview} alt={t("areaStorefrontAlt")} className="absolute inset-0 h-full w-full object-cover" /> : null}
        <span className={cn("relative flex items-center gap-1.5 rounded-full px-3 py-1.5", preview && "glass text-foreground")}>
          {rate.isPending ? <Loader2 className="size-4 animate-spin" /> : <Camera className="size-4" />}
          {rate.isPending ? t("areaRating") : preview ? t("areaAnotherPhoto") : t("areaUploadStorefront")}
        </span>
      </button>
      <input ref={input} type="file" disabled={rate.isPending || !venueId} accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
      {rate.error && <p role="alert" className="text-xs text-destructive">{rate.error instanceof Error ? rate.error.message : String(rate.error)}</p>}
      {appeal && (
        <div className="space-y-2 rounded-2xl border border-glass-border bg-foreground/[0.02] p-3">
          <div className="flex items-end justify-between">
            <div>
              <div className="eyebrow">{t("areaAppeal")}</div>
              <div className="num text-3xl font-medium tracking-[-0.05em]">{formatDecimal(appeal.overall, 1)}<span className="text-base text-muted-foreground">/10</span></div>
            </div>
            <div className="text-right text-xs">
              <div className="text-muted-foreground">{richText(t("areaPull"), { before: formatDecimal(result!.previous_attractiveness, 2), after: <span className="num font-semibold text-foreground">{formatDecimal(appeal.attractiveness, 2)}</span> })}</div>
              <div className={cn("num font-semibold", delta >= 0 ? "text-positive" : "text-negative")}>{delta >= 0 ? "+" : ""}{formatPercent(delta, 0)}</div>
            </div>
          </div>
          {SCORES.map(([key, label]) => (
            <div key={key} className="flex items-center gap-2 text-xs">
              <span className="w-16 text-muted-foreground">{t(label)}</span>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-foreground/10">
                <div className="aurora-gradient h-full rounded-full" style={{ width: `${appeal[key] * 10}%` }} />
              </div>
              <span className="num w-7 text-right">{formatDecimal(appeal[key], 0)}</span>
            </div>
          ))}
          <p className="text-[0.72rem] text-muted-foreground">{appeal.method === "vlm" ? `${appeal.model}: ` : ""}{appeal.reasons}</p>
        </div>
      )}
    </section>
  );
}
