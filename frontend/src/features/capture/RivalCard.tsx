// A rival's shelf against ours: price index and assortment overlap of a captured competitor shelf,
// optionally fed into the rival's pull in the neighborhood model.

import { useLayoutEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Swords } from "lucide-react";

import * as api from "@/shared/api/client";
import type { CaptureResult } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { formatMoney, formatPercent, formatDecimal } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import { richText } from "@/shared/i18n/richText";

export function RivalCard({ projectId, captureId, result }: { projectId: string; captureId: string; result: CaptureResult }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data: setups = [] } = useQuery({ queryKey: queryKeys.setups(projectId), queryFn: ({ signal }) => api.getSetups(projectId, signal) });
  const { data: town } = useQuery({ queryKey: queryKeys.town(projectId), queryFn: ({ signal }) => api.getTown(projectId, signal) });
  const rivals = (town?.venues ?? []).filter((v) => !v.is_focal && (v.category === "convenience" || v.category === "supermarket"));
  const [setupId, setSetupId] = useState("");
  const [venueId, setVenueId] = useState("");
  const base = setupId || setups[setups.length - 1]?.id || "";
  const run = useMutation({
    mutationFn: ({ projectId: pid, captureId: cid, ...request }: { projectId: string; captureId: string; setup_id: string; venue_id: string; apply: boolean }) => api.compareRival(pid, cid, request),
    onSuccess: async (_, request) => {
      if (request.apply) await qc.invalidateQueries({ queryKey: queryKeys.town(request.projectId) });
    },
  });
  const { reset } = run;
  useLayoutEffect(() => reset(), [projectId, captureId, base, venueId, result, reset]);
  const compare = (apply: boolean) => run.mutate({ projectId, captureId, setup_id: base, venue_id: venueId, apply });
  const report = run.data;
  const c = report?.comparison;
  const labeled = result.items.some((i) => i.labeled);
  const field = "h-9 rounded-xl border bg-card/60 px-2.5 text-xs";
  const pct = c?.price_index != null ? Math.round((c.price_index - 1) * 100) : null;
  const priceIndex = c?.price_index == null ? "–" : c.price_index > 0 && c.price_index < 0.01 ? `<${formatDecimal(0.01, 2)}` : formatDecimal(c.price_index, 2);

  return (
    <section className="rounded-2xl border border-glass-border bg-foreground/[0.02] p-3 text-sm">
      <div className="mb-1 flex items-center gap-2">
        <Swords className="size-4 text-heat-3" />
        <h3 className="section-title">{t("capRivalTitle")}</h3>
      </div>
      <p className="mb-2 text-xs text-muted-foreground">{t("capRivalHint")}</p>
      <div className="grid grid-cols-2 gap-2">
        <select className={field} value={base} onChange={(e) => setSetupId(e.target.value)} aria-label={t("capOurLayout")}>
          {setups.map((s) => <option key={s.id} value={s.id}>{t("capOurs", { name: s.name })}</option>)}
        </select>
        <select className={field} value={venueId} onChange={(e) => setVenueId(e.target.value)} aria-label={t("capRivalVenue")}>
          <option value="">{t("capNoVenue")}</option>
          {rivals.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select>
      </div>
      {!labeled && <p className="mt-2 rounded-lg tone-warn border p-2 text-xs">{t("capNameProductsFirst")}</p>}
      {run.error && <p className="mt-2 text-xs text-destructive">{run.error instanceof Error ? run.error.message : String(run.error)}</p>}
      <Button variant="outline" className="mt-2 w-full gap-2" disabled={!base || !labeled || run.isPending} onClick={() => compare(false)}>
        {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <Swords className="size-4" />} {t("capCompareWithOurs")}
      </Button>
      {c && (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="min-w-0 rounded-xl border border-glass-border p-2.5 [overflow-wrap:anywhere]">
              <div className="eyebrow">{t("capPriceIndex")}</div>
              <div className="num text-2xl font-medium tracking-[-0.04em]">{priceIndex}</div>
              {pct != null && <div className={cn("text-xs", pct < 0 ? "text-negative" : "text-positive")}>{pct < 0 ? t("capRivalCheaper", { pct: -pct }) : pct > 0 ? t("capRivalDearer", { pct }) : t("capSamePrices")}</div>}
            </div>
            <div className="min-w-0 rounded-xl border border-glass-border p-2.5">
              <div className="eyebrow">{t("capOverlap")}</div>
              <div className="num text-2xl font-medium tracking-[-0.04em]">{formatPercent(c.overlap, 0)}</div>
              <div className="text-xs text-muted-foreground">{t("capOverlapCount", { matched: c.matched, total: c.rival_products })}</div>
            </div>
          </div>
          {c.prices.length > 0 && (
            <ul className="space-y-1 text-xs">
              {c.prices.slice(0, 5).map((p) => (
                <li key={p.name} className="grid min-w-0 gap-0.5 [overflow-wrap:anywhere]">
                  <span>{p.name}</span>
                  <span className="num text-muted-foreground">
                    {t("capVs", { rival: formatMoney(p.rival_price, result.currency), ours: formatMoney(p.our_price, result.currency) })}
                    <span className={cn("ml-1.5 font-semibold", p.ratio < 1 ? "text-negative" : "text-positive")}>{p.ratio < 1 ? "−" : "+"}{Math.abs(Math.round((p.ratio - 1) * 100))}%</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {c.only_rival.length > 0 && <p className="text-xs text-muted-foreground"><span className="font-medium text-foreground">{t("capOnlyAtRival")}</span> {c.only_rival.slice(0, 6).join(", ")}</p>}
          {report?.model_matches && Object.keys(report.model_matches).length > 0 && (
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">{t("capModelMatches", { count: Object.keys(report.model_matches).length })}</summary>
              <ul className="mt-1 space-y-0.5">
                {Object.entries(report.model_matches).map(([theirs, ours]) => <li key={theirs}>{theirs} → <span className="text-foreground">{ours}</span></li>)}
              </ul>
            </details>
          )}
          {report?.match_note && <p className="text-xs text-muted-foreground">{report.match_note}</p>}
          {venueId && c.suggested_pull_factor != null && (
            <Button className="w-full gap-2" disabled={run.isPending} onClick={() => compare(true)}>
              {t("capApplyPull", { factor: formatDecimal(c.suggested_pull_factor, 2) })}
            </Button>
          )}
          {report?.attractiveness != null && report.previous_attractiveness != null && report.attractiveness !== report.previous_attractiveness && (
            <p className="text-xs text-muted-foreground">{richText(t("capRivalPull"), { before: formatDecimal(report.previous_attractiveness, 2), after: <span className="font-semibold text-foreground">{formatDecimal(report.attractiveness, 2)}</span> })}</p>
          )}
        </div>
      )}
    </section>
  );
}
