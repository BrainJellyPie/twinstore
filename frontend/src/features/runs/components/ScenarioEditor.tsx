// The situation a run simulates: pick a preset (heatwave weekend, rainy commute, big match night…)
// or customize weather, calendar, events, promotions, stock-outs and crowding. A live preview shows
// what the scenario does to traffic and category demand before anything runs.

import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CloudSun, Loader2, Plus, SlidersHorizontal, Sparkles, Trash2 } from "lucide-react";

import * as api from "@/shared/api/client";
import type { Crowding, DayType, EventKind, PromotionKind, Scenario, Weather } from "@/shared/api/client";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { BASELINE_SCENARIO } from "../scenarioDefaults";

const WEATHER: { value: Weather; icon: string; label: MessageKey }[] = [
  { value: "clear", icon: "☀️", label: "sitClear" },
  { value: "cloudy", icon: "☁️", label: "sitCloudy" },
  { value: "rain", icon: "🌧️", label: "sitRain" },
  { value: "heavy_rain", icon: "⛈️", label: "sitHeavyRain" },
  { value: "snow", icon: "🌨️", label: "sitSnow" },
  { value: "heatwave", icon: "🥵", label: "sitHeatwave" },
  { value: "cold_snap", icon: "🥶", label: "sitColdSnap" },
  { value: "fine_dust", icon: "😷", label: "sitFineDust" },
  { value: "typhoon", icon: "🌀", label: "sitTyphoon" },
];
const DAY_TYPES: { value: DayType; label: MessageKey }[] = [
  { value: "weekday", label: "sitWeekday" },
  { value: "weekend", label: "sitWeekend" },
  { value: "public_holiday", label: "sitPublicHoliday" },
  { value: "holiday_season", label: "sitHolidaySeason" },
  { value: "school_vacation", label: "sitSchoolVacation" },
];
const EVENTS: { value: EventKind; label: MessageKey }[] = [
  { value: "festival", label: "sitFestival" },
  { value: "sports_match", label: "sitSportsMatch" },
  { value: "concert", label: "sitConcert" },
  { value: "exam_period", label: "sitExamPeriod" },
  { value: "payday", label: "sitPayday" },
  { value: "competitor_opening", label: "sitCompetitorOpens" },
  { value: "competitor_closed", label: "sitCompetitorClosed" },
  { value: "road_construction", label: "sitRoadWorks" },
  { value: "marathon", label: "sitMarathon" },
  { value: "conference", label: "sitConference" },
  { value: "night_market", label: "sitNightMarket" },
];
const CROWDING: { value: Crowding; label: MessageKey }[] = [
  { value: "quiet", label: "sitQuiet" }, { value: "normal", label: "sitNormal" },
  { value: "busy", label: "sitBusy" }, { value: "packed", label: "sitPacked" },
];
const PROMO_KINDS: { value: PromotionKind; label?: MessageKey }[] = [
  { value: "discount", label: "sitDiscount" }, { value: "1+1" }, { value: "2+1" }, { value: "featured", label: "sitFeatured" },
];
const CATEGORY_LABELS: Record<string, MessageKey> = {
  cold_drinks: "sitColdDrinks", water: "sitWater", hot_food: "sitHotFood", ice_cream: "sitIceCream", snacks: "sitSnacks",
  meals: "sitMeals", alcohol: "sitAlcohol", health: "sitHealth", caffeine: "sitCaffeine", desserts: "sitDesserts",
};
// Stored on the run's scenario; only its display label is translated.
const CUSTOM_NAME = "Custom situation";


export function ScenarioEditor({
  value,
  onChange,
  projectId,
  setupId,
}: {
  value: Scenario | null;
  onChange: (next: Scenario | null) => void;
  /** With both, a described day's promotions and stock-outs are checked against this layout's products. */
  projectId?: string;
  setupId?: string;
}) {
  const { t } = useI18n();
  const { data: presets = [] } = useQuery({
    queryKey: queryKeys.scenarios(projectId, setupId),
    queryFn: ({ signal }) => api.getScenarios({ projectId, setupId }, signal),
    staleTime: Infinity,
  });
  const [customOpen, setCustomOpen] = useState(false);
  const scenario = value ?? null;

  // Debounced live preview of a custom scenario.
  const [debounced, setDebounced] = useState(scenario);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(scenario), 300);
    return () => clearTimeout(id);
  }, [scenario]);
  const presetEffects = useMemo(
    () => presets.find((p) => p.scenario.id === scenario?.id)?.effects,
    [presets, scenario?.id],
  );
  const { data: liveEffects } = useQuery({
    queryKey: queryKeys.scenarioPreview(debounced, projectId, setupId),
    queryFn: ({ signal }) => api.previewScenario(debounced!, { projectId, setupId }, signal),
    enabled: !!debounced && debounced.id === "custom",
    staleTime: Infinity,
  });
  const effects = scenario?.id === "custom" ? liveEffects : presetEffects;

  const set = (patch: Partial<Scenario>) =>
    onChange({
      ...(scenario ?? BASELINE_SCENARIO), ...patch, id: "custom",
      name: scenario?.id === "custom" ? scenario.name : CUSTOM_NAME,
    });

  // "Describe the day": the text model fills in the settings; the details open so they can be checked.
  const [day, setDay] = useState("");
  const dayLength = Array.from(day.trim()).length;
  const [described, setDescribed] = useState<api.DescribedScenario | null>(null);
  const describe = useMutation({
    mutationFn: (text: string) => api.describeScenario({ text, project_id: projectId, setup_id: setupId }),
  });
  const resetDescription = describe.reset;
  // Detach the old request before a reply can overwrite a newly committed edit or layout.
  useLayoutEffect(() => {
    resetDescription();
  }, [day, value, projectId, setupId, resetDescription]);
  const setUp = () => {
    if (dayLength >= 3 && !describe.isPending) describe.mutate(day.trim(), {
      // Per-request callbacks run only while this editor still observes that request.
      onSuccess: (r) => {
        setDescribed(r);
        onChange(r.scenario);
        setCustomOpen(true);
      },
    });
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-sm font-medium">
          <CloudSun className="size-4" aria-hidden /> {t("optSituation")}
        </div>
        <button
          type="button"
          onClick={() => setCustomOpen((o) => !o)}
          className="flex items-center gap-1 text-xs text-primary hover:underline"
          aria-expanded={customOpen}
        >
          <SlidersHorizontal className="size-3" /> {customOpen ? t("sitHideDetails") : t("sitCustomize")}
        </button>
      </div>

      <select
        className="h-8 w-full rounded-md border bg-background px-2 text-sm"
        value={scenario ? scenario.id : "baseline"}
        onChange={(e) => {
          const id = e.target.value;
          if (id === "baseline") onChange(null);
          else if (id === "custom") onChange(scenario ?? { ...BASELINE_SCENARIO });
          else onChange(presets.find((p) => p.scenario.id === id)?.scenario ?? null);
        }}
        aria-label={t("sitPreset")}
      >
        {presets.map((p) => (
          <option key={p.scenario.id} value={p.scenario.id}>
            {/* "baseline" is the no-situation choice the run summary also names; other preset names are the server's. */}
            {p.scenario.id === "baseline" ? t("baselineSituation") : p.scenario.name}
          </option>
        ))}
        <option value="custom">{scenario?.id === "custom" && scenario.name !== CUSTOM_NAME ? scenario.name : t("sitCustom")}</option>
      </select>
      {scenario?.description && scenario.id !== "custom" && (
        <p className="text-xs text-muted-foreground">{scenario.description}</p>
      )}

      {/* Not a <form>: the editor sits inside the run dialog's form, and a nested submit would start the run. */}
      <div className="flex items-start gap-1.5">
        <textarea
          value={day}
          onChange={(e) => setDay(Array.from(e.target.value).slice(0, 800).join(""))}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) {
              e.preventDefault();
              e.stopPropagation();
              setUp();
            }
          }}
          rows={2}
          placeholder={t("sitDescribePlaceholder")}
          aria-label={t("sitDescribe")}
          className="min-h-[2.4rem] flex-1 resize-none rounded-md border bg-background px-2 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        />
        <button
          type="button"
          onClick={setUp}
          disabled={dayLength < 3 || describe.isPending}
          className="flex h-[2.4rem] shrink-0 items-center gap-1 rounded-md border px-2 text-xs font-medium text-primary hover:bg-primary/5 disabled:opacity-50"
        >
          {describe.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
          {t("optSetUp")}
        </button>
      </div>
      {describe.error && <p role="alert" className="text-xs text-destructive">{describe.error.message}</p>}
      {described && scenario?.description === described.scenario.description && described.warnings.length > 0 && (
        <ul className="space-y-0.5 text-xs text-muted-foreground" aria-label={t("sitDescribedNotes")}>
          {described.warnings.map((w) => <li key={w}>· {w}</li>)}
        </ul>
      )}

      {customOpen && (
        <div className="space-y-3 rounded-md border bg-muted/20 p-3 text-xs">
          <div className="grid grid-cols-2 gap-2">
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">{t("sitWeather")}</span>
              <select
                className="h-7 rounded border bg-background px-1"
                value={scenario?.weather ?? "clear"}
                onChange={(e) => set({ weather: e.target.value as Weather })}
              >
                {WEATHER.map((w) => <option key={w.value} value={w.value}>{w.icon} {t(w.label)}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">{t("sitDay")}</span>
              <select
                className="h-7 rounded border bg-background px-1"
                value={scenario?.day_type ?? "weekday"}
                onChange={(e) => set({ day_type: e.target.value as DayType })}
              >
                {DAY_TYPES.map((d) => <option key={d.value} value={d.value}>{t(d.label)}</option>)}
              </select>
            </label>
            <label className="col-span-2 flex items-center gap-2">
              <input
                type="checkbox"
                checked={scenario?.temperature_c != null}
                onChange={(e) => set({ temperature_c: e.target.checked ? 20 : null })}
              />
              <span className="w-24 text-muted-foreground">{t("sitTemperature")}</span>
              <input
                type="range"
                min={-20}
                max={40}
                disabled={scenario?.temperature_c == null}
                value={scenario?.temperature_c ?? 20}
                onChange={(e) => set({ temperature_c: Number(e.target.value) })}
                className="flex-1 accent-primary"
                aria-label={t("sitTemperature")}
              />
              <span className="w-12 text-right tabular-nums">{scenario?.temperature_c != null ? `${scenario.temperature_c}°C` : "—"}</span>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">{t("sitCrowding")}</span>
              <select
                className="h-7 rounded border bg-background px-1"
                value={scenario?.crowding ?? "normal"}
                onChange={(e) => set({ crowding: e.target.value as Crowding })}
              >
                {CROWDING.map((c) => <option key={c.value} value={c.value}>{t(c.label)}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-muted-foreground">{t("sitExtraTraffic")}</span>
              <Input
                type="number"
                step={0.1}
                min={0}
                max={5}
                value={scenario?.traffic_multiplier ?? 1}
                onChange={(e) => set({ traffic_multiplier: Number(e.target.value) || 0 })}
                className="h-7 text-xs"
              />
            </label>
          </div>

          <div>
            <div className="mb-1 text-muted-foreground">{t("sitLocalEvents")}</div>
            <div className="flex flex-wrap gap-1">
              {EVENTS.map((ev) => {
                const active = scenario?.events.find((x) => x.kind === ev.value);
                return (
                  <button
                    key={ev.value}
                    type="button"
                    onClick={() =>
                      set({
                        events: active
                          ? (scenario?.events ?? []).filter((x) => x.kind !== ev.value)
                          : [...(scenario?.events ?? []), { kind: ev.value, intensity: 0.7, start_hour: 0, end_hour: 24 }],
                      })
                    }
                    className={cn("rounded-full border px-2 py-0.5", active ? "border-primary bg-primary/10" : "hover:bg-muted")}
                  >
                    {t(ev.label)}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between text-muted-foreground">
              {t("sitPromotions")}
              <button
                type="button"
                className="flex items-center gap-0.5 text-primary"
                onClick={() =>
                  set({ promotions: [...(scenario?.promotions ?? []), { target: "", kind: "discount", discount_pct: 20 }] })
                }
              >
                <Plus className="size-3" /> {t("sitAdd")}
              </button>
            </div>
            {(scenario?.promotions ?? []).map((pr, i) => (
              <div key={i} className="mb-1 flex items-center gap-1">
                <Input
                  placeholder={t("sitPromotionTarget")}
                  value={pr.target}
                  onChange={(e) =>
                    set({ promotions: scenario!.promotions.map((x, j) => (j === i ? { ...x, target: e.target.value } : x)) })
                  }
                  className="h-7 flex-1 text-xs"
                />
                <select
                  className="h-7 rounded border bg-background px-1"
                  value={pr.kind}
                  onChange={(e) =>
                    set({ promotions: scenario!.promotions.map((x, j) => (j === i ? { ...x, kind: e.target.value as PromotionKind } : x)) })
                  }
                >
                  {PROMO_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label ? t(k.label) : k.value}</option>)}
                </select>
                {pr.kind === "discount" && (
                  <Input
                    type="number"
                    min={0}
                    max={90}
                    value={pr.discount_pct}
                    onChange={(e) =>
                      set({ promotions: scenario!.promotions.map((x, j) => (j === i ? { ...x, discount_pct: Number(e.target.value) || 0 } : x)) })
                    }
                    className="h-7 w-14 text-xs"
                    aria-label={t("sitDiscountPercent")}
                  />
                )}
                <button
                  type="button"
                  onClick={() => set({ promotions: scenario!.promotions.filter((_, j) => j !== i) })}
                  aria-label={t("sitRemovePromotion")}
                >
                  <Trash2 className="size-3.5 text-muted-foreground" />
                </button>
              </div>
            ))}
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-muted-foreground">{t("sitSoldOut")}</span>
            <Input
              value={(scenario?.stockouts ?? []).join(", ")}
              onChange={(e) => set({ stockouts: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
              placeholder={t("sitSoldOutPlaceholder")}
              className="h-7 text-xs"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-muted-foreground">{t("sitNotes")}</span>
            <Input
              value={scenario?.notes ?? ""}
              maxLength={400}
              onChange={(e) => set({ notes: e.target.value })}
              placeholder={t("sitNotesPlaceholder")}
              className="h-7 text-xs"
            />
          </label>
        </div>
      )}

      {effects && scenario && <EffectsPreview effects={effects} />}
    </div>
  );
}

function EffectsPreview({ effects }: { effects: api.ScenarioEffects }) {
  const { t } = useI18n();
  const demand = Object.entries(effects.demand).sort((a, b) => Math.abs(b[1] - 1) - Math.abs(a[1] - 1)).slice(0, 6);
  const hourly = Object.values(effects.traffic_by_hour);
  const peak = hourly.length ? Math.max(...hourly) : 1;
  return (
    <div className="space-y-1.5 rounded-md bg-muted/40 px-3 py-2 text-xs">
      <div className="flex flex-wrap gap-x-3 gap-y-1 tabular-nums">
        <span>{t("sitEffectTraffic", { value: effects.traffic.toFixed(2) })}{peak > 1.01 ? ` ${t("sitEffectPeak", { value: (effects.traffic * peak).toFixed(2) })}` : ""}</span>
        {effects.dwell !== 1 && <span>{t("sitEffectDwell", { value: effects.dwell.toFixed(2) })}</span>}
        {effects.impulse !== 1 && <span>{t("sitEffectImpulse", { value: effects.impulse.toFixed(2) })}</span>}
        {effects.budget !== 1 && <span>{t("sitEffectBudget", { value: effects.budget.toFixed(2) })}</span>}
        {effects.walkout !== 1 && <span>{t("sitEffectWalkouts", { value: effects.walkout.toFixed(2) })}</span>}
      </div>
      {demand.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {demand.map(([cat, m]) => (
            <span
              key={cat}
              className={cn(
                "rounded-full px-1.5 py-0.5 tabular-nums",
                m > 1 ? "tone-good" : "tone-bad",
              )}
            >
              {m > 1 ? "▲" : "▼"} {CATEGORY_LABELS[cat] ? t(CATEGORY_LABELS[cat]) : cat} ×{m.toFixed(2)}
            </span>
          ))}
        </div>
      )}
      {effects.situation && <p className="text-muted-foreground">{t("sitToldShoppers", { situation: effects.situation })}</p>}
    </div>
  );
}
