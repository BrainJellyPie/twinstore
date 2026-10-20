// Shelf capture: photograph a shelf, let detection + a VLM read it into a planogram, correct what
// it got wrong, and put it into a layout to simulate.

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Camera, Check, ImagePlus, Loader2, Minus, Plus, Save, Trash2, Upload, Wand2 } from "lucide-react";

import * as api from "@/shared/api/client";
import type { CaptureDetector, CaptureEdit, CaptureItem, CaptureResult, CaptureStatus } from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";
import { formatMoney } from "@/shared/utils/money";
import { cn } from "@/shared/utils/cn";

import { CAPTURE_CATEGORIES, categoryColor, categoryLabel } from "./categories";

const capturesKey = (pid: string) => ["projects", pid, "captures"] as const;

export function CapturePage({ projectId }: { projectId: string }) {
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({
    queryKey: capturesKey(projectId),
    queryFn: ({ signal }) => api.listCaptures(projectId, signal),
    refetchInterval: (q) => (q.state.data?.some((c) => c.status === "pending" || c.status === "running") ? 1500 : false),
  });
  const captures = useMemo(() => list.data ?? [], [list.data]);
  const [chosenNew, setChosenNew] = useState(false);
  useEffect(() => {
    if (!selected && !chosenNew && captures.length > 0) setSelected(captures[0]!.capture_id);
  }, [captures, selected, chosenNew]);
  const select = (id: string | null) => { setChosenNew(id === null); setSelected(id); };

  return (
    <div className="flex min-h-0 flex-1">
      <div className="flex min-w-0 flex-1 flex-col gap-3 p-4">
        <CaptureStrip projectId={projectId} captures={captures} selected={selected} onSelect={select} />
        {selected ? (
          <CaptureWorkspace key={selected} projectId={projectId} captureId={selected} onDeleted={() => select(null)} />
        ) : (
          <UploadCard projectId={projectId} onStarted={select} large />
        )}
      </div>
    </div>
  );
}

// ── Upload ────────────────────────────────────────────────────────────────

function UploadCard({ projectId, onStarted, large = false }: { projectId: string; onStarted: (id: string) => void; large?: boolean }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [detector, setDetector] = useState<CaptureDetector>("auto");
  const [model, setModel] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [rackType, setRackType] = useState<"shelf" | "fridge">("shelf");
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const upload = useMutation({
    mutationFn: (file: File) => api.createCapture(projectId, file, { detector, model, currency, rack_type: rackType }),
    onSuccess: async (s) => {
      await qc.invalidateQueries({ queryKey: capturesKey(projectId) });
      onStarted(s.capture_id);
    },
  });
  const pick = (files: FileList | null) => {
    const f = files?.[0];
    if (f) upload.mutate(f);
  };

  return (
    <div className={cn("grid gap-4", large ? "mx-auto mt-6 w-full max-w-3xl" : "")}>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files); }}
        className={cn(
          "flex flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed bg-card p-10 text-center transition-colors",
          drag ? "border-primary bg-primary/5" : "hover:border-primary/60",
        )}
      >
        {upload.isPending ? <Loader2 className="size-10 animate-spin text-primary" /> : <ImagePlus className="size-10 text-primary" />}
        <span className="font-display text-2xl font-semibold">Photograph a shelf, get its planogram</span>
        <span className="max-w-lg text-muted-foreground">
          Drop a photo of one shelf section, taken straight on. Parastore finds the shelves and every facing, reads each
          product and its price tag, and turns it into a rack you can put into a layout and simulate.
        </span>
        <span className="mt-1 inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 font-medium text-primary-foreground">
          <Upload className="size-4" /> Choose a photo
        </span>
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => pick(e.target.files)} />
      </button>
      {upload.error && <p className="text-sm text-destructive">{upload.error instanceof Error ? upload.error.message : String(upload.error)}</p>}
      <div className="grid grid-cols-2 gap-3 rounded-2xl border bg-card p-4 text-sm md:grid-cols-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Find products with</span>
          <select className="h-9 rounded-lg border bg-background px-2" value={detector} onChange={(e) => setDetector(e.target.value as CaptureDetector)}>
            <option value="auto">Best available</option>
            <option value="gdino">Grounding DINO (object detector)</option>
            <option value="classic">Shelf geometry (fast)</option>
            <option value="vlm">Vision model boxes</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Read products with</span>
          <select className="h-9 rounded-lg border bg-background px-2" value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="">App's vision model</option>
            {models.filter((m) => m.vision).map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
            <option value="none">Don't read (typical prices)</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Prices in</span>
          <select className="h-9 rounded-lg border bg-background px-2" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            <option value="USD">US dollars</option>
            <option value="KRW">Korean won</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">It is a</span>
          <select className="h-9 rounded-lg border bg-background px-2" value={rackType} onChange={(e) => setRackType(e.target.value as "shelf" | "fridge")}>
            <option value="shelf">Shelf / gondola</option>
            <option value="fridge">Fridge</option>
          </select>
        </label>
      </div>
    </div>
  );
}

// ── History strip ─────────────────────────────────────────────────────────

function CaptureStrip({ projectId, captures, selected, onSelect }: {
  projectId: string; captures: CaptureStatus[]; selected: string | null; onSelect: (id: string | null) => void;
}) {
  if (captures.length === 0) return null;
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1">
      <button type="button" onClick={() => onSelect(null)}
        className="flex h-16 w-24 shrink-0 flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed text-xs text-muted-foreground hover:border-primary hover:text-foreground">
        <Camera className="size-4" /> New photo
      </button>
      {captures.map((c) => (
        <button key={c.capture_id} type="button" onClick={() => onSelect(c.capture_id)}
          className={cn("relative h-16 w-24 shrink-0 overflow-hidden rounded-xl border-2 transition-colors",
            selected === c.capture_id ? "border-primary" : "border-transparent hover:border-border")}
          title={c.image_name}>
          <img src={api.captureImageUrl(projectId, c.capture_id)} alt="" className="h-full w-full object-cover" />
          <span className="absolute inset-x-0 bottom-0 bg-black/55 px-1.5 py-0.5 text-left text-[0.68rem] text-white">
            {c.status === "completed" ? `${c.items} products` : c.status === "failed" ? "failed" : `${Math.round(c.progress * 100)} %`}
          </span>
        </button>
      ))}
    </div>
  );
}

// ── Workspace ─────────────────────────────────────────────────────────────

const STAGES: Record<string, string> = {
  queued: "Waiting…", detecting: "Finding shelves and products…", grouping: "Grouping identical facings…",
  reading: "Reading products and price tags…", planogram: "Building the planogram…", done: "Done",
};

function CaptureWorkspace({ projectId, captureId, onDeleted }: { projectId: string; captureId: string; onDeleted: () => void }) {
  const qc = useQueryClient();
  const view = useQuery({
    queryKey: [...capturesKey(projectId), captureId],
    queryFn: ({ signal }) => api.getCapture(projectId, captureId, signal),
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status.status) ? false : 1200),
  });
  const del = useMutation({
    mutationFn: () => api.deleteCapture(projectId, captureId),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: capturesKey(projectId) }); onDeleted(); },
  });
  const [hover, setHover] = useState<string | null>(null);
  const status = view.data?.status;
  const result = view.data?.result ?? null;

  if (!status) return <div className="flex flex-1 items-center justify-center"><Loader2 className="size-6 animate-spin" /></div>;
  return (
    <div className="flex min-h-0 flex-1 gap-4">
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="relative flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-2xl border bg-[var(--scene)]">
          <PhotoOverlay projectId={projectId} captureId={captureId} result={result} size={status.image_size} hover={hover} onHover={setHover} />
          {status.status !== "completed" && status.status !== "failed" && (
            <div className="glass absolute inset-x-6 bottom-6 rounded-2xl border p-4 shadow-float">
              <div className="mb-2 font-medium">{STAGES[status.stage] ?? status.stage}</div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="heat-gradient h-full transition-[width]" style={{ width: `${Math.max(4, status.progress * 100)}%` }} />
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span className="truncate">
            {status.image_name}
            {result ? ` · ${result.items.length} products · ${result.items.reduce((a, i) => a + i.facings, 0)} facings · ${result.bands.length} shelves · ${result.gaps.length} gaps`
              + ` · ${result.detector}${result.model ? ` + ${result.model}` : ""}` : ""}
          </span>
          <button type="button" className="flex items-center gap-1 hover:text-destructive" onClick={() => del.mutate()}>
            <Trash2 className="size-3.5" /> Delete
          </button>
        </div>
      </div>
      <aside className="flex w-[27rem] shrink-0 flex-col gap-3 overflow-y-auto">
        {status.status === "failed" && <p className="rounded-xl border tone-bad p-3 text-sm">{status.error}</p>}
        {result && <ItemsEditor projectId={projectId} captureId={captureId} result={result} hover={hover} onHover={setHover} />}
        {result && <ApplyPanel projectId={projectId} captureId={captureId} result={result} />}
      </aside>
    </div>
  );
}

function PhotoOverlay({ projectId, captureId, result, size, hover, onHover }: {
  projectId: string; captureId: string; result: CaptureResult | null; size: [number, number];
  hover: string | null; onHover: (id: string | null) => void;
}) {
  const [w, h] = result?.image_size ?? size;
  if (!w || !h) return null;
  return (
    <div className="relative max-h-full max-w-full" style={{ aspectRatio: `${w} / ${h}`, height: "100%" }}>
      <img src={api.captureImageUrl(projectId, captureId)} alt="Shelf photo" className="absolute inset-0 h-full w-full rounded-lg object-contain" />
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
          {result.items.map((it) => it.boxes.map((bx, j) => (
            <rect key={`${it.id}-${j}`} x={bx.x1} y={bx.y1} width={bx.x2 - bx.x1} height={bx.y2 - bx.y1} rx={w / 200}
              fill={categoryColor(it.category)} fillOpacity={hover === it.id ? 0.45 : 0.12}
              stroke={categoryColor(it.category)} strokeWidth={hover === it.id ? Math.max(3, w / 200) : Math.max(1.5, w / 450)}
              onMouseEnter={() => onHover(it.id)} className="cursor-pointer">
              <title>{it.name || "Unrecognized product"}</title>
            </rect>
          )))}
        </svg>
      )}
    </div>
  );
}

// ── Product list ──────────────────────────────────────────────────────────

interface Draft { id: string; name: string; brand: string; size: string; category: string; price: string; facings: number; level: number; estimated: boolean; confidence: number }

const toDraft = (it: CaptureItem, currency: string): Draft => ({
  id: it.id, name: it.name, brand: it.brand, size: it.size, category: it.category,
  price: it.price == null ? "" : currency === "KRW" ? String(it.price) : (it.price / 100).toFixed(2),
  facings: it.facings, level: it.level, estimated: it.price_estimated, confidence: it.confidence,
});

function ItemsEditor({ projectId, captureId, result, hover, onHover }: {
  projectId: string; captureId: string; result: CaptureResult; hover: string | null; onHover: (id: string | null) => void;
}) {
  const qc = useQueryClient();
  const initial = useMemo(() => [...result.items].sort((a, b) => b.level - a.level || a.order - b.order).map((i) => toDraft(i, result.currency)), [result]);
  const [drafts, setDrafts] = useState<Draft[]>(initial);
  useEffect(() => setDrafts(initial), [initial]);
  const dirty = JSON.stringify(drafts) !== JSON.stringify(initial);
  const save = useMutation({
    mutationFn: () => api.updateCapture(projectId, captureId, drafts.map((d): CaptureEdit => ({
      id: d.id, name: d.name, brand: d.brand, size: d.size, category: d.category, facings: d.facings, level: d.level,
      price: d.price.trim() === "" ? null : result.currency === "KRW" ? Math.round(Number(d.price)) : Math.round(Number(d.price) * 100),
    }))),
    onSuccess: (v) => qc.setQueryData([...capturesKey(projectId), captureId], v),
  });
  const patch = (id: string, p: Partial<Draft>) => setDrafts((ds) => ds.map((d) => (d.id === id ? { ...d, ...p } : d)));
  const levels = [...new Set(drafts.map((d) => d.level))].sort((a, b) => b - a);
  const levelName: Record<number, string> = { 4: "Top shelf", 3: "Eye level", 2: "Waist", 1: "Bottom shelf" };

  return (
    <section className="rounded-2xl border bg-card p-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="section-title">Products on this shelf</h3>
        <Button size="sm" disabled={!dirty || save.isPending} onClick={() => save.mutate()} className="gap-1.5">
          {save.isPending ? <Loader2 className="size-3.5 animate-spin" /> : save.isSuccess && !dirty ? <Check className="size-3.5" /> : <Save className="size-3.5" />}
          {dirty ? "Save changes" : "Saved"}
        </Button>
      </div>
      <div className="space-y-3">
        {levels.map((lv) => (
          <div key={lv}>
            <div className="mb-1 text-xs font-medium text-muted-foreground">{levelName[lv] ?? `Level ${lv}`}</div>
            <ul className="space-y-1.5">
              {drafts.filter((d) => d.level === lv).map((d) => (
                <li key={d.id} onMouseEnter={() => onHover(d.id)} onMouseLeave={() => onHover(null)}
                  className={cn("rounded-xl border p-2 transition-colors", hover === d.id ? "border-primary bg-primary/5" : "")}>
                  <div className="flex items-center gap-2">
                    <span className="size-2.5 shrink-0 rounded-full" style={{ background: categoryColor(d.category) }} />
                    <Input value={d.name} placeholder="Product name" onChange={(e) => patch(d.id, { name: e.target.value })} className="h-8 flex-1 text-sm" />
                    <button type="button" aria-label="Remove product" className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-destructive"
                      onClick={() => setDrafts((ds) => ds.filter((x) => x.id !== d.id))}>
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                  <div className="mt-1.5 grid grid-cols-[1fr_88px_92px] items-center gap-2 text-xs">
                    <select className="h-7 min-w-0 rounded-md border bg-background px-1" value={d.category} onChange={(e) => patch(d.id, { category: e.target.value })}>
                      <option value="">{categoryLabel("")}</option>
                      {CAPTURE_CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                    </select>
                    <div className="relative">
                      <Input value={d.price} inputMode="decimal" onChange={(e) => patch(d.id, { price: e.target.value, estimated: false })}
                        className={cn("h-7 pr-1 text-xs tabular-nums", d.estimated && "border-dashed text-muted-foreground")} placeholder="price"
                        title={d.estimated ? "Tag unreadable — typical price for the category" : undefined} />
                    </div>
                    <div className="flex items-center justify-end gap-1">
                      <button type="button" aria-label="Fewer facings" className="rounded-md border p-0.5 hover:bg-muted" onClick={() => patch(d.id, { facings: Math.max(1, d.facings - 1) })}><Minus className="size-3" /></button>
                      <span className="w-12 text-center tabular-nums">{d.facings}×</span>
                      <button type="button" aria-label="More facings" className="rounded-md border p-0.5 hover:bg-muted" onClick={() => patch(d.id, { facings: d.facings + 1 })}><Plus className="size-3" /></button>
                    </div>
                  </div>
                  {(d.brand || d.size || d.confidence > 0) && (
                    <div className="mt-1 truncate text-xs text-muted-foreground">
                      {[d.brand, d.size].filter(Boolean).join(" · ")}{d.confidence > 0 ? `${d.brand || d.size ? " · " : ""}read with confidence ${d.confidence}/10` : ""}
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
        Prices in {result.currency}{result.items.some((i) => i.price_estimated) ? "; dashed prices are typical prices for the category because the tag could not be read" : ""}.
        {` Total ${result.items.length} products, ${formatMoney(result.items.reduce((a, i) => a + (i.price ?? 0), 0), result.currency)} for one of each.`}
      </p>
    </section>
  );
}

// ── Apply to a layout ─────────────────────────────────────────────────────

function ApplyPanel({ projectId, captureId, result }: { projectId: string; captureId: string; result: CaptureResult }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const setSelectedSetupId = useSimulationStore((s) => s.setSelectedSetupId);
  const currentSetup = useSimulationStore((s) => s.selectedSetupId);
  const { data: setups = [] } = useQuery({ queryKey: queryKeys.setups(projectId), queryFn: ({ signal }) => api.getSetups(projectId, signal) });
  const [setupId, setSetupId] = useState<string>("");
  const base = setupId || currentSetup || setups[setups.length - 1]?.id || "";
  const { data: setup } = useQuery({
    queryKey: ["projects", projectId, "setups", base, "detail"],
    queryFn: ({ signal }) => api.getSetup(projectId, base, signal),
    enabled: !!base,
  });
  const racks = (setup?.store?.racks ?? []).filter((r) => r.type === (result.rack_type === "fridge" ? "fridge" : "shelf"));
  const [mode, setMode] = useState<"new" | "replace">("new");
  const [rackId, setRackId] = useState("");
  const apply = useMutation({
    mutationFn: () => api.applyCapture(projectId, captureId, mode === "new" ? { setup_id: base, new_rack: true } : { setup_id: base, rack_id: rackId || racks[0]?.id }),
    onSuccess: async (r) => {
      await qc.invalidateQueries({ queryKey: queryKeys.setups(projectId) });
      await qc.invalidateQueries({ queryKey: capturesKey(projectId) });
      setSelectedSetupId(r.setup_id);
      void navigate({ to: "/projects/$pid", params: { pid: projectId } });
    },
  });
  return (
    <section className="rounded-2xl border bg-card p-3 text-sm">
      <h3 className="section-title mb-2">Put it in a layout</h3>
      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">Start from</span>
        <select className="h-9 rounded-lg border bg-background px-2" value={base} onChange={(e) => setSetupId(e.target.value)}>
          {setups.map((s) => <option key={s.id} value={s.id}>{s.name}{s.status === "draft" ? " (draft)" : ""}</option>)}
        </select>
      </label>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        {([
          { id: "new", title: "Add as a new rack", hint: "Placed on free floor; wide photos become several racks" },
          { id: "replace", title: "Replace a rack", hint: "Swap the contents of one existing rack face" },
        ] as const).map((o) => (
          <button key={o.id} type="button" onClick={() => setMode(o.id)}
            className={cn("rounded-lg border p-2 text-left", mode === o.id ? "border-primary bg-primary/5" : "hover:bg-muted/50")}>
            <div className="font-medium">{o.title}</div>
            <div className="text-muted-foreground">{o.hint}</div>
          </button>
        ))}
      </div>
      {mode === "replace" && (
        <select className="mt-2 h-9 w-full rounded-lg border bg-background px-2" value={rackId || racks[0]?.id || ""} onChange={(e) => setRackId(e.target.value)}>
          {racks.map((r) => <option key={r.id} value={r.id}>{r.rack_name || r.id}</option>)}
        </select>
      )}
      {apply.error && <p className="mt-2 text-xs text-destructive">{apply.error instanceof Error ? apply.error.message : String(apply.error)}</p>}
      <Button className="mt-3 w-full gap-2" size="lg" disabled={!base || apply.isPending || (mode === "replace" && racks.length === 0)} onClick={() => apply.mutate()}>
        {apply.isPending ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />} Create a layout with this shelf
      </Button>
      <p className="mt-2 text-xs text-muted-foreground">Saved as a new draft layout — the original stays as it is, ready for an A/B run.</p>
    </section>
  );
}
