// Send virtual shoppers through one store, or compare up to four variants on the very same shoppers.

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play } from "lucide-react";

import { ModelPicker, type ModelChoice } from "@/features/runs/components/ModelPicker";
import { useAvailableModels } from "@/features/runs/hooks";
import { MISSIONS, onlineKeys, startRun, type ShopperMission, type ShopperPolicyKind, type SiteSummary } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

import { MISSION_HINTS, MISSION_LABELS, POLICY_HINTS, POLICY_LABELS } from "./labels";

const MAX_VARIANTS = 4;
const DEFAULT_MIX: Record<ShopperMission, number> = { purchase: 25, browse: 35, compare: 15, deal_hunt: 10, gift: 7, replenish: 8 };
// Pages a session typically takes, for the estimate of model calls (rule runs make none).
const TYPICAL_STEPS = 11;

export function RunLauncher({ projectId, sites, firstSiteId, hasCustomers, onStarted }: {
  projectId: string; sites: SiteSummary[]; firstSiteId: string; hasCustomers: boolean; onStarted: (runId: string) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [chosen, setChosen] = useState<string[]>([firstSiteId]);
  const [shoppers, setShoppers] = useState(30);
  const [policy, setPolicy] = useState<ShopperPolicyKind>("rule");
  const [model, setModel] = useState<ModelChoice>({ kind: "default" });
  const [seed, setSeed] = useState(1);
  const [maxSteps, setMaxSteps] = useState(24);
  const [mix, setMix] = useState(DEFAULT_MIX);
  const [mobile, setMobile] = useState(55);
  const [source, setSource] = useState<"panel" | "project">("panel");
  const [imageWidth, setImageWidth] = useState(896);
  const [shuffle, setShuffle] = useState(true);
  const [name, setName] = useState("");
  const mixTotal = Object.values(mix).reduce((a, b) => a + b, 0);
  const sessions = shoppers * chosen.length;
  const models = useAvailableModels(policy !== "rule");
  const available = models.data?.filter((m) => policy !== "vlm" || m.vision);
  let modelError: string | null = null;
  if (policy !== "rule" && model.kind !== "default") {
    if (!available) modelError = t(models.isError ? "onRunModelsFailed" : "loadingModels");
    else if (model.kind === "single") {
      modelError = !model.model ? t("onRunChooseModel")
        : available.some((m) => m.ref === model.model) ? null : t("onRunModelUnavailable");
    } else {
      const members = model.ensemble?.members ?? [];
      if (!members.length) modelError = t("onRunNeedEnsemble");
      else if (members.some((member) => !available.some((m) => m.ref === member.model))) modelError = t("onRunModelUnavailable");
      else if (members.some((member) => !Number.isFinite(member.weight) || member.weight <= 0)) modelError = t("invalidWeights");
    }
  }

  const start = useMutation({
    mutationFn: () => startRun(projectId, {
      site_ids: chosen, name: name.trim() || undefined, shoppers, policy, seed, max_steps: maxSteps,
      missions: Object.fromEntries(MISSIONS.map((m) => [m, mix[m] / 100])) as Record<ShopperMission, number>,
      mobile_share: mobile / 100, source, image_width: imageWidth, shuffle_marks: shuffle,
      model: policy !== "rule" && model.kind === "single" ? model.model ?? null : null,
      ensemble: policy !== "rule" && model.kind === "ensemble" && model.ensemble?.members.length ? model.ensemble : null,
    }),
    onSuccess: (status) => {
      void qc.invalidateQueries({ queryKey: onlineKeys.runs(projectId) });
      onStarted(status.run_id);
    },
  });
  const toggleSite = (id: string) =>
    setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= MAX_VARIANTS ? c : [...c, id]));

  return (
    <div className="grid gap-3 xl:grid-cols-2">
      <section className="panel flex flex-col gap-3 rounded-[1.4rem] p-4 text-sm">
        <h3 className="font-semibold">{t("onRunStores")}</h3>
        <p className="text-xs text-muted-foreground">{t("onRunStoresHint", { max: MAX_VARIANTS })}</p>
        <ul className="space-y-1">
          {sites.map((s) => {
            const index = chosen.indexOf(s.id);
            return (
              <li key={s.id}>
                <label className={cn("flex items-center gap-2 rounded-lg border px-2 py-1.5", index >= 0 && "border-primary bg-primary/5")}>
                  <input type="checkbox" checked={index >= 0} onChange={() => toggleSite(s.id)}
                    disabled={index < 0 && chosen.length >= MAX_VARIANTS} />
                  <span className="size-3 shrink-0 rounded-full" style={{ background: s.theme_color }} aria-hidden />
                  <span className="min-w-0 flex-1 truncate">{s.name}</span>
                  {index >= 0 && (
                    <span className="rounded bg-muted px-1.5 text-[0.7rem]">
                      {index === 0 ? t("onControl") : t("onVariantLetter", { letter: String.fromCharCode(65 + index) })}
                    </span>
                  )}
                </label>
              </li>
            );
          })}
        </ul>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-muted-foreground">{t("onRunName")}</span>
          <Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
        </label>
      </section>

      <section className="panel flex flex-col gap-3 rounded-[1.4rem] p-4 text-sm">
        <h3 className="font-semibold">{t("onRunWho")}</h3>
        <div className="grid grid-cols-3 gap-2 text-xs">
          <label className="flex flex-col gap-1"><span className="text-muted-foreground">{t("onRunShoppers")}</span>
            <Input type="number" min={1} max={500} value={shoppers} onChange={(e) => setShoppers(Math.min(500, Math.max(1, Number(e.target.value) || 1)))} /></label>
          <label className="flex flex-col gap-1"><span className="text-muted-foreground">{t("onRunSeed")}</span>
            <Input type="number" value={seed} onChange={(e) => setSeed(Math.trunc(Number(e.target.value) || 0))} /></label>
          <label className="flex flex-col gap-1"><span className="text-muted-foreground">{t("onRunMaxSteps")}</span>
            <Input type="number" min={3} max={80} value={maxSteps} onChange={(e) => setMaxSteps(Math.min(80, Math.max(3, Number(e.target.value) || 3)))} /></label>
        </div>
        <fieldset className="space-y-1">
          <legend className="text-xs font-medium">{t("onRunMissions")}</legend>
          <p className="text-[0.7rem] text-muted-foreground">{t("onRunMissionsHint")}</p>
          {MISSIONS.map((m) => (
            <label key={m} className="grid grid-cols-[110px_minmax(0,1fr)_40px] items-center gap-2 text-xs" title={t(MISSION_HINTS[m])}>
              <span>{t(MISSION_LABELS[m])}</span>
              <input type="range" min={0} max={100} value={mix[m]} onChange={(e) => setMix((x) => ({ ...x, [m]: Number(e.target.value) }))} aria-label={t(MISSION_LABELS[m])} />
              <span className="text-right tabular-nums">{mixTotal ? Math.round((mix[m] / mixTotal) * 100) : 0}%</span>
            </label>
          ))}
        </fieldset>
        <label className="grid grid-cols-[110px_minmax(0,1fr)_40px] items-center gap-2 text-xs">
          <span>{t("onRunMobile")}</span>
          <input type="range" min={0} max={100} value={mobile} onChange={(e) => setMobile(Number(e.target.value))} aria-label={t("onRunMobile")} />
          <span className="text-right tabular-nums">{mobile}%</span>
        </label>
        <fieldset className="flex flex-wrap gap-3 text-xs">
          <legend className="mb-1 w-full font-medium">{t("onRunSource")}</legend>
          <label className="flex items-center gap-1"><input type="radio" checked={source === "panel"} onChange={() => setSource("panel")} /> {t("onRunSourcePanel")}</label>
          <label className={cn("flex items-center gap-1", !hasCustomers && "opacity-50")}>
            <input type="radio" checked={source === "project"} disabled={!hasCustomers} onChange={() => setSource("project")} /> {t("onRunSourceProject")}
          </label>
        </fieldset>
      </section>

      <section className="panel flex flex-col gap-3 rounded-[1.4rem] p-4 text-sm xl:col-span-2">
        <h3 className="font-semibold">{t("onRunHow")}</h3>
        <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label={t("onRunHow")}>
          {(["rule", "vlm", "text"] as ShopperPolicyKind[]).map((p) => (
            <button key={p} type="button" role="radio" aria-checked={policy === p} onClick={() => setPolicy(p)}
              className={cn("rounded-xl border p-3 text-left", policy === p ? "border-primary bg-primary/8 ring-2 ring-primary/25" : "hover:bg-muted")}>
              <span className="block font-medium">{t(POLICY_LABELS[p])}</span>
              <span className="block text-xs text-muted-foreground">{t(POLICY_HINTS[p])}</span>
            </button>
          ))}
        </div>
        {policy !== "rule" && (
          <>
            <ModelPicker engine={policy === "vlm" ? "vlm_glance" : "pattern_intent_impulse"} value={model} onChange={setModel} allowVote={false} />
            {modelError && <p id="run-model-error" role="alert" className="text-xs text-destructive">{modelError}</p>}
            <div className="flex flex-wrap items-center gap-4 text-xs">
              {policy === "vlm" && (
                <label className="flex items-center gap-2">{t("onRunImageWidth")}
                  <select className="h-8 rounded-md border bg-background px-2" value={imageWidth} onChange={(e) => setImageWidth(Number(e.target.value))}>
                    {[512, 640, 768, 896, 1024, 1280].map((w) => <option key={w} value={w}>{w}px</option>)}
                  </select>
                </label>
              )}
              <label className="flex items-center gap-1.5" title={t("onShuffleHint")}>
                <input type="checkbox" checked={shuffle} onChange={(e) => setShuffle(e.target.checked)} /> {t("onShuffle")}
              </label>
            </div>
            <p className="text-xs text-muted-foreground">{t("onRunCalls", { calls: sessions * TYPICAL_STEPS, max: sessions * maxSteps })}</p>
          </>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => { if (!modelError) start.mutate(); }} disabled={start.isPending || chosen.length === 0 || mixTotal === 0 || modelError !== null}>
            {start.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />}
            {chosen.length > 1 ? t("onRunStartCompare", { count: chosen.length }) : t("onRunStart")}
          </Button>
          <span className="text-xs text-muted-foreground">{t("onRunSessions", { count: sessions })}</span>
        </div>
        {mixTotal === 0 && <p className="text-xs text-destructive">{t("onRunMixEmpty")}</p>}
        {start.error && <p role="alert" className="text-xs text-destructive">{start.error.message}</p>}
      </section>
    </div>
  );
}
