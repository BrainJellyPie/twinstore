// Completed runs of a draft layout, so previews stay reachable while editing.

import { Eye } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { useRuns } from "@/shared/queries/useRuns";
import { useSimulationStore } from "@/stores/simulationStore";
import { currencyCode, formatMoney, formatPercent } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";

import { focusPlayWhenShown } from "@/features/playback/focusPlay";

import { runLabel } from "../labels";

export function PreviewRunsList({ projectId, setupId }: { projectId: string; setupId: string }) {
  const { locale, t } = useI18n();
  const runs = useRuns(projectId, setupId).data
    .filter((r) => r.status === "completed")
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 6);
  const setViewRunId = useSimulationStore((s) => s.setViewRunId);
  if (runs.length === 0) return null;

  return (
    <section className="flex flex-col gap-2 rounded-lg border bg-card p-4 text-sm">
      <h3 className="text-sm font-medium">{t("previousRuns")}</h3>
      <ul className="flex flex-col gap-1.5">
        {runs.map((r) => {
          const s = r.summary;
          const code = currencyCode(s?.currency);
          return (
            <li key={r.run_id} className="flex items-center justify-between gap-2 rounded-md border px-2 py-1.5">
              <div className="min-w-0">
                <div className="truncate text-xs font-medium">{runLabel(r, locale)}</div>
                {s?.conversion_rate !== undefined && (
                  <div className="text-xs tabular-nums text-muted-foreground">
                    {t("previousRunLine", { conversion: formatPercent(s.conversion_rate, 0), perVisitor: formatMoney(s.revenue_per_visitor ?? 0, code) })}
                  </div>
                )}
              </div>
              <Button size="sm" variant="outline" className="h-7 shrink-0 gap-1 px-2 text-xs" aria-label={t("previousRunViewName", { run: runLabel(r, locale) })}
                onClick={() => { setViewRunId(r.run_id); focusPlayWhenShown(); }}>
                <Eye className="size-3" /> {t("previousRunView")}
              </Button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
