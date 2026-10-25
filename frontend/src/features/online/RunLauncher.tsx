// Send virtual shoppers through one store, or compare up to four variants on the very same shoppers.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Loader2, Play } from "lucide-react";

import { ModelPicker, type ModelChoice } from "@/features/runs/components/ModelPicker";
import { useAvailableModels } from "@/features/runs/hooks";
import {
  ACCESSIBILITY, ARRIVALS, copySite, getSite, MISSIONS, onlineKeys, startRun, type Accessibility, type Arrival, type ShopperMission,
  type ShopperPolicyKind,
  type SiteSummary,
} from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

import { experimentsFor } from "./experiments";
import { ACCESSIBILITY_LABELS, ARRIVAL_HINTS, ARRIVAL_LABELS, MISSION_HINTS, MISSION_LABELS, POLICY_HINTS, POLICY_LABELS } from "./labels";

const MAX_VARIANTS = 4;
const DEFAULT_ARRIVALS: Record<Arrival, number> = { direct: 100, search_engine: 0, social: 0, email: 0 };
const DEFAULT_MIX: Record<ShopperMission, number> = { purchase: 25, browse: 35, compare: 15, deal_hunt: 10, gift: 7, replenish: 8 };
// Pages a session typically takes, for the estimate of model calls (rule runs make none).
const TYPICAL_STEPS = 11;

export function RunLauncher({ projectId, sites, firstSiteId, compareWith, hasCustomers, onStarted }: {
  projectId: string; sites: SiteSummary[]; firstSiteId: string;
  /** A variant to compare with the first store from the start (made by the design chat). */
  compareWith?: string;
  hasCustomers: boolean; onStarted: (runId: string) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [chosen, setChosen] = useState<string[]>(compareWith ? [firstSiteId, compareWith] : [firstSiteId]);
  const [shoppers, setShoppers] = useState(30);
  const [policy, setPolicy] = useState<ShopperPolicyKind>("rule");
  const [model, setModel] = useState<ModelChoice>({ kind: "default" });
  const [seed, setSeed] = useState(1);
  const [maxSteps, setMaxSteps] = useState(24);
  const [mix, setMix] = useState(DEFAULT_MIX);
  const [mobile, setMobile] = useState(55);
  const [arrivals, setArrivals] = useState<Record<Arrival, number>>(DEFAULT_ARRIVALS);
  const [source, setSource] = useState<"panel" | "project">("panel");
  const [imageWidth, setImageWidth] = useState(896);
  const [shuffle, setShuffle] = useState(true);
  const [accessibility, setAccessibility] = useState<Accessibility>("typical");
  const [survey, setSurvey] = useState(true);
  const [name, setName] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [rival, setRival] = useState("");
  const [createdSites, setCreatedSites] = useState<Pick<SiteSummary, "id" | "name" | "theme_color" | "cart_reminder" | "currency">[]>([]);
  const listedSites = [...sites, ...createdSites.filter((copy) => !sites.some((site) => site.id === copy.id))];
  const controlId = chosen[0] ?? "";
  const control = useQuery({ queryKey: onlineKeys.site(projectId, controlId), queryFn: () => getSite(projectId, controlId), enabled: !!controlId });
  const available = control.data ? experimentsFor(control.data) : [];
  const room = MAX_VARIANTS - chosen.length;
  // Picks that no longer apply (another first store, or no room left) simply drop out.
  const experiments = available.filter((x) => picked.includes(x.id)).slice(0, Math.max(0, room));
  const mixTotal = Object.values(mix).reduce((a, b) => a + b, 0);
  const arrivalTotal = Object.values(arrivals).reduce((a, b) => a + b, 0);
  const currency = listedSites.find((site) => site.id === controlId)?.currency;
  const rivals = listedSites.filter((site) => !chosen.includes(site.id) && site.currency === currency);
  // A rival that became one of the compared stores (or another currency) simply drops out.
  const rivalId = rivals.some((site) => site.id === rival) ? rival : "";
  // Rival visits: at most one per shopper, roughly every other shopper in a typical run.
  const rivalVisits = rivalId ? Math.round(shoppers / 2) : 0;
  const sessions = shoppers * (chosen.length + experiments.length);
  // Unknown summaries reserve a possible return visit until refreshed by a current server.
  const maxVisits = chosen.reduce((sum, id) => sum + (listedSites.find((site) => site.id === id)?.cart_reminder === false ? 1 : 2), 0)
    + experiments.reduce((sum, experiment) => sum + (experiment.options.cart_reminder ? 2 : 1), 0);
  const rivalMaxVisits = rivalId ? (listedSites.find((site) => site.id === rivalId)?.cart_reminder === false ? 1 : 2) : 0;
  const maxResponses = shoppers * (maxVisits + rivalMaxVisits) * maxSteps + (survey ? sessions : 0);
  const models = useAvailableModels(policy !== "rule");
  const availableModels = models.data?.filter((m) => policy !== "vlm" || m.vision);
  let modelError: string | null = null;
  if (policy !== "rule" && model.kind !== "default") {
    if (!availableModels) modelError = t(models.isError ? "onRunModelsFailed" : "loadingModels");
    else if (model.kind === "single") {
      modelError = !model.model ? t("onRunChooseModel")
        : availableModels.some((m) => m.ref === model.model) ? null : t("onRunModelUnavailable");
    } else {
      const members = model.ensemble?.members ?? [];
      if (!members.length) modelError = t("onRunNeedEnsemble");
      else if (members.some((member) => !availableModels.some((m) => m.ref === member.model))) modelError = t("onRunModelUnavailable");
      else if (members.some((member) => !Number.isFinite(member.weight) || member.weight <= 0)) modelError = t("invalidWeights");
    }
  }

  const start = useMutation({
    mutationFn: async () => {
      // Each picked change becomes a copy of the first store, then all are run on the same shoppers.
      const created: string[] = [];
      for (const x of experiments) {
        const label = t(x.label);
        const base = control.data!;
        const copy = await copySite(projectId, base.id, {
          name: `${base.name} – ${label}`.slice(0, 60), note: label, options: x.options, products: x.products,
        });
        created.push(copy.id);
        // Keep confirmed copies selected if a later copy or the run start fails.
        setCreatedSites((previous) => [...previous, {
          id: copy.id, name: copy.name, theme_color: copy.options.theme_color, cart_reminder: copy.options.cart_reminder,
          currency: copy.currency,
        }]);
        setChosen((previous) => [...previous, copy.id]);
        setPicked((previous) => previous.filter((id) => id !== x.id));
        qc.setQueryData(onlineKeys.site(projectId, copy.id), copy);
      }
      return startRun(projectId, {
        site_ids: [...chosen, ...created], rival_site_id: rivalId || null, name: name.trim() || undefined, shoppers, policy, seed, max_steps: maxSteps,
        missions: Object.fromEntries(MISSIONS.map((m) => [m, mix[m] / 100])) as Record<ShopperMission, number>,
        arrivals: Object.fromEntries(ARRIVALS.map((a) => [a, arrivals[a] / 100])),
        mobile_share: mobile / 100, source, image_width: imageWidth, shuffle_marks: shuffle, accessibility,
        exit_survey: survey,
        model: policy !== "rule" && model.kind === "single" ? model.model ?? null : null,
        ensemble: policy !== "rule" && model.kind === "ensemble" && model.ensemble?.members.length ? model.ensemble : null,
      });
    },
    onSuccess: (status) => {
      void qc.invalidateQueries({ queryKey: onlineKeys.runs(projectId) });
      setPicked([]);
      onStarted(status.run_id);
    },
    onSettled: () => void qc.invalidateQueries({ queryKey: onlineKeys.sites(projectId) }),
  });
  const toggleSite = (id: string) =>
    setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : c.length >= MAX_VARIANTS ? c : [...c, id]));

  return (
    <div className="grid gap-3 xl:grid-cols-2">
      <section className="panel flex flex-col gap-3 rounded-[1.4rem] p-4 text-sm">
        <h3 className="font-semibold">{t("onRunStores")}</h3>
        <p className="text-xs text-muted-foreground">{t("onRunStoresHint", { max: MAX_VARIANTS })}</p>
        {/* The chosen stores stay in sight however long the list is. */}
        <ul className="flex flex-wrap gap-1.5" aria-label={t("onRunChosen")}>
          {chosen.map((id, i) => {
            const s = listedSites.find((x) => x.id === id);
            return s && (
              <li key={id} className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-primary/40 bg-primary/5 px-2.5 py-1 text-xs">
                <span className="size-2.5 shrink-0 rounded-full ring-1 ring-foreground/25" style={{ background: s.theme_color }} aria-hidden />
                <span className="truncate font-medium">{s.name}</span>
                <span className="shrink-0 text-muted-foreground">{i === 0 ? t("onControl") : t("onVariantLetter", { letter: String.fromCharCode(65 + i) })}</span>
              </li>
            );
          })}
        </ul>
        <ul className="max-h-[22rem] space-y-1 overflow-y-auto pr-1">
          {listedSites.map((s) => {
            const index = chosen.indexOf(s.id);
            return (
              <li key={s.id}>
                <label className={cn("flex items-center gap-2 rounded-lg border px-2 py-1.5", index >= 0 && "border-primary bg-primary/5")}>
                  <input type="checkbox" checked={index >= 0} onChange={() => toggleSite(s.id)}
                    disabled={start.isPending || (index < 0 && chosen.length >= MAX_VARIANTS)} />
                  <span className="size-3 shrink-0 rounded-full ring-1 ring-foreground/25" style={{ background: s.theme_color }} aria-hidden />
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
        {control.data && (
          <fieldset disabled={start.isPending} className="space-y-2 rounded-xl border border-dashed p-3">
            <legend className="flex items-center gap-1 px-1 text-xs font-medium">
              <FlaskConical className="size-3.5 text-primary" aria-hidden /> {t("onXpTitle")}
            </legend>
            <p className="text-[0.7rem] text-muted-foreground">{t("onXpHint", { name: control.data.name })}</p>
            {available.length === 0 ? <p className="text-xs text-muted-foreground">{t("onXpNone")}</p> : (
              <div className="grid gap-1 sm:grid-cols-2">
                {available.map((x) => {
                  const on = experiments.some((e) => e.id === x.id);
                  return (
                    <label key={x.id} className={cn("flex items-center gap-2 text-xs", !on && experiments.length >= room && "opacity-50")}>
                      <input type="checkbox" checked={on} disabled={!on && experiments.length >= room}
                        onChange={() => setPicked((p) => (on ? p.filter((id) => id !== x.id) : [...p.filter((id) => experiments.some((e) => e.id === id)), x.id]))} />
                      {t(x.label)}
                    </label>
                  );
                })}
              </div>
            )}
            <p className="text-[0.7rem] text-muted-foreground">{t("onXpRoom", { count: Math.max(0, room - experiments.length) })}</p>
          </fieldset>
        )}
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium">{t("onRunRival")}</span>
          <select className="h-8 rounded-md border bg-background px-2" value={rivalId} disabled={start.isPending}
            onChange={(e) => setRival(e.target.value)}>
            <option value="">{t("onRunRivalNone")}</option>
            {rivals.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}
          </select>
          <span className="text-[0.7rem] text-muted-foreground">{t("onRunRivalHint")}</span>
        </label>
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
        <fieldset className="space-y-1">
          <legend className="text-xs font-medium">{t("onRunArrivals")}</legend>
          <p className="text-[0.7rem] text-muted-foreground">{t("onRunArrivalsHint")}</p>
          {ARRIVALS.map((a) => (
            <label key={a} className="grid grid-cols-[110px_minmax(0,1fr)_40px] items-center gap-2 text-xs" title={t(ARRIVAL_HINTS[a])}>
              <span>{t(ARRIVAL_LABELS[a])}</span>
              <input type="range" min={0} max={100} value={arrivals[a]} aria-label={t(ARRIVAL_LABELS[a])}
                onChange={(e) => setArrivals((x) => ({ ...x, [a]: Number(e.target.value) }))} />
              <span className="text-right tabular-nums">{arrivalTotal ? Math.round((arrivals[a] / arrivalTotal) * 100) : 0}%</span>
            </label>
          ))}
        </fieldset>
        <label className="grid grid-cols-[110px_minmax(0,1fr)_40px] items-center gap-2 text-xs">
          <span>{t("onRunMobile")}</span>
          <input type="range" min={0} max={100} value={mobile} onChange={(e) => setMobile(Number(e.target.value))} aria-label={t("onRunMobile")} />
          <span className="text-right tabular-nums">{mobile}%</span>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium">{t("onRunEyesight")}</span>
          <select className="h-8 rounded-md border bg-background px-2" value={accessibility} onChange={(e) => setAccessibility(e.target.value as Accessibility)}>
            {ACCESSIBILITY.map((a) => <option key={a} value={a}>{t(ACCESSIBILITY_LABELS[a])}</option>)}
          </select>
          <span className="text-[0.7rem] text-muted-foreground">{t("onRunEyesightHint")}</span>
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
              <label className="flex items-center gap-1.5" title={t("onRunSurveyHint")}>
                <input type="checkbox" checked={survey} onChange={(e) => setSurvey(e.target.checked)} /> {t("onRunSurvey")}
              </label>
            </div>
            <p className="text-xs text-muted-foreground">
              {t("onRunCalls", {
                calls: sessions * (Math.min(TYPICAL_STEPS, maxSteps) + (survey ? 1 : 0)) + rivalVisits * Math.min(TYPICAL_STEPS, maxSteps),
                max: maxResponses,
              })}
            </p>
          </>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => { if (!modelError) start.mutate(); }} disabled={start.isPending || chosen.length === 0 || mixTotal === 0 || arrivalTotal === 0 || modelError !== null}>
            {start.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />}
            {experiments.length ? t("onXpStart") : chosen.length > 1 ? t("onRunStartCompare", { count: chosen.length }) : t("onRunStart")}
          </Button>
          <span className="text-xs text-muted-foreground">{t("onRunSessions", { count: sessions })}</span>
        </div>
        {mixTotal === 0 && <p className="text-xs text-destructive">{t("onRunMixEmpty")}</p>}
        {arrivalTotal === 0 && <p className="text-xs text-destructive">{t("onRunArrivalsEmpty")}</p>}
        {start.error && <p role="alert" className="text-xs text-destructive">{start.error.message}</p>}
      </section>
    </div>
  );
}
