// Places every SlotItem as stocked packages (facings × rows × stacks) on its
// rack face/level, plus one price tag per item and a shelf-talker for promos.
// Pure: the output is plain numbers that RealisticStore turns into instances.

import type { SlotItem } from "@/shared/types/domain";
import { M, PRODUCT_SCALE } from "./constants";
import { classifyProduct, hash01, type PackageKind } from "./productCatalog";
import {
  CHEST_DIMS,
  TABLE_DIMS,
  frameFor,
  frameToWorld,
  type Bank,
  type FixturePlan,
  type Frame,
} from "./fixtureSpecs";

export interface ProductInstance {
  name: string;
  imageUrl?: string | null;
  kind: PackageKind;
  // Bottom-centre of the package (store-local world coordinates).
  x: number;
  y: number;
  z: number;
  yaw: number;
  // Lie face-up (label towards +Y) — chest freezers.
  flat: boolean;
  // World size: width (facing), height, depth — before the flat rotation.
  sx: number;
  sy: number;
  sz: number;
}

export interface TagInstance {
  price: number;
  promo: string;
  x: number;
  y: number;
  z: number;
  yaw: number;
  // Tilt back about the tag's horizontal axis (radians), for chest dividers.
  tilt: number;
}

export interface TalkerInstance {
  promo: string;
  x: number;
  y: number;
  z: number;
  yaw: number;
}

export interface ProductLayout {
  products: ProductInstance[];
  tags: TagInstance[];
  talkers: TalkerInstance[];
}

export interface LayoutOptions {
  maxRows: number;
}

const SHELF_T = 0.022;
const UPRIGHT = 0.035;
const GAP = 0.006;
const MAX_FACINGS = 6;

function worldSize(name: string) {
  const s = classifyProduct(name);
  const k = M * PRODUCT_SCALE;
  return { spec: s, w: s.w * k, h: s.h * k, d: s.d * k };
}

function stackable(kind: PackageKind, h: number, clearance: number): number {
  if (kind === "perfumeBottle" || kind === "teaCup") return 1;
  if (kind === "bottle" || kind === "bag" || kind === "tube" || kind === "jar" || kind === "banana" || kind === "apple" || kind === "applePair" || kind === "avocado" || kind === "lemon" || kind === "pot" || kind === "croissant" || kind === "wateringCan") return 1;
  return Math.max(1, Math.min(kind === "can" ? 3 : 2, Math.floor((clearance - 0.01) / (h + 0.004))));
}

interface Emit {
  products: ProductInstance[];
  tags: TagInstance[];
  talkers: TalkerInstance[];
}

interface ShelfEdge {
  // v of the stock's front edge and of the price-channel face.
  stockFront: number;
  railFace: number;
}

function placeOnShelf(
  out: Emit,
  bank: Bank,
  edge: ShelfEdge,
  items: SlotItem[],
  u0: number,
  u1: number,
  shelfY: number,
  clearance: number,
  maxRows: number,
) {
  const m = items.length;
  if (!m) return;
  const slotW = (u1 - u0) / m;
  const shelfDepth = edge.stockFront - bank.back - 0.02;
  items.forEach((item, k) => {
    const { spec, w, h, d } = worldSize(item.name);
    const preserveProportions = spec.category === "produce" || spec.kind === "pot" || spec.kind === "croissant" || spec.kind === "wateringCan" || spec.kind === "perfumeBottle" || spec.kind === "teaCup";
    let fit = Math.min(1, (clearance - 0.012) / h);
    if (preserveProportions) fit = Math.min(fit, shelfDepth / d, (slotW - GAP) / w);
    const ph = h * fit;
    const pd = Math.min(d * fit, shelfDepth);
    let pw = w * fit;
    const facings = Math.max(1, Math.min(MAX_FACINGS, Math.floor(slotW / (pw * (preserveProportions ? 1 : 0.85) + GAP))));
    const pitch = slotW / facings;
    pw = Math.min(pw * (preserveProportions ? 1 : 1.12), pitch - GAP);
    const rows = Math.max(1, Math.min(maxRows, Math.floor(shelfDepth / (pd + 0.006))));
    const rowPitch = rows > 1 ? Math.min((shelfDepth - pd) / (rows - 1), pd * 2.2) : 0;
    const stacks = stackable(spec.kind, ph, clearance);
    const center = u0 + slotW * (k + 0.5);
    for (let f = 0; f < facings; f++) {
      for (let r = 0; r < rows; r++) {
        for (let s = 0; s < stacks; s++) {
          const key = `${item.name}|${f}|${r}|${s}`;
          const u = u0 + slotW * k + pitch * (f + 0.5) + (hash01(key, 1) - 0.5) * 0.006;
          const v = edge.stockFront - 0.014 - pd / 2 - r * rowPitch;
          const [x, z] = frameToWorld(bank, u, v);
          out.products.push({
            name: item.name,
            imageUrl: item.image_url,
            kind: spec.kind,
            x,
            y: shelfY + s * (ph + 0.003),
            z,
            yaw: bank.yaw + (hash01(key, 2) - 0.5) * 0.08,
            flat: false,
            sx: pw,
            sy: ph,
            sz: pd,
          });
        }
      }
    }
    const [tx, tz] = frameToWorld(bank, center, edge.railFace + 0.0015);
    out.tags.push({ price: item.price, promo: item.promo, x: tx, y: shelfY - 0.019, z: tz, yaw: bank.yaw, tilt: 0 });
    if (item.promo) {
      const [px, pz] = frameToWorld(bank, u0 + slotW * (k + 1) - 0.012, edge.railFace + 0.03);
      out.talkers.push({ promo: item.promo, x: px, y: shelfY + 0.03, z: pz, yaw: bank.yaw });
    }
  });
}

function layoutBanks(out: Emit, plan: FixturePlan, maxRows: number) {
  const top = plan.height;
  const fridge = plan.kind === "reachIn";
  for (const bank of plan.banks) {
    const blocks = Math.max(1, Math.round(bank.width));
    const half = bank.width / 2 - UPRIGHT;
    const blockW = (half * 2) / blocks;
    for (const slot of plan.rack.slots ?? []) {
      if (slot.face !== bank.face || !slot.items?.length) continue;
      const li = Math.max(0, Math.min(bank.shelfYs.length - 1, slot.level - 1));
      const y = bank.shelfYs[li]!;
      const next = bank.shelfYs[li + 1];
      const ceiling = next !== undefined ? next - SHELF_T : Math.min(top - 0.06, y + 0.3);
      const b = Math.max(0, Math.min(blocks - 1, slot.block));
      const u0 = -half + blockW * b;
      // Must match buildStore: fridge wire shelves stop short of the doors.
      const edge: ShelfEdge = fridge
        ? { stockFront: bank.front - 0.075, railFace: bank.front - 0.068 }
        : { stockFront: bank.front, railFace: bank.front + 0.012 };
      placeOnShelf(out, bank, edge, slot.items, u0, u0 + blockW, y, ceiling - y, maxRows);
    }
  }
}

// Chest freezers and bakery tables: levels become rows from front (level 1) to back.
function layoutBin(out: Emit, plan: FixturePlan, frame: Frame, floorY: number, headroom: number, preferFlat: boolean) {
  const slots = (plan.rack.slots ?? []).filter((s) => s.items?.length);
  if (!slots.length) return;
  const levels = [...new Set(slots.map((s) => s.level))].sort((a, b) => a - b);
  const innerW = frame.width - 0.1;
  const innerD = frame.depth - 0.12;
  const rowD = innerD / levels.length;
  levels.forEach((level, ri) => {
    const items = slots.filter((s) => s.level === level).flatMap((s) => s.items);
    const slotW = innerW / items.length;
    const vFront = innerD / 2 - ri * rowD;
    items.forEach((item, k) => {
      const { spec, w, h, d } = worldSize(item.name);
      const flat = preferFlat && spec.lieFlatInChest;
      // Footprint along t (fw) and n (fd), and height above the floor (fh).
      const fw = w;
      const fd = flat ? h : d;
      const fh = flat ? d : h;
      const fit = Math.min(1, (slotW - GAP) / fw, (rowD - 0.02) / fd, headroom / fh);
      const cols = Math.max(1, Math.min(4, Math.floor(slotW / (fw * fit + GAP))));
      const deep = Math.max(1, Math.min(3, Math.floor((rowD - 0.02) / (fd * fit + 0.01))));
      const layers = spec.kind === "pot" || spec.kind === "croissant" || spec.kind === "wateringCan" || spec.kind === "avocado" || spec.kind === "lemon" || spec.kind === "perfumeBottle" || spec.kind === "teaCup" ? 1 : Math.max(1, Math.min(2, Math.floor(headroom / (fh * fit + 0.004))));
      const pitchW = slotW / cols;
      const pitchD = (rowD - 0.02) / deep;
      for (let c = 0; c < cols; c++) {
        for (let r = 0; r < deep; r++) {
          for (let l = 0; l < layers; l++) {
            const key = `${item.name}|${c}|${r}|${l}`;
            const u = -innerW / 2 + slotW * k + pitchW * (c + 0.5) + (hash01(key, 3) - 0.5) * 0.01;
            const v = vFront - 0.01 - pitchD * (r + 0.5);
            const [x, z] = frameToWorld(frame, u, v);
            out.products.push({
              name: item.name,
              imageUrl: item.image_url,
              kind: spec.kind,
              x,
              y: floorY + l * (fh * fit + 0.003),
              z,
              yaw: frame.yaw + (hash01(key, 4) - 0.5) * (flat ? 0.25 : 0.12),
              flat,
              sx: w * fit,
              sy: h * fit,
              sz: d * fit,
            });
          }
        }
      }
      const [tx, tz] = frameToWorld(frame, -innerW / 2 + slotW * (k + 0.5), vFront + 0.004);
      out.tags.push({
        price: item.price,
        promo: item.promo,
        x: tx,
        y: preferFlat ? CHEST_DIMS.height - 0.07 : floorY + 0.012,
        z: tz,
        yaw: frame.yaw,
        tilt: preferFlat ? 0.85 : 1.2,
      });
      if (item.promo) {
        const [px, pz] = frameToWorld(frame, -innerW / 2 + slotW * (k + 1) - 0.01, vFront + 0.02);
        out.talkers.push({ promo: item.promo, x: px, y: floorY + headroom * 0.7, z: pz, yaw: frame.yaw });
      }
    });
  });
}

export function layoutProducts(plans: FixturePlan[], opts: LayoutOptions): ProductLayout {
  const out: Emit = { products: [], tags: [], talkers: [] };
  for (const plan of plans) {
    switch (plan.kind) {
      case "gondola":
      case "wallShelf":
      case "reachIn":
        layoutBanks(out, plan, opts.maxRows);
        break;
      case "chest": {
        const frame = frameFor(plan, CHEST_DIMS.depth, "back");
        layoutBin(out, plan, frame, CHEST_DIMS.binFloor, CHEST_DIMS.height - CHEST_DIMS.binFloor - 0.08, true);
        break;
      }
      case "table": {
        const frame = frameFor(plan, TABLE_DIMS.depth, "center");
        layoutBin(out, plan, frame, TABLE_DIMS.height, 0.3, false);
        break;
      }
      default:
        break;
    }
  }
  return out;
}
