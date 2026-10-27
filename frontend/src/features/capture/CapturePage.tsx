// Shelf capture: photograph a shelf, let detection + a VLM read it into a planogram, correct what
// it got wrong, and put it into a layout to simulate.

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useBlocker, useNavigate, useRouter } from "@tanstack/react-router";
import { Camera, Check, Eye, EyeOff, FlaskConical, ListChecks, Loader2, Minus, Plus, Save, Trash2, Wand2 } from "lucide-react";

import * as api from "@/shared/api/client";
import type { CaptureBox, CaptureEdit, CaptureItem, CaptureResult, CaptureStatus } from "@/shared/api/client";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { formatMoney, minorUnitDivisor, toMinor, formatPercent } from "@/shared/utils/money";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { CAPTURE_CATEGORIES, categoryColor, categoryLabel } from "./categories";
import { EMPTY_DRAFT, needsOther, type LabDraft } from "./labDraft";
import { RivalCard } from "./RivalCard";
import { CaptureBatch } from "./CaptureBatch";
import { CaptureUploadQueue } from "./CaptureUploadQueue";
import { BeforeAfter, ShelfLabPanel } from "./ShelfLab";
import { STAGES } from "./stages";

// Detectors a finished capture reports it used; "gdino" reads as its product name and unknown names as they are.
const DETECTORS: Record<string, MessageKey> = { classic: "capDetectorClassicName", vlm: "capDetectorVlmName" };

const capturesKey = (pid: string) => ["projects", pid, "captures"] as const;
const blockLeaving = () => true;

export function CapturePage({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({
    queryKey: capturesKey(projectId),
    queryFn: ({ signal }) => api.listCaptures(projectId, signal),
    refetchInterval: (q) => (q.state.data?.some((c) => c.status === "pending" || c.status === "running") ? 1500 : false),
  });
  const captures = useMemo(() => list.data ?? [], [list.data]);
  const [chosenNew, setChosenNew] = useState(false);
  const [hasSavedQueue, setHasSavedQueue] = useState(false);
  useEffect(() => {
    if (!selected && !chosenNew && captures.length > 0) setSelected(captures[0]!.capture_id);
  }, [captures, selected, chosenNew]);
  const show = (id: string | null) => { setChosenNew(id === null); setSelected(id); };
  // Unsaved product corrections on the open photo: ask before another photo, another page or a reload drops them.
  const [unsaved, setUnsaved] = useState(false);
  const [switchTo, setSwitchTo] = useState<{ id: string | null } | null>(null);
  const leave = useBlocker({ shouldBlockFn: blockLeaving, withResolver: true, enableBeforeUnload: true, disabled: !unsaved });
  const select = (id: string | null) => {
    if (unsaved && id !== selected) setSwitchTo({ id });
    else show(id);
  };

  return (
    <div className="flex min-h-0 min-w-0 flex-1 overflow-y-auto">
      <div className="flex min-w-0 flex-1 flex-col gap-3 p-4 md:min-h-0">
        <h1 className="sr-only">{t("shelfCapture")}</h1>
        <CaptureStrip projectId={projectId} captures={captures} selected={selected} onSelect={select} />
        {selected && hasSavedQueue && <Button variant="outline" onClick={() => select(null)}>{t("capContinueQueue")}</Button>}
        {captures.length > 0 && <CaptureBatch key={projectId} projectId={projectId} captures={captures} onReview={select} />}
        <div hidden={!!selected} className="min-h-64 shrink-0 md:flex-1"><CaptureUploadQueue key={projectId} visible={!selected} projectId={projectId} onAccepted={() => setChosenNew(true)} onReview={select} onRecoveryAvailable={setHasSavedQueue} /></div>
        {selected && (
          <CaptureWorkspace key={selected} projectId={projectId} captureId={selected} onDeleted={() => show(null)} onUnsaved={setUnsaved} />
        )}
      </div>
      <AlertDialog open={leave.status === "blocked" || switchTo !== null}
        onOpenChange={(open) => { if (!open) { setSwitchTo(null); leave.reset?.(); } }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("capLeaveEditsTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("capLeaveEditsDescription")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("keepEditing")}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => {
              if (switchTo) { setUnsaved(false); show(switchTo.id); setSwitchTo(null); } else leave.proceed?.();
            }}>{t("capLeaveEdits")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ── History strip ─────────────────────────────────────────────────────────

function CaptureStrip({ projectId, captures, selected, onSelect }: {
  projectId: string; captures: CaptureStatus[]; selected: string | null; onSelect: (id: string | null) => void;
}) {
  const { t } = useI18n();
  if (captures.length === 0) return null;
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1">
      <button type="button" onClick={() => onSelect(null)}
        className="flex h-16 w-24 shrink-0 flex-col items-center justify-center gap-1 rounded-2xl border-2 border-dashed border-foreground/15 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground">
        <Camera className="size-4" /> {t("capAddPhotos")}
      </button>
      {captures.map((c) => (
        <button aria-pressed={selected === c.capture_id} key={c.capture_id} type="button" onClick={() => onSelect(c.capture_id)}
          className={cn("relative h-16 w-24 shrink-0 overflow-hidden rounded-2xl border-2 transition-[border-color,box-shadow]",
            selected === c.capture_id ? "border-primary shadow-[0_0_0_4px_color-mix(in_oklab,var(--primary)_20%,transparent)]" : "border-transparent hover:border-border")}
          title={c.image_name}>
          <img src={api.captureImageUrl(projectId, c.capture_id)} alt="" className="h-full w-full object-cover" />
          <span className="absolute inset-x-0 bottom-0 bg-black/55 px-1.5 py-0.5 text-left text-[0.68rem] text-white">
            {c.status === "completed" ? t("capStripProducts", { count: c.items }) : c.status === "failed" ? t("capStripFailed") : formatPercent(c.progress, 0)}
          </span>
        </button>
      ))}
    </div>
  );
}

// ── Workspace ─────────────────────────────────────────────────────────────

function CaptureWorkspace({ projectId, captureId, onDeleted, onUnsaved }: {
  projectId: string; captureId: string; onDeleted: () => void; onUnsaved: (unsaved: boolean) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const view = useQuery({
    queryKey: [...capturesKey(projectId), captureId],
    queryFn: ({ signal }) => api.getCapture(projectId, captureId, signal),
    refetchInterval: (q) => (q.state.status === "error" || (q.state.data && ["completed", "failed"].includes(q.state.data.status.status)) ? false : 1200),
  });
  const del = useMutation({
    mutationFn: () => api.deleteCapture(projectId, captureId),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: capturesKey(projectId) }); onDeleted(); },
  });
  // The photo, its reading, corrections and Shelf Lab results go with it: the first click asks, the second deletes.
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [hover, setHover] = useState<string | null>(null);
  const [tab, setTab] = useState<"planogram" | "lab">("planogram");
  const [draft, setDraft] = useState<LabDraft>(EMPTY_DRAFT);
  const [editId, setEditId] = useState<string | null>(null);
  const [showMask, setShowMask] = useState(false);
  const [focus, setFocus] = useState<CaptureBox | null>(null);
  const [attention, setAttention] = useState<Record<string, number> | null>(null);
  const status = view.data?.status;
  const result = view.data?.result ?? null;
  const processing = status?.status === "pending" || status?.status === "running";
  const pick = (id: string) => {
    if (draft.slot === "other" && needsOther(draft.kind)) setDraft({ ...draft, other: id, slot: "target" });
    else setDraft({ ...draft, target: id, slot: needsOther(draft.kind) && !draft.other ? "other" : "target" });
  };

  const loadError = view.isError ? (
    <div role="alert" className="space-y-2 rounded-xl border tone-bad p-3 text-sm">
      <p>{view.error instanceof Error ? view.error.message : t("capLoadError")}</p>
      <Button variant="outline" disabled={view.isFetching} onClick={() => void view.refetch()}>{t("capRetryCapture")}</Button>
    </div>
  ) : null;
  if (!status) return loadError ?? <div role="status" className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-6 animate-spin" />{t("capLoadingCapture")}</div>;
  return (
    <>
    {loadError}
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 md:flex-row">
      <div className="flex min-h-[55dvh] min-w-0 shrink-0 flex-col gap-2 md:min-h-0 md:flex-1">
        <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-[1.6rem] border border-glass-border bg-[var(--scene)] p-3 shadow-[var(--shadow-lift)]">
          {editId && result ? (
            <BeforeAfter beforeUrl={api.captureImageUrl(projectId, captureId)} afterUrl={api.editFileUrl(projectId, captureId, editId, "image")}
              maskUrl={api.editFileUrl(projectId, captureId, editId, "mask")} size={result.image_size} showMask={showMask} />
          ) : (
            <PhotoOverlay projectId={projectId} captureId={captureId} result={result} size={status.image_size} hover={hover} onHover={setHover}
              onPick={tab === "lab" ? pick : undefined} marks={tab === "lab" ? { target: draft.target, other: draft.other } : undefined} focus={focus}
              attention={tab === "lab" ? attention : null} />
          )}
          {editId && (
            <button type="button" onClick={() => setShowMask(!showMask)} className="glass absolute bottom-5 left-5 flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium">
              {showMask ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />} {showMask ? t("capHideChanged") : t("capShowChanged")}
            </button>
          )}
          {status.status !== "completed" && status.status !== "failed" && (
            <div className="glass absolute inset-x-6 bottom-6 rounded-2xl border p-4 shadow-float">
              <div className="mb-2 font-medium">{STAGES[status.stage] ? t(STAGES[status.stage]!) : status.stage}</div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="heat-gradient h-full transition-[width]" style={{ width: `${Math.max(4, status.progress * 100)}%` }} />
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="truncate">
            {status.image_name}
            {result ? t("capSummary", { products: result.items.length, facings: result.items.reduce((a, i) => a + i.facings, 0), shelves: result.bands.length, gaps: result.gaps.length })
              + ` · ${Object.prototype.hasOwnProperty.call(DETECTORS, result.detector) ? t(DETECTORS[result.detector]!) : result.detector === "gdino" ? "Grounding DINO" : result.detector}${result.model ? ` + ${result.model}` : ""}` : ""}
          </span>
          {!processing && (
            <button type="button" className={cn("flex shrink-0 items-center gap-1 rounded-md px-1 hover:text-destructive disabled:opacity-50", confirmDelete && "bg-destructive text-white hover:text-white dark:text-neutral-950 dark:hover:text-neutral-950")}
              disabled={del.isPending} onBlur={() => setConfirmDelete(false)} onClick={() => (confirmDelete ? del.mutate() : setConfirmDelete(true))}>
              {del.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />} {confirmDelete ? t("mkDeleteConfirm") : t("studioDelete")}
            </button>
          )}
        </div>
        {del.error && <p role="alert" className="text-xs text-destructive">{del.error.message}</p>}
      </div>
      <aside className="panel flex w-full min-w-0 shrink-0 flex-col overflow-hidden rounded-[1.6rem] md:w-[28rem]">
        <div className="flex gap-1 border-b border-glass-border p-2">
          {([
            { id: "planogram", label: t("capTabPlanogram"), icon: ListChecks },
            { id: "lab", label: t("capTabLab"), icon: FlaskConical },
          ] as const).map(({ id, label, icon: Icon }) => (
            <button aria-pressed={tab === id} key={id} type="button" onClick={() => setTab(id)}
              className={cn("flex h-10 min-w-0 flex-1 items-center justify-center gap-1.5 rounded-xl px-2 text-sm font-medium transition-colors",
                tab === id ? "bg-foreground/[0.08] text-foreground shadow-[inset_0_1px_0_var(--highlight)]" : "text-muted-foreground hover:text-foreground")}>
              <Icon className="hidden size-4 shrink-0 sm:block" /> {label}
              {id === "lab" && <span className="hidden rounded-full bg-primary px-1.5 py-px text-[0.68rem] font-bold text-primary-foreground sm:inline">{t("capNewBadge")}</span>}
            </button>
          ))}
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3">
          {status.status === "failed" && <p className="rounded-xl border tone-bad p-3 text-sm">{status.error}</p>}
          {/* Kept mounted on the Shelf Lab tab so unsaved corrections survive a look there. */}
          {result && <div hidden={tab !== "planogram"}><ItemsEditor projectId={projectId} captureId={captureId} result={result} hover={hover} onHover={setHover} onUnsaved={onUnsaved} /></div>}
          {result && tab === "planogram" && <ApplyPanel projectId={projectId} captureId={captureId} result={result} />}
          {result && tab === "planogram" && <RivalCard projectId={projectId} captureId={captureId} result={result} />}
          {result && tab === "lab" && (
            <ShelfLabPanel projectId={projectId} captureId={captureId} result={result} draft={draft} setDraft={setDraft}
              editId={editId} onSelectEdit={setEditId} onFocus={setFocus} onAttention={setAttention} />
          )}
          {!result && status.status !== "failed" && <p className="p-6 text-center text-sm text-muted-foreground">{t("capReadingShelf")}</p>}
        </div>
      </aside>
    </div>
    </>
  );
}

function PhotoOverlay({ projectId, captureId, result, size, hover, onHover, onPick, marks, focus, attention }: {
  projectId: string; captureId: string; result: CaptureResult | null; size: [number, number];
  hover: string | null; onHover: (id: string | null) => void;
  onPick?: (id: string) => void; marks?: { target: string | null; other: string | null }; focus?: CaptureBox | null;
  attention?: Record<string, number> | null;
}) {
  const { t } = useI18n();
  const [w, h] = result?.image_size ?? size;
  if (!w || !h) return null;
  return (
    <div className="relative max-h-full max-w-full" style={{ aspectRatio: `${w} / ${h}`, height: "100%" }}>
      <img src={api.captureImageUrl(projectId, captureId)} alt={t("capShelfPhotoAlt")} className="absolute inset-0 h-full w-full rounded-lg object-contain" />
      {result && (
        <svg viewBox={`0 0 ${w} ${h}`} className="absolute inset-0 h-full w-full" onMouseLeave={() => onHover(null)}>
          {result.bands.map((b) => (
            <polygon key={b.index} points={b.polygon.map(([x, y]) => `${x},${y}`).join(" ")} fill="none"
              stroke="white" strokeOpacity={0.8} strokeWidth={Math.max(2, w / 400)} strokeDasharray={`${w / 80} ${w / 120}`} />
          ))}
          {result.gaps.map((g, i) => (
            <rect key={i} x={g.box.x1} y={g.box.y1} width={g.box.x2 - g.box.x1} height={g.box.y2 - g.box.y1}
              fill="#e0304a" fillOpacity={0.28} stroke="#e0304a" strokeWidth={Math.max(2, w / 350)} />
          ))}
          {result.items.map((it) => it.boxes.map((bx, j) => {
            const role = marks?.target === it.id ? "target" : marks?.other === it.id ? "other" : null;
            const color = role === "target" ? "var(--volt)" : role === "other" ? "var(--heat-1)" : categoryColor(it.category);
            return (
              <rect key={`${it.id}-${j}`} x={bx.x1} y={bx.y1} width={bx.x2 - bx.x1} height={bx.y2 - bx.y1} rx={w / 200}
                fill={color} fillOpacity={role ? 0.35 : hover === it.id ? 0.45 : 0.12}
                stroke={color} strokeWidth={role || hover === it.id ? Math.max(3, w / 180) : Math.max(1.5, w / 450)}
                onMouseEnter={() => onHover(it.id)} onClick={onPick ? () => onPick(it.id) : undefined} className="cursor-pointer">
                <title>{it.name || t("capUnrecognized")}</title>
              </rect>
            );
          }))}
          {attention && result.items.map((it) => {
            const share = attention[it.sku] ?? 0;
            const b = it.boxes[0];
            if (!b) return null;
            const all = it.boxes.reduce((acc, bx) => ({ x1: Math.min(acc.x1, bx.x1), y1: Math.min(acc.y1, bx.y1), x2: Math.max(acc.x2, bx.x2), y2: Math.max(acc.y2, bx.y2) }), b);
            const heat = share >= 0.3 ? "var(--heat-3)" : share >= 0.12 ? "var(--heat-2)" : share > 0 ? "var(--heat-1)" : "#000";
            return (
              <g key={`att-${it.id}`} pointerEvents="none">
                <rect x={all.x1} y={all.y1} width={all.x2 - all.x1} height={all.y2 - all.y1} rx={w / 160}
                  fill={heat} fillOpacity={share > 0 ? 0.25 + Math.min(0.5, share) : 0.45} stroke={share > 0 ? heat : "none"} strokeWidth={Math.max(2, w / 300)} />
                {share > 0 && (
                  <text x={(all.x1 + all.x2) / 2} y={all.y1 + (all.y2 - all.y1) / 2} textAnchor="middle" dominantBaseline="central"
                    fontSize={Math.max(14, w / 30)} fontWeight={700} fill="white" stroke="black" strokeWidth={Math.max(1, w / 500)} paintOrder="stroke">
                    {formatPercent(share, 0)}
                  </text>
                )}
              </g>
            );
          })}
          {focus && (
            <rect x={focus.x1} y={focus.y1} width={focus.x2 - focus.x1} height={focus.y2 - focus.y1} rx={w / 150}
              fill="none" stroke="var(--volt)" strokeWidth={Math.max(4, w / 120)} className="animate-pulse" pointerEvents="none" />
          )}
        </svg>
      )}
    </div>
  );
}

// ── Product list ──────────────────────────────────────────────────────────

const MAX_FACINGS = 24;  // the most the server saves for one product
interface Draft { id: string; name: string; brand: string; size: string; category: string; price: string; facings: number; level: number; estimated: boolean; confidence: number }

const toDraft = (it: CaptureItem, currency: string): Draft => ({
  id: it.id, name: it.name, brand: it.brand, size: it.size, category: it.category,
  price: it.price == null ? "" : minorUnitDivisor(currency) === 1 ? String(it.price) : (it.price / minorUnitDivisor(currency)).toFixed(2),
  facings: it.facings, level: it.level, estimated: it.price_estimated, confidence: it.confidence,
});

function ItemsEditor({ projectId, captureId, result, hover, onHover, onUnsaved }: {
  projectId: string; captureId: string; result: CaptureResult; hover: string | null; onHover: (id: string | null) => void;
  onUnsaved: (unsaved: boolean) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const initial = useMemo(() => [...result.items].sort((a, b) => b.level - a.level || a.order - b.order).map((i) => toDraft(i, result.currency)), [result]);
  const [drafts, setDrafts] = useState<Draft[]>(initial);
  useEffect(() => setDrafts(initial), [initial]);
  const dirty = JSON.stringify(drafts) !== JSON.stringify(initial);
  useEffect(() => { onUnsaved(dirty); }, [dirty, onUnsaved]);
  useEffect(() => () => onUnsaved(false), [onUnsaved]);
  const badPrice = (d: Draft) => d.price.trim() !== "" && toMinor(d.price, minorUnitDivisor(result.currency)) === null;
  const invalidPrice = drafts.some(badPrice);
  const priceErrorId = useId();
  const save = useMutation({
    mutationFn: () => api.updateCapture(projectId, captureId, drafts.map((d): CaptureEdit => ({
      id: d.id, name: d.name, brand: d.brand, size: d.size, category: d.category, facings: d.facings, level: d.level,
      // An untouched estimated price stays estimated: null keeps the stored price and flag.
      price: d.estimated ? null : toMinor(d.price, minorUnitDivisor(result.currency)),
    }))),
    onSuccess: (v) => qc.setQueryData([...capturesKey(projectId), captureId], v),
  });
  const patch = (id: string, p: Partial<Draft>) => setDrafts((ds) => ds.map((d) => (d.id === id ? { ...d, ...p } : d)));
  const levels = [...new Set(drafts.map((d) => d.level))].sort((a, b) => b - a);
  const levelName: Record<number, MessageKey> = { 4: "capLevelTop", 3: "capLevelEye", 2: "capLevelWaist", 1: "capLevelBottom" };

  return (
    <section className="rounded-2xl border bg-card p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="section-title">{t("capProductsOnShelf")}</h3>
        <Button size="sm" disabled={!dirty || invalidPrice || save.isPending} onClick={() => save.mutate()} className="gap-1.5">
          {save.isPending ? <Loader2 className="size-3.5 animate-spin" /> : save.isSuccess && !dirty ? <Check className="size-3.5" /> : <Save className="size-3.5" />}
          {dirty ? t("capSaveChanges") : t("studioSaved")}
        </Button>
      </div>
      {invalidPrice && <p id={priceErrorId} role="alert" className="mb-2 text-sm text-destructive">{t("capInvalidPriceKeep")}</p>}
      {save.error && <p role="alert" className="mb-2 text-sm text-destructive">{save.error instanceof Error ? save.error.message : String(save.error)}</p>}
      <div className="space-y-3">
        {levels.map((lv) => (
          <div key={lv}>
            <div className="mb-1 text-xs font-medium text-muted-foreground">{levelName[lv] ? t(levelName[lv]!) : t("capLevelN", { level: lv })}</div>
            <ul className="space-y-1.5">
              {drafts.filter((d) => d.level === lv).map((d) => (
                <li key={d.id} onMouseEnter={() => onHover(d.id)} onMouseLeave={() => onHover(null)}
                  className={cn("rounded-xl border p-2 transition-colors", hover === d.id ? "border-primary bg-primary/5" : "")}>
                  <div className="flex items-center gap-2">
                    <span className="size-2.5 shrink-0 rounded-full" style={{ background: categoryColor(d.category) }} />
                    <Input value={d.name} placeholder={t("capProductName")} aria-label={t("capProductName")} onChange={(e) => patch(d.id, { name: e.target.value })} className="h-8 flex-1 text-sm" />
                    <button type="button" aria-label={t("capRemoveProduct", { name: d.name || t("capProductName") })} className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
                      onClick={() => setDrafts((ds) => ds.filter((x) => x.id !== d.id))}>
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                  <div className="mt-1.5 grid grid-cols-[minmax(0,1fr)_92px] items-center gap-2 text-xs sm:grid-cols-[minmax(0,1fr)_88px_92px]">
                    <select className="col-span-2 h-7 min-w-0 rounded-md border bg-background px-1 sm:col-span-1" value={d.category}
                      aria-label={t("capCategoryOf", { name: d.name || t("capProductName") })} onChange={(e) => patch(d.id, { category: e.target.value })}>
                      <option value="">{categoryLabel("", t)}</option>
                      {CAPTURE_CATEGORIES.map((c) => <option key={c.key} value={c.key}>{t(c.label)}</option>)}
                    </select>
                    <div className="relative">
                      <Input value={d.price} inputMode="decimal" aria-label={t("capPriceOf", { name: d.name || t("capProductName") })}
                        aria-invalid={badPrice(d)} aria-describedby={badPrice(d) ? priceErrorId : undefined} onChange={(e) => {
                          // Typing confirms an estimated price; putting the original text back leaves it estimated.
                          const start = initial.find((x) => x.id === d.id);
                          patch(d.id, { price: e.target.value, estimated: start?.estimated === true && start.price === e.target.value });
                        }}
                        className={cn("h-7 pr-1 text-xs tabular-nums", d.estimated && "border-dashed text-muted-foreground")} placeholder={t("capPricePlaceholder")}
                        title={d.estimated ? t("capEstimatedPriceTitle") : undefined} />
                    </div>
                    <div className="flex items-center justify-end gap-1">
                      {/* At a limit the button stays focusable, so pressing it repeatedly does not drop keyboard focus. */}
                      <button type="button" aria-label={t("capFewerFacings", { name: d.name || t("capProductName") })} aria-disabled={d.facings <= 1} className="rounded-md border p-0.5 hover:bg-muted aria-disabled:opacity-40 aria-disabled:hover:bg-transparent" onClick={() => patch(d.id, { facings: Math.max(1, d.facings - 1) })}><Minus className="size-3" /></button>
                      <span className="w-12 text-center tabular-nums" aria-live="polite">{d.facings}×</span>
                      <button type="button" aria-label={t("capMoreFacings", { name: d.name || t("capProductName") })} aria-disabled={d.facings >= MAX_FACINGS} className="rounded-md border p-0.5 hover:bg-muted aria-disabled:opacity-40 aria-disabled:hover:bg-transparent" onClick={() => patch(d.id, { facings: Math.min(MAX_FACINGS, d.facings + 1) })}><Plus className="size-3" /></button>
                    </div>
                  </div>
                  {(d.brand || d.size || d.confidence > 0) && (
                    <div className="mt-1 truncate text-xs text-muted-foreground">
                      {[d.brand, d.size].filter(Boolean).join(" · ")}{d.confidence > 0 ? `${d.brand || d.size ? " · " : ""}${t("capConfidence", { value: d.confidence })}` : ""}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {result.notes.length > 0 && <ul className="mt-3 list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
      <p className="mt-2 text-xs text-muted-foreground">
        {t(result.items.some((i) => i.price_estimated) ? "capPricesInDashed" : "capPricesIn", { currency: result.currency })}
        {t("capPricesTotal", { count: result.items.length, amount: formatMoney(result.items.reduce((a, i) => a + (i.price ?? 0), 0), result.currency) })}
      </p>
    </section>
  );
}

// ── Apply to a layout ─────────────────────────────────────────────────────

function ApplyPanel({ projectId, captureId, result }: { projectId: string; captureId: string; result: CaptureResult }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const router = useRouter();
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const setSelectedSetupId = useSimulationStore((s) => s.setSelectedSetupId);
  const currentSetup = useSimulationStore((s) => s.selectedSetupId);
  const { data: setups = [] } = useQuery({ queryKey: queryKeys.setups(projectId), queryFn: ({ signal }) => api.getSetups(projectId, signal) });
  const [setupId, setSetupId] = useState<string>("");
  const base = [setupId, currentSetup].find((id) => setups.some((s) => s.id === id)) ?? setups[setups.length - 1]?.id ?? "";
  const { data: setup } = useQuery({
    queryKey: ["projects", projectId, "setups", base, "detail"],
    queryFn: ({ signal }) => api.getSetup(projectId, base, signal),
    enabled: !!base,
  });
  const racks = (setup?.store?.racks ?? []).filter((r) => r.type === (result.rack_type === "fridge" ? "fridge" : "shelf"));
  const [mode, setMode] = useState<"new" | "replace">("new");
  const [rackId, setRackId] = useState("");
  const targetRackId = racks.some((r) => r.id === rackId) ? rackId : racks[0]?.id;
  const apply = useMutation({
    mutationFn: () => api.applyCapture(projectId, captureId, mode === "new" ? { setup_id: base, new_rack: true } : { setup_id: base, rack_id: targetRackId }),
    onSuccess: async (r) => {
      // Captured SKU photos also decorate cached run playback.
      await qc.invalidateQueries({ queryKey: queryKeys.project(projectId) });
      await qc.invalidateQueries({ queryKey: capturesKey(projectId) });
      if (!mounted.current || router.state.location.pathname !== `/capture/${projectId}`) return;
      setSelectedSetupId(r.setup_id);
      void navigate({ to: "/projects/$pid", params: { pid: projectId } });
    },
  });
  return (
    <section className="rounded-2xl border bg-card p-3 text-sm">
      <h3 className="section-title mb-2">{t("capApplyTitle")}</h3>
      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">{t("capStartFrom")}</span>
        <select className="h-10 rounded-xl border bg-card/60 px-2.5" value={base} onChange={(e) => setSetupId(e.target.value)}>
          {setups.map((s) => <option key={s.id} value={s.id}>{s.name}{s.status === "draft" ? t("capDraftSuffix") : ""}</option>)}
        </select>
      </label>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        {([
          { id: "new", title: t("capAddNewRack"), hint: t("capAddNewRackHint") },
          { id: "replace", title: t("capReplaceRack"), hint: t("capReplaceRackHint") },
        ] as const).map((o) => (
          <button aria-pressed={mode === o.id} key={o.id} type="button" onClick={() => setMode(o.id)}
            className={cn("rounded-lg border p-2 text-left", mode === o.id ? "border-primary bg-primary/5" : "hover:bg-muted/50")}>
            <div className="font-medium">{o.title}</div>
            <div className="text-muted-foreground">{o.hint}</div>
          </button>
        ))}
      </div>
      {mode === "replace" && (
        <select className="mt-2 h-9 w-full rounded-lg border bg-background px-2" value={targetRackId ?? ""} onChange={(e) => setRackId(e.target.value)}>
          {racks.map((r) => <option key={r.id} value={r.id}>{r.rack_name || r.id}</option>)}
        </select>
      )}
      {apply.error && <p className="mt-2 text-xs text-destructive">{apply.error instanceof Error ? apply.error.message : String(apply.error)}</p>}
      <Button className="mt-3 h-auto min-h-10 w-full gap-2 py-2.5 whitespace-normal" size="lg" disabled={!base || apply.isPending || (mode === "replace" && !targetRackId)} onClick={() => apply.mutate()}>
        {apply.isPending ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />} {t("capCreateLayout")}
      </Button>
      <p className="mt-2 text-xs text-muted-foreground">{t("capCreateLayoutHint")}</p>
    </section>
  );
}
