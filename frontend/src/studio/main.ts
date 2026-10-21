// Shelf studio: one gondola bay rendered up close with Realistic mode's packages, labels and price
// tags, lit like a store aisle and finished like a phone photo. It exposes the exact box of every
// front facing (window.studioResult, shaped like the backend's CaptureResult), so the render can be
// fed to Shelf Lab as a "photo" with perfect ground truth.
//
//   http://localhost:5173/studio.html?preset=drinks&w=1600&h=1200&ss=1.5&seed=3
//   http://localhost:5173/studio.html?solo=Volt%20Lime%20Cola%2020oz&w=360&h=960   (one package, transparent)
//
// Dev-only (studio.html is not an entry of the production build).

import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { RectAreaLightUniformsLib } from "three/examples/jsm/lights/RectAreaLightUniformsLib.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { GTAOPass } from "three/examples/jsm/postprocessing/GTAOPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";

import { classifyProduct } from "@/features/store-viewer/realistic/productCatalog";
import type { ProductInstance, TagInstance, TalkerInstance } from "@/features/store-viewer/realistic/productLayout";
import { buildProductMeshes } from "@/features/store-viewer/realistic/productMeshes";

import { PRESETS, type Run } from "./presets";

interface Box { x1: number; y1: number; x2: number; y2: number }
interface StudioItem {
  id: string; band: number; level: number; order: number; facings: number; boxes: Box[];
  sku: string; name: string; price: number; labeled: boolean; confidence: number;
}
interface StudioResult {
  image_size: [number, number];
  detector: string;
  currency: string;
  rack_type: "shelf";
  bands: { index: number; level: number; top: number; bottom: number }[];
  items: StudioItem[];
  gaps: { band: number; level: number; box: Box; facings: number }[];
  notes: string[];
}

declare global {
  interface Window { studioResult?: StudioResult; studioReady?: boolean }
}

const q = new URLSearchParams(location.search);
const W_OUT = Number(q.get("w") ?? 1600);
const H_OUT = Number(q.get("h") ?? 1200);
const SS = Number(q.get("ss") ?? 1.5);
const SEED = Number(q.get("seed") ?? 3);
const preset = PRESETS[q.get("preset") ?? "drinks"] ?? PRESETS.drinks!;

// Bay geometry (metres): shelf tops from the bottom up, front of the shelves at z = DEPTH / 2.
const BAY_W = 1.24;
const DEPTH = 0.42;
const SHELF_Y = [0.1, 0.47, 0.84, 1.21, 1.58];
const BAY_H = 1.96;
const FRONT = DEPTH / 2;

function rng(seed: number): () => number {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >>> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}
const rand = rng(SEED);
const jitter = (a: number) => (rand() * 2 - 1) * a;

function canvas(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  if (!ctx) throw new Error("2D canvas unavailable");
  return [c, ctx];
}

function texture(c: HTMLCanvasElement, repeat: [number, number] = [1, 1], srgb = true): THREE.CanvasTexture {
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat[0], repeat[1]);
  t.anisotropy = 8;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// Pegboard back panel: off-white metal with punched holes and faint streaks.
function pegboard(): THREE.CanvasTexture {
  const [c, ctx] = canvas(512, 512);
  ctx.fillStyle = "#d9dbdc";
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 2600; i++) {
    ctx.fillStyle = `rgba(${rand() < 0.5 ? "255,255,255" : "0,0,0"},${0.015 + rand() * 0.02})`;
    ctx.fillRect(rand() * 512, rand() * 512, 1 + rand() * 30, 1);
  }
  for (let y = 16; y < 512; y += 32) {
    for (let x = 16; x < 512; x += 32) {
      ctx.fillStyle = "rgba(40,42,46,0.75)";
      ctx.beginPath();
      ctx.arc(x, y, 3.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,0.35)";
      ctx.beginPath();
      ctx.arc(x + 0.8, y + 1.2, 3.2, 0, Math.PI);
      ctx.fill();
    }
  }
  return texture(c, [3, 4]);
}

// Vinyl floor tiles with grout and wear.
function floorTiles(): THREE.CanvasTexture {
  const [c, ctx] = canvas(512, 512);
  for (let ty = 0; ty < 2; ty++) {
    for (let tx = 0; tx < 2; tx++) {
      const v = 214 + Math.floor(rand() * 14);
      ctx.fillStyle = `rgb(${v},${v - 2},${v - 6})`;
      ctx.fillRect(tx * 256, ty * 256, 256, 256);
    }
  }
  for (let i = 0; i < 5000; i++) {
    ctx.fillStyle = `rgba(0,0,0,${rand() * 0.035})`;
    ctx.fillRect(rand() * 512, rand() * 512, 2, 2);
  }
  ctx.strokeStyle = "rgba(120,118,112,0.55)";
  ctx.lineWidth = 3;
  for (const p of [0, 256, 512]) {
    ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, 512); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(512, p); ctx.stroke();
  }
  return texture(c, [6, 6]);
}

function header(text: string): THREE.CanvasTexture {
  const [c, ctx] = canvas(1024, 128);
  const g = ctx.createLinearGradient(0, 0, 0, 128);
  g.addColorStop(0, "#1f6f5c");
  g.addColorStop(1, "#18584a");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 1024, 128);
  ctx.fillStyle = "#ffffff";
  ctx.font = '800 64px "Geist Variable", "Helvetica Neue", Arial, sans-serif';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 512, 68);
  return texture(c);
}

interface Placed {
  products: ProductInstance[];
  tags: TagInstance[];
  talkers: TalkerInstance[];
  // front facings of the centre bay, for the exported boxes
  runs: { level: number; run: Run; order: number; facings: { x: number; y: number; z: number; w: number; h: number; d: number }[] }[];
  gaps: { level: number; x0: number; x1: number; y: number }[];
}

function fillBay(offsetX: number, levels: Run[][], record: boolean, placed: Placed): void {
  levels.forEach((runs, li) => {
    const shelfTop = SHELF_Y[li]!;
    let cursor = offsetX - BAY_W / 2 + 0.012;
    const end = offsetX + BAY_W / 2 - 0.012;
    let order = 0;
    runs.forEach((run, ri) => {
      if (run.gap) {
        const gw = run.gap * 0.075;
        if (record) placed.gaps.push({ level: li, x0: cursor, x1: Math.min(end, cursor + gw), y: shelfTop });
        cursor += gw;
        return;
      }
      const spec = classifyProduct(run.name);
      const fw = spec.w + 0.006;
      const rows = Math.max(1, Math.min(5, Math.floor((DEPTH - 0.03) / (spec.d + 0.005))));
      const isLast = ri === runs.length - 1;
      let facings = run.facings;
      if (isLast) facings = Math.max(facings, Math.floor((end - cursor) / fw));
      const facingBoxes: Placed["runs"][number]["facings"] = [];
      const runStart = cursor;
      for (let f = 0; f < facings && cursor + fw <= end + 0.002; f++) {
        const x = cursor + fw / 2;
        for (let r = 0; r < rows; r++) {
          // Shoppers take from the front: some front facings stand a little back.
          const recess = r === 0 && rand() < 0.22 ? 0.02 + rand() * 0.05 : 0;
          const z = FRONT - 0.012 - spec.d / 2 - r * (spec.d + 0.005) - recess;
          placed.products.push({
            name: run.name, kind: spec.kind, x: x + jitter(0.003), y: shelfTop, z, yaw: jitter(0.06), flat: false,
            sx: spec.w, sy: spec.h, sz: spec.d,
          });

        }
        if (record) {
          // the visible column: the front package and the copies stacked behind it
          const zFront = FRONT - 0.012;
          const zBack = FRONT - 0.012 - rows * (spec.d + 0.005);
          facingBoxes.push({ x, y: shelfTop, z: (zFront + zBack) / 2, w: spec.w + 0.004, h: spec.h, d: zFront - zBack });
        }
        cursor += fw;
      }
      placed.tags.push({ price: Math.round(run.price * 100), promo: run.promo ?? "", x: runStart + 0.05, y: shelfTop - 0.021, z: FRONT + 0.011, yaw: 0, tilt: 0 });
      if (run.promo) placed.talkers.push({ promo: run.promo, x: (runStart + cursor) / 2, y: shelfTop - 0.045, z: FRONT + 0.012, yaw: 0 });
      if (record && facingBoxes.length) placed.runs.push({ level: li, run, order: order++, facings: facingBoxes });
    });
  });
}

function buildFixture(scene: THREE.Scene, offsetX: number, mats: Record<string, THREE.Material>): void {
  const add = (geom: THREE.BufferGeometry, mat: THREE.Material, x: number, y: number, z: number) => {
    const m = new THREE.Mesh(geom, mat);
    m.position.set(offsetX + x, y, z);
    m.castShadow = true;
    m.receiveShadow = true;
    scene.add(m);
    return m;
  };
  add(new THREE.PlaneGeometry(BAY_W + 0.06, BAY_H - 0.08), mats.back!, 0, (BAY_H + 0.08) / 2, -DEPTH / 2);
  // slotted uprights at the back; the shelves cantilever forward from them
  for (const side of [-1, 1]) add(new THREE.BoxGeometry(0.03, BAY_H, 0.05), mats.upright!, side * (BAY_W / 2 + 0.015), BAY_H / 2, -DEPTH / 2 + 0.025);
  for (const y of SHELF_Y.slice(1)) {
    add(new THREE.BoxGeometry(BAY_W, 0.016, DEPTH), mats.shelf!, 0, y - 0.008, 0);
  }
  for (const y of SHELF_Y) {
    // ticket channel along the front edge: the price tags clip into it
    add(new THREE.BoxGeometry(BAY_W, 0.042, 0.014), mats.strip!, 0, y - 0.021, FRONT + 0.004);
  }
  add(new THREE.BoxGeometry(BAY_W, 0.1, 0.02), mats.kick!, 0, 0.05, FRONT - 0.005);
  add(new THREE.BoxGeometry(BAY_W + 0.06, 0.13, 0.05), mats.header!, 0, BAY_H + 0.06, FRONT - 0.02);
}

function project(v: THREE.Vector3, camera: THREE.Camera): [number, number] {
  const p = v.clone().project(camera);
  return [((p.x + 1) / 2) * W_OUT, ((1 - p.y) / 2) * H_OUT];
}

function screenBox(cx: number, y: number, z: number, w: number, h: number, d: number, camera: THREE.Camera): Box {
  const xs: number[] = [];
  const ys: number[] = [];
  for (const dx of [-w / 2, w / 2]) {
    for (const dy of [0, h]) {
      for (const dz of [d / 2, -d / 2]) {
        const [px, py] = project(new THREE.Vector3(cx + dx, y + dy, z + dz), camera);
        xs.push(px);
        ys.push(py);
      }
    }
  }
  return { x1: Math.min(...xs), y1: Math.min(...ys), x2: Math.max(...xs), y2: Math.max(...ys) };
}

// Phone-photo finish on the 2D canvas: warm white balance, vignette, slight chromatic fringe, grain.
function finish(ctx: CanvasRenderingContext2D): void {
  ctx.fillStyle = "rgba(255,236,214,0.05)";
  ctx.globalCompositeOperation = "multiply";
  ctx.fillRect(0, 0, W_OUT, H_OUT);
  ctx.globalCompositeOperation = "source-over";
  const v = ctx.createRadialGradient(W_OUT / 2, H_OUT / 2, H_OUT * 0.35, W_OUT / 2, H_OUT / 2, H_OUT * 0.95);
  v.addColorStop(0, "rgba(0,0,0,0)");
  v.addColorStop(1, "rgba(0,0,0,0.30)");
  ctx.fillStyle = v;
  ctx.fillRect(0, 0, W_OUT, H_OUT);
  const img = ctx.getImageData(0, 0, W_OUT, H_OUT);
  const src = new Uint8ClampedArray(img.data);
  const px = img.data;
  const cx = W_OUT / 2;
  for (let y = 0; y < H_OUT; y++) {
    for (let x = 0; x < W_OUT; x++) {
      const i = (y * W_OUT + x) * 4;
      const shift = Math.round(((x - cx) / cx) * 1.2);
      const xr = Math.min(W_OUT - 1, Math.max(0, x + shift));
      const xb = Math.min(W_OUT - 1, Math.max(0, x - shift));
      const n = (rand() - 0.5) * 9;
      px[i] = src[(y * W_OUT + xr) * 4]! + n;
      px[i + 1] = src[i + 1]! + n;
      px[i + 2] = src[(y * W_OUT + xb) * 4 + 2]! + n;
    }
  }
  ctx.putImageData(img, 0, 0);
}

// One package, front view, on a transparent background: a "new product" image for Shelf Lab's
// replace edit that matches the shelf's look.
function renderSolo(name: string): void {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(W_OUT, H_OUT, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.setClearColor(0x000000, 0);
  const scene = new THREE.Scene();
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.6;
  const spec = classifyProduct(name);
  const meshes = buildProductMeshes({
    products: [{ name, kind: spec.kind, x: 0, y: 0, z: 0, yaw: 0, flat: false, sx: spec.w, sy: spec.h, sz: spec.d }],
    tags: [], talkers: [],
  }, "USD", 512, false, 8, false);
  meshes.setDetail(true);
  scene.add(meshes.group);
  const key = new THREE.DirectionalLight("#fffaf2", 1.6);
  key.position.set(0.5, 2, 2);
  scene.add(key, new THREE.HemisphereLight("#f4f7ff", "#a39a8c", 0.5));
  const camera = new THREE.PerspectiveCamera(12, W_OUT / H_OUT, 0.05, 30);
  const dist = (spec.h * 0.56) / Math.tan(THREE.MathUtils.degToRad(6));
  camera.position.set(0, spec.h / 2, dist);
  camera.lookAt(0, spec.h / 2, 0);
  renderer.render(scene, camera);
  renderer.domElement.style.background = "transparent";
  document.body.appendChild(renderer.domElement);
  window.studioReady = true;
}

async function main(): Promise<void> {
  await document.fonts.load('700 32px "Geist Variable"').catch(() => undefined);
  const solo = q.get("solo");
  if (solo) {
    renderSolo(solo);
    return;
  }
  RectAreaLightUniformsLib.init();
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(Math.round(W_OUT * SS), Math.round(H_OUT * SS), false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.02;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#d8d6d1");
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.55;

  const metal = (color: string, rough: number) => new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: 0.55 });
  const mats: Record<string, THREE.Material> = {
    back: new THREE.MeshStandardMaterial({ map: pegboard(), roughness: 0.75, metalness: 0.15 }),
    upright: metal("#9aa0a6", 0.45),
    shelf: metal("#c9ccce", 0.38),
    strip: new THREE.MeshStandardMaterial({ color: "#eeeeea", roughness: 0.4 }),
    kick: metal("#5d6166", 0.5),
    header: new THREE.MeshStandardMaterial({ map: header(preset.header), roughness: 0.5 }),
  };
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.MeshStandardMaterial({ map: floorTiles(), roughness: 0.32, metalness: 0 }));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  const placed: Placed = { products: [], tags: [], talkers: [], runs: [], gaps: [] };
  const step = BAY_W + 0.03;
  for (const [i, off] of [-step, 0, step].entries()) {
    buildFixture(scene, off, mats);
    fillBay(off, i === 1 ? preset.levels : preset.neighbours[i === 0 ? 0 : 1]!, i === 1, placed);
  }
  const meshes = buildProductMeshes({ products: placed.products, tags: placed.tags, talkers: placed.talkers }, "USD", 512, true, 8, false);
  meshes.setDetail(true);
  scene.add(meshes.group);

  // Ceiling fixture in front of the bay, a sun-like key for contact shadows, a little sky fill.
  const area = new THREE.RectAreaLight("#fff3e2", 5.5, 3.2, 0.5);
  area.position.set(0, 2.75, 1.5);
  area.lookAt(0, 0.95, 0);
  scene.add(area);
  const key = new THREE.DirectionalLight("#fffaf2", 1.7);
  key.position.set(0.7, 3.4, 2.4);
  key.target.position.set(0, 0.9, 0);
  key.castShadow = true;
  key.shadow.mapSize.set(4096, 4096);
  key.shadow.camera.left = -2.2;
  key.shadow.camera.right = 2.2;
  key.shadow.camera.top = 2.4;
  key.shadow.camera.bottom = -0.4;
  key.shadow.radius = 5;
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.015;
  scene.add(key, key.target);
  scene.add(new THREE.HemisphereLight("#f4f7ff", "#a39a8c", 0.22));

  const camera = new THREE.PerspectiveCamera(50, W_OUT / H_OUT, 0.05, 30);
  camera.position.set(0.08 + jitter(0.03), 1.26 + jitter(0.02), 2.4);
  camera.lookAt(0.0, 1.1, 0);
  camera.rotateZ(jitter(0.006));
  camera.updateMatrixWorld();

  const target = new THREE.WebGLRenderTarget(Math.round(W_OUT * SS), Math.round(H_OUT * SS), { samples: 4, type: THREE.HalfFloatType });
  const composer = new EffectComposer(renderer, target);
  composer.addPass(new RenderPass(scene, camera));
  const gtao = new GTAOPass(scene, camera, Math.round(W_OUT * SS), Math.round(H_OUT * SS));
  gtao.updateGtaoMaterial({ radius: 0.12, distanceExponent: 1.4, thickness: 1.2, scale: 1.1, samples: 16 });
  gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 16 });
  gtao.blendIntensity = 1.0;
  composer.addPass(gtao);
  composer.addPass(new OutputPass());
  composer.render();

  const [out, ctx] = canvas(W_OUT, H_OUT);
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(renderer.domElement, 0, 0, W_OUT, H_OUT);
  finish(ctx);
  document.body.appendChild(out);

  // Exact boxes of the centre bay, in output pixels.
  const levels = SHELF_Y.length;
  const band = (li: number) => levels - 1 - li;
  const items: StudioItem[] = placed.runs.map((r, i) => ({
    id: `i${String(i + 1).padStart(2, "0")}`,
    band: band(r.level),
    level: r.level + 1,
    order: r.order,
    facings: r.facings.length,
    boxes: r.facings.map((f) => screenBox(f.x, f.y, f.z, f.w, f.h, f.d, camera)),
    sku: r.run.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
    name: r.run.name,
    price: Math.round(r.run.price * 100),
    labeled: true,
    confidence: 10,
  }));
  const bands = SHELF_Y.map((y, li) => {
    const top = Math.min(...items.filter((it) => it.level === li + 1).flatMap((it) => it.boxes.map((b) => b.y1)), project(new THREE.Vector3(0, y + 0.3, FRONT), camera)[1]);
    return { index: band(li), level: li + 1, top, bottom: project(new THREE.Vector3(0, y, FRONT), camera)[1] };
  }).sort((a, b) => a.index - b.index);
  const gaps = placed.gaps.map((g) => {
    const a = project(new THREE.Vector3(g.x0, g.y, FRONT), camera);
    const b = project(new THREE.Vector3(g.x1, g.y + 0.24, FRONT), camera);
    return { band: band(g.level), level: g.level + 1, box: { x1: a[0], y1: b[1], x2: b[0], y2: a[1] }, facings: (g.x1 - g.x0) / 0.075 };
  });
  window.studioResult = {
    image_size: [W_OUT, H_OUT], detector: "studio", currency: "USD", rack_type: "shelf", bands, items, gaps,
    notes: [`shelf studio render · preset ${q.get("preset") ?? "drinks"} · seed ${SEED}`],
  };
  window.studioReady = true;
}

void main();
