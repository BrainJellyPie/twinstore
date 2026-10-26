// What the vision-language shoppers looked at and decided — shown for vision runs only.
// Lets a reviewer judge the model at a glance: how often it named a product, how tempted
// it said shoppers were, whether its answers mapped to real shelf products, and its reasons.

import { Camera, DoorOpen, Eye } from "lucide-react";

import { formatPercent, formatDecimal } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { useRunDiagnostics } from "../hooks";

const LEVEL_NAMES: Record<string, MessageKey> = { "4": "visionLevelTop", "3": "visionLevelEye", "2": "visionLevelWaist", "1": "visionLevelBottom" };

export function VisionGlancesSection({ projectId, runId }: { projectId: string; runId: string }) {
  const { locale, t } = useI18n();
  const meta = useRunDiagnostics(projectId, runId).data?.engine_meta;
  if (!meta || meta.glances === undefined) return null;

  const glances = meta.glances ?? 0;
  const resolved = meta.resolved_by ?? {};
  const answered = glances - (meta.errors ?? 0);
  const mapped = (resolved.name ?? 0) + (resolved.number ?? 0);
  const levels = meta.picked_level ?? {};
  const levelTotal = Object.values(levels).reduce((a, b) => a + b, 0);

  const tiles: { label: string; value: string; hint: string }[] = [
    { label: t("visionGlances"), value: glances.toLocaleString(locale), hint: t("visionFailed", { count: meta.errors ?? 0 }) },
    { label: t("visionNoticed"), value: formatPercent(meta.noticed_rate ?? 0, 0), hint: t("visionOfAnswered") },
    {
      label: t("visionInterest"),
      value: `${formatDecimal(meta.mean_interest ?? 0, 1)} / 10`,
      hint: t("visionBuyScale", { scale: meta.buy_scale ?? "—" }),
    },
    {
      label: t("visionMapped"),
      value: answered > 0 ? formatPercent(mapped / Math.max(1, mapped + (resolved.invalid ?? 0)), 0) : "—",
      hint: t("visionMappedHint", { byName: resolved.name ?? 0, byNumber: resolved.number ?? 0 }),
    },
  ];

  return (
    <section className="border-t px-3 py-3 text-xs">
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium">
        <Eye className="size-4" aria-hidden /> {t("visionShoppers")}
        {meta.model && <span className="truncate font-normal text-muted-foreground">· {meta.model}</span>}
      </h3>
      {meta.shelf_view === "photo_chart" && (
        <p className="mb-2 flex items-center gap-1.5 text-muted-foreground">
          <Camera className="size-3.5" aria-hidden />
          {t("visionPhotoChart", { shown: meta.views?.photo_chart ?? 0, glances })}
          {(meta.views?.chart ?? 0) > 0 && ` ${t("visionChartFallback")}`}
        </p>
      )}
      <div className="grid grid-cols-2 gap-2">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-md border px-2 py-1.5">
            <div className="text-muted-foreground">{t.label}</div>
            <div className="text-base font-semibold tabular-nums">{t.value}</div>
            <div className="truncate text-xs text-muted-foreground">{t.hint}</div>
          </div>
        ))}
      </div>

      {meta.planning && meta.plan_policy === "vlm" && (
        <div className="mt-3 rounded-md border p-2">
          <div className="mb-1 flex items-center gap-1.5 font-medium"><DoorOpen className="size-3.5" aria-hidden /> {t("visionAtDoor")}</div>
          <div className="grid grid-cols-3 gap-2 tabular-nums">
            <div><div className="text-muted-foreground">{t("visionWentIn")}</div><div className="text-sm font-semibold">{formatPercent(meta.planning.enter_rate, 0)}</div></div>
            <div><div className="text-muted-foreground">{t("visionItemsPlanned")}</div><div className="text-sm font-semibold">{formatDecimal(meta.planning.mean_items_named, 1)}</div></div>
            <div><div className="text-muted-foreground">{t("visionFoundOnShelf")}</div><div className="text-sm font-semibold">{formatPercent(meta.planning.resolution_rate, 0)}</div></div>
          </div>
          {meta.planning.plan_errors > 0 && (
            <div className="mt-1 text-warn">{t(meta.planning.plan_errors === 1 ? "visionPlanFallbackOne" : "visionPlanFallbackMany", { count: meta.planning.plan_errors })}</div>
          )}
          {(meta.plan_examples?.length ?? 0) > 0 && (
            <ul className="mt-2 space-y-1.5">
              {meta.plan_examples!.filter((p) => p.mission).slice(0, 4).map((p) => (
                <li key={p.persona_id} className="leading-snug">
                  <span className="font-medium">“{p.mission}”</span>
                  {p.items.length > 0 && <span className="text-muted-foreground"> — {p.items.map(([, prod, q]) => `${prod}${q > 1 ? ` ×${q}` : ""}`).join(", ")}</span>}
                  {!p.enter && <span className="text-warn"> {t("visionTurnedBack")}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {levelTotal > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-muted-foreground">{t("visionPicksByLevel")}</div>
          <ul className="space-y-1">
            {["4", "3", "2", "1"].map((lvl) => {
              const n = levels[lvl] ?? 0;
              return (
                <li key={lvl} className="grid grid-cols-[72px_1fr_32px] items-center gap-2">
                  <span>{t(LEVEL_NAMES[lvl]!)}</span>
                  <span className="h-1.5 rounded-full bg-muted">
                    <span
                      className="block h-1.5 rounded-full bg-primary"
                      style={{ width: `${(n / levelTotal) * 100}%` }}
                    />
                  </span>
                  <span className="text-right tabular-nums">{n}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {(meta.examples?.length ?? 0) > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-muted-foreground">{t("visionCaughtEye")}</div>
          <ul className="space-y-1.5">
            {meta.examples!.map((g, i) => (
              <li key={`${g.persona_id}-${g.rack}-${i}`} className="rounded-md bg-muted/40 px-2 py-1.5">
                <div className="flex justify-between gap-2">
                  <span className="truncate font-medium">{g.product || "—"}</span>
                  <span className={g.outcome === "buy" ? "shrink-0 text-positive" : "shrink-0 text-muted-foreground"}>
                    {g.outcome === "buy" ? t("visionBought") : t("visionLooked")}
                  </span>
                </div>
                <div className="truncate text-muted-foreground" title={g.reason}>
                  {g.rack} · {g.reason || t("visionNoReason")}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
