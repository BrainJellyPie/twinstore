// The same customer in the online twin: on a physical-store shopper's page, the visits online shoppers made from this
// customer paid to web shops, each one click from its replay.

import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Globe2, Play } from "lucide-react";

import { getPersonaVisits, onlineKeys } from "@/shared/api/online";
import { cn } from "@/shared/utils/cn";
import { formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";

import { OUTCOME_COLORS, OUTCOME_LABELS } from "./labels";

export function PersonaOnlineVisits({ projectId, personaId }: { projectId: string; personaId: string }) {
  const { t } = useI18n();
  const visits = useQuery({
    queryKey: onlineKeys.personaVisits(projectId, personaId),
    queryFn: ({ signal }) => getPersonaVisits(projectId, personaId, signal),
    staleTime: 30_000,
  });
  if (!visits.data?.length) return null;
  return (
    <section className="rounded-2xl border bg-card p-3" aria-label={t("onPersonaVisitsTitle")}>
      <div className="flex items-center gap-1.5 text-sm font-semibold"><Globe2 className="size-4 text-primary" aria-hidden />{t("onPersonaVisitsTitle")}</div>
      <p className="mb-2 text-[0.7rem] text-muted-foreground">{t("onPersonaVisitsHint")}</p>
      <ul className="space-y-1">
        {visits.data.slice(0, 8).map((v) => (
          <li key={`${v.run_id}:${v.variant}`}>
            <Link to="/online/$pid" params={{ pid: projectId }} search={{ run: v.run_id, shopper: v.shopper_id, variant: v.variant }}
              className="flex items-center gap-2 rounded-xl border bg-card/60 px-2.5 py-1.5 text-xs transition-colors hover:border-primary/50">
              <span className={cn("size-2 shrink-0 rounded-full", OUTCOME_COLORS[v.outcome])} aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{v.site_name}</span>
                <span className="block truncate text-[0.68rem] text-muted-foreground">{v.run_name}</span>
              </span>
              <span className="shrink-0 text-right">
                {t(OUTCOME_LABELS[v.outcome])}{v.order_total > 0 ? ` · ${formatMoney(v.order_total, v.currency)}` : ""}
              </span>
              <Play className="size-3.5 shrink-0 text-primary" aria-label={t("onPersonaVisitsWatch")} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
