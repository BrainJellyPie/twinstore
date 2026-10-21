// Which model(s) drive the synthetic shoppers of a run: the server default, one model from any
// connected provider, or an ensemble (mixture: each customer gets one model; vote: every model
// looks at each shelf and the majority wins).

import { Link } from "@tanstack/react-router";
import { Eye, Users } from "lucide-react";

import type { EngineType, EnsembleConfig } from "@/shared/api/client";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import { Button } from "@/shared/components/ui/button";
import { useAvailableModels } from "../hooks";
import { cn } from "@/shared/utils/cn";

export interface ModelChoice {
  kind: "default" | "single" | "ensemble";
  model?: string;
  ensemble?: EnsembleConfig;
  // Keep partially typed weights editable; only validated ensemble numbers reach the API.
  weightInputs?: Record<string, string>;
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
  const { t } = useI18n();
  const query = useAvailableModels();
  const models = query.data ?? [];
  const usable = engine === "vlm_glance" ? models.filter((m) => m.vision) : models;
  const members = value.ensemble?.members ?? [];
  const unavailableMembers = query.data ? members.filter((member) => !usable.some((model) => model.ref === member.model)) : [];
  const weightOf = (ref: string) => members.find((m) => m.model === ref)?.weight;

  const toggleMember = (ref: string) => {
    const next = weightOf(ref) !== undefined ? members.filter((m) => m.model !== ref) : [...members, { model: ref, weight: 1 }];
    const weightInputs = { ...value.weightInputs };
    delete weightInputs[ref];
    onChange({ kind: "ensemble", ensemble: { members: next, mode: value.ensemble?.mode ?? "mixture" }, weightInputs });
  };
  const setWeight = (ref: string, raw: string) =>
    onChange({
      kind: "ensemble",
      ensemble: {
        members: members.map((m) => (m.model === ref ? { ...m, weight: raw.trim() === "" ? NaN : Number(raw) } : m)),
        mode: value.ensemble?.mode ?? "mixture",
      },
      weightInputs: { ...value.weightInputs, [ref]: raw },
    });

  const tabs: { id: ModelChoice["kind"]; label: string }[] = [
    { id: "default", label: t("serverDefault") },
    { id: "single", label: t("oneModel") },
    { id: "ensemble", label: t("ensemble") },
  ];

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{t("model")}</div>
        <Link to="/settings" className="text-xs text-primary hover:underline">
          {t("connectProviders")}
        </Link>
      </div>
      <div className="flex max-w-full flex-wrap rounded-md border p-0.5 text-xs" role="group" aria-label={t("modelChoice")}>
        {tabs.map((option) => (
          <button
            key={option.id}
            type="button"
            aria-pressed={value.kind === option.id}
            onClick={() => {
              if (value.kind === option.id) return;
              onChange(
                option.id === "default"
                  ? { kind: "default" }
                  : option.id === "single"
                    ? { kind: "single", model: value.model ?? usable[0]?.ref }
                    : { kind: "ensemble", ensemble: value.ensemble ?? { members: [], mode: "mixture" } },
              );
            }}
            className={cn("rounded px-2.5 py-1", value.kind === option.id ? "bg-primary text-primary-foreground" : "hover:bg-muted")}
          >
            {option.label}
          </button>
        ))}
      </div>

      {value.kind === "default" && (
        <p className="text-xs text-muted-foreground">{defaultModel ? t("usesModel", { model: defaultModel }) : t("usesServerModel")}</p>
      )}

      {query.isError && (
        <div className="space-y-2 rounded-md border border-destructive/30 p-2 text-xs">
          <p role="alert" className="break-words">{query.error instanceof Error ? query.error.message : t("modelListError")}</p>
          <Button type="button" size="sm" variant="outline" onClick={() => { void query.refetch(); }} disabled={query.isFetching}>{t("retryModels")}</Button>
        </div>
      )}
      {value.kind !== "default" && query.isPending && <p role="status" className="text-xs text-muted-foreground">{t("loadingModels")}</p>}
      {value.kind !== "default" && query.data !== undefined && usable.length === 0 && (
        <p className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">{t(engine === "vlm_glance" ? "noVisionModels" : "noModels")}</p>
      )}

      {value.kind === "single" && (
        <select
          className="h-8 w-full rounded-md border bg-background px-2 text-sm"
          value={value.model ?? ""}
          onChange={(e) => onChange({ kind: "single", model: e.target.value })}
          aria-label={t("model")}
          aria-invalid={!value.model || !usable.some((model) => model.ref === value.model)}
          aria-describedby="run-model-error"
          disabled={query.isPending || usable.length === 0}
        >
          <option value="" disabled>{t("chooseModel")}</option>
          {value.model && !usable.some((model) => model.ref === value.model) && <option value={value.model} disabled>{t("unavailableModel", { model: value.model })}</option>}
          {usable.map((m) => (
            <option key={m.ref} value={m.ref}>
              {m.provider} · {m.label}
            </option>
          ))}
        </select>
      )}

      {value.kind === "ensemble" && unavailableMembers.map((member) => (
        <div key={member.model} className="flex items-start gap-2 rounded-md border border-destructive/30 p-2 text-xs">
          <span className="min-w-0 flex-1 break-all">{t("unavailableModel", { model: member.model })}</span>
          <Button type="button" size="sm" variant="outline" aria-label={t("removeModel", { model: member.model })} onClick={() => toggleMember(member.model)}>{t("remove")}</Button>
        </div>
      ))}

      {value.kind === "ensemble" && usable.length > 0 && (
        <div className="space-y-2">
          <button
            type="button"
            className="text-xs font-medium text-primary underline-offset-4 hover:underline"
            onClick={() => {
              // One model per provider, equal shares: every shopper is drawn at random from them.
              const perProvider = new Map<string, string>();
              for (const m of usable) if (!perProvider.has(m.provider)) perProvider.set(m.provider, m.ref);
              onChange({
                kind: "ensemble",
                ensemble: { members: [...perProvider.values()].map((ref) => ({ model: ref, weight: 1 })), mode: "mixture" },
              });
            }}
          >
            {t("mixProviders")}
          </button>
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
                    {m.vision && <Eye className="size-3 shrink-0 text-muted-foreground" aria-label={t("visionShoppers")} />}
                    <span className="truncate">{m.provider} · {m.label}</span>
                  </label>
                  {w !== undefined && (
                    <Input
                      type="number"
                      step="any"
                      min={0}
                      value={value.weightInputs?.[m.ref] ?? String(w)}
                      onChange={(e) => setWeight(m.ref, e.target.value)}
                      aria-invalid={!Number.isFinite(w) || w <= 0}
                      aria-describedby="run-model-error"
                      className="h-6 w-16 px-1.5 text-xs"
                      aria-label={t("modelWeight", { model: m.label })}
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
                onChange={() => onChange({ kind: "ensemble", ensemble: { members, mode: "mixture" }, weightInputs: value.weightInputs })}
              />
              {t("mixtureHint")}
            </label>
          </div>
          {engine === "vlm_glance" && (
            <label className="flex items-center gap-1 pl-6 text-xs">
              <input
                type="radio"
                name="ensemble-mode"
                checked={value.ensemble?.mode === "vote"}
                onChange={() => onChange({ kind: "ensemble", ensemble: { members, mode: "vote" }, weightInputs: value.weightInputs })}
              />
              {t("voteHint")}
            </label>
          )}
        </div>
      )}
    </div>
  );
}
