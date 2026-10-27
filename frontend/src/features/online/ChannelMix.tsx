// The same customers in both twins: for a run whose shoppers are the store's customers, who bought in the newest
// store run of those customers, online, in both or in neither, what they spent in each, and the split by age and gender.

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { ArrowUpRight, Loader2 } from "lucide-react";

import { getChannelMix, onlineKeys, type ChannelGroup } from "@/shared/api/online";
import { currencyCode, formatMoney, formatPercent } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { personaLabel } from "@/shared/i18n/personaLabels";
import { useSimulationStore } from "@/stores/simulationStore";

type Cell = "both" | "store_only" | "online_only" | "neither";
const CELLS: { key: Cell; label: MessageKey; color: string }[] = [
  { key: "both", label: "onChBoth", color: "var(--viz-3)" },
  { key: "store_only", label: "onChStore", color: "var(--viz-1)" },
  { key: "online_only", label: "onChOnline", color: "var(--viz-2)" },
  { key: "neither", label: "onChNeither", color: "var(--viz-other)" },
];

export function ChannelMix({ projectId, runId }: { projectId: string; runId: string }) {
  const { t, locale } = useI18n();
  const navigate = useNavigate();
  const mix = useQuery({ queryKey: onlineKeys.channels(projectId, runId), queryFn: ({ signal }) => getChannelMix(projectId, runId, signal) });
  if (mix.isPending) return <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><Loader2 className="size-3.5 animate-spin" aria-hidden /> {t("studioLoading")}</p>;
  if (mix.isError) return <p role="alert" className="text-xs text-destructive">{mix.error.message}</p>;
  const m = mix.data;
  if (!m) return <p className="text-xs text-muted-foreground">{t("onChNoStoreRun")}</p>;
  const pct = (n: number, of: number) => formatPercent(n / Math.max(1, of), 0);
  const sameCurrency = m.store_currency === m.online_currency;
  const spend = [
    { label: t("onChSpendStore"), amount: m.store_spend, currency: m.store_currency, color: "var(--viz-1)" },
    { label: t("onChSpendOnline"), amount: m.online_spend, currency: m.online_currency, color: "var(--viz-2)" },
  ];
  const top = Math.max(1, ...spend.map((s) => s.amount));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p className="text-xs text-muted-foreground">
          {t("onChFrom", { date: m.store_run_at ? new Date(m.store_run_at).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" }) : m.store_run_id, store: m.online_store, count: m.customers })}
        </p>
        {/* The other twin's side of the comparison: that store run's results on its layout. */}
        {m.store_setup_id && (
          <button type="button" className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            onClick={() => {
              const store = useSimulationStore.getState();
              store.setSelectedSetupId(m.store_setup_id);
              store.setViewRunId(m.store_run_id);
              store.setActiveTab("dashboard");
              void navigate({ to: "/projects/$pid", params: { pid: projectId } });
            }}>
            {t("onChOpenStoreRun")} <ArrowUpRight className="size-3.5" aria-hidden />
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="grid grid-cols-2 gap-2 self-start">
          {CELLS.map((c) => (
            <div key={c.key} className="relative overflow-hidden rounded-2xl border bg-card/60 p-3">
              <span className="absolute inset-y-0 left-0 w-1" style={{ background: c.color }} aria-hidden />
              <div className="font-display text-3xl leading-none tabular-nums">{m[c.key]}</div>
              <div className="mt-1 text-xs font-medium">{t(c.label)}</div>
              <div className="text-[0.7rem] text-muted-foreground tabular-nums">{pct(m[c.key], m.customers)}</div>
            </div>
          ))}
        </div>
        <div className="space-y-4">
          <div className="space-y-1.5">
            {spend.map((s) => (
              <div key={s.label} className="grid grid-cols-[minmax(6rem,9rem)_1fr_auto] items-center gap-2 text-xs">
                <span className="text-muted-foreground">{s.label}</span>
                {sameCurrency
                  ? <span className="h-2.5 rounded-r-[4px]" style={{ width: `${Math.max(1, (s.amount / top) * 100)}%`, background: s.color }} aria-hidden />
                  : <span />}
                <span className="font-medium tabular-nums">{formatMoney(s.amount, currencyCode(s.currency))}</span>
              </div>
            ))}
          </div>
          <Split title={t("onChByAge")} groups={m.by_age} label={(g) => personaLabel(g, t)} />
          <Split title={t("onChByGender")} groups={m.by_gender} label={(g) => personaLabel(g, t)} />
          <div className="flex flex-wrap gap-3 text-[0.7rem] text-muted-foreground">
            {CELLS.map((c) => <span key={c.key} className="inline-flex items-center gap-1"><i className="size-2.5 rounded-sm" style={{ background: c.color }} aria-hidden />{t(c.label)}</span>)}
          </div>
        </div>
      </div>
    </div>
  );
}

function Split({ title, groups, label }: { title: string; groups: ChannelGroup[]; label: (group: string) => string }) {
  const { t } = useI18n();
  if (groups.length < 2) return null;
  return (
    <div className="space-y-1">
      <div className="text-xs font-medium">{title}</div>
      {groups.map((g) => (
        <div key={g.group} className="grid grid-cols-[minmax(4rem,6rem)_1fr_2.5rem] items-center gap-2 text-xs">
          <span className="truncate text-muted-foreground">{label(g.group)}</span>
          <span className="flex h-3 gap-[2px]" role="img"
            aria-label={CELLS.map((c) => `${t(c.label)}: ${g[c.key]}`).join(" · ")}>
            {CELLS.filter((c) => g[c.key] > 0).map((c) => (
              <i key={c.key} className="h-full first:rounded-l-[4px] last:rounded-r-[4px]" title={`${t(c.label)}: ${g[c.key]}`}
                style={{ width: `${(g[c.key] / Math.max(1, g.customers)) * 100}%`, background: c.color }} />
            ))}
          </span>
          <span className="text-right text-muted-foreground tabular-nums">{g.customers}</span>
        </div>
      ))}
    </div>
  );
}
