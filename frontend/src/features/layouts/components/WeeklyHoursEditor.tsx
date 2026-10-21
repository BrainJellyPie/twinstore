import type { DaySchedule } from "@/shared/types/domain";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function WeeklyHoursEditor({ hours, onChange }: { hours: DaySchedule[]; onChange: (hours: DaySchedule[]) => void }) {
  const openCount = hours.filter((entry) => entry.is_open).length;
  const update = (day: number, patch: Partial<DaySchedule>) => onChange(hours.map((entry) => entry.day === day ? { ...entry, ...patch } : entry));
  return <div className="space-y-3">
    {[...hours].sort((a, b) => a.day - b.day).map((entry) => <div key={entry.day} className="space-y-1 rounded border p-2">
      <label className="flex items-center gap-2"><input type="checkbox" aria-label={WEEKDAYS[entry.day - 1]} checked={entry.is_open}
        disabled={entry.is_open && openCount === 1} onChange={(event) => update(entry.day, { is_open: event.target.checked })} />
        {WEEKDAYS[entry.day - 1]}{!entry.is_open && <span className="text-muted-foreground">Closed</span>}
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="space-y-1">Opens
          <input type="number" min={0} max={23} step={1} aria-label={`${WEEKDAYS[entry.day - 1]} opening hour`}
            className="w-full rounded border bg-background px-2 py-1.5 disabled:opacity-50" disabled={!entry.is_open}
            value={Number.isFinite(entry.open_hour) ? entry.open_hour : ""} onChange={(event) => update(entry.day, { open_hour: event.target.value === "" ? NaN : Number(event.target.value) })} />
        </label>
        <label className="space-y-1">Closes
          <input type="number" min={1} max={24} step={1} aria-label={`${WEEKDAYS[entry.day - 1]} closing hour`}
            className="w-full rounded border bg-background px-2 py-1.5 disabled:opacity-50" disabled={!entry.is_open}
            value={Number.isFinite(entry.close_hour) ? entry.close_hour : ""} onChange={(event) => update(entry.day, { close_hour: event.target.value === "" ? NaN : Number(event.target.value) })} />
        </label>
      </div>
    </div>)}
    <p className="text-muted-foreground">Each open day needs a closing hour later than its opening hour. Use 0–24 for all-day opening. Overnight hours are not supported. Keep at least one open weekday.</p>
  </div>;
}
