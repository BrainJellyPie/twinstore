import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";

import { getMovementReport, uploadMovement } from "@/shared/api/movement";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { formatPercent, formatDecimal } from "@/shared/utils/money";

function Heatmap({ values, denominator, label, width, height, maxValue }: {
  values: number[][]; denominator: number; label: string; width: number; height: number; maxValue: number;
}) {
  const { t } = useI18n();
  return <figure className="min-w-0 space-y-1">
    <figcaption className="text-xs font-medium">{label}</figcaption>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t("movementHeatmap", { label })} className="aspect-square w-full rounded border bg-muted">
      {values.flatMap((row, y) => row.map((count, x) => {
        const value = denominator > 0 ? count / denominator : 0;
        return <rect key={`${x},${y}`} x={x} y={y} width={0.95} height={0.95}
          fill={value > 0 ? `rgba(14, 116, 144, ${0.15 + 0.85 * value / Math.max(maxValue, 1e-12)})` : "transparent"}>
          <title>{`${label}: (${x}, ${y}) · ${formatPercent(value, 1)}`}</title>
        </rect>;
      }))}
    </svg>
  </figure>;
}

function checkedAt(iso: string, locale: string): string {
  const date = new Date(iso);
  return locale === "en" || Number.isNaN(date.getTime()) ? iso : date.toLocaleString(locale);
}

export function MovementSection({ projectId, runId }: { projectId: string; runId: string }) {
  const { locale, t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [maxGap, setMaxGap] = useState(30);
  const [layer, setLayer] = useState<"visitors" | "occupancy_seconds">("visitors");
  const client = useQueryClient();
  const key = ["movement", projectId, runId];
  const saved = useQuery({ queryKey: key, queryFn: () => getMovementReport(projectId, runId), retry: false });
  const upload = useMutation({
    mutationFn: (file: File) => uploadMovement(projectId, runId, file, maxGap),
    onSuccess: async (report) => {
      await client.cancelQueries({ queryKey: key });
      client.setQueryData(key, report);
    },
  });
  const report = saved.data;
  const real = report?.observed;
  const sim = report?.simulated;
  const denominatorReal = layer === "visitors" ? real?.tracks ?? 0 : real?.observed_seconds ?? 0;
  const denominatorSim = layer === "visitors" ? sim?.tracks ?? 0 : sim?.observed_seconds ?? 0;
  let maxValue = 0;
  for (const [summary, denominator] of [[real, denominatorReal], [sim, denominatorSim]] as const) {
    for (const row of summary?.[layer] ?? []) {
      for (const value of row) maxValue = Math.max(maxValue, value / (denominator || 1));
    }
  }
  const validGap = Number.isFinite(maxGap) && maxGap > 0 && maxGap <= 300;

  return <section aria-label={t("movementTitle")} className="space-y-2 border-t px-3 py-3">
    <h3 className="section-title">{t("movementTitle")}</h3>
    <p className="text-xs text-muted-foreground">{t("movementHint")}</p>
    <div className="flex items-end gap-2">
      <label className="flex-1 text-xs">{t("movementMaxGapSeconds")}
        <input type="number" min="0.1" max="300" step="0.1" value={maxGap} disabled={upload.isPending}
          onChange={(e) => setMaxGap(Number(e.target.value))} className="mt-1 w-full rounded border bg-background px-2 py-1"
          aria-label={t("movementMaxGap")} />
      </label>
      <Button size="sm" variant="outline" disabled={upload.isPending || !validGap} onClick={() => inputRef.current?.click()}>
        <Upload className="mr-1 size-3" />{upload.isPending ? t("movementComparing") : t("movementUpload")}
      </Button>
      <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => {
        const file = e.target.files?.[0];
        if (file) upload.mutate(file);
        e.target.value = "";
      }} />
    </div>
    {(upload.isError || saved.isError) && <p role="alert" className="text-xs text-destructive">{(upload.error ?? saved.error)?.message}</p>}
    {report && real && sim && <div className="space-y-2 text-xs">
      <p>{t("movementSummary", { tracks: real.tracks, shoppers: sim.tracks, samples: real.samples })}</p>
      <div className="grid grid-cols-2 gap-2 rounded border p-2">
        <span>{t("movementVisitation")} <b className="block tabular-nums">{report.visitation_similarity == null ? t("notAvailable") : formatDecimal(report.visitation_similarity, 3)}</b></span>
        <span>{t("movementOccupancy")} <b className="block tabular-nums">{report.occupancy_similarity == null ? t("notAvailable") : formatDecimal(report.occupancy_similarity, 3)}</b></span>
      </div>
      <label>{t("movementMapLayer")}
        <select aria-label={t("movementMapLayerAria")} value={layer} onChange={(e) => setLayer(e.target.value as typeof layer)} className="ml-2 rounded border bg-background px-2 py-1">
          <option value="visitors">{t("movementShareVisitors")}</option>
          <option value="occupancy_seconds">{t("movementShareTime")}</option>
        </select>
      </label>
      <div className="grid grid-cols-2 gap-2">
        <Heatmap values={real[layer]} denominator={denominatorReal} label={t("movementObserved")} width={report.grid_size[0]} height={report.grid_size[1]} maxValue={maxValue} />
        <Heatmap values={sim[layer]} denominator={denominatorSim} label={t("movementSimulated")} width={report.grid_size[0]} height={report.grid_size[1]} maxValue={maxValue} />
      </div>
      <p className="text-muted-foreground">{t("movementScale", { max: formatDecimal(maxValue * 100, 1) })}</p>
      <p>{t("movementRetained", { seconds: formatDecimal(real.observed_seconds, 1), gaps: real.excluded_gaps, excluded: formatDecimal(real.excluded_seconds, 1) })}</p>
      <table className="w-full text-left tabular-nums">
        <caption className="mb-1 text-left font-medium">{t("movementLargestGaps")}</caption>
        <thead><tr><th>{t("movementCell")}</th><th>{t("movementReal")}</th><th>{t("movementSim")}</th><th>{t("movementGap")}</th></tr></thead>
        <tbody>{report.largest_gaps.slice(0, 5).map((g) => <tr key={`${g.x},${g.y}`}>
          <td>({g.x}, {g.y})</td><td>{formatPercent(g.observed_visit_rate, 1)}</td><td>{formatPercent(g.simulated_visit_rate, 1)}</td>
          <td>{g.difference > 0 ? "+" : ""}{formatDecimal(100 * g.difference, 1)}</td>
        </tr>)}</tbody>
      </table>
      <details className="text-muted-foreground"><summary>{t("movementAssumptions")}</summary>
        <ul className="list-disc space-y-1 pl-4">{report.notes.map((note, i) => <li key={i}>{note}</li>)}</ul>
        <p className="mt-1">{t("movementChecked", { date: checkedAt(report.created_at, locale), seconds: String(report.max_gap_seconds) })}</p>
      </details>
    </div>}
  </section>;
}
