// What the vision-language shoppers looked at and decided — shown for vision runs only.
// Lets a reviewer judge the model at a glance: how often it named a product, how tempted
// it said shoppers were, whether its answers mapped to real shelf products, and its reasons.

import { Eye } from "lucide-react";

import { formatPercent } from "@/shared/utils/money";

import { useRunDiagnostics } from "../hooks";

const LEVEL_NAMES: Record<string, string> = { "4": "Top", "3": "Eye level", "2": "Waist", "1": "Bottom" };

export function VisionGlancesSection({ projectId, runId }: { projectId: string; runId: string }) {
  const meta = useRunDiagnostics(projectId, runId).data?.engine_meta;
  if (!meta || meta.glances === undefined) return null;

  const glances = meta.glances ?? 0;
  const resolved = meta.resolved_by ?? {};
  const answered = glances - (meta.errors ?? 0);
  const mapped = (resolved.name ?? 0) + (resolved.number ?? 0);
  const levels = meta.picked_level ?? {};
  const levelTotal = Object.values(levels).reduce((a, b) => a + b, 0);

  const tiles: { label: string; value: string; hint: string }[] = [
    { label: "Shelf glances", value: glances.toLocaleString(), hint: `${meta.errors ?? 0} failed` },
    { label: "Noticed something", value: formatPercent(meta.noticed_rate ?? 0, 0), hint: "of answered glances" },
    {
      label: "Mean interest",
      value: `${(meta.mean_interest ?? 0).toFixed(1)} / 10`,
      hint: `buy scale ${meta.buy_scale ?? "—"}`,
    },
    {
      label: "Mapped to shelf",
      value: answered > 0 ? formatPercent(mapped / Math.max(1, mapped + (resolved.invalid ?? 0)), 0) : "—",
      hint: `${resolved.name ?? 0} by name · ${resolved.number ?? 0} by #`,
    },
  ];

  return (
    <section className="border-t px-3 py-3 text-xs">
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-medium">
        <Eye className="size-4" aria-hidden /> Vision shoppers
        {meta.model && <span className="truncate font-normal text-muted-foreground">· {meta.model}</span>}
      </h3>
      <div className="grid grid-cols-2 gap-2">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-md border px-2 py-1.5">
            <div className="text-muted-foreground">{t.label}</div>
            <div className="text-base font-semibold tabular-nums">{t.value}</div>
            <div className="truncate text-xs text-muted-foreground">{t.hint}</div>
          </div>
        ))}
      </div>

      {levelTotal > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-muted-foreground">Picks by shelf level</div>
          <ul className="space-y-1">
            {["4", "3", "2", "1"].map((lvl) => {
              const n = levels[lvl] ?? 0;
              return (
                <li key={lvl} className="grid grid-cols-[72px_1fr_32px] items-center gap-2">
                  <span>{LEVEL_NAMES[lvl]}</span>
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
          <div className="mb-1 text-muted-foreground">What caught their eye</div>
          <ul className="space-y-1.5">
            {meta.examples!.map((g, i) => (
              <li key={`${g.persona_id}-${g.rack}-${i}`} className="rounded-md bg-muted/40 px-2 py-1.5">
                <div className="flex justify-between gap-2">
                  <span className="truncate font-medium">{g.product || "—"}</span>
                  <span className={g.outcome === "buy" ? "shrink-0 text-positive" : "shrink-0 text-muted-foreground"}>
                    {g.outcome === "buy" ? "bought" : "looked"}
                  </span>
                </div>
                <div className="truncate text-muted-foreground" title={g.reason}>
                  {g.rack} · {g.reason || "no reason given"}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
