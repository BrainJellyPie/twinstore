// Procedural store shell + fixtures for Realistic mode. Produces merged
// geometries per material, the signage atlas and the automatic-door specs.

import type { BufferGeometry } from "three";
import type { Face, Rack } from "@/shared/types/domain";
import { CEILING_HEIGHT, CUTAWAY_HEIGHT, FLOOR_SLAB, WALL_HEIGHT, WALL_THICKNESS } from "./constants";
import {
  CHEST_DIMS,
  COUNTER_DIMS,
  SPINE,
  TABLE_DIMS,
  doorSide,
  frameFor,
  frameToWorld,
  planFixture,
  type Bank,
  type FixturePlan,
  type Frame,
} from "./fixtureSpecs";
import { StaticBuilder, type MatKey } from "./staticBuilder";
import { createSignAtlas, signKey, signText, type Atlas, type SignStyle } from "./canvasArt";
import { cellUv } from "./atlasLayout";

export interface DoorSpec {
  key: string;
  // Centre of the opening on the wall line (world, store-local).
  x: number;
  z: number;
  // Yaw of the inward normal.
  yaw: number;
  width: number;
  tall: boolean;
}

interface Decal {
  x: number;
  z: number;
  w: number;
  d: number;
  yaw: number;
  opacity: number;
}

export interface BuiltStore {
  geometries: Map<MatKey, BufferGeometry>;
  // Upper parts of the camera-side (cutaway) walls; shown only in the
  // first-person shopper view so the store is enclosed.
  upperGeometries: Map<MatKey, BufferGeometry>;
  signAtlas: Atlas;
  doors: DoorSpec[];
  plans: FixturePlan[];
  storefront: Face | null;
}

interface SignRequest {
  text: string;
  style: SignStyle;
  w: number;
  h: number;
  x: number;
  y: number;
  z: number;
  yaw: number;
}

const T = WALL_THICKNESS;
const SHELF_T = 0.022;
const UPRIGHT = 0.035;

const SIDE_YAW: Record<Face, number> = { N: 0, S: Math.PI, W: Math.PI / 2, E: -Math.PI / 2 };
const TALL: Record<Face, boolean> = { N: true, W: true, S: false, E: false };

function sideOrigin(side: Face, w: number, d: number): [number, number] {
  switch (side) {
    case "N":
      return [0, 0];
    case "S":
      return [w, d];
    case "W":
      return [0, d];
    case "E":
      return [w, 0];
  }
}

// Grid cell adjacent to the wall at position s (0..L) along a side.
function sideCell(side: Face, k: number, w: number, d: number): [number, number] {
  switch (side) {
    case "N":
      return [k, 0];
    case "S":
      return [w - 1 - k, d - 1];
    case "W":
      return [0, d - 1 - k];
    case "E":
      return [w - 1, k];
  }
}

const SHELVING = new Set(["gondola", "wallShelf", "reachIn"]);

interface Ctx {
  b: StaticBuilder;
  upper: StaticBuilder;
  w: number;
  d: number;
  cells: Map<string, FixturePlan>;
  signs: SignRequest[];
  decals: Decal[];
}

// ---------------------------------------------------------------------------
// Shell

function buildFloor(ctx: Ctx, storefront: Face | null) {
  const { b, w, d } = ctx;
  b.resetFrame();
  // Slab under the floor and walls (diorama base).
  b.span("plinth", -T, -FLOOR_SLAB, -T, w + T, -0.002, d + T);
  if (!storefront) return;
  // Pavement outside the storefront.
  const out = 1.7;
  const [x0, z0, x1, z1] =
    storefront === "N"
      ? [-T - 0.4, -T - out, w + T + 0.4, -T]
      : storefront === "S"
        ? [-T - 0.4, d + T, w + T + 0.4, d + T + out]
        : storefront === "W"
          ? [-T - out, -T - 0.4, -T, d + T + 0.4]
          : [w + T, -T - 0.4, w + T + out, d + T + 0.4];
  b.span("pavement", x0, -0.07, z0, x1, -0.03, z1);
  b.span("plinth", x0, -FLOOR_SLAB, z0, x1, -0.07, z1);
  // Curb along the outer edge.
  if (storefront === "N") b.span("curb", x0, -0.12, z0 - 0.12, x1, -0.03, z0);
  if (storefront === "S") b.span("curb", x0, -0.12, z1, x1, -0.03, z1 + 0.12);
  if (storefront === "W") b.span("curb", x0 - 0.12, -0.12, z0, x0, -0.03, z1);
  if (storefront === "E") b.span("curb", x1, -0.12, z0, x1 + 0.12, -0.03, z1);
}

function buildCeiling(ctx: Ctx) {
  const { b, w, d } = ctx;
  b.resetFrame();
  for (let i = 0; i < w; i++) {
    for (let j = 0; j < d; j++) {
      if ((i + j) % 2 !== 0) continue;
      b.quad("ceilingLight", 0.46, 0.46, i + 0.5, CEILING_HEIGHT - 0.004, j + 0.5, 0, Math.PI / 2);
    }
  }
}

function wallSegment(ctx: Ctx, side: Face, s0: number, s1: number, kind: "solid" | "glass" | "door", h: number) {
  const { b } = ctx;
  const tall = TALL[side];
  const len = s1 - s0;
  const mid = (s0 + s1) / 2;
  const band = () => {
    if (!tall) return;
    b.span("band", s0, 2.06, 0, s1, 2.2, 0.008);
    b.span("trim", s0, h - 0.06, 0, s1, h, 0.03);
  };
  if (kind === "solid") {
    b.span("wall", s0, 0, -T, s1, h, 0);
    b.span("trim", s0, 0, 0, s1, 0.09, 0.012);
    if (tall) b.span("bandLine", s0, 2.01, 0, s1, 2.035, 0.008);
    band();
  } else if (kind === "glass") {
    const top = tall ? 2.0 : h;
    b.span("aluminum", s0, 0, -T * 0.7, s1, 0.12, -T * 0.2);
    b.quad("glass", len, top - 0.12, mid, (top + 0.12) / 2, -T * 0.45);
    b.span("aluminum", s0, 0.12, -T * 0.7, s0 + 0.035, top, -T * 0.2);
    b.span("aluminum", s1 - 0.035, 0.12, -T * 0.7, s1, top, -T * 0.2);
    if (tall) {
      b.span("aluminum", s0, top, -T * 0.7, s1, top + 0.06, -T * 0.2);
      b.span("wall", s0, top + 0.06, -T, s1, h, 0);
      band();
    } else {
      b.span("aluminum", s0, top - 0.02, -T * 0.8, s1, top, -T * 0.1);
    }
  } else {
    // Door opening: posts + operator header; leaves are animated separately.
    const top = tall ? 2.0 : h;
    b.span("aluminum", s0, 0, -T * 0.8, s0 + 0.05, top, -T * 0.1);
    b.span("aluminum", s1 - 0.05, 0, -T * 0.8, s1, top, -T * 0.1);
    b.span("aluminum", s0, -0.002, -T, s1, 0.006, 0.02);
    if (tall) {
      b.span("darkMetal", s0, 2.0, -T * 0.9, s1, 2.12, 0.05);
      b.span("wall", s0, 2.12, -T, s1, h, 0);
      b.span("trim", s0, h - 0.06, 0, s1, h, 0.03);
      // Exit sign housing above the door (inside).
      b.span("darkMetal", mid - 0.16, 2.14, 0.0, mid + 0.16, 2.26, 0.03);
    }
  }
  // Section cut on top of the wall.
  b.span("cut", s0, h, -T, s1, h + 0.008, 0);
}

// Full-height continuation of a cutaway segment, from CUTAWAY_HEIGHT up.
function upperSegment(b: StaticBuilder, s0: number, s1: number, kind: "solid" | "glass" | "door") {
  const y0 = CUTAWAY_HEIGHT;
  const h = WALL_HEIGHT;
  const len = s1 - s0;
  const mid = (s0 + s1) / 2;
  // Faces sit 2 mm proud of the cutaway wall so its section cap doesn't z-fight.
  if (kind === "solid") {
    b.span("wall", s0, y0 - 0.01, -T, s1, h, 0.002);
    b.span("bandLine", s0, 2.01, 0, s1, 2.035, 0.01);
  } else if (kind === "glass") {
    b.quad("glass", len, 2.0 - y0, mid, (2.0 + y0) / 2, -T * 0.45);
    b.span("aluminum", s0, y0, -T * 0.7, s0 + 0.035, 2.0, -T * 0.2);
    b.span("aluminum", s1 - 0.035, y0, -T * 0.7, s1, 2.0, -T * 0.2);
    b.span("aluminum", s0, 2.0, -T * 0.7, s1, 2.06, -T * 0.2);
    b.span("wall", s0, 2.06, -T, s1, h, 0.002);
  } else {
    b.span("aluminum", s0, y0, -T * 0.8, s0 + 0.05, 2.0, -T * 0.1);
    b.span("aluminum", s1 - 0.05, y0, -T * 0.8, s1, 2.0, -T * 0.1);
    b.span("darkMetal", s0, 2.0, -T * 0.9, s1, 2.12, 0.05);
    b.span("wall", s0, 2.12, -T, s1, h, 0.002);
  }
  b.span("band", s0, 2.06, 0, s1, 2.2, 0.01);
  b.span("trim", s0, h - 0.06, 0, s1, h, 0.03);
}

function buildWalls(ctx: Ctx, doorCells: Map<string, Face>, storefront: Face | null): DoorSpec[] {
  const { b, w, d } = ctx;
  const doors: DoorSpec[] = [];
  for (const side of ["N", "W", "S", "E"] as Face[]) {
    const L = side === "N" || side === "S" ? w : d;
    const [ox, oz] = sideOrigin(side, w, d);
    const yaw = SIDE_YAW[side];
    const h = TALL[side] ? WALL_HEIGHT : CUTAWAY_HEIGHT;
    b.setFrame(ox, oz, yaw);
    if (!TALL[side]) ctx.upper.setFrame(ox, oz, yaw);
    let k = 0;
    while (k < L) {
      const [cx, cz] = sideCell(side, k, w, d);
      const isDoor = doorCells.get(`${cx},${cz}`) === side;
      let kind: "solid" | "glass" | "door" = "solid";
      if (isDoor) kind = "door";
      else if (storefront === side) {
        const p = ctx.cells.get(`${cx},${cz}`);
        kind = p && SHELVING.has(p.kind) ? "solid" : "glass";
      }
      // Merge consecutive door tiles into one wide opening.
      let k1 = k + 1;
      if (kind === "door") {
        while (k1 < L) {
          const [nx, nz] = sideCell(side, k1, w, d);
          if (doorCells.get(`${nx},${nz}`) !== side) break;
          k1++;
        }
      }
      wallSegment(ctx, side, k, k1, kind, h);
      if (!TALL[side]) upperSegment(ctx.upper, k, k1, kind);
      if (kind === "door") {
        const mid = (k + k1) / 2;
        const [wx, wz] = localToWorld(ox, oz, yaw, mid, -T * 0.45);
        doors.push({ key: `${side}${k}`, x: wx, z: wz, yaw, width: k1 - k, tall: TALL[side] });
        if (TALL[side]) {
          const [sx, sz] = localToWorld(ox, oz, yaw, mid, 0.032);
          ctx.signs.push({ text: "EXIT", style: "exit", w: 0.3, h: 0.1, x: sx, y: 2.2, z: sz, yaw });
        }
        // Entrance mat inside the door.
        b.span("mat", k + 0.08, 0, 0.04, k1 - 0.08, 0.008, 0.62);
      }
      k = k1;
    }
    // Wall-foot AO along tall walls.
    if (TALL[side]) {
      const [ax, az] = localToWorld(ox, oz, yaw, L / 2, 0);
      ctx.decals.push({ x: ax, z: az, w: L + 0.3, d: 0.55, yaw, opacity: 0.38 });
    }
  }
  // Corner posts.
  b.resetFrame();
  b.span("wall", -T, 0, -T, 0, WALL_HEIGHT, 0);
  b.span("cut", -T, WALL_HEIGHT, -T, 0, WALL_HEIGHT + 0.008, 0);
  b.span("wall", w, 0, -T, w + T, WALL_HEIGHT, 0);
  b.span("cut", w, WALL_HEIGHT, -T, w + T, WALL_HEIGHT + 0.008, 0);
  b.span("wall", -T, 0, d, 0, WALL_HEIGHT, d + T);
  b.span("cut", -T, WALL_HEIGHT, d, 0, WALL_HEIGHT + 0.008, d + T);
  b.span("wall", w, 0, d, w + T, CUTAWAY_HEIGHT, d + T);
  b.span("cut", w, CUTAWAY_HEIGHT, d, w + T, CUTAWAY_HEIGHT + 0.008, d + T);
  ctx.upper.resetFrame();
  ctx.upper.span("wall", w, CUTAWAY_HEIGHT + 0.008, d, w + T, WALL_HEIGHT, d + T);
  return doors;
}

function localToWorld(ox: number, oz: number, yaw: number, lx: number, lz: number): [number, number] {
  const c = Math.cos(yaw);
  const s = Math.sin(yaw);
  return [ox + lx * c + lz * s, oz - lx * s + lz * c];
}

function buildExterior(ctx: Ctx, storefront: Face | null, doors: DoorSpec[]) {
  if (!storefront) return;
  const { b } = ctx;
  for (const door of doors) {
    // Planters and bollards either side of the door, outside.
    b.setFrame(door.x, door.z, door.yaw);
    for (const sgn of [-1, 1]) {
      const u = sgn * (door.width / 2 + 0.45);
      b.box("pot", 0.34, 0.3, 0.34, u, 0.12, -0.55);
      b.sphere("plant", 0.2, u, 0.42, -0.55, 1.15);
      b.sphere("plant", 0.14, u + 0.08, 0.56, -0.5, 1.2);
      b.cylinder("aluminum", 0.04, 0.04, 0.55, sgn * (door.width / 2 + 0.05), 0.22, -1.25, 10);
    }
  }
}

// ---------------------------------------------------------------------------
// Fixtures

function cellOf(x: number, z: number): string {
  return `${Math.floor(x)},${Math.floor(z)}`;
}

function bankEndOpen(ctx: Ctx, bank: Bank, end: 1 | -1, self: FixturePlan): boolean {
  const mid = (bank.back + bank.front) / 2;
  const [x, z] = frameToWorld(bank, end * (bank.width / 2 + 0.5), mid);
  const p = ctx.cells.get(cellOf(x, z));
  return !p || p === self || p.kind !== self.kind;
}

function addFootprintDecal(ctx: Ctx, pts: [number, number][], opacity: number) {
  let x0 = Infinity;
  let z0 = Infinity;
  let x1 = -Infinity;
  let z1 = -Infinity;
  for (const [x, z] of pts) {
    x0 = Math.min(x0, x);
    z0 = Math.min(z0, z);
    x1 = Math.max(x1, x);
    z1 = Math.max(z1, z);
  }
  const m = 0.2;
  ctx.decals.push({ x: (x0 + x1) / 2, z: (z0 + z1) / 2, w: x1 - x0 + 2 * m, d: z1 - z0 + 2 * m, yaw: 0, opacity });
}

function bankCorners(bank: Bank, back: number): [number, number][] {
  const h = bank.width / 2;
  return [
    frameToWorld(bank, -h, back),
    frameToWorld(bank, h, back),
    frameToWorld(bank, -h, bank.front),
    frameToWorld(bank, h, bank.front),
  ];
}

function buildShelving(ctx: Ctx, plan: FixturePlan) {
  const { b } = ctx;
  const H = plan.height;
  const pts: [number, number][] = [];
  const tall = plan.kind === "wallShelf";
  plan.banks.forEach((bank, bi) => {
    const half = bank.width / 2;
    const panelBack = bank.back - (plan.layout === "double" ? SPINE / 2 : SPINE);
    pts.push(...bankCorners(bank, panelBack));
    b.setFrame(bank.ox, bank.oz, bank.yaw);
    // Back panel (pegboard) and uprights.
    b.span("backPanel", -half, 0.08, panelBack, half, H, bank.back);
    for (const sgn of [-1, 1]) {
      b.span("metalGrey", sgn * half - (sgn > 0 ? UPRIGHT : 0), 0, bank.back, sgn * half + (sgn < 0 ? UPRIGHT : 0), H, bank.back + 0.035);
    }
    // Kick plate and base deck.
    b.span("kick", -half, 0, bank.front - 0.03, half, bank.shelfYs[0]! - SHELF_T, bank.front);
    b.span("kick", -half, 0, bank.back, half, 0.02, bank.front - 0.03);
    bank.shelfYs.forEach((y, li) => {
      const inset = li === 0 ? 0 : UPRIGHT;
      b.span("metalWhite", -half + inset, y - SHELF_T, bank.back, half - inset, y, bank.front);
      // Price channel along the shelf edge.
      b.span("rail", -half + inset, y - SHELF_T - 0.022, bank.front, half - inset, y + 0.004, bank.front + 0.012);
    });
    // End panels where the run stops.
    for (const end of [-1, 1] as const) {
      if (!bankEndOpen(ctx, bank, end, plan)) continue;
      const x = end * half;
      b.span("metalWhite", x - (end > 0 ? 0.018 : 0), 0, panelBack, x + (end < 0 ? 0.018 : 0), H + (tall ? 0 : 0.02), bank.front + 0.01);
    }
    // Header sign: topper on gondolas, fascia on wall shelving.
    const text = signText(plan.rack.rack_name, "GROCERY");
    if (tall) {
      b.span("metalWhite", -half, H - 0.02, panelBack, half, H + 0.03, bank.back + 0.28);
      const [sx, sz] = frameToWorld(bank, 0, bank.back + 0.006);
      ctx.signs.push({ text, style: "header", w: Math.min(bank.width * 0.8, 0.95), h: 0.16, x: sx, y: H - 0.14, z: sz, yaw: bank.yaw });
    } else {
      if (plan.layout === "double") {
        if (bi === 0) b.span("metalWhite", -half * 0.85, H, -0.02, half * 0.85, H + 0.2, 0.02);
      } else {
        b.span("metalWhite", -half * 0.85, H, bank.back - 0.02, half * 0.85, H + 0.2, bank.back + 0.004);
      }
      const [sx, sz] = frameToWorld(bank, 0, plan.layout === "double" ? 0.021 : bank.back + 0.006);
      ctx.signs.push({ text, style: "header", w: Math.min(bank.width * 0.82, 0.92), h: 0.18, x: sx, y: H + 0.1, z: sz, yaw: bank.yaw });
    }
  });
  addFootprintDecal(ctx, pts, 0.55);
}

function buildReachIn(ctx: Ctx, plan: FixturePlan) {
  const { b } = ctx;
  const H = plan.height;
  const pts: [number, number][] = [];
  for (const bank of plan.banks) {
    const half = bank.width / 2;
    const back = bank.back - SPINE;
    const front = bank.front;
    pts.push(...bankCorners(bank, back));
    b.setFrame(bank.ox, bank.oz, bank.yaw);
    // Cabinet shell.
    b.span("fridgeShell", -half, 0, back, half, H, bank.back);
    b.span("fridgeShell", -half, 0, back, -half + 0.04, H, front + 0.05);
    b.span("fridgeShell", half - 0.04, 0, back, half, H, front + 0.05);
    b.span("fridgeShell", -half, H - 0.06, back, half, H, front + 0.05);
    // Header canopy and kick grille.
    b.span("darkMetal", -half, H, back, half, H + 0.2, front + 0.07);
    b.span("darkMetal", -half, 0, front - 0.06, half, 0.11, front + 0.05);
    for (let g = 0; g < 6; g++) b.span("black", -half + 0.06, 0.025 + g * 0.014, front + 0.05, half - 0.06, 0.03 + g * 0.014, front + 0.052);
    // Interior.
    b.span("fridgeInterior", -half + 0.04, 0.11, bank.back, half - 0.04, H - 0.06, bank.back + 0.006);
    b.span("fridgeInterior", -half + 0.04, 0.11, back, half - 0.04, 0.12, front - 0.06);
    bank.shelfYs.forEach((y) => {
      b.span("wire", -half + 0.045, y - 0.012, bank.back + 0.01, half - 0.045, y, front - 0.075);
      b.span("rail", -half + 0.045, y - 0.03, front - 0.075, half - 0.045, y + 0.004, front - 0.068);
    });
    // Doors: frames, glass, handles; LED strips behind the mullions.
    const doors = Math.max(1, Math.round(bank.width / 0.5));
    const dw = (bank.width - 0.08) / doors;
    const dz = front + 0.03;
    for (let i = 0; i < doors; i++) {
      const x0 = -half + 0.04 + i * dw;
      const x1 = x0 + dw;
      const fy0 = 0.11;
      const fy1 = H - 0.04;
      b.span("darkMetal", x0, fy0, dz - 0.015, x0 + 0.035, fy1, dz + 0.015);
      b.span("darkMetal", x1 - 0.035, fy0, dz - 0.015, x1, fy1, dz + 0.015);
      b.span("darkMetal", x0, fy0, dz - 0.015, x1, fy0 + 0.04, dz + 0.015);
      b.span("darkMetal", x0, fy1 - 0.04, dz - 0.015, x1, fy1, dz + 0.015);
      b.quad("glass", dw - 0.07, fy1 - fy0 - 0.08, (x0 + x1) / 2, (fy0 + fy1) / 2, dz);
      // Handle on the opening side.
      const hx = i % 2 === 0 ? x1 - 0.07 : x0 + 0.07;
      b.cylinder("chrome", 0.011, 0.011, 0.62, hx, 0.95, dz + 0.045, 10);
      b.span("chrome", hx - 0.008, 0.66, dz + 0.015, hx + 0.008, 0.675, dz + 0.045);
      b.span("chrome", hx - 0.008, 1.24, dz + 0.015, hx + 0.008, 1.255, dz + 0.045);
      // Vertical LED strip just inside each door edge.
      b.span("led", x0 + 0.04, 0.16, front - 0.035, x0 + 0.052, H - 0.1, front - 0.025);
    }
    b.span("led", half - 0.092, 0.16, front - 0.035, half - 0.08, H - 0.1, front - 0.025);
    b.span("led", -half + 0.06, H - 0.085, front - 0.06, half - 0.06, H - 0.075, front - 0.02);
    const [sx, sz] = frameToWorld(bank, 0, front + 0.071);
    ctx.signs.push({
      text: signText(plan.rack.rack_name, "COLD DRINKS"),
      style: "fridge",
      w: Math.min(bank.width - 0.12, 0.9),
      h: 0.15,
      x: sx,
      y: H + 0.1,
      z: sz,
      yaw: bank.yaw,
    });
  }
  addFootprintDecal(ctx, pts, 0.6);
}

function chestRows(plan: FixturePlan): number {
  const levels = new Set((plan.rack.slots ?? []).filter((s) => s.items?.length).map((s) => s.level));
  return Math.max(1, levels.size);
}

function buildChest(ctx: Ctx, plan: FixturePlan) {
  const { b } = ctx;
  const f: Frame = frameFor(plan, CHEST_DIMS.depth, "back");
  const W = f.width;
  const D = f.depth;
  const H = CHEST_DIMS.height;
  const hw = W / 2;
  const hd = D / 2;
  b.setFrame(f.ox, f.oz, f.yaw);
  b.span("kick", -hw + 0.02, 0, -hd + 0.02, hw - 0.02, 0.07, hd - 0.02);
  // Insulated walls.
  b.span("freezerBody", -hw, 0.07, hd - 0.06, hw, H - 0.04, hd);
  b.span("freezerBody", -hw, 0.07, -hd, hw, H - 0.04, -hd + 0.06);
  b.span("freezerBody", -hw, 0.07, -hd, -hw + 0.06, H - 0.04, hd);
  b.span("freezerBody", hw - 0.06, 0.07, -hd, hw, H - 0.04, hd);
  b.span("freezerBody", -hw, 0.07, -hd, hw, CHEST_DIMS.binFloor - 0.02, hd);
  b.span("freezerInterior", -hw + 0.06, CHEST_DIMS.binFloor - 0.02, -hd + 0.06, hw - 0.06, CHEST_DIMS.binFloor, hd - 0.06);
  // Bumper rail on top.
  b.span("bumper", -hw, H - 0.04, hd - 0.065, hw, H, hd + 0.01);
  b.span("bumper", -hw, H - 0.04, -hd - 0.01, hw, H, -hd + 0.065);
  b.span("bumper", -hw - 0.01, H - 0.04, -hd, -hw + 0.065, H, hd);
  b.span("bumper", hw - 0.065, H - 0.04, -hd, hw + 0.01, H, hd);
  // Coloured front band.
  b.span("band", -hw + 0.03, 0.1, hd, hw - 0.03, 0.16, hd + 0.004);
  // Row dividers.
  const rows = chestRows(plan);
  const innerD = D - 0.12;
  for (let r = 1; r < rows; r++) {
    const v = innerD / 2 - (innerD / rows) * r;
    b.span("wire", -hw + 0.06, CHEST_DIMS.binFloor, v - 0.004, hw - 0.06, H - 0.1, v + 0.004);
  }
  // Interior LED along the back rim.
  b.span("led", -hw + 0.08, H - 0.075, -hd + 0.06, hw - 0.08, H - 0.065, -hd + 0.07);
  // Sliding glass lids with aluminium frames.
  const lidY = H + 0.004;
  b.quad("lidGlass", hw - 0.04, D - 0.1, -hw / 2, lidY, 0, 0, -Math.PI / 2);
  b.quad("lidGlass", hw - 0.04, D - 0.1, hw / 2, lidY + 0.018, 0, 0, -Math.PI / 2);
  for (const [x0, y] of [[-hw + 0.02, lidY], [0.01, lidY + 0.018]] as [number, number][]) {
    b.span("aluminum", x0, y - 0.006, -hd + 0.04, x0 + hw - 0.03, y + 0.006, -hd + 0.06);
    b.span("aluminum", x0, y - 0.006, hd - 0.06, x0 + hw - 0.03, y + 0.006, hd - 0.04);
    b.span("aluminum", x0, y - 0.006, -hd + 0.04, x0 + 0.02, y + 0.006, hd - 0.04);
    b.span("aluminum", x0 + hw - 0.05, y - 0.006, -hd + 0.04, x0 + hw - 0.03, y + 0.006, hd - 0.04);
  }
  const [sx, sz] = frameToWorld(f, 0, hd + 0.006);
  ctx.signs.push({ text: signText(plan.rack.rack_name, "FROZEN"), style: "header", w: Math.min(W * 0.62, 0.6), h: 0.12, x: sx, y: 0.36, z: sz, yaw: f.yaw });
  ctx.decals.push({ x: f.ox, z: f.oz, w: W + 0.36, d: D + 0.36, yaw: f.yaw, opacity: 0.5 });
}

function buildCounter(ctx: Ctx, plan: FixturePlan) {
  const { b } = ctx;
  const f = frameFor(plan, COUNTER_DIMS.depth, "center");
  const W = f.width;
  const D = f.depth;
  const H = COUNTER_DIMS.height;
  const hw = W / 2;
  const hd = D / 2;
  b.setFrame(f.ox, f.oz, f.yaw);
  b.span("black", -hw + 0.03, 0, -hd + 0.1, hw - 0.03, 0.07, hd - 0.03);
  b.span("wood", -hw, 0.07, hd - 0.04, hw, H - 0.04, hd);
  b.span("wood", -hw, 0.07, -hd + 0.08, -hw + 0.04, H - 0.04, hd);
  b.span("wood", hw - 0.04, 0.07, -hd + 0.08, hw, H - 0.04, hd);
  // Cashier-side cabinet shelves.
  b.span("metalWhite", -hw + 0.04, 0.07, -hd + 0.08, hw - 0.04, 0.09, hd - 0.04);
  b.span("metalWhite", -hw + 0.04, 0.38, -hd + 0.08, hw - 0.04, 0.4, hd - 0.04);
  b.span("metalWhite", -hw + 0.04, 0.07, hd - 0.08, hw - 0.04, H - 0.04, hd - 0.04);
  b.span("counterTop", -hw - 0.02, H - 0.04, -hd + 0.02, hw + 0.02, H, hd + 0.05);
  // POS terminal facing the cashier (-Z), customer display facing +Z.
  b.cylinder("black", 0.025, 0.04, 0.16, -0.12, H + 0.08, -0.05, 10);
  b.box("black", 0.3, 0.21, 0.03, -0.12, H + 0.25, -0.06, -0.25);
  b.quad("screen", 0.27, 0.18, -0.12, H + 0.25, -0.077, Math.PI, 0.25);
  b.box("black", 0.36, 0.1, 0.34, -0.12, H + 0.05, -0.12 + 0.02);
  b.box("black", 0.13, 0.08, 0.02, -0.12, H + 0.38, 0.0, 0.2);
  b.quad("screen", 0.11, 0.06, -0.12, H + 0.38, 0.012, 0, -0.2);
  // Card terminal and receipt printer.
  b.box("black", 0.08, 0.04, 0.14, 0.14, H + 0.02, 0.14, 0.35);
  b.quad("screen", 0.06, 0.05, 0.14, H + 0.048, 0.13, 0, -Math.PI / 2 + 0.35);
  b.box("black", 0.12, 0.1, 0.14, 0.32, H + 0.05, -0.12);
  // Impulse rack on the customer side.
  b.span("wire", 0.24, H, 0.06, 0.44, H + 0.008, 0.26);
  b.span("wire", 0.24, H + 0.008, 0.06, 0.44, H + 0.2, 0.07);
  ctx.decals.push({ x: f.ox, z: f.oz, w: W + 0.4, d: D + 0.4, yaw: f.yaw, opacity: 0.5 });
}

function buildTable(ctx: Ctx, plan: FixturePlan) {
  const { b } = ctx;
  const f = frameFor(plan, TABLE_DIMS.depth, "center");
  const hw = f.width / 2;
  const hd = f.depth / 2;
  const H = TABLE_DIMS.height;
  b.setFrame(f.ox, f.oz, f.yaw);
  b.span("wood", -hw, H - 0.04, -hd, hw, H, hd);
  b.span("wood", -hw, 0.12, -hd + 0.04, hw, 0.15, hd - 0.04);
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]] as const) {
    b.span("metalGrey", x * hw - (x > 0 ? 0.04 : 0), 0, z * hd - (z > 0 ? 0.04 : 0), x * hw + (x < 0 ? 0.04 : 0), H - 0.04, z * hd + (z < 0 ? 0.04 : 0));
  }
  b.span("rail", -hw, H - 0.07, hd, hw, H - 0.02, hd + 0.01);
  ctx.decals.push({ x: f.ox, z: f.oz, w: f.width + 0.3, d: f.depth + 0.3, yaw: f.yaw, opacity: 0.4 });
}

// ---------------------------------------------------------------------------

function addSigns(b: StaticBuilder, signs: SignRequest[]): Atlas {
  const atlas = createSignAtlas(signs.map((s) => ({ text: s.text, style: s.style })));
  b.resetFrame();
  for (const s of signs) {
    const idx = atlas.index.get(signKey(s.text, s.style));
    if (idx === undefined) continue;
    b.quad("sign", s.w, s.h, s.x, s.y, s.z, s.yaw, 0, cellUv(atlas.grid, idx));
  }
  return atlas;
}

export function buildStore(width: number, depth: number, racks: Rack[]): BuiltStore {
  const b = new StaticBuilder();
  const plans = racks.map((r) => planFixture(r, width, depth));
  const cells = new Map<string, FixturePlan>();
  for (const p of plans) {
    if (p.kind === "door" || p.kind === "none") continue;
    for (let x = 0; x < p.fp.w; x++) for (let z = 0; z < p.fp.d; z++) cells.set(`${p.fp.x0 + x},${p.fp.z0 + z}`, p);
  }
  const doorCells = new Map<string, Face>();
  const sideVotes = new Map<Face, number>();
  for (const p of plans) {
    if (p.kind !== "door") continue;
    for (let x = 0; x < p.fp.w; x++) {
      for (let z = 0; z < p.fp.d; z++) {
        const cx = p.fp.x0 + x;
        const cz = p.fp.z0 + z;
        const side = doorSide(cx, cz, width, depth);
        if (!side) continue;
        doorCells.set(`${cx},${cz}`, side);
        sideVotes.set(side, (sideVotes.get(side) ?? 0) + 1);
      }
    }
  }
  const storefront = [...sideVotes.entries()].sort((a, c) => c[1] - a[1])[0]?.[0] ?? null;

  const ctx: Ctx = { b, upper: new StaticBuilder(), w: width, d: depth, cells, signs: [], decals: [] };
  buildFloor(ctx, storefront);
  buildCeiling(ctx);
  const doors = buildWalls(ctx, doorCells, storefront);
  buildExterior(ctx, storefront, doors);
  for (const plan of plans) {
    switch (plan.kind) {
      case "gondola":
      case "wallShelf":
        buildShelving(ctx, plan);
        break;
      case "reachIn":
        buildReachIn(ctx, plan);
        break;
      case "chest":
        buildChest(ctx, plan);
        break;
      case "counter":
        buildCounter(ctx, plan);
        break;
      case "table":
        buildTable(ctx, plan);
        break;
      default:
        break;
    }
  }
  // Soft contact shadows (fake AO) under fixtures and along wall feet.
  for (const dc of ctx.decals) {
    b.setFrame(dc.x, dc.z, dc.yaw);
    b.quad("ao", dc.w, dc.d, 0, 0.004, 0, 0, -Math.PI / 2);
  }
  const signAtlas = addSigns(b, ctx.signs);
  return { geometries: b.build(), upperGeometries: ctx.upper.build(), signAtlas, doors, plans, storefront };
}
