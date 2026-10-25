/**
 * One shopper's visits to two stores of a run played together: the same person on the same random draws, so the
 * visits match until a difference between the stores makes them part ways, and the step where that happens is marked.
 */
import { useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { GitFork, RotateCcw } from "lucide-react";
import { getSession, onlineKeys } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import { JourneyPlayer } from "./JourneyPlayer";
import { partingStep } from "./parting";
import { OUTCOME_LABELS } from "./labels";

export function SideBySide({ projectId, runId, shopperId, stores, names, money }: {
  projectId: string; runId: string; shopperId: string; stores: [number, number]; names: string[];
  money: (amount: number) => string;
}) {
  const { t } = useI18n();
  const views = useQueries({
    queries: stores.map((variant) => ({
      queryKey: onlineKeys.session(projectId, runId, variant, shopperId),
      queryFn: ({ signal }: { signal: AbortSignal }) => getSession(projectId, runId, variant, shopperId, signal),
    })),
  });
  const [indices, setIndices] = useState<[number, number]>([0, 0]);
  const [round, setRound] = useState(0);  // a new round restarts both players together
  const failed = views.find((v) => v.isError);
  if (failed?.error) return <p role="alert" className="text-sm text-destructive">{failed.error.message}</p>;
  const [left, right] = views.map((v) => v.data);
  if (!left || !right) return <p className="text-sm text-muted-foreground">{t("studioLoading")}</p>;
  const part = partingStep(left.session.steps, right.session.steps);
  const start = (at: number) => { setIndices([at, at]); setRound((r) => r + 1); };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-muted/40 p-2 text-xs">
        <GitFork className="size-4 text-primary" aria-hidden />
        <span className="font-medium">{part === null ? t("onSideSame") : t("onSideParts", { step: part + 1 })}</span>
        {part !== null && part > 0 && (
          <Button size="xs" variant="outline" onClick={() => start(Math.max(0, part - 1))}>{t("onSideJump")}</Button>
        )}
        <Button size="xs" variant="ghost" onClick={() => start(0)}><RotateCcw aria-hidden /> {t("onPlayRestart")}</Button>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {[left, right].map((view, side) => (
          <section key={`${side}:${round}`} aria-label={names[stores[side]!]} className="min-w-0 space-y-1">
            {/* One line on both sides, so the two players stay level. */}
            <div className="flex items-baseline gap-2 text-xs">
              <span className="min-w-0 truncate text-sm font-semibold" title={names[stores[side]!]}>{names[stores[side]!]}</span>
              <span className={cn("shrink-0 rounded px-1.5", view.session.outcome === "purchased" ? "tone-good" : "bg-muted")}>
                {t(OUTCOME_LABELS[view.session.outcome])}{view.session.order_total ? ` · ${money(view.session.order_total)}` : ""}
              </span>
              {part !== null && indices[side]! >= part && <span className="shrink-0 rounded bg-amber-500/15 px-1.5 font-medium">{t("onSideApart")}</span>}
            </div>
            <JourneyPlayer projectId={projectId} runId={runId} view={view} index={Math.min(indices[side]!, view.session.steps.length - 1)}
              onIndex={(i) => setIndices((prev) => (side === 0 ? [i, prev[1]] : [prev[0], i]))} money={money} rival="" onRival={() => {}} />
          </section>
        ))}
      </div>
    </div>
  );
}
