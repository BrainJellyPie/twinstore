// Shelf snapshots: each stocked rack face photographed in Realistic mode, straight on from a shopper's eye
// height, for vision runs that show the model this photo above the shelf chart ("chart + 3D photo").
//
// Every face is rendered on its own: the rack alone in an empty store of its own (so no other fixture
// stands between the camera and the shelf), with the store's own materials, labels, product photos and
// price tags. The screen box of every product goes with the picture, keyed like the backend's item refs
// ("face:level:block:index"), so the server can put the chart's #N numbers on the right packages.

import * as THREE from "three";

import type { Face, Rack, Store } from "@/shared/types/domain";

import { canvasTexture } from "./atlasMaterial";
import { buildStore } from "./buildStore";
import { EYE_HEIGHT } from "./constants";
import { FACE_NORMAL, footprint, frameToWorld, type FixturePlan } from "./fixtureSpecs";
import { createShellMaterials, disposeMaterials, NO_CAST, NO_RECEIVE } from "./materials";
import { layoutProducts, type ProductInstance } from "./productLayout";
import { buildProductMeshes } from "./productMeshes";
import { createStoreEnvironmentScene, disposeScene } from "./storeEnvironment";

// The frame is rendered at this size, then cropped to the fixture (aspect 1.0–1.8) so the picture is shelf,
// not floor and ceiling.
export const SNAPSHOT_WIDTH = 1024;
export const SNAPSHOT_HEIGHT = 768;
const PAD = 4; // empty tiles around the rack: room for the camera, walls well out of the way
const FOV = 50;

export type Box = [number, number, number, number];

export interface ShelfShot {
  image: string; // data:image/jpeg;base64,…
  width: number;
  height: number;
  boxes: Record<string, Box[]>;
}

export interface FaceRequest {
  rackId: string;
  face: Face;
}

// The rack alone in the middle of an empty store, PAD tiles from every wall.
export function isolate(rack: Rack): { rack: Rack; width: number; depth: number } {
  const { w, d } = footprint({ ...rack, position: [0, 0] });
  return { rack: { ...rack, position: [PAD, PAD] }, width: Math.ceil(w) + 2 * PAD, depth: Math.ceil(d) + 2 * PAD };
}

// Where the camera stands for one face: at eye height in front of it, far enough back for the whole face.
// Chest freezers and tables are seen from above, as a shopper leaning over them looks in; `focus` is the
// middle of the face's products there.
export function faceCamera(plan: FixturePlan, face: Face, aspect: number, focus?: THREE.Vector3): { position: THREE.Vector3; target: THREE.Vector3 } {
  const vTan = Math.tan(THREE.MathUtils.degToRad(FOV / 2));
  const hTan = vTan * aspect;
  const height = Math.max(plan.height, 0.6);
  const bank = plan.banks.find((b) => b.face === face);
  if (bank) {
    const dist = Math.max((bank.width / 2 + 0.12) / hTan, (height * 0.56) / vTan, 0.8);
    const [cx, cz] = frameToWorld(bank, 0, bank.front + dist);
    const [tx, tz] = frameToWorld(bank, 0, bank.front);
    return { position: new THREE.Vector3(cx, EYE_HEIGHT.realistic, cz), target: new THREE.Vector3(tx, height * 0.47, tz) };
  }
  const n = FACE_NORMAL[face];
  const along = face === "N" || face === "S" ? plan.fp.w : plan.fp.d;
  const across = face === "N" || face === "S" ? plan.fp.d : plan.fp.w;
  const target = focus?.clone() ?? new THREE.Vector3(plan.fp.cx, height * 0.75, plan.fp.cz);
  const dist = Math.max((along / 2 + 0.15) / hTan, (across / 2 + 0.2) / vTan, 1.1);
  const down = THREE.MathUtils.degToRad(55);
  return {
    position: new THREE.Vector3(target.x + n[0] * dist * Math.cos(down), target.y + dist * Math.sin(down), target.z + n[1] * dist * Math.cos(down)),
    target,
  };
}

const _v = new THREE.Vector3();

// Screen box of every product of `face` (all its packages together), clipped to the picture.
export function productBoxes(products: ProductInstance[], face: Face, camera: THREE.Camera, width: number, height: number): Record<string, Box[]> {
  const union = new Map<string, Box>();
  for (const p of products) {
    if (!p.ref?.startsWith(`${face}:`)) continue;
    const c = Math.cos(p.yaw), s = Math.sin(p.yaw);
    let box = union.get(p.ref);
    for (const dx of [-p.sx / 2, p.sx / 2]) {
      for (const dz of [-p.sz / 2, p.sz / 2]) {
        for (const dy of [0, p.flat ? p.sz : p.sy]) {
          _v.set(p.x + dx * c + dz * s, p.y + dy, p.z - dx * s + dz * c).project(camera);
          if (_v.z > 1) continue; // behind the camera
          const x = ((_v.x + 1) / 2) * width;
          const y = ((1 - _v.y) / 2) * height;
          box = box ? [Math.min(box[0], x), Math.min(box[1], y), Math.max(box[2], x), Math.max(box[3], y)] : [x, y, x, y];
        }
      }
    }
    if (box) union.set(p.ref, box);
  }
  const out: Record<string, Box[]> = {};
  const round = (v: number) => Math.round(v * 10) / 10;
  for (const [ref, [x1, y1, x2, y2]] of union) {
    const box: Box = [round(Math.max(0, x1)), round(Math.max(0, y1)), round(Math.min(width, x2)), round(Math.min(height, y2))];
    if (box[2] - box[0] >= 2 && box[3] - box[1] >= 2) out[ref] = [box];
  }
  return out;
}

// The part of the frame to keep: every product and the fixture's front, a margin around it, widened or
// heightened to an aspect between minAspect and maxAspect, inside the frame.
export function cropRegion(boxes: Box[], width: number, height: number, margin = 0.06, minAspect = 1.0, maxAspect = 1.8): Box {
  if (!boxes.length) return [0, 0, width, height];
  let x1 = Math.min(...boxes.map((b) => b[0])), y1 = Math.min(...boxes.map((b) => b[1]));
  let x2 = Math.max(...boxes.map((b) => b[2])), y2 = Math.max(...boxes.map((b) => b[3]));
  const pad = Math.max(x2 - x1, y2 - y1) * margin;
  x1 -= pad; y1 -= pad; x2 += pad; y2 += pad;
  let w = x2 - x1, h = y2 - y1;
  if (w / h < minAspect) { const grow = h * minAspect - w; x1 -= grow / 2; w += grow; }
  if (w / h > maxAspect) { const grow = w / maxAspect - h; y1 -= grow / 2; h += grow; }
  w = Math.min(w, width);
  h = Math.min(h, height);
  x1 = Math.max(0, Math.min(width - w, x1));
  y1 = Math.max(0, Math.min(height - h, y1));
  return [Math.round(x1), Math.round(y1), Math.round(x1 + w), Math.round(y1 + h)];
}

// Screen box of the fixture's front (shelf banks) or top (chest, table).
function fixtureBox(plan: FixturePlan, face: Face, camera: THREE.Camera, width: number, height: number): Box | null {
  const bank = plan.banks.find((b) => b.face === face);
  const corners: THREE.Vector3[] = [];
  if (bank) {
    for (const u of [-bank.width / 2, bank.width / 2]) {
      const [x, z] = frameToWorld(bank, u, bank.front);
      corners.push(new THREE.Vector3(x, 0, z), new THREE.Vector3(x, plan.height, z));
    }
  } else {
    const { x0, z0, w, d } = plan.fp;
    for (const [x, z] of [[x0, z0], [x0 + w, z0], [x0, z0 + d], [x0 + w, z0 + d]] as const) {
      corners.push(new THREE.Vector3(x, 0, z), new THREE.Vector3(x, Math.max(plan.height, 0.6), z));
    }
  }
  const pts = corners.map((c) => c.project(camera)).filter((p) => p.z <= 1).map((p) => [((p.x + 1) / 2) * width, ((1 - p.y) / 2) * height] as const);
  if (!pts.length) return null;
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return [Math.max(0, Math.min(...xs)), Math.max(0, Math.min(...ys)), Math.min(width, Math.max(...xs)), Math.min(height, Math.max(...ys))];
}

function waitForPhotos(start: (done: () => void) => () => void, timeoutMs: number): Promise<() => void> {
  return new Promise((resolve) => {
    let stop: () => void = () => {};
    const timer = window.setTimeout(() => resolve(stop), timeoutMs);
    stop = start(() => {
      window.clearTimeout(timer);
      resolve(stop);
    });
  });
}

async function renderOne(renderer: THREE.WebGLRenderer, env: THREE.Texture, store: Store, rack: Rack, face: Face, currency: string): Promise<ShelfShot> {
  const placed = isolate(rack);
  const built = buildStore(placed.width, placed.depth, [placed.rack], false);
  const plan = built.plans[0]!;
  const signTexture = canvasTexture(built.signAtlas.canvas, { anisotropy: 1 });
  const materials = createShellMaterials("medium", signTexture, env, null, null, store.design_theme ?? "classic", null, null, null, store.design_colors ?? null, null);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#d9d6cf");
  scene.environment = null;
  for (const [key, geometry] of built.geometries) {
    const mesh = new THREE.Mesh(geometry, materials[key]);
    mesh.castShadow = !NO_CAST.has(key);
    mesh.receiveShadow = !NO_RECEIVE.has(key);
    mesh.renderOrder = key === "ao" ? 1 : key === "glass" || key === "lidGlass" ? 3 : 0;
    scene.add(mesh);
  }
  const layout = layoutProducts(built.plans, { maxRows: 3 });
  const products = buildProductMeshes(layout, currency, 192, true, 4, false);
  products.setDetail(true);
  scene.add(products.group);
  const stopAssets = await waitForPhotos((done) => products.loadAssets(undefined, done), 8000);

  const mine = layout.products.filter((p) => p.ref?.startsWith(`${face}:`));
  const focus = mine.length
    ? new THREE.Vector3(...[0, 1, 2].map((axis) => mine.reduce((sum, p) => sum + [p.x, p.y, p.z][axis]!, 0) / mine.length) as [number, number, number])
    : undefined;
  const { position, target } = faceCamera(plan, face, SNAPSHOT_WIDTH / SNAPSHOT_HEIGHT, focus);
  const camera = new THREE.PerspectiveCamera(FOV, SNAPSHOT_WIDTH / SNAPSHOT_HEIGHT, 0.05, 60);
  camera.position.copy(position);
  camera.lookAt(target);
  camera.updateMatrixWorld();

  // Ceiling light above the aisle in front of the face, a soft fill from the shopper's side.
  scene.add(new THREE.HemisphereLight("#fbfdff", "#d9d2c6", 1.05));
  scene.add(new THREE.AmbientLight("#fffdf8", 0.38));
  const sun = new THREE.DirectionalLight("#fffaf2", 2.1);
  sun.position.set((position.x + target.x) / 2, 6, (position.z + target.z) / 2);
  sun.target.position.copy(target);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.radius = 4;
  sun.shadow.bias = -0.0003;
  sun.shadow.normalBias = 0.015;
  const ext = Math.max(placed.width, placed.depth) / 2;
  Object.assign(sun.shadow.camera, { left: -ext, right: ext, top: ext, bottom: -ext, near: 0.5, far: 30 });
  scene.add(sun, sun.target);
  const fill = new THREE.DirectionalLight("#eef4ff", 0.45);
  fill.position.copy(position).add(new THREE.Vector3(0, 0.5, 0));
  fill.target.position.copy(target);
  scene.add(fill, fill.target);

  renderer.shadowMap.needsUpdate = true;
  renderer.render(scene, camera);
  const frameBoxes = productBoxes(layout.products, face, camera, SNAPSHOT_WIDTH, SNAPSHOT_HEIGHT);
  const fixture = fixtureBox(plan, face, camera, SNAPSHOT_WIDTH, SNAPSHOT_HEIGHT);
  const [cx1, cy1, cx2, cy2] = cropRegion([...Object.values(frameBoxes).flat(), ...(fixture ? [fixture] : [])], SNAPSHOT_WIDTH, SNAPSHOT_HEIGHT);
  const crop = document.createElement("canvas");
  crop.width = cx2 - cx1;
  crop.height = cy2 - cy1;
  crop.getContext("2d")!.drawImage(renderer.domElement, cx1, cy1, crop.width, crop.height, 0, 0, crop.width, crop.height);
  const image = crop.toDataURL("image/jpeg", 0.88);
  const boxes = Object.fromEntries(Object.entries(frameBoxes).map(([ref, list]) =>
    [ref, list.map(([x1, y1, x2, y2]) => [x1 - cx1, y1 - cy1, x2 - cx1, y2 - cy1] as Box)]));

  stopAssets();
  products.dispose();
  for (const g of built.geometries.values()) g.dispose();
  for (const g of built.upperGeometries.values()) g.dispose();
  disposeMaterials(materials);
  signTexture.dispose();
  return { image, width: crop.width, height: crop.height, boxes };
}

// Photographs the requested faces of `store` one by one. Throws when the browser has no WebGL.
export async function renderShelfFaces(
  store: Store,
  faces: FaceRequest[],
  currency: string,
  onShot: (face: FaceRequest, shot: ShelfShot, index: number) => Promise<void> | void,
  signal?: AbortSignal,
): Promise<void> {
  await document.fonts?.ready;
  const canvas = document.createElement("canvas");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  try {
    renderer.setPixelRatio(1);
    renderer.setSize(SNAPSHOT_WIDTH, SNAPSHOT_HEIGHT, false);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    // Khronos PBR Neutral keeps package colours true, as in Realistic mode.
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.toneMappingExposure = 0.98;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.shadowMap.autoUpdate = false;
    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = createStoreEnvironmentScene();
    const env = pmrem.fromScene(room, 0.025).texture;
    disposeScene(room);
    pmrem.dispose();
    try {
      const racks = new Map(store.racks.map((r) => [r.id, r]));
      for (const [i, request] of faces.entries()) {
        if (signal?.aborted) return;
        const rack = racks.get(request.rackId);
        if (!rack) continue;
        await onShot(request, await renderOne(renderer, env, store, rack, request.face, currency), i);
      }
    } finally {
      env.dispose();
    }
  } finally {
    renderer.dispose();
    renderer.forceContextLoss();
  }
}
