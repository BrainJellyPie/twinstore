import type { RunStatus } from "@/shared/api/client";

import { useI18n } from "@/shared/i18n/i18n";
import { translate } from "@/shared/i18n/translate";
import type { Locale } from "@/shared/i18n/messages";

import { engineLabel } from "../labels";

function formatDuration(sec: number, locale: Locale): string {
  if (!Number.isFinite(sec) || sec < 0) return "—";
  if (sec < 60) return translate(locale, "durationSeconds", { seconds: String(Math.round(sec)) });
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return m < 60 ? translate(locale, "durationMinutesSeconds", { minutes: String(m), seconds: String(s) })
    : translate(locale, "durationHoursMinutes", { hours: String(Math.floor(m / 60)), minutes: String(m % 60) });
}

export function RunProgress({ status, now }: { status: RunStatus | undefined; now: number }) {
  const { locale, t } = useI18n();
  const total = status?.total_customers ?? 0;
  const done = status?.completed_customers ?? 0;
  const failed = status?.failed_customers ?? 0;
  const ratio = total > 0 ? Math.min(1, done / total) : 0;
  const started = status?.started_at ? Date.parse(status.started_at) : NaN;
  const elapsed = Number.isNaN(started) ? NaN : (now - started) / 1000;
  const eta = done > 0 && ratio < 1 ? (elapsed / done) * (total - done) : NaN;

  return (
    <div className="flex flex-col gap-3 px-1 pt-8 pb-6">
      <div className="text-center">
        <div className="text-sm font-medium">
          {status?.status === "pending"
            ? t("progressStarting")
            : done === 0
              ? t("progressPreparing")
              : t("progressSimulating")}
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {t("progressEngine", { engine: engineLabel(status?.engine_type, locale) })}{status?.preview ? ` · ${t("runLabelPreview")}` : ""}
        </div>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={done}
      >
        <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${ratio * 100}%` }} />
      </div>
      <dl className="grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <dt className="text-muted-foreground">{t("customers")}</dt>
          <dd className="font-medium tabular-nums">
            {done.toLocaleString(locale)} / {total.toLocaleString(locale)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("progressElapsed")}</dt>
          <dd className="font-medium tabular-nums">{formatDuration(elapsed, locale)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{t("progressRemaining")}</dt>
          <dd className="font-medium tabular-nums">{formatDuration(eta, locale)}</dd>
        </div>
      </dl>
      {failed > 0 && (
        <p className="rounded-md border tone-warn px-2.5 py-1.5 text-sm">
          {t(failed === 1 ? "progressFailedOne" : "progressFailedMany", { count: failed })}
        </p>
      )}
    </div>
  );
}
