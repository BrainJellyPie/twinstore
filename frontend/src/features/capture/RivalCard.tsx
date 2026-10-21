// A rival's shelf against ours: price index and assortment overlap of a captured competitor shelf,
// optionally fed into the rival's pull in the neighborhood model.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Swords } from "lucide-react";

import * as api from "@/shared/api/client";
import type { CaptureResult } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { formatMoney } from "@/shared/utils/money";

export function RivalCard({ projectId, captureId, result }: { projectId: string; captureId: string; result: CaptureResult }) {
  const qc = useQueryClient();
  const { data: setups = [] } = useQuery({ queryKey: queryKeys.setups(projectId), queryFn: ({ signal }) => api.getSetups(projectId, signal) });
  const { data: town } = useQuery({ queryKey: queryKeys.town(projectId), queryFn: ({ signal }) => api.getTown(projectId, signal) });
  const rivals = (town?.venues ?? []).filter((v) => !v.is_focal && (v.category === "convenience" || v.category === "supermarket"));
  const [setupId, setSetupId] = useState("");
  const [venueId, setVenueId] = useState("");
  const base = setupId || setups[setups.length - 1]?.id || "";
  const run = useMutation({
    mutationFn: (apply: boolean) => api.compareRival(projectId, captureId, { setup_id: base, venue_id: venueId, apply }),
    onSuccess: async (_, apply) => {
      if (apply) await qc.invalidateQueries({ queryKey: queryKeys.town(projectId) });
    },
  });
  const report = run.data;
  const c = report?.comparison;
  const labeled = result.items.some((i) => i.labeled);
  const field = "h-9 rounded-xl border bg-card/60 px-2.5 text-xs";
  const pct = c?.price_index != null ? Math.round((c.price_index - 1) * 100) : null;

  return (
    <section className="rounded-2xl border border-glass-border bg-foreground/[0.02] p-3 text-sm">
      <div className="mb-1 flex items-center gap-2">
        <Swords className="size-4 text-heat-3" />
        <h3 className="section-title">Is this a rival's shelf?</h3>
      </div>
      <p className="mb-2 text-xs text-muted-foreground">Compare its prices and assortment with our layout; feed the result into the rival's pull.</p>
      <div className="grid grid-cols-2 gap-2">
        <select className={field} value={base} onChange={(e) => setSetupId(e.target.value)} aria-label="Our layout">
          {setups.map((s) => <option key={s.id} value={s.id}>Ours: {s.name}</option>)}
        </select>
        <select className={field} value={venueId} onChange={(e) => setVenueId(e.target.value)} aria-label="Rival venue">
          <option value="">No venue</option>
          {rivals.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select>
      </div>
      {!labeled && <p className="mt-2 rounded-lg tone-warn border p-2 text-xs">Name the products first (read with a vision model, or type them in).</p>}
      {run.error && <p className="mt-2 text-xs text-destructive">{run.error instanceof Error ? run.error.message : String(run.error)}</p>}
      <Button variant="outline" className="mt-2 w-full gap-2" disabled={!base || !labeled || run.isPending} onClick={() => run.mutate(false)}>
        {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <Swords className="size-4" />} Compare with our store
      </Button>
      {c && (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-glass-border p-2.5">
              <div className="eyebrow">Price index</div>
              <div className="num text-2xl font-medium tracking-[-0.04em]">{c.price_index?.toFixed(2) ?? "–"}</div>
              {pct != null && <div className={cn("text-xs", pct < 0 ? "text-negative" : "text-positive")}>{pct < 0 ? `rival ${-pct}% cheaper` : pct > 0 ? `rival ${pct}% dearer` : "same prices"}</div>}
            </div>
            <div className="rounded-xl border border-glass-border p-2.5">
              <div className="eyebrow">Assortment overlap</div>
              <div className="num text-2xl font-medium tracking-[-0.04em]">{Math.round(c.overlap * 100)}%</div>
              <div className="text-xs text-muted-foreground">{c.matched} of {c.rival_products} products shared</div>
            </div>
          </div>
          {c.prices.length > 0 && (
            <ul className="space-y-1 text-xs">
              {c.prices.slice(0, 5).map((p) => (
                <li key={p.name} className="flex items-center justify-between gap-2">
                  <span className="truncate">{p.name}</span>
                  <span className="num shrink-0 text-muted-foreground">
                    {formatMoney(p.rival_price, result.currency)} vs {formatMoney(p.our_price, result.currency)}
                    <span className={cn("ml-1.5 font-semibold", p.ratio < 1 ? "text-negative" : "text-positive")}>{p.ratio < 1 ? "−" : "+"}{Math.abs(Math.round((p.ratio - 1) * 100))}%</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {c.only_rival.length > 0 && <p className="text-xs text-muted-foreground"><span className="font-medium text-foreground">Only at the rival:</span> {c.only_rival.slice(0, 6).join(", ")}</p>}
          {venueId && c.suggested_pull_factor != null && (
            <Button className="w-full gap-2" disabled={run.isPending} onClick={() => run.mutate(true)}>
              Apply ×{c.suggested_pull_factor.toFixed(2)} to the rival's pull
            </Button>
          )}
          {report?.attractiveness != null && report.previous_attractiveness != null && report.attractiveness !== report.previous_attractiveness && (
            <p className="text-xs text-muted-foreground">Rival pull {report.previous_attractiveness.toFixed(2)} → <span className="font-semibold text-foreground">{report.attractiveness.toFixed(2)}</span> in the neighborhood model.</p>
          )}
        </div>
      )}
    </section>
  );
}
