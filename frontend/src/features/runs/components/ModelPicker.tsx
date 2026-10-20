// Which model(s) drive the synthetic shoppers of a run: the server default, one model from any
// connected provider, or an ensemble (mixture: each customer gets one model; vote: every model
// looks at each shelf and the majority wins).

import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Eye, Users } from "lucide-react";

import * as api from "@/shared/api/client";
import type { EngineType, EnsembleConfig } from "@/shared/api/client";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";

export interface ModelChoice {
  kind: "default" | "single" | "ensemble";
  model?: string;
  ensemble?: EnsembleConfig;
}

export function ModelPicker({
  engine,
  defaultModel,
  value,
  onChange,
}: {
  engine: EngineType;
  defaultModel?: string;
  value: ModelChoice;
  onChange: (next: ModelChoice) => void;
}) {
  const { data: models = [] } = useQuery({
    queryKey: queryKeys.models(),
    queryFn: ({ signal }) => api.getModels(signal),
    staleTime: 60_000,
  });
  const usable = engine === "vlm_glance" ? models.filter((m) => m.vision) : models;
  const members = value.ensemble?.members ?? [];
  const weightOf = (ref: string) => members.find((m) => m.model === ref)?.weight;

  const toggleMember = (ref: string) => {
    const next = weightOf(ref) !== undefined ? members.filter((m) => m.model !== ref) : [...members, { model: ref, weight: 1 }];
    onChange({ kind: "ensemble", ensemble: { members: next, mode: value.ensemble?.mode ?? "mixture" } });
  };
  const setWeight = (ref: string, weight: number) =>
    onChange({
      kind: "ensemble",
      ensemble: {
        members: members.map((m) => (m.model === ref ? { ...m, weight: Math.max(0.1, weight) } : m)),
        mode: value.ensemble?.mode ?? "mixture",
      },
    });

  const tabs: { id: ModelChoice["kind"]; label: string }[] = [
    { id: "default", label: "Server default" },
    { id: "single", label: "One model" },
    { id: "ensemble", label: "Ensemble" },
  ];

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">Model</div>
        <Link to="/settings" className="text-xs text-primary hover:underline">
          Connect providers
        </Link>
      </div>
      <div className="inline-flex rounded-md border p-0.5 text-xs" role="tablist" aria-label="Model choice">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={value.kind === t.id}
            onClick={() =>
              onChange(
                t.id === "default"
                  ? { kind: "default" }
                  : t.id === "single"
                    ? { kind: "single", model: value.model ?? usable[0]?.ref }
                    : { kind: "ensemble", ensemble: value.ensemble ?? { members: [], mode: "mixture" } },
              )
            }
            className={cn("rounded px-2.5 py-1", value.kind === t.id ? "bg-primary text-primary-foreground" : "hover:bg-muted")}
          >
            {t.label}
          </button>
        ))}
      </div>

      {value.kind === "default" && (
        <p className="text-xs text-muted-foreground">{defaultModel ? `Uses ${defaultModel}.` : "Uses the server's configured model."}</p>
      )}

      {value.kind !== "default" && usable.length === 0 && (
        <p className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
          No {engine === "vlm_glance" ? "vision " : ""}models connected yet — add an API key or a local server in{" "}
          <Link to="/settings" className="text-primary hover:underline">Model providers</Link>.
        </p>
      )}

      {value.kind === "single" && usable.length > 0 && (
        <select
          className="h-8 w-full rounded-md border bg-background px-2 text-sm"
          value={value.model ?? ""}
          onChange={(e) => onChange({ kind: "single", model: e.target.value })}
          aria-label="Model"
        >
          {usable.map((m) => (
            <option key={m.ref} value={m.ref}>
              {m.provider} · {m.label}
            </option>
          ))}
        </select>
      )}

      {value.kind === "ensemble" && usable.length > 0 && (
        <div className="space-y-2">
          <ul className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-1.5">
            {usable.map((m) => {
              const w = weightOf(m.ref);
              return (
                <li key={m.ref} className="flex items-center gap-2 text-xs">
                  <input
                    id={`ens-${m.ref}`}
                    type="checkbox"
                    className="size-3.5 accent-primary"
                    checked={w !== undefined}
                    onChange={() => toggleMember(m.ref)}
                  />
                  <label htmlFor={`ens-${m.ref}`} className="flex min-w-0 flex-1 items-center gap-1 truncate">
                    {m.vision && <Eye className="size-3 shrink-0 text-muted-foreground" aria-label="vision" />}
                    <span className="truncate">{m.provider} · {m.label}</span>
                  </label>
                  {w !== undefined && (
                    <Input
                      type="number"
                      step={0.5}
                      min={0.1}
                      value={w}
                      onChange={(e) => setWeight(m.ref, Number(e.target.value) || 1)}
                      className="h-6 w-16 text-xs"
                      aria-label={`Weight of ${m.label}`}
                    />
                  )}
                </li>
              );
            })}
          </ul>
          <div className="flex items-center gap-3 text-xs">
            <Users className="size-3.5 text-muted-foreground" aria-hidden />
            <label className="flex items-center gap-1">
              <input
                type="radio"
                name="ensemble-mode"
                checked={(value.ensemble?.mode ?? "mixture") === "mixture"}
                onChange={() => onChange({ kind: "ensemble", ensemble: { members, mode: "mixture" } })}
              />
              Mixture — each shopper is one model (weights = population share)
            </label>
          </div>
          {engine === "vlm_glance" && (
            <label className="flex items-center gap-1 pl-6 text-xs">
              <input
                type="radio"
                name="ensemble-mode"
                checked={value.ensemble?.mode === "vote"}
                onChange={() => onChange({ kind: "ensemble", ensemble: { members, mode: "vote" } })}
              />
              Vote — every model looks at each shelf; majority decides
            </label>
          )}
        </div>
      )}
    </div>
  );
}
