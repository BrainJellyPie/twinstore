import type { RunStatus } from "@/shared/api/client";

import { engineLabel } from "../labels";

function formatDuration(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) return "—";
  if (sec < 60) return `${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return m < 60 ? `${m}m ${s}s` : `${Math.floor(m / 60)}h ${m % 60}m`;
}

export function RunProgress({ status, now }: { status: RunStatus | undefined; now: number }) {
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
            ? "Starting simulation…"
            : done === 0
              ? "Preparing store model…"
              : "Simulating shoppers…"}
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {engineLabel(status?.engine_type)} engine{status?.preview ? " · preview" : ""}
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
          <dt className="text-muted-foreground">Customers</dt>
          <dd className="font-medium tabular-nums">
            {done.toLocaleString()} / {total.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Elapsed</dt>
          <dd className="font-medium tabular-nums">{formatDuration(elapsed)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Remaining</dt>
          <dd className="font-medium tabular-nums">{formatDuration(eta)}</dd>
        </div>
      </dl>
      {failed > 0 && (
        <p className="rounded-md border tone-warn px-2.5 py-1.5 text-sm">
          {failed} customer{failed === 1 ? "" : "s"} failed after retries — they are listed in the run diagnostics.
        </p>
      )}
    </div>
  );
}
