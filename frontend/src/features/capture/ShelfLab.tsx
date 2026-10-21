// Shelf Lab: controlled experiments on the captured photo.
// - Counterfactual: swap products, empty a run, put a new package on the shelf, change a price tag or hang
//   a promotion sign — rendered into the real photo, with the exact changed pixels as a mask.
// - Sim2real: the same shoppers on the photo and on the simulator's render of the same planogram.
// - Audit: the photo against the layout's reference face, differences priced per day by paired simulation.

import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  BadgePercent,
  ClipboardCheck,
  Copy,
  Download,
  FlaskConical,
  Loader2,
  PackagePlus,
  PackageX,
  Play,
  Plus,
  ScanSearch,
  Tag,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import * as api from "@/shared/api/client";
import type {
  AuditFinding,
  AuditReport,
  CaptureBox,
  CaptureResult,
  EditKind,
  EditedShelf,
  PhotoEdit,
  Sim2RealCondition,
  Sim2RealReport,
} from "@/shared/api/client";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { formatMoney, minorUnitDivisor, toMinor } from "@/shared/utils/money";
import { RestockPlanner } from "./RestockPlanner";

import { EMPTY_DRAFT, needsOther, type LabDraft } from "./labDraft";

const OPS: { kind: EditKind; label: string; hint: string; icon: typeof Tag }[] = [
  { kind: "swap", label: "Swap", hint: "Two products trade places", icon: ArrowLeftRight },
  { kind: "remove", label: "Stock-out", hint: "Empty the product's facings", icon: PackageX },
  { kind: "replace", label: "New package", hint: "Put a new product on the shelf", icon: PackagePlus },
  { kind: "price", label: "Price tag", hint: "Change the shelf price", icon: Tag },
  { kind: "promo", label: "Promo sign", hint: "Hang a 1+1 / SALE sticker", icon: BadgePercent },
  { kind: "duplicate", label: "Extend", hint: "Copy a product over a neighbour", icon: Copy },
];

const PROMOS = ["1+1", "2+1", "SALE", "-30%", "NEW"];

const editsKey = (pid: string, cid: string) => ["projects", pid, "captures", cid, "edits"] as const;
const jobsKey = (pid: string, cid: string) => ["projects", pid, "captures", cid, "lab-jobs"] as const;

function describe(edit: PhotoEdit, names: Map<string, string>): string {
  const t = names.get(edit.item_id) ?? edit.item_id;
  const o = edit.other_id ? names.get(edit.other_id) ?? edit.other_id : "";
  switch (edit.kind) {
    case "swap": return `Swap ${t} ⇄ ${o}`;
    case "remove": return `Stock-out: ${t}`;
    case "replace": return `${t} → ${edit.name || "new package"}`;
    case "price": return `Price of ${t}`;
    case "promo": return `${edit.promo || "SALE"} on ${t}`;
    case "duplicate": return `${t} over ${o}`;
  }
}

// ── Before / after ────────────────────────────────────────────────────────

export function BeforeAfter({ beforeUrl, afterUrl, maskUrl, size, showMask }: {
  beforeUrl: string; afterUrl: string; maskUrl: string; size: [number, number]; showMask: boolean;
}) {
  const [split, setSplit] = useState(50);
  const [w, h] = size;
  return (
    <div className="relative max-h-full max-w-full select-none" style={{ aspectRatio: `${w} / ${h}`, height: "100%" }}>
      <img src={beforeUrl} alt="Original photo" className="absolute inset-0 h-full w-full rounded-lg object-contain" draggable={false} />
      <img
        src={afterUrl}
        alt="Counterfactual photo"
        className="absolute inset-0 h-full w-full rounded-lg object-contain"
        style={{ clipPath: `inset(0 0 0 ${split}%)` }}
        draggable={false}
      />
      {showMask && (
        <div
          className="pointer-events-none absolute inset-0 animate-pulse bg-volt/70 mix-blend-multiply dark:mix-blend-screen"
          style={{ maskImage: `url(${maskUrl})`, WebkitMaskImage: `url(${maskUrl})`, maskMode: "luminance", maskSize: "100% 100%", WebkitMaskSize: "100% 100%" }}
          aria-hidden
        />
      )}
      <div className="pointer-events-none absolute inset-y-0" style={{ left: `${split}%` }} aria-hidden>
        <div className="absolute inset-y-0 -left-px w-0.5 bg-white shadow-[0_0_12px_rgb(0_0_0/0.5)]" />
        <div className="absolute top-1/2 -left-5 grid size-10 -translate-y-1/2 place-items-center rounded-full bg-white text-[#0b0c10] shadow-lg">
          <ArrowLeftRight className="size-4" />
        </div>
      </div>
      <span className="glass absolute top-3 left-3 rounded-full px-2.5 py-1 text-xs font-medium">Original</span>
      <span className="absolute top-3 right-3 rounded-full bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground">Counterfactual</span>
      <input
        type="range"
        min={0}
        max={100}
        value={split}
        onChange={(e) => setSplit(Number(e.target.value))}
        className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0"
        aria-label="Compare original and counterfactual"
      />
    </div>
  );
}

// ── Composer ──────────────────────────────────────────────────────────────

function ProductSlot({ label, itemId, names, active, onActivate, onClear }: {
  label: string; itemId: string | null; names: Map<string, string>; active: boolean; onActivate: () => void; onClear: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onActivate}
      className={cn(
        "flex min-w-0 flex-1 items-center gap-2 rounded-xl border px-3 py-2 text-left text-sm transition-[border-color,box-shadow]",
        active ? "border-primary shadow-[0_0_0_3px_color-mix(in_oklab,var(--primary)_22%,transparent)]" : "hover:border-foreground/20",
      )}
    >
      <span className="eyebrow shrink-0">{label}</span>
      <span className={cn("min-w-0 flex-1 truncate font-medium", !itemId && "text-muted-foreground")}>
        {itemId ? names.get(itemId) ?? itemId : active ? "Click it on the photo" : "Not chosen"}
      </span>
      {itemId && (
        <span
          role="button"
          tabIndex={0}
          aria-label={`Clear ${label}`}
          onClick={(e) => { e.stopPropagation(); onClear(); }}
          onKeyDown={(e) => { if (e.key === "Enter") { e.stopPropagation(); onClear(); } }}
          className="rounded-md p-0.5 text-muted-foreground hover:bg-foreground/10 hover:text-foreground"
        >
          <X className="size-3.5" />
        </span>
      )}
    </button>
  );
}

function Composer({ projectId, captureId, result, draft, setDraft, onCreated }: {
  projectId: string; captureId: string; result: CaptureResult; draft: LabDraft;
  setDraft: (d: LabDraft) => void; onCreated: (shelf: EditedShelf) => void;
}) {
  const qc = useQueryClient();
  const names = useMemo(() => new Map(result.items.map((i) => [i.id, i.name || `Product ${i.band + 1}.${i.order + 1}`])), [result]);
  const [queue, setQueue] = useState<PhotoEdit[]>([]);
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [promo, setPromo] = useState("1+1");
  const [assetId, setAssetId] = useState("");
  const parsedPrice = toMinor(price, minorUnitDivisor(result.currency));
  const invalidPrice = (draft.kind === "replace" || draft.kind === "price") && price.trim() !== "" && parsedPrice === null;
  const fileRef = useRef<HTMLInputElement>(null);
  const packages = useQuery({ queryKey: ["projects", projectId, "lab-packages"], queryFn: ({ signal }) => api.listPackages(projectId, signal) });
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadPackage(projectId, file),
    onSuccess: async (asset) => {
      setAssetId(asset.asset_id);
      if (!name) setName(asset.name);
      await qc.invalidateQueries({ queryKey: ["projects", projectId, "lab-packages"] });
    },
  });

  const current: PhotoEdit | null = (() => {
    if (!draft.target || invalidPrice) return null;
    if (needsOther(draft.kind) && (!draft.other || draft.other === draft.target)) return null;
    const base: PhotoEdit = { kind: draft.kind, item_id: draft.target };
    switch (draft.kind) {
      case "swap":
      case "duplicate":
        return { ...base, other_id: draft.other ?? "" };
      case "replace":
        return { ...base, name: name.trim() || "New product", price: parsedPrice, asset_id: assetId };
      case "price": {
        const p = parsedPrice;
        return p == null ? null : { ...base, price: p };
      }
      case "promo":
        return { ...base, promo: promo.trim() || "SALE" };
      default:
        return base;
    }
  })();

  const render = useMutation({
    mutationFn: (edits: PhotoEdit[]) => api.createEdit(projectId, captureId, edits),
    onSuccess: async (shelf) => {
      setQueue([]);
      setDraft({ ...EMPTY_DRAFT, kind: draft.kind });
      await qc.invalidateQueries({ queryKey: editsKey(projectId, captureId) });
      onCreated(shelf);
    },
  });
  const recipe = current ? [...queue, current] : queue;
  const op = OPS.find((o) => o.kind === draft.kind)!;

  return (
    <section className="space-y-3">
      <div className="grid grid-cols-3 gap-1.5">
        {OPS.map(({ kind, label, icon: Icon }) => (
          <button
            key={kind}
            type="button"
            onClick={() => setDraft({ ...draft, kind, slot: "target", other: needsOther(kind) ? draft.other : null })}
            className={cn(
              "flex flex-col items-center gap-1.5 rounded-xl border px-2 py-2.5 text-xs font-medium transition-[background-color,border-color,color]",
              draft.kind === kind ? "border-transparent bg-primary text-primary-foreground shadow-[0_8px_20px_-10px_var(--primary)]" : "text-muted-foreground hover:border-foreground/20 hover:text-foreground",
            )}
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{op.hint}. Click products on the photo to choose them.</p>

      <div className="flex flex-col gap-2">
        <ProductSlot label="Product" itemId={draft.target} names={names} active={draft.slot === "target"}
          onActivate={() => setDraft({ ...draft, slot: "target" })} onClear={() => setDraft({ ...draft, target: null, slot: "target" })} />
        {needsOther(draft.kind) && (
          <ProductSlot label={draft.kind === "swap" ? "With" : "Over"} itemId={draft.other} names={names} active={draft.slot === "other"}
            onActivate={() => setDraft({ ...draft, slot: "other" })} onClear={() => setDraft({ ...draft, other: null, slot: "other" })} />
        )}
      </div>

      {draft.kind === "replace" && (
        <div className="space-y-2 rounded-xl border bg-foreground/[0.02] p-3">
          <div className="grid grid-cols-[1fr_6.5rem] gap-2">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="New product name" />
            <Input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="Price" inputMode="decimal" className="num" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setAssetId("")}
              className={cn("h-14 rounded-lg border px-3 text-xs", !assetId ? "border-primary text-foreground" : "text-muted-foreground hover:border-foreground/20")}
            >
              Printed<br />label
            </button>
            {(packages.data ?? []).map((p) => (
              <button
                key={p.asset_id}
                type="button"
                onClick={() => setAssetId(p.asset_id)}
                title={p.name}
                className={cn("grid size-14 place-items-center overflow-hidden rounded-lg border bg-white", assetId === p.asset_id ? "border-primary ring-2 ring-primary/40" : "hover:border-foreground/20")}
              >
                <img src={api.packageUrl(projectId, p.asset_id)} alt={p.name} className="max-h-full max-w-full object-contain" />
              </button>
            ))}
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="flex h-14 items-center gap-1.5 rounded-lg border border-dashed px-3 text-xs text-muted-foreground hover:border-primary hover:text-foreground"
            >
              {upload.isPending ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
              Package image
            </button>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
          </div>
          <p className="text-[0.72rem] text-muted-foreground">A PNG with transparency works best; a photo on a plain background is cut out automatically.</p>
        </div>
      )}
      {draft.kind === "price" && (
        <Input value={price} onChange={(e) => setPrice(e.target.value)} placeholder={`New price (${result.currency})`} inputMode="decimal" className="num" />
      )}
      {draft.kind === "promo" && (
        <div className="flex flex-wrap gap-1.5">
          {PROMOS.map((p) => (
            <button key={p} type="button" onClick={() => setPromo(p)}
              className={cn("rounded-full border px-3 py-1 text-xs font-semibold", promo === p ? "border-transparent bg-[#e8182e] text-white" : "hover:border-foreground/20")}>
              {p}
            </button>
          ))}
          <Input value={promo} onChange={(e) => setPromo(e.target.value)} className="h-8 w-24 text-xs" maxLength={8} />
        </div>
      )}

      {queue.length > 0 && (
        <ol className="space-y-1">
          {queue.map((e, i) => (
            <li key={i} className="flex items-center gap-2 rounded-lg bg-foreground/[0.04] px-2.5 py-1.5 text-xs">
              <span className="num text-muted-foreground">{i + 1}</span>
              <span className="min-w-0 flex-1 truncate">{describe(e, names)}</span>
              <button type="button" aria-label="Remove step" onClick={() => setQueue(queue.filter((_, k) => k !== i))} className="text-muted-foreground hover:text-destructive">
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ol>
      )}
      {render.error && <p className="text-xs text-destructive">{render.error instanceof Error ? render.error.message : String(render.error)}</p>}
      {invalidPrice && <p role="alert" className="text-xs text-destructive">Enter a valid nonnegative price.</p>}
      <div className="flex gap-2">
        <Button variant="outline" className="gap-1.5" disabled={!current} onClick={() => { if (current) { setQueue([...queue, current]); setDraft({ ...EMPTY_DRAFT, kind: draft.kind }); } }}>
          <Plus className="size-4" /> Add step
        </Button>
        <Button className="flex-1 gap-2" disabled={invalidPrice || recipe.length === 0 || render.isPending} onClick={() => render.mutate(recipe)}>
          {render.isPending ? <Loader2 className="size-4 animate-spin" /> : <FlaskConical className="size-4" />}
          Render counterfactual{recipe.length > 1 ? ` (${recipe.length} steps)` : ""}
        </Button>
      </div>
    </section>
  );
}

// ── Edits gallery ─────────────────────────────────────────────────────────

function EditsGallery({ projectId, captureId, editId, onSelect }: {
  projectId: string; captureId: string; editId: string | null; onSelect: (id: string | null) => void;
}) {
  const qc = useQueryClient();
  const edits = useQuery({ queryKey: editsKey(projectId, captureId), queryFn: ({ signal }) => api.listEdits(projectId, captureId, signal) });
  const del = useMutation({
    mutationFn: (id: string) => api.deleteEdit(projectId, captureId, id),
    onSuccess: async (_, id) => {
      if (id === editId) onSelect(null);
      await qc.invalidateQueries({ queryKey: editsKey(projectId, captureId) });
    },
  });
  const list = edits.data ?? [];
  if (list.length === 0) return null;
  const selected = list.find((e) => e.edit_id === editId);
  return (
    <section className="space-y-2">
      <div className="eyebrow">Counterfactuals</div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        <button type="button" onClick={() => onSelect(null)}
          className={cn("grid h-16 w-20 shrink-0 place-items-center rounded-xl border text-xs", !editId ? "border-primary" : "text-muted-foreground hover:border-foreground/20")}>
          Original
        </button>
        {list.map((e) => (
          <button key={e.edit_id} type="button" onClick={() => onSelect(e.edit_id)}
            className={cn("relative h-16 w-20 shrink-0 overflow-hidden rounded-xl border-2", e.edit_id === editId ? "border-primary" : "border-transparent hover:border-foreground/20")}>
            <img src={api.editFileUrl(projectId, captureId, e.edit_id, "image")} alt="" className="h-full w-full object-cover" />
            <span className="absolute inset-x-0 bottom-0 bg-black/60 px-1 py-0.5 text-[0.62rem] text-white">{e.edits.length} edit{e.edits.length > 1 ? "s" : ""}</span>
          </button>
        ))}
      </div>
      {selected && (
        <div className="rounded-xl border bg-foreground/[0.02] p-2.5 text-xs">
          <ul className="space-y-0.5">
            {selected.changes.filter((c, i, all) => all.findIndex((x) => x.item_id === c.item_id && x.kind === c.kind) === i).map((c, i) => (
              <li key={i} className="flex gap-1.5"><span className="font-medium capitalize">{c.kind}</span><span className="truncate text-muted-foreground">{c.before} → {c.after}</span></li>
            ))}
          </ul>
          <div className="mt-2 flex gap-1.5">
            <Button variant="outline" size="xs" asChild><a href={api.editFileUrl(projectId, captureId, selected.edit_id, "image")} download={`${selected.edit_id}.jpg`}><Download /> Image</a></Button>
            <Button variant="outline" size="xs" asChild><a href={api.editFileUrl(projectId, captureId, selected.edit_id, "mask")} download={`${selected.edit_id}_mask.png`}><Download /> GT mask</a></Button>
            <Button variant="ghost" size="xs" className="ml-auto hover:text-destructive" onClick={() => del.mutate(selected.edit_id)}><Trash2 /> Delete</Button>
          </div>
        </div>
      )}
    </section>
  );
}

// ── Jobs ──────────────────────────────────────────────────────────────────

function useLabJob(projectId: string, captureId: string, jobId: string | null) {
  return useQuery({
    queryKey: [...jobsKey(projectId, captureId), jobId],
    queryFn: ({ signal }) => api.getLabJob(projectId, captureId, jobId!, signal),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status.status) ? false : 1000),
  });
}

function Progress({ value, label }: { value: number; label: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-muted-foreground"><span>{label}</span><span className="num">{Math.round(value * 100)}%</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-foreground/10">
        <div className="aurora-gradient h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.max(3, value * 100)}%` }} />
      </div>
    </div>
  );
}

function RecentJobs({ projectId, captureId, kind, current, onPick }: {
  projectId: string; captureId: string; kind: "sim2real" | "audit"; current: string | null; onPick: (id: string) => void;
}) {
  const jobs = useQuery({ queryKey: jobsKey(projectId, captureId), queryFn: ({ signal }) => api.listLabJobs(projectId, captureId, signal) });
  const mine = (jobs.data ?? []).filter((j) => j.kind === kind && j.status === "completed").slice(0, 6);
  if (mine.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <span className="text-muted-foreground">Earlier runs:</span>
      {mine.map((j) => (
        <button key={j.job_id} type="button" onClick={() => onPick(j.job_id)}
          className={cn("num rounded-full border px-2 py-0.5", current === j.job_id ? "border-primary text-foreground" : "text-muted-foreground hover:border-foreground/20")}>
          {new Date(j.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </button>
      ))}
    </div>
  );
}

const CONDITION_LABEL: Record<Sim2RealCondition, string> = { render: "Render", photo: "Photo + tags", photo_raw: "Raw photo" };
const LEVEL_COLORS: Record<string, string> = { "4": "var(--heat-1)", "3": "var(--volt)", "2": "var(--heat-2)", "1": "var(--heat-3)" };

function Sim2RealView({ report }: { report: Sim2RealReport }) {
  return (
    <div className="space-y-4">
      {report.agreement.map((a) => (
        <div key={a.condition}>
          <div className="flex items-end justify-between">
            <div>
              <div className="eyebrow">{CONDITION_LABEL[a.condition]} vs render</div>
              {a.pairs > 0
                ? <div className="num text-3xl font-medium tracking-[-0.05em]">{Math.round(a.same_pick * 100)}%</div>
                : <p className="mt-1 text-xs text-muted-foreground">No complete response pairs</p>}
            </div>
            <div className="text-right text-xs text-muted-foreground">
              same pick · n={a.pairs}<br />
              interest ρ {a.interest_spearman == null ? "–" : a.interest_spearman.toFixed(2)}
            </div>
          </div>
          {a.pairs > 0 && <div className="relative mt-2 h-2 rounded-full bg-foreground/10">
            <div className="absolute inset-y-0 left-0 rounded-full aurora-gradient" style={{ width: `${a.same_pick * 100}%` }} />
            <div className="absolute -top-1 -bottom-1 border-x-2 border-foreground/60" style={{ left: `${a.ci_low * 100}%`, width: `${Math.max(0.5, (a.ci_high - a.ci_low) * 100)}%` }} title="95% Wilson interval" />
          </div>}
        </div>
      ))}
      <div className="space-y-2">
        <div className="eyebrow">Where the picks land (shelf level)</div>
        {report.stats.map((s) => (
          <div key={s.condition} className="flex items-center gap-2 text-xs">
            <span className="w-24 shrink-0 text-muted-foreground">{CONDITION_LABEL[s.condition]}</span>
            <div className="flex h-3 flex-1 overflow-hidden rounded-full bg-foreground/10">
              {["4", "3", "2", "1"].map((lv) => (s.level_share[lv] ? (
                <div key={lv} style={{ width: `${s.level_share[lv]! * 100}%`, background: LEVEL_COLORS[lv] }} title={`level ${lv}: ${Math.round(s.level_share[lv]! * 100)}%`} />
              ) : null))}
            </div>
            <span className="num w-14 text-right text-muted-foreground">{s.answers > 0 ? `${Math.round(s.none_rate * 100)}% none` : "—"}</span>
          </div>
        ))}
        <div className="flex gap-3 text-[0.68rem] text-muted-foreground">
          {[["4", "Top"], ["3", "Eye"], ["2", "Waist"], ["1", "Bottom"]].map(([lv, n]) => (
            <span key={lv} className="flex items-center gap-1"><span className="size-2 rounded-full" style={{ background: LEVEL_COLORS[lv!] }} />{n}</span>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-2">
        {report.stats.map((s) => (
          <div key={s.condition} className="rounded-xl border p-2.5 text-xs">
            <div className="mb-1 font-medium">{CONDITION_LABEL[s.condition]} · top picks</div>
            {Object.entries(s.picks).slice(0, 3).map(([sku, n]) => (
              <div key={sku} className="flex justify-between gap-2"><span className="truncate">{report.products[sku] ?? sku}</span><span className="num text-muted-foreground">{n}</span></div>
            ))}
            {Object.keys(s.picks).length === 0 && <span className="text-muted-foreground">{s.answers > 0 ? "No picks" : "No successful responses"}</span>}
            {s.errors > 0 && <p className="mt-1 text-destructive">{s.errors} model call{s.errors === 1 ? "" : "s"} failed</p>}
          </div>
        ))}
      </div>
      <p className="text-[0.72rem] text-muted-foreground">
        {report.personas} shoppers · {report.model} · {report.seconds}s{report.notes.length ? ` · ${report.notes.join("; ")}` : ""}
      </p>
    </div>
  );
}

function AttentionToggle({ report, onAttention }: { report: Sim2RealReport; onAttention: (shares: Record<string, number> | null) => void }) {
  const [on, setOn] = useState<Sim2RealCondition | null>(null);
  const show = (c: Sim2RealCondition | null) => {
    setOn(c);
    const stats = c ? report.stats.find((s) => s.condition === c) : undefined;
    onAttention(stats && stats.answers > 0 ? Object.fromEntries(Object.entries(stats.picks).map(([sku, n]) => [sku, n / stats.answers])) : null);
  };
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <span className="text-muted-foreground">Attention on the photo:</span>
      {report.conditions.map((c) => (
        <button key={c} type="button" onClick={() => show(on === c ? null : c)}
          className={cn("rounded-full border px-2.5 py-1", on === c ? "border-transparent bg-primary font-medium text-primary-foreground" : "hover:border-foreground/20")}>
          {CONDITION_LABEL[c]}
        </button>
      ))}
    </div>
  );
}

function Sim2RealCard({ projectId, captureId, editId, labeled, onAttention }: {
  projectId: string; captureId: string; editId: string | null; labeled: boolean;
  onAttention: (shares: Record<string, number> | null) => void;
}) {
  const qc = useQueryClient();
  const [personas, setPersonas] = useState(24);
  const [raw, setRaw] = useState(true);
  const [situation, setSituation] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useLabJob(projectId, captureId, jobId);
  const start = useMutation({
    mutationFn: () => api.startSim2Real(projectId, captureId, {
      personas, situation, edit_id: editId ?? "", conditions: raw ? ["render", "photo", "photo_raw"] : ["render", "photo"],
    }),
    onSuccess: async (s) => { setJobId(s.job_id); await qc.invalidateQueries({ queryKey: jobsKey(projectId, captureId) }); },
  });
  const status = job.data?.status;
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <ScanSearch className="size-4 text-heat-1" />
        <h3 className="section-title">Sim2real</h3>
        <span className="ml-auto text-xs text-muted-foreground">{editId ? "on the counterfactual" : "on the original"}</span>
      </div>
      <p className="text-xs text-muted-foreground">The same shoppers and seeds glance at the photo and at the simulator's render of this planogram.</p>
      <label className="flex items-center gap-3 text-xs">
        <span className="w-20 text-muted-foreground">Shoppers</span>
        <input type="range" min={8} max={96} step={8} value={personas} onChange={(e) => setPersonas(Number(e.target.value))} className="flex-1" />
        <span className="num w-8 text-right">{personas}</span>
      </label>
      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={raw} onChange={(e) => setRaw(e.target.checked)} />
        Also the raw photo, without number tags (set-of-mark ablation)
      </label>
      <Input value={situation} onChange={(e) => setSituation(e.target.value)} placeholder="Today (optional), e.g. heatwave, 34°C" className="h-9 text-sm" />
      {!labeled && <p className="rounded-lg tone-warn border p-2 text-xs">Read the products with a vision model first — sim2real compares named products.</p>}
      {start.error && <p className="text-xs text-destructive">{start.error instanceof Error ? start.error.message : String(start.error)}</p>}
      <Button className="w-full gap-2" disabled={!labeled || start.isPending || status?.status === "running" || status?.status === "pending"} onClick={() => start.mutate()}>
        {start.isPending ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />} Run sim2real panel
      </Button>
      <RecentJobs projectId={projectId} captureId={captureId} kind="sim2real" current={jobId} onPick={setJobId} />
      {status && status.status !== "completed" && status.status !== "failed" && <Progress value={status.progress} label="Shoppers glancing…" />}
      {status?.status === "failed" && <p className="rounded-lg tone-bad border p-2 text-xs">{status.error}</p>}
      {job.data?.sim2real && (
        <>
          <AttentionToggle report={job.data.sim2real} onAttention={onAttention} />
          <Sim2RealView report={job.data.sim2real} />
        </>
      )}
    </section>
  );
}

// ── Audit ─────────────────────────────────────────────────────────────────

const FINDING_STYLE: Record<AuditFinding["kind"], { label: string; tone: string }> = {
  missing: { label: "Missing", tone: "tone-bad" },
  gap: { label: "Empty", tone: "tone-bad" },
  unexpected: { label: "Unexpected", tone: "tone-warn" },
  misplaced: { label: "Misplaced", tone: "tone-warn" },
  facings: { label: "Facings", tone: "tone-warn" },
  price: { label: "Price", tone: "tone-warn" },
};

function ComplianceRing({ value }: { value: number }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 84 84" className="size-24 shrink-0 -rotate-90">
      <defs>
        <linearGradient id="ring-aurora" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--heat-1)" />
          <stop offset="0.5" stopColor="var(--heat-2)" />
          <stop offset="1" stopColor="var(--volt)" />
        </linearGradient>
      </defs>
      <circle cx="42" cy="42" r={r} fill="none" stroke="currentColor" strokeOpacity={0.1} strokeWidth="9" />
      <circle cx="42" cy="42" r={r} fill="none" stroke="url(#ring-aurora)" strokeWidth="9" strokeLinecap="round"
        strokeDasharray={`${c * value} ${c}`} className="transition-[stroke-dasharray] duration-700" />
      <text x="42" y="42" textAnchor="middle" dominantBaseline="central" className="num rotate-90 fill-foreground text-[17px] font-semibold" style={{ transformOrigin: "42px 42px" }}>
        {Math.round(value * 100)}%
      </text>
    </svg>
  );
}

function AuditView({ report, onFocus }: { report: AuditReport; onFocus: (box: CaptureBox | null) => void }) {
  const delta = report.revenue_delta_per_day;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <ComplianceRing value={report.compliance} />
        <div className="min-w-0">
          <div className="eyebrow">Planogram compliance</div>
          <div className="mt-1 text-sm text-muted-foreground">Revenue vs reference</div>
          <div className={cn("num text-2xl font-medium tracking-[-0.04em]", delta != null && delta < 0 ? "text-negative" : "text-positive")}>
            {delta == null ? "–" : `${delta >= 0 ? "+" : "−"}${formatMoney(Math.abs(delta), report.currency)}`}<span className="text-sm text-muted-foreground"> /day</span>
          </div>
          {report.revenue_delta_ci && (
            <div className="num text-[0.72rem] text-muted-foreground">
              95% CI {formatMoney(report.revenue_delta_ci[0], report.currency)} … {formatMoney(report.revenue_delta_ci[1], report.currency)}
            </div>
          )}
        </div>
      </div>
      <div className="space-y-1.5">
        {report.levels.map((lv) => (
          <div key={lv.level} className="flex items-center gap-2 text-xs">
            <span className="w-14 text-muted-foreground">Level {lv.level}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-foreground/10">
              <div className="aurora-gradient h-full rounded-full" style={{ width: `${lv.score * 100}%` }} />
            </div>
            <span className="num w-16 text-right text-muted-foreground">{lv.matched_facings}/{lv.expected_facings}</span>
          </div>
        ))}
      </div>
      <ul className="space-y-1.5">
        {report.findings.map((f, i) => {
          const style = FINDING_STYLE[f.kind];
          return (
            <li key={i}>
              <button type="button" onMouseEnter={() => onFocus(f.box)} onMouseLeave={() => onFocus(null)}
                className="flex w-full items-center gap-2 rounded-xl border px-2.5 py-2 text-left text-xs transition-colors hover:bg-foreground/[0.03]">
                <span className={cn("shrink-0 rounded-full border px-2 py-0.5 text-[0.68rem] font-semibold", style.tone)}>{style.label}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{f.name || `Level ${f.level}`}</span>
                  <span className="block truncate text-muted-foreground">expected {f.expected} · found {f.found}</span>
                </span>
                {f.loss_per_day != null && (
                  <span className={cn("num shrink-0 text-right", f.loss_per_day > 0 ? "text-negative" : "text-positive")} title={f.loss_ci ? `Stockout revenue loss; 95% CI ${formatMoney(f.loss_ci[0], report.currency)} … ${formatMoney(f.loss_ci[1], report.currency)}` : "Stockout revenue loss"}>
                    {formatMoney(f.loss_per_day, report.currency)}<span className="block text-muted-foreground">loss/day</span>
                  </span>
                )}
              </button>
            </li>
          );
        })}
        {report.findings.length === 0 && <li className="rounded-xl tone-good border p-2.5 text-xs">The shelf matches the reference planogram.</li>}
      </ul>
      <p className="text-[0.72rem] text-muted-foreground">
        Rack {report.rack_id} face {report.face} · {report.panel_size} shoppers per paired run · {report.visitors_per_day} visitors/day · {report.seconds}s
        {report.notes.length ? ` · ${report.notes.join("; ")}` : ""}
      </p>
      <RestockPlanner key={report.job_id} report={report} onFocus={onFocus} />
    </div>
  );
}

function AuditCard({ projectId, captureId, editId, result, onFocus }: {
  projectId: string; captureId: string; editId: string | null; result: CaptureResult; onFocus: (box: CaptureBox | null) => void;
}) {
  const qc = useQueryClient();
  const { data: setups = [] } = useQuery({ queryKey: queryKeys.setups(projectId), queryFn: ({ signal }) => api.getSetups(projectId, signal) });
  const [setupId, setSetupId] = useState("");
  const base = setupId || setups[setups.length - 1]?.id || "";
  const { data: setup } = useQuery({
    queryKey: ["projects", projectId, "setups", base, "detail"],
    queryFn: ({ signal }) => api.getSetup(projectId, base, signal),
    enabled: !!base,
  });
  const racks = (setup?.store?.racks ?? []).filter((r) => (r.type === "fridge" || r.type === "shelf") && (r.slots?.length ?? 0) > 0);
  const sameType = racks.filter((r) => r.type === (result.rack_type === "fridge" ? "fridge" : "shelf"));
  const [rackId, setRackId] = useState("");
  const rack = rackId || sameType[0]?.id || racks[0]?.id || "";
  const [panel, setPanel] = useState(300);
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useLabJob(projectId, captureId, jobId);
  const start = useMutation({
    mutationFn: () => api.startAudit(projectId, captureId, { setup_id: base, rack_id: rack, edit_id: editId ?? "", panel }),
    onSuccess: async (s) => { setJobId(s.job_id); await qc.invalidateQueries({ queryKey: jobsKey(projectId, captureId) }); },
  });
  const status = job.data?.status;
  const field = "h-9 rounded-xl border bg-card/60 px-2.5 text-sm";
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <ClipboardCheck className="size-4 text-heat-2" />
        <h3 className="section-title">Compliance audit</h3>
        <span className="ml-auto text-xs text-muted-foreground">{editId ? "on the counterfactual" : "on the original"}</span>
      </div>
      <p className="text-xs text-muted-foreground">Compares this photo with the rack's reference planogram and prices each stock-out per day.</p>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">Reference layout</span>
          <select className={field} value={base} onChange={(e) => { setSetupId(e.target.value); setRackId(""); }}>
            {setups.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">Rack in the photo</span>
          <select className={field} value={rack} onChange={(e) => setRackId(e.target.value)}>
            {racks.map((r) => <option key={r.id} value={r.id}>{r.rack_name || r.id} · {r.type}</option>)}
          </select>
        </label>
      </div>
      <label className="flex items-center gap-3 text-xs">
        <span className="w-20 text-muted-foreground">Shoppers</span>
        <input type="range" min={100} max={1000} step={100} value={panel} onChange={(e) => setPanel(Number(e.target.value))} className="flex-1" />
        <span className="num w-10 text-right">{panel}</span>
      </label>
      {start.error && <p className="text-xs text-destructive">{start.error instanceof Error ? start.error.message : String(start.error)}</p>}
      <Button variant="outline" className="w-full gap-2" disabled={!base || !rack || start.isPending || status?.status === "running" || status?.status === "pending"} onClick={() => start.mutate()}>
        {start.isPending ? <Loader2 className="size-4 animate-spin" /> : <ClipboardCheck className="size-4" />} Audit against the layout
      </Button>
      <RecentJobs projectId={projectId} captureId={captureId} kind="audit" current={jobId} onPick={setJobId} />
      {status && status.status !== "completed" && status.status !== "failed" && <Progress value={status.progress} label={status.stage === "simulating" ? "Simulating shoppers…" : "Comparing…"} />}
      {status?.status === "failed" && <p className="rounded-lg tone-bad border p-2 text-xs">{status.error}</p>}
      {job.data?.audit && <AuditView report={job.data.audit} onFocus={onFocus} />}
    </section>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────

export function ShelfLabPanel({ projectId, captureId, result, draft, setDraft, editId, onSelectEdit, onFocus, onAttention }: {
  projectId: string; captureId: string; result: CaptureResult; draft: LabDraft; setDraft: (d: LabDraft) => void;
  editId: string | null; onSelectEdit: (id: string | null) => void; onFocus: (box: CaptureBox | null) => void;
  onAttention: (shares: Record<string, number> | null) => void;
}) {
  const labeled = result.items.some((i) => i.labeled);
  const divider = "border-t border-glass-border pt-4";
  return (
    <div className="space-y-4">
      <Composer projectId={projectId} captureId={captureId} result={result} draft={draft} setDraft={setDraft} onCreated={(s) => onSelectEdit(s.edit_id)} />
      <EditsGallery projectId={projectId} captureId={captureId} editId={editId} onSelect={onSelectEdit} />
      <div className={divider}>
        <Sim2RealCard projectId={projectId} captureId={captureId} editId={editId} labeled={labeled} onAttention={onAttention} />
      </div>
      <div className={divider}>
        <AuditCard projectId={projectId} captureId={captureId} editId={editId} result={result} onFocus={onFocus} />
      </div>
    </div>
  );
}
