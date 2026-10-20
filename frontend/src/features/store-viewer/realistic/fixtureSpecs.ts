// Fixture planning for Realistic mode: which procedural fixture a rack becomes,
// where its shelf banks sit and at which heights each level is. Pure (no three.js)
// so the product layout and the geometry builder agree on every number.

import type { Face, Rack } from "@/shared/types/domain";
import { rackBounds } from "@/shared/utils/grid";

export type FixtureKind = "gondola" | "wallShelf" | "reachIn" | "chest" | "counter" | "table" | "door" | "none";

export const FACES: Face[] = ["N", "E", "S", "W"];

// Outward normal (x, z) of each face. +X = East, +Z = South.
export const FACE_NORMAL: Record<Face, [number, number]> = {
  N: [0, -1],
  S: [0, 1],
  E: [1, 0],
  W: [-1, 0],
};

// Yaw that turns a fixture-local +Z front toward the face normal.
export const FACE_YAW: Record<Face, number> = {
  S: 0,
  E: Math.PI / 2,
  N: Math.PI,
  W: -Math.PI / 2,
};

export const OPPOSITE: Record<Face, Face> = { N: "S", S: "N", E: "W", W: "E" };

// Shopper's right-hand direction when facing the shelf (looking against the normal).
export function faceTangent(face: Face): [number, number] {
  const [nx, nz] = FACE_NORMAL[face];
  return [nz === 0 ? 0 : nz, nx === 0 ? 0 : -nx];
}

// Grid-editor convention: rotation 0 ⇒ front = S, 90 ⇒ W, 180 ⇒ N, 270 ⇒ E.
export const ROTATION_FRONT: Record<number, Face> = { 0: "S", 90: "W", 180: "N", 270: "E" };

export interface Footprint {
  x0: number;
  z0: number;
  w: number;
  d: number;
  cx: number;
  cz: number;
}

export function footprint(rack: Rack): Footprint {
  const { w, d } = rackBounds(rack);
  const [x0, z0] = rack.position;
  return { x0, z0, w, d, cx: x0 + w / 2, cz: z0 + d / 2 };
}

export interface FixtureDims {
  height: number;
  // Depth of a single-sided unit / one side of a double-sided unit.
  depthSingle: number;
  depthDouble: number;
  firstShelf: number;
  lastShelf: number;
}

export const FIXTURE_DIMS: Record<"gondola" | "wallShelf" | "reachIn", FixtureDims> = {
  gondola: { height: 1.3, depthSingle: 0.5, depthDouble: 0.41, firstShelf: 0.1, lastShelf: 1.0 },
  wallShelf: { height: 1.55, depthSingle: 0.5, depthDouble: 0.41, firstShelf: 0.1, lastShelf: 1.25 },
  reachIn: { height: 1.62, depthSingle: 0.7, depthDouble: 0.36, firstShelf: 0.13, lastShelf: 1.2 },
};

export const CHEST_DIMS = { height: 0.68, depth: 0.7, binFloor: 0.47, rim: 0.05 };
export const COUNTER_DIMS = { height: 0.76, depth: 0.58 };
export const TABLE_DIMS = { height: 0.74, depth: 0.7 };
export const SPINE = 0.03;

export interface Bank {
  face: Face;
  yaw: number;
  n: [number, number];
  t: [number, number];
  // Bank frame origin (world x/z). Points are origin + t·u + n·v.
  ox: number;
  oz: number;
  width: number;
  back: number; // v of the back panel
  front: number; // v of the shelf front edge
  shelfYs: number[]; // shelf top surface per level (index 0 = level 1)
}

export interface FixturePlan {
  rack: Rack;
  kind: FixtureKind;
  fp: Footprint;
  front: Face;
  faces: Face[];
  layout: "double" | "single" | "cube" | "none";
  height: number;
  banks: Bank[];
}

export function productFaces(rack: Rack): Face[] {
  const set = new Set<Face>();
  for (const s of rack.slots ?? []) if (s.items?.length) set.add(s.face);
  return FACES.filter((f) => set.has(f));
}

export function levelCount(rack: Rack): number {
  let n = Math.max(1, rack.levels || 0);
  for (const s of rack.slots ?? []) n = Math.max(n, s.level);
  return Math.min(6, n);
}

export function shelfHeights(first: number, last: number, n: number): number[] {
  if (n <= 1) return [first];
  const step = (last - first) / (n - 1);
  return Array.from({ length: n }, (_, i) => first + step * i);
}

// Whether the tile edge behind `face` is the store boundary (so a single-sided
// unit stands against a wall).
function backsOntoWall(fp: Footprint, face: Face, gridW: number, gridD: number): boolean {
  switch (face) {
    case "S":
      return fp.z0 === 0;
    case "N":
      return fp.z0 + fp.d === gridD;
    case "E":
      return fp.x0 === 0;
    case "W":
      return fp.x0 + fp.w === gridW;
  }
}

function kindFor(rack: Rack): FixtureKind {
  switch (rack.type) {
    case "shelf":
      return "gondola";
    case "fridge":
      return rack.design_variant === "b" ? "chest" : "reachIn";
    case "display":
      return "chest";
    case "table":
      return "table";
    case "counter":
      return "counter";
    case "entrance":
    case "exit":
      return "door";
    default:
      return "none";
  }
}

function makeBank(face: Face, ox: number, oz: number, width: number, back: number, front: number, shelfYs: number[]): Bank {
  return { face, yaw: FACE_YAW[face], n: FACE_NORMAL[face], t: faceTangent(face), ox, oz, width, back, front, shelfYs };
}

export function planFixture(rack: Rack, gridW: number, gridD: number): FixturePlan {
  const fp = footprint(rack);
  let kind = kindFor(rack);
  const faces = productFaces(rack);
  const front = faces[0] ?? ROTATION_FRONT[rack.rotation ?? 0] ?? "S";
  const base: FixturePlan = { rack, kind, fp, front, faces, layout: "none", height: 0, banks: [] };

  if (kind === "door" || kind === "none") return base;
  if (kind === "counter") {
    const f = ROTATION_FRONT[rack.rotation ?? 0] ?? "S";
    return { ...base, front: f, height: COUNTER_DIMS.height };
  }
  if (kind === "chest" || kind === "table") {
    const f = faces.length === 1 ? faces[0]! : ROTATION_FRONT[rack.rotation ?? 0] ?? front;
    const h = kind === "chest" ? CHEST_DIMS.height : TABLE_DIMS.height;
    return { ...base, front: f, height: h };
  }

  const usedFaces = faces.length ? faces : [front];
  const pairNS = usedFaces.length === 2 && usedFaces.includes("N") && usedFaces.includes("S");
  const pairEW = usedFaces.length === 2 && usedFaces.includes("E") && usedFaces.includes("W");
  const n = levelCount(rack);

  if (pairNS || pairEW) {
    const dims = FIXTURE_DIMS[kind === "reachIn" ? "reachIn" : "gondola"];
    const ys = shelfHeights(dims.firstShelf, dims.lastShelf, n);
    const banks = usedFaces.map((f) => {
      const along = f === "N" || f === "S" ? fp.w : fp.d;
      return makeBank(f, fp.cx, fp.cz, along - 0.02, SPINE / 2, dims.depthDouble, ys);
    });
    return { ...base, kind, layout: "double", height: dims.height, banks };
  }

  if (usedFaces.length === 1) {
    const f = usedFaces[0]!;
    if (kind === "gondola" && backsOntoWall(fp, f, gridW, gridD)) kind = "wallShelf";
    const dims = FIXTURE_DIMS[kind as "gondola" | "wallShelf" | "reachIn"];
    const ys = shelfHeights(dims.firstShelf, dims.lastShelf, n);
    const along = f === "N" || f === "S" ? fp.w : fp.d;
    const depthExtent = f === "N" || f === "S" ? fp.d : fp.w;
    const back = -depthExtent / 2 + 0.02;
    const bank = makeBank(f, fp.cx, fp.cz, along - 0.02, back + SPINE, back + dims.depthSingle, ys);
    return { ...base, kind, front: f, layout: "single", height: dims.height, banks: [bank] };
  }

  // Three or four faces, or two adjacent faces: a square island with shallow
  // shelves on every stocked side.
  const dims = FIXTURE_DIMS[kind === "reachIn" ? "reachIn" : "gondola"];
  const ys = shelfHeights(dims.firstShelf, dims.lastShelf, n);
  const half = Math.min(fp.w, fp.d) * 0.42;
  const banks = usedFaces.map((f) => {
    const width = f === "N" || f === "S" ? half * 2 : half * 2 - 0.44;
    return makeBank(f, fp.cx, fp.cz, Math.max(0.2, width), half - 0.22, half, ys);
  });
  return { ...base, kind, layout: "cube", height: dims.height, banks };
}

// Local frame of a one-piece fixture (chest freezer, counter, table): front faces
// `plan.front`, origin at the unit's centre. "back" anchors the unit against the
// rear edge of its tiles; "center" centres it.
export interface Frame {
  ox: number;
  oz: number;
  n: [number, number];
  t: [number, number];
  yaw: number;
  width: number; // along t
  depth: number; // along n
}

export function frameFor(plan: FixturePlan, depth: number, anchor: "back" | "center"): Frame {
  const f = plan.front;
  const n = FACE_NORMAL[f];
  const t = faceTangent(f);
  const ns = f === "N" || f === "S";
  const along = ns ? plan.fp.w : plan.fp.d;
  const extentN = ns ? plan.fp.d : plan.fp.w;
  const v = anchor === "back" ? -extentN / 2 + 0.03 + depth / 2 : 0;
  return {
    ox: plan.fp.cx + n[0] * v,
    oz: plan.fp.cz + n[1] * v,
    n,
    t,
    yaw: FACE_YAW[f],
    width: along - 0.06,
    depth,
  };
}

// World x/z of a point given in a frame's (u along t, v along n) coordinates.
export function frameToWorld(f: { ox: number; oz: number; n: [number, number]; t: [number, number] }, u: number, v: number): [number, number] {
  return [f.ox + f.t[0] * u + f.n[0] * v, f.oz + f.t[1] * u + f.n[1] * v];
}

// Store side ("N" | "E" | "S" | "W") a door tile sits on, or null for interior tiles.
export function doorSide(x: number, z: number, gridW: number, gridD: number): Face | null {
  const dists: [Face, number][] = [
    ["W", x],
    ["E", gridW - 1 - x],
    ["N", z],
    ["S", gridD - 1 - z],
  ];
  dists.sort((a, b) => a[1] - b[1]);
  const [side, dist] = dists[0]!;
  return dist === 0 ? side : null;
}
