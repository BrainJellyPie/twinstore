// Ask the vision shoppers what a neighboring venue does to our store: the demand model says how
// many visitors it brings or takes; paired VLM simulations (with the venue in the shoppers' trip
// context and without it) say how their baskets change.

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Eye, Loader2, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import type { SynergyRow, TownDayType, VLMSynergyResult } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { ModelPicker, type ModelChoice } from "@/features/runs/components/ModelPicker";
import { currencyCode, formatMoney, formatPercent } from "@/shared/utils/money";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

export function VlmSynergyDialog({
  projectId, venue, dayType, scenarioId, onOpenChange,
}: {
  projectId: string;
  venue: SynergyRow | null;
  dayType: TownDayType;
  scenarioId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={!!venue} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-[680px]">
        {venue && <Body projectId={projectId} venue={venue} dayType={dayType} scenarioId={scenarioId} />}
      </DialogContent>
    </Dialog>
  );
}

function Body({ projectId, venue, dayType, scenarioId }: { projectId: string; venue: SynergyRow; dayType: TownDayType; scenarioId: string | null }) {
  const { t } = useI18n();
  const [customers, setCustomers] = useState(24);
  const [model, setModel] = useState<ModelChoice>({ kind: "default" });
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const start = useMutation({
    mutationFn: () => api.startVlmSynergy(projectId, venue.venue_id, {
      customers, day_type: dayType, scenario_id: scenarioId,
      model: model.kind === "single" ? model.model : null,
      ensemble: model.kind === "ensemble" && model.ensemble?.members.length ? model.ensemble : null,
    }),
    onSuccess: (s) => { setJobId(s.job_id); setError(null); },
    onError: (e) => setError(e instanceof Error ? e.message : String(e)),
  });
  const job = useQuery({
    queryKey: ["projects", projectId, "synergy-jobs", jobId],
    queryFn: ({ signal }) => api.getVlmSynergyJob(projectId, jobId!, signal),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && ["completed", "failed", "canceled"].includes(q.state.data.status.status) ? false : 1500),
  });

  return (
    <div className="space-y-4 text-sm">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2"><Eye className="size-5" /> {t("areaVlmTitle", { name: venue.name })}</DialogTitle>
        <DialogDescription>{t("areaVlmDescription", { name: venue.name })}</DialogDescription>
      </DialogHeader>

      {!jobId && (
        <div className="space-y-3">
          <ModelPicker engine="vlm_glance" value={model} onChange={setModel} />
          <label className="flex items-center gap-3 text-xs">
            <span className="text-muted-foreground">{t("areaVlmVisitors")}</span>
            <Input type="number" min={4} max={400} value={customers} className="h-8 w-24"
              onChange={(e) => setCustomers(Math.min(400, Math.max(4, Number(e.target.value) || 4)))} />
            <span className="text-muted-foreground">{t("areaVlmPairedHint")}</span>
          </label>
          {/* Up to two thirds of the panel are affected visitors, each walked a second time without the venue. */}
          <p className="text-xs text-muted-foreground">{t("optVlmVisits", { count: customers + Math.ceil((customers * 2) / 3) })}</p>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="flex justify-end">
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} {t("areaVlmRun")}
            </Button>
          </div>
        </div>
      )}

      {jobId && job.isPending && <p role="status" className="text-xs text-muted-foreground">{t("areaVlmLoadingStatus")}</p>}
      {jobId && job.isError && <div className="space-y-2">
        <p role="alert" className="text-xs text-destructive">{job.error instanceof Error ? job.error.message : t("areaVlmStatusError")}</p>
        <Button variant="outline" disabled={job.isFetching} onClick={() => void job.refetch()}>{t("areaVlmRetryStatus")}</Button>
      </div>}
      {jobId && job.data && !job.data.result && (
        <div className="space-y-3 py-6 text-center">
          {job.data.status.status === "failed" ? (
            <p className="text-destructive">{job.data.status.error}</p>
          ) : (
            <>
              <div className="font-medium">
                {job.data.status.phase === "with venue" ? t("areaVlmPhaseWith", { name: venue.name })
                  : job.data.status.phase === "without venue" ? t("areaVlmPhaseWithout", { name: venue.name }) : t("areaVlmChoosing")}
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="heat-gradient h-full transition-[width]" style={{ width: `${(job.data.status.total ? job.data.status.done / job.data.status.total : 0.03) * 100}%` }} />
              </div>
              <div className="text-xs text-muted-foreground">{t("areaVlmVisits", { done: job.data.status.done, total: job.data.status.total })}</div>
            </>
          )}
        </div>
      )}

      {job.data?.result && <ResultView r={job.data.result} />}
    </div>
  );
}

function ResultView({ r }: { r: VLMSynergyResult }) {
  const { t, locale } = useI18n();
  const currency = r.currency ? currencyCode(r.currency) : null;
  const money = (x: number) => currency ? formatMoney(x, currency) : t("studioMinorUnits", { amount: x.toLocaleString(locale) });
  const signed = (x: number, f: (v: number) => string) => `${x >= 0 ? "+" : "−"}${f(Math.abs(x))}`;
  const ci = r.delta_spend_ci_low != null && r.delta_spend_ci_high != null
    ? t("studioCi95", { low: signed(r.delta_spend_ci_low, money), high: signed(r.delta_spend_ci_high, money) }) : "";
  const shifts = [...r.category_shifts].sort((a, b) => Math.abs(b.spend_diff) - Math.abs(a.spend_diff)).slice(0, 6);
  const maxShift = Math.max(1, ...shifts.map((s) => Math.abs(s.spend_diff)));
  return (
    <div className="space-y-4">
      {!currency && <p className="text-xs text-muted-foreground">{t("areaVlmNoCurrency")}</p>}
      <div className={cn("rounded-xl border p-3", r.delta_revenue_per_day >= 0 ? "tone-good" : "tone-bad")}>
        <div className="font-display text-2xl font-bold tabular-nums">{t("studioPerDay", { amount: signed(r.delta_revenue_per_day, money) })}</div>
        <div className="text-xs">
          {t("areaVlmRevenueSplit", { visitors: signed(r.delta_revenue_from_visitors, money), baskets: signed(r.delta_revenue_from_baskets, money) })}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <Tile label={t("areaVisitorsPerDay")} value={`${r.delta_visitors >= 0 ? "+" : ""}${r.delta_visitors.toFixed(1)}`} hint={t("areaVlmStraightFrom", { count: r.linked_visitors_from_venue.toFixed(1) })} />
        <Tile label={t("areaVlmSpendPerVisitor")} value={signed(r.delta_spend_per_visitor, money)} hint={ci || "—"} />
        <Tile label={t("areaVlmConversion")} value={t("studioPp", { value: `${r.delta_conversion >= 0 ? "+" : ""}${(r.delta_conversion * 100).toFixed(1)}` })} hint={t("areaVlmAffected", { share: formatPercent(r.affected_share, 1) })} />
      </div>
      {shifts.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-muted-foreground">{t("areaVlmShiftsTitle")}</div>
          <ul className="space-y-1 text-xs">
            {shifts.map((s) => (
              <li key={s.category} className="grid grid-cols-[110px_1fr_70px] items-center gap-2">
                <span className="truncate">{s.category}</span>
                <span className="relative h-2 rounded-full bg-muted">
                  <span className={cn("absolute top-0 h-2 rounded-full", s.spend_diff >= 0 ? "left-1/2 bg-positive" : "right-1/2 bg-negative")}
                    style={{ width: `${(Math.abs(s.spend_diff) / maxShift) * 50}%` }} />
                </span>
                <span className="text-right tabular-nums">{signed(s.spend_diff, money)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {r.examples.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-muted-foreground">{t("areaVlmExamplesTitle")}</div>
          <ul className="space-y-2 text-xs">
            {r.examples.slice(0, 3).map((e) => (
              <li key={e.persona_id} className="grid grid-cols-2 gap-2 rounded-lg border p-2">
                <div><div className="text-muted-foreground">{t("areaVlmWith", { name: r.venue_name })}</div>“{e.mission_with || "—"}” · {money(e.spend_with)}</div>
                <div><div className="text-muted-foreground">{t("areaVlmWithout")}</div>“{e.mission_without || "—"}” · {money(e.spend_without)}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        {t("areaVlmFooter", { panel: r.panel_customers, affected: r.affected_customers, calls: r.vlm_requests, minutes: Math.round(r.seconds / 60) })}
        {r.model ? ` · ${r.model}` : ""}
      </p>
      {r.notes.length > 0 && <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{r.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
    </div>
  );
}

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border px-2 py-1.5">
      <div className="text-muted-foreground">{label}</div>
      <div className="text-base font-semibold tabular-nums">{value}</div>
      <div className="truncate text-muted-foreground" title={hint}>{hint}</div>
    </div>
  );
}
