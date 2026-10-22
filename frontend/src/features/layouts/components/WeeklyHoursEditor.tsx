import { useI18n } from "@/shared/i18n/i18n";
import { weekdayLong } from "@/shared/i18n/timeFormat";
import type { DaySchedule } from "@/shared/types/domain";

export function WeeklyHoursEditor({ hours, onChange }: { hours: DaySchedule[]; onChange: (hours: DaySchedule[]) => void }) {
  const { t, locale } = useI18n();
  const openCount = hours.filter((entry) => entry.is_open).length;
  const update = (day: number, patch: Partial<DaySchedule>) => onChange(hours.map((entry) => entry.day === day ? { ...entry, ...patch } : entry));
  return <div className="space-y-3">
    {[...hours].sort((a, b) => a.day - b.day).map((entry) => <div key={entry.day} className="space-y-1 rounded border p-2">
      <label className="flex items-center gap-2"><input type="checkbox" aria-label={weekdayLong(entry.day, locale)} checked={entry.is_open}
        disabled={entry.is_open && openCount === 1} onChange={(event) => update(entry.day, { is_open: event.target.checked })} />
        {weekdayLong(entry.day, locale)}{!entry.is_open && <span className="text-muted-foreground">{t("hoursClosed")}</span>}
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="space-y-1">{t("templateOpens")}
          <input type="number" min={0} max={23} step={1} aria-label={t("templateDayOpening", { day: weekdayLong(entry.day, locale) })}
            className="w-full rounded border bg-background px-2 py-1.5 disabled:opacity-50" disabled={!entry.is_open}
            value={Number.isFinite(entry.open_hour) ? entry.open_hour : ""} onChange={(event) => update(entry.day, { open_hour: event.target.value === "" ? NaN : Number(event.target.value) })} />
        </label>
        <label className="space-y-1">{t("templateCloses")}
          <input type="number" min={1} max={24} step={1} aria-label={t("templateDayClosing", { day: weekdayLong(entry.day, locale) })}
            className="w-full rounded border bg-background px-2 py-1.5 disabled:opacity-50" disabled={!entry.is_open}
            value={Number.isFinite(entry.close_hour) ? entry.close_hour : ""} onChange={(event) => update(entry.day, { close_hour: event.target.value === "" ? NaN : Number(event.target.value) })} />
        </label>
      </div>
    </div>)}
    <p className="text-muted-foreground">{t("templateWeekdayHint")}</p>
  </div>;
}
