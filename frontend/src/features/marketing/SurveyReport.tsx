// Concept test result: the board respondents saw, 1–5 scales per product (mean with CI, top-2-box, distribution),
// preference shares, the Van Westendorp price range, segment means and verbatims; respondent-level CSV export.

import { useState } from "react";
import { Download, FileText, Quote } from "lucide-react";

import { surveyBoardUrl, surveyCsvUrl, surveyReportUrl, type ScaleKind, type SurveyReport as Report } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { richText } from "@/shared/i18n/richText";

import { LikertBar, LikertLegend, ShareBars, VanWestendorpChart } from "./charts";
import { segmentLabel } from "@/shared/i18n/personaLabels";
import { questionLabel } from "./questions";
import { PackagesOnline } from "./PackagesOnline";
import { StudyReading } from "./StudyReading";

const LETTERS = "ABCD";
const SCALE_ENDS: Record<ScaleKind, [MessageKey, MessageKey]> = {
  purchase_intent: ["mkEndDefinitelyNot", "mkEndDefinitely"],
  appeal: ["mkEndNotAtAll", "mkEndVery"],
  value: ["mkEndPoor", "mkEndExcellent"],
  uniqueness: ["mkEndSame", "mkEndVeryDifferent"],
};

export function SurveyReportView({ projectId, report: r }: { projectId: string; report: Report }) {
  const { t, locale } = useI18n();
  const [showTable, setShowTable] = useState(false);
  const scales = (Object.keys(SCALE_ENDS) as ScaleKind[]).filter((q) => r.questions.includes(q));
  const name = (i: number) => r.stimulus_names[i] || LETTERS[i]!;
  const money = (v: number | null) => (v == null ? "–" : formatMoney(v, r.currency));
  const best = (q: ScaleKind) => {
    const rows = r.scales.filter((s) => s.question === q);
    return rows.length > 1 ? rows.reduce((a, b) => (b.mean > a.mean ? b : a)) : null;
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <figure className="overflow-hidden rounded-2xl border bg-[#f6f5f2]">
          <img src={surveyBoardUrl(projectId, r.survey_id)} alt={t("mkBoardAlt")} className="mx-auto max-h-72 object-contain" />
        </figure>
        <div className="flex flex-col gap-2 rounded-2xl border bg-card p-4">
          <div className="grid grid-cols-3 gap-2">
            <Stat label={t("mkRespondents")} value={r.respondents.toLocaleString(locale)} />
            <Stat label={t("mkProducts")} value={String(r.stimuli.length)} />
            <Stat label={t("studioModel")} value={r.model.split("/").pop() ?? r.model} small />
          </div>
          <ul className="mt-1 space-y-1 text-sm">
            {scales.map((q) => {
              const b = best(q);
              const label = questionLabel(q, t);
              if (b) return <li key={q}><b>{name(b.stimulus)}</b>{t("mkLeadsOn", { question: label.toLowerCase() })}<span className="num text-muted-foreground">({b.mean.toFixed(2)} / 5)</span></li>;
              const one = r.scales.find((s) => s.question === q);
              return one ? <li key={q}>{richText(t("mkScaleOne"), { question: label, mean: <b className="num">{one.mean.toFixed(2)}</b>, top2: <span className="num">{Math.round(one.top2 * 100)}%</span> })}</li> : null;
            })}
            {r.price?.optimal_price_point != null && (
              <li>{richText(t("mkAcceptablePrice"), { name: name(0), range: <b className="num">{money(r.price.point_of_marginal_cheapness)}–{money(r.price.point_of_marginal_expensiveness)}</b>, optimal: <b className="num">{money(r.price.optimal_price_point)}</b> })}</li>
            )}
          </ul>
          <div className="mt-auto flex flex-wrap gap-2 pt-2">
            <Button asChild size="sm"><a href={surveyReportUrl(projectId, r.survey_id)} target="_blank" rel="noopener"><FileText className="size-4" /> {t("studioReport")}</a></Button>
            <Button asChild variant="outline" size="sm"><a href={surveyCsvUrl(projectId, r.survey_id)} download><Download className="size-4" /> {t("mkAnswersCsv")}</a></Button>
            <Button asChild variant="ghost" size="sm"><a href={surveyBoardUrl(projectId, r.survey_id)} download={`${r.survey_id}-board.jpg`}><Download className="size-4" /> {t("mkBoard")}</a></Button>
          </div>
        </div>
      </div>

      <StudyReading projectId={projectId} study="surveys" jobId={r.survey_id} answers={r.answers.filter((a) => a.why && !a.error).length} />

      {scales.length > 0 && (
        <section className="rounded-2xl border bg-card p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">{t("mkScales")} <span className="font-normal text-muted-foreground">{t("mkScalesHint")}</span></h3>
            <button type="button" onClick={() => setShowTable((s) => !s)} className="text-xs text-muted-foreground underline-offset-2 hover:underline">{showTable ? t("mkShowBars") : t("mkShowTable")}</button>
          </div>
          {showTable ? (
            <table className="w-full text-xs">
              <thead className="text-left text-muted-foreground"><tr><th className="py-1">{t("mkColQuestion")}</th><th>{t("mkColProduct")}</th><th className="text-right">n</th><th className="text-right">{t("mkColMean")}</th><th className="text-right">{t("mkColCi")}</th><th className="text-right">{t("mkColTop2")}</th><th className="text-right">1 · 2 · 3 · 4 · 5</th></tr></thead>
              <tbody className="num">
                {r.scales.map((s) => (
                  <tr key={`${s.question}-${s.stimulus}`} className="border-t border-foreground/[0.06]">
                    <td className="py-1">{questionLabel(s.question, t)}</td><td>{name(s.stimulus)}</td><td className="text-right">{s.n}</td>
                    <td className="text-right">{s.mean.toFixed(2)}</td><td className="text-right">{s.ci_low.toFixed(2)}–{s.ci_high.toFixed(2)}</td>
                    <td className="text-right">{Math.round(s.top2 * 100)}%</td><td className="text-right">{s.distribution.join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              {scales.map((q) => (
                <div key={q} className="space-y-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-sm font-medium">{questionLabel(q, t)}</span>
                    <LikertLegend low={t(SCALE_ENDS[q][0])} high={t(SCALE_ENDS[q][1])} />
                  </div>
                  {r.scales.filter((s) => s.question === q).map((s) => (
                    <div key={s.stimulus} className="grid grid-cols-[minmax(4rem,7rem)_1fr_5.5rem] items-center gap-3">
                      <span className="truncate text-sm"><b className="mr-1 text-muted-foreground">{LETTERS[s.stimulus]}</b>{name(s.stimulus)}</span>
                      <LikertBar counts={s.distribution} />
                      <span className="num text-right text-sm"><b>{s.mean.toFixed(2)}</b> <span className="text-[0.68rem] text-muted-foreground">±{((s.ci_high - s.ci_low) / 2).toFixed(2)}</span></span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-3">
          {r.preference.length > 0 && (
            <section className="rounded-2xl border bg-card p-4">
              <h3 className="text-sm font-semibold">{t("mkWouldTakeHome")}</h3>
              <p className="mb-3 text-xs text-muted-foreground">{t("mkWilsonHint")}</p>
              <ShareBars rows={r.preference.map((p) => ({ label: `${LETTERS[p.stimulus]} ${p.name}`, share: p.share, lo: p.ci_low, hi: p.ci_high }))} />
            </section>
          )}
          {r.verbatims.length > 0 && <Verbatims items={r.verbatims} />}
        </div>
        {r.price ? (
          <section className="self-start rounded-2xl border bg-card p-4">
            <h3 className="text-sm font-semibold">{t("mkPriceRangeFor", { name: name(0) })} <span className="font-normal text-muted-foreground">{t("mkVwN", { n: r.price.n })}</span></h3>
            <p className="mb-1 text-xs text-muted-foreground">{t("mkVwHint")}</p>
            <VanWestendorpChart price={r.price} currency={r.currency} />
            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
              {([["mkVwFloor", r.price.point_of_marginal_cheapness], ["mkVwOptimal", r.price.optimal_price_point], ["mkVwIndifference", r.price.indifference_price_point], ["mkVwCeiling", r.price.point_of_marginal_expensiveness]] as const).map(([k, v]) => (
                <div key={k}><dt className="text-muted-foreground">{t(k)}</dt><dd className="num font-semibold">{money(v)}</dd></div>
              ))}
            </dl>
          </section>
        ) : r.questions.includes("price_vw") ? (
          <section className="self-start rounded-2xl border bg-card p-4 text-sm text-muted-foreground">{t("mkVwTooFew")}</section>
        ) : null}
      </div>

      <PackagesOnline projectId={projectId} report={r} />

      {r.segments.length > 0 && <Segments report={r} />}

      <footer className="space-y-1 text-xs text-muted-foreground">
        <p>{t("mkRespondentsCount", { count: r.respondents })}{r.errors ? t("mkFailedShort", { count: r.errors }) : ""} · {r.seconds}s</p>
        {r.notes.map((n) => <p key={n}>{n}</p>)}
      </footer>
    </div>
  );
}

function Verbatims({ items }: { items: string[] }) {
  const { t } = useI18n();
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, 6);
  return (
    <section className="flex min-h-0 flex-1 flex-col rounded-2xl border bg-card p-4">
      <h3 className="mb-2 text-sm font-semibold">{t("mkInTheirWords")} <span className="font-normal text-muted-foreground">· {items.length}</span></h3>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {shown.map((v, i) => (
          <blockquote key={i} className="rounded-xl bg-foreground/[0.035] px-3 py-2 text-sm">
            <Quote className="mb-1 size-3.5 text-muted-foreground" aria-hidden />{v}
          </blockquote>
        ))}
      </div>
      {items.length > 6 && (
        <button type="button" onClick={() => setAll((a) => !a)} className="mt-2 self-start text-xs text-muted-foreground underline-offset-2 hover:underline">
          {all ? t("studioShowFewer") : t("studioShowAll", { count: items.length })}
        </button>
      )}
    </section>
  );
}

function Stat({ label, value, small = false }: { label: string; value: string; small?: boolean }) {
  return (
    <div className="rounded-xl bg-foreground/[0.035] px-3 py-2">
      <div className="text-[0.7rem] text-muted-foreground">{label}</div>
      <div className={cn("truncate font-semibold", small ? "text-sm" : "text-xl")} title={value}>{value}</div>
    </div>
  );
}

/** Segment means as a table; cells are tinted by their distance from the column mean (blue above, red below). */
function Segments({ report: r }: { report: Report }) {
  const { t } = useI18n();
  const cols = [...new Set(r.segments.flatMap((s) => Object.keys(s.values)))];
  const colMean = (c: string) => {
    const xs = r.segments.map((s) => s.values[c]).filter((v): v is number => v != null);
    return xs.reduce((a, b) => a + b, 0) / (xs.length || 1);
  };
  const means = Object.fromEntries(cols.map((c) => [c, colMean(c)]));
  const pretty = (c: string) => {
    const [q, l] = c.split("·");
    const label = q === "prefer" ? t("mkPrefer") : questionLabel(q ?? "", t);
    return `${label} ${l}`;
  };
  return (
    <section className="rounded-2xl border bg-card p-4">
      <h3 className="text-sm font-semibold">{t("mkBySegment")}</h3>
      <p className="mb-2 text-xs text-muted-foreground">{t("mkSurveySegmentHint")}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-left text-muted-foreground">
            <tr><th className="py-1 pr-3">{t("mkColSegment")}</th><th className="pr-3 text-right">n</th>{cols.map((c) => <th key={c} className="px-2 text-right whitespace-nowrap">{pretty(c)}</th>)}</tr>
          </thead>
          <tbody className="num">
            {r.segments.map((s) => (
              <tr key={s.segment} className="border-t border-foreground/[0.06]">
                <td className="py-1 pr-3 whitespace-nowrap">{segmentLabel(s.segment, t)}</td>
                <td className="pr-3 text-right text-muted-foreground">{s.n}</td>
                {cols.map((c) => {
                  const v = s.values[c];
                  const share = c.startsWith("prefer");
                  const dev = v == null ? 0 : (v - means[c]!) / (share ? 0.25 : 1);
                  const tint = Math.min(1, Math.abs(dev)) * 26;
                  return (
                    <td key={c} className="px-2 text-right"
                      style={{ background: v == null || s.n < 5 ? undefined : `color-mix(in oklab, ${dev >= 0 ? "var(--viz-pos-2)" : "var(--viz-neg-2)"} ${tint}%, transparent)` }}>
                      {v == null ? "–" : share ? `${Math.round(v * 100)}%` : v.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
