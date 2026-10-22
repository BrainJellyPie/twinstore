// Model providers: paste an API key (stored on the backend machine only), point local servers at
// their endpoint, pick a default model and test the connection with a tiny text or image request.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Cloud, Eye, Loader2, Server, XCircle } from "lucide-react";

import * as api from "@/shared/api/client";
import type { ConnectionTest, ProviderStatus } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

export function ProvidersPanel() {
  const { t } = useI18n();
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.providers(),
    queryFn: ({ signal }) => api.getProviders(signal),
  });

  if (isLoading) return <p className="text-sm text-muted-foreground">{t("providersLoading")}</p>;
  if (error || !data) return <p className="text-sm text-destructive">{t("providersLoadFailed")}</p>;

  const cloud = data.filter((p) => !p.preset.local);
  const local = data.filter((p) => p.preset.local);
  return (
    <div className="space-y-8">
      <Section title={t("providersCloud")} icon={Cloud} providers={cloud} />
      <Section title={t("providersLocal")} icon={Server} providers={local} />
    </div>
  );
}

function Section({ title, icon: Icon, providers }: { title: string; icon: typeof Cloud; providers: ProviderStatus[] }) {
  return (
    <section>
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <Icon className="size-4" aria-hidden /> {title}
      </h2>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {providers.map((p) => (
          <ProviderCard key={p.preset.kind} status={p} />
        ))}
      </div>
    </section>
  );
}

function ProviderCard({ status }: { status: ProviderStatus }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { preset } = status;
  const [key, setKey] = useState("");
  const [base, setBase] = useState(status.api_base ?? "");
  const [model, setModel] = useState(status.default_model ?? preset.models[0]?.id ?? "");
  const [result, setResult] = useState<ConnectionTest | null>(null);

  const save = useMutation({
    mutationFn: (update: api.ProviderUpdate) => api.updateProvider(preset.kind, update),
    onSuccess: () => {
      setKey("");
      void qc.invalidateQueries({ queryKey: queryKeys.providers() });
      void qc.invalidateQueries({ queryKey: queryKeys.models() });
      void qc.invalidateQueries({ queryKey: queryKeys.engines() });
    },
  });
  const test = useMutation({
    mutationFn: (vision: boolean) => api.testModel(`${preset.kind}:${model}`, vision),
    onSuccess: setResult,
    onError: (e) => setResult({ ok: false, model, latency_ms: 0, reply: "", error: e.message, vision: false }),
    // A test can find the key turned down (or working again): refresh the badge and what runs can use.
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.providers() });
      void qc.invalidateQueries({ queryKey: queryKeys.models() });
      void qc.invalidateQueries({ queryKey: queryKeys.engines() });
    },
  });

  const badge = !status.enabled
    ? { text: preset.local ? t("providerOff") : t("providerDisabled"), cls: "bg-muted text-muted-foreground" }
    : status.key_rejected
      ? { text: t("providerKeyRejected"), cls: "tone-bad" }
      : status.ready && status.answers === false
        // An address saved earlier with nothing listening there now (a server stopped, or an older version's).
        ? { text: t("providerNotRunning"), cls: "tone-warn" }
      : status.ready
        ? { text: t("providerReady"), cls: "tone-good" }
        : preset.local
          ? { text: t("providerNeedsEndpoint"), cls: "tone-warn" }
          : { text: t("providerNeedsKey"), cls: "tone-warn" };
  const listId = `models-${preset.kind}`;

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-4 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-medium">{preset.label}</div>
          <div className="text-xs text-muted-foreground">
            {status.key_source === "env" && t("providerKeyFromEnv", { env: preset.api_key_env ?? "" })}
            {status.key_source === "settings" && t("providerKeyStored", { hint: status.key_hint })}
            {status.key_source === "none" && (preset.api_key_env ? t("providerOrSetEnv", { env: preset.api_key_env }) : "")}
            {status.key_source === "not needed" && t("providerNoKeyNeeded")}
          </div>
          {save.error && (
            <div role="alert" className="mt-1 break-words text-xs text-destructive">{save.error.message}</div>
          )}
          {status.key_rejected && (
            <div role="alert" className="mt-1 text-xs text-destructive">
              {t("providerKeyRejectedHint", { provider: preset.label })}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", badge.cls)}>{badge.text}</span>
          {preset.local && (
            <Button
              size="sm"
              variant={status.enabled ? "outline" : "default"}
              className="h-6 px-2 text-xs"
              onClick={() => save.mutate({ enabled: !status.enabled, ...(base ? { api_base: base } : {}) })}
            >
              {status.enabled ? t("providerTurnOff") : t("providerTurnOn")}
            </Button>
          )}
        </div>
      </div>

      {preset.needs_key || preset.kind === "vllm" || preset.kind === "custom" ? (
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (key.trim()) save.mutate({ api_key: key.trim() });
          }}
        >
          <Input
            type="password"
            autoComplete="off"
            placeholder={status.has_key ? t("providerReplaceKey") : t("providerPasteKey")}
            value={key}
            onChange={(e) => setKey(e.target.value)}
            className="h-8"
            aria-label={t("providerApiKey", { provider: preset.label })}
          />
          <Button type="submit" size="sm" className="h-8" disabled={!key.trim() || save.isPending}>
            {t("providerSave")}
          </Button>
          {status.key_source === "settings" && (
            <Button type="button" size="sm" variant="outline" className="h-8" onClick={() => save.mutate({ api_key: "" })}>
              {t("remove")}
            </Button>
          )}
        </form>
      ) : null}

      {(preset.default_api_base || preset.local) && (
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">{t("providerEndpoint")}</span>
          <div className="flex gap-2">
            <Input value={base} placeholder="http://host:port/v1" onChange={(e) => setBase(e.target.value)} className="h-8 font-mono text-xs" />
            <Button
              size="sm"
              variant="outline"
              className="h-8"
              disabled={save.isPending || base === (status.api_base ?? "")}
              onClick={() => save.mutate({ api_base: base })}
            >
              {t("providerSave")}
            </Button>
          </div>
        </label>
      )}

      <label className="flex flex-col gap-1 text-xs">
        <span className="text-muted-foreground">{t("model")}</span>
        <div className="flex gap-2">
          <Input list={listId} value={model} onChange={(e) => setModel(e.target.value)} className="h-8 font-mono text-xs" />
          <datalist id={listId}>
            {preset.models.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </datalist>
          <Button
            size="sm"
            variant="outline"
            className="h-8"
            disabled={!model || save.isPending || model === status.default_model}
            onClick={() => save.mutate({ default_model: model })}
            title={t("providerDefaultHint")}
          >
            {t("providerDefault")}
          </Button>
        </div>
      </label>

      <div className="flex flex-wrap gap-1">
        {preset.models.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => setModel(m.id)}
            className={cn(
              "flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs",
              m.id === model ? "border-primary bg-primary/5" : "hover:bg-muted",
            )}
          >
            {m.vision && <Eye className="size-3" aria-label={t("providerVision")} />}
            {m.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <Button size="sm" variant="secondary" className="h-7" disabled={!status.ready || !model || test.isPending} onClick={() => test.mutate(false)}>
          {test.isPending ? <Loader2 className="size-3 animate-spin" /> : null} {t("providerTest")}
        </Button>
        <Button size="sm" variant="secondary" className="h-7" disabled={!status.ready || !model || test.isPending} onClick={() => test.mutate(true)}>
          <Eye className="size-3" /> {t("providerTestVision")}
        </Button>
      </div>
      {result && (
        <p
          data-testid="provider-test-result"
          className={cn("flex min-w-0 items-start gap-1 text-xs", result.ok ? "text-positive" : "text-destructive")}
          title={result.error}
        >
          {result.ok ? <CheckCircle2 className="mt-px size-3.5 shrink-0" /> : <XCircle className="mt-px size-3.5 shrink-0" />}
          <span className="line-clamp-4 min-w-0 break-words">
            {result.ok ? `${t("providerTestOk", { latency: result.latency_ms })}${result.reply ? ` · "${result.reply}"` : ""}` : result.error || t("providerTestFailed")}
          </span>
        </p>
      )}
    </div>
  );
}
