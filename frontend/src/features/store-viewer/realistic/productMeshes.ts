// Builds the instanced meshes for packages, price tags and shelf talkers from a
// ProductLayout. Imperative three.js so a single InstancedMesh per package kind
// covers every product in the store.

import * as THREE from "three";
import { cellUv } from "./atlasLayout";
import { createAtlasMaterial, canvasTexture } from "./atlasMaterial";
import { createLabelAtlas, createTagAtlas, createTalkerAtlas, tagKey, type Atlas } from "./canvasArt";
import { createCanParts, createPackageGeometry, PACKAGE_KINDS } from "./productGeometries";
import type { PackageKind } from "./productCatalog";
import type { ProductLayout } from "./productLayout";
import { attachProductPhotos, productLabelKey } from "./productPhotos";
import { loadScannedProducts, type ScannedProductTarget } from "./scannedProducts";
import { produceVariation } from "./produceVariation";

const KIND_SURFACE: Record<PackageKind, { roughness: number; metalness: number }> = {
  bottle: { roughness: 0.18, metalness: 0 },
  perfumeBottle: { roughness: 0.12, metalness: 0.08 },
  teaCup: { roughness: 0.3, metalness: 0 },
  can: { roughness: 0.38, metalness: 0 },
  cup: { roughness: 0.55, metalness: 0 },
  pint: { roughness: 0.5, metalness: 0 },
  jar: { roughness: 0.22, metalness: 0 },
  tube: { roughness: 0.35, metalness: 0.25 },
  box: { roughness: 0.62, metalness: 0 },
  bag: { roughness: 0.32, metalness: 0.15 },
  wateringCan: { roughness: 0.65, metalness: 0.7 },
  croissant: { roughness: 0.68, metalness: 0 },
  burgerBun: { roughness: 0.8, metalness: 0 },
  pot: { roughness: 0.85, metalness: 0 },
  banana: { roughness: 0.55, metalness: 0 },
  avocado: { roughness: 0.74, metalness: 0 },
  lemon: { roughness: 0.65, metalness: 0 },
  onion: { roughness: 0.72, metalness: 0 },
  kiwi: { roughness: 0.85, metalness: 0 },
  sweetPotato: { roughness: 0.8, metalness: 0 },
  asianPear: { roughness: 0.65, metalness: 0 },
  ginger: { roughness: 0.85, metalness: 0 },
  apple: { roughness: 0.38, metalness: 0 },
  applePair: { roughness: 0.38, metalness: 0 },
};

const SCANNED_PRODUCTS: Partial<Record<PackageKind, { url: string; name: string }>> = {
  wateringCan: { url: "/assets/products/watering-can.glb", name: "watering-can" },
  croissant: { url: "/assets/products/croissant.glb", name: "croissant" },
  burgerBun: { url: "/assets/products/burger-bun.glb", name: "burger-bun" },
  pot: { url: "/assets/products/terracotta-pot.glb", name: "pot" },
  banana: { url: "/assets/produce/bananas.glb", name: "bananas" },
  avocado: { url: "/assets/produce/avocado.glb", name: "avocado" },
  lemon: { url: "/assets/produce/lemon.glb", name: "lemon" },
  onion: { url: "/assets/produce/onion.glb", name: "onion" },
  kiwi: { url: "/assets/produce/kiwi.glb", name: "kiwi" },
  sweetPotato: { url: "/assets/produce/sweet-potato.glb", name: "sweet-potato" },
  asianPear: { url: "/assets/produce/asian-pear.glb", name: "asian-pear" },
  ginger: { url: "/assets/produce/ginger.glb", name: "ginger" },
  apple: { url: "/assets/produce/apples.glb", name: "apple" },
  applePair: { url: "/assets/produce/apples.glb", name: "apple-pair" },
};

export interface ProductLod {
  mesh: THREE.InstancedMesh;
  coarse: THREE.BufferGeometry;
  fine: THREE.BufferGeometry;
}

export interface ProductMeshes {
  group: THREE.Group;
  atlases: Atlas[];
  textures: THREE.CanvasTexture[];
  // Swap package meshes between the coarse (overview) and fine (close-up) LOD.
  setDetail: (fine: boolean) => void;
  loadAssets: (onReady?: () => void) => () => void;
  dispose: () => void;
}

const noRaycast = () => undefined;

const _m = new THREE.Matrix4();
const _t = new THREE.Matrix4();
const _q = new THREE.Quaternion();
const _p = new THREE.Vector3();
const _s = new THREE.Vector3();
const _e = new THREE.Euler();
const _color = new THREE.Color();

function instanced(geom: THREE.BufferGeometry, mat: THREE.Material, count: number): THREE.InstancedMesh {
  const mesh = new THREE.InstancedMesh(geom, mat, count);
  mesh.raycast = noRaycast;
  mesh.frustumCulled = false;
  geom.setAttribute("aCell", new THREE.InstancedBufferAttribute(new Float32Array(count * 2), 2));
  return mesh;
}

export function buildProductMeshes(
  layout: ProductLayout,
  currency: string,
  cellPx: number,
  castShadow: boolean,
  anisotropy: number,
  cheap: boolean,
): ProductMeshes {
  const group = new THREE.Group();
  group.name = "realistic-products";
  const disposables: { dispose: () => void }[] = [];

  // --- Packages
  const labelAtlas = createLabelAtlas(layout.products.map((p) => ({ key: productLabelKey(p), name: p.name })), cellPx);
  const labelTex = canvasTexture(labelAtlas.canvas, { anisotropy });
  const photos = attachProductPhotos(labelAtlas, layout.products, () => { labelTex.needsUpdate = true; });
  disposables.push(labelTex);
  const scale = cellUv(labelAtlas.grid, 0).scale;
  const byKind = new Map<PackageKind, typeof layout.products>();
  for (const p of layout.products) {
    const list = byKind.get(p.kind);
    if (list) list.push(p);
    else byKind.set(p.kind, [p]);
  }
  const lods: ProductLod[] = [];
  const scans = new Map<string, ScannedProductTarget[]>();
  for (const kind of PACKAGE_KINDS) {
    const list = byKind.get(kind);
    if (!list?.length) continue;
    const canParts = kind === "can" && !cheap ? [createCanParts(0), createCanParts(1)] as const : null;
    const geom = canParts?.[0].body ?? createPackageGeometry(kind, 0);
    const fine = canParts?.[1].body ?? createPackageGeometry(kind, 1);
    const mat = createAtlasMaterial(labelTex, scale, { ...KIND_SURFACE[kind], cheap, selfLight: cheap ? 0.22 : 0.1 });
    const mesh = instanced(geom, mat, list.length);
    fine.setAttribute("aCell", geom.getAttribute("aCell"));
    const lod = { mesh, coarse: geom, fine };
    lods.push(lod);
    const scan = SCANNED_PRODUCTS[kind];
    if (scan) {
      const targets = scans.get(scan.url) ?? [];
      targets.push({ lod, name: scan.name, roughness: KIND_SURFACE[kind].roughness });
      scans.set(scan.url, targets);
    }
    disposables.push(fine);
    mesh.name = `pkg-${kind}`;
    mesh.castShadow = castShadow;
    mesh.receiveShadow = true;
    const cells = geom.getAttribute("aCell") as THREE.InstancedBufferAttribute;
    list.forEach((p, i) => {
      const variation = produceVariation(kind, `${kind}|${p.x}|${p.y}|${p.z}`);
      _p.set(p.x, p.y, p.z);
      _q.setFromAxisAngle(THREE.Object3D.DEFAULT_UP, p.yaw + (variation?.yaw ?? 0));
      _m.compose(_p, _q, _s.set(1, 1, 1));
      if (p.flat) {
        // Lay face-up: front (+Z) → +Y, centred on the footprint.
        _t.makeTranslation(0, p.sz / 2, p.sy / 2);
        _m.multiply(_t);
        _t.makeRotationX(-Math.PI / 2);
        _m.multiply(_t);
      }
      const size = variation?.scale ?? 1;
      _t.makeScale(p.sx * size, p.sy * size, p.sz * size);
      _m.multiply(_t);
      mesh.setMatrixAt(i, _m);
      if (variation) mesh.setColorAt(i, _color.setScalar(variation.brightness));
      const uv = cellUv(labelAtlas.grid, labelAtlas.index.get(productLabelKey(p)) ?? 0);
      cells.setXY(i, uv.offset[0], uv.offset[1]);
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    cells.needsUpdate = true;
    group.add(mesh);
    disposables.push(mesh, geom, mat);
    if (canParts) {
      // A single additional instanced batch covers the bare ends/rims of every
      // can. It shares the label atlas, with independent transforms and buffers.
      const metalMat = createAtlasMaterial(labelTex, scale, { roughness: 0.22, metalness: 1, selfLight: 0 });
      const coarseMetal = canParts[0].metal, fineMetal = canParts[1].metal;
      const metal = instanced(coarseMetal, metalMat, list.length);
      const metalCells = coarseMetal.getAttribute("aCell") as THREE.InstancedBufferAttribute;
      metalCells.array.set(cells.array);
      metalCells.needsUpdate = true;
      fineMetal.setAttribute("aCell", metalCells);
      metal.instanceMatrix.array.set(mesh.instanceMatrix.array);
      metal.instanceMatrix.needsUpdate = true;
      metal.name = "pkg-can-metal";
      metal.castShadow = castShadow;
      metal.receiveShadow = true;
      group.add(metal);
      lods.push({ mesh: metal, coarse: coarseMetal, fine: fineMetal });
      disposables.push(metal, coarseMetal, fineMetal, metalMat);
    }
  }

  // --- Price tags
  const tagAtlas = createTagAtlas(layout.tags, currency);
  const tagTex = canvasTexture(tagAtlas.canvas, { anisotropy });
  disposables.push(tagTex);
  if (layout.tags.length) {
    const geom = new THREE.PlaneGeometry(0.085, 0.04);
    const mat = createAtlasMaterial(tagTex, cellUv(tagAtlas.grid, 0).scale, { roughness: 0.55, selfLight: 0.35, cheap });
    const mesh = instanced(geom, mat, layout.tags.length);
    mesh.name = "price-tags";
    const cells = geom.getAttribute("aCell") as THREE.InstancedBufferAttribute;
    layout.tags.forEach((t, i) => {
      _e.set(-t.tilt, t.yaw, 0, "YXZ");
      _q.setFromEuler(_e);
      _m.compose(_p.set(t.x, t.y, t.z), _q, _s.set(1, 1, 1));
      mesh.setMatrixAt(i, _m);
      const uv = cellUv(tagAtlas.grid, tagAtlas.index.get(tagKey(t.price, t.promo)) ?? 0);
      cells.setXY(i, uv.offset[0], uv.offset[1]);
    });
    mesh.instanceMatrix.needsUpdate = true;
    group.add(mesh);
    disposables.push(mesh, geom, mat);
  }

  // --- Shelf talkers (promo cards sticking out into the aisle)
  const talkerAtlas = createTalkerAtlas(layout.talkers.map((t) => t.promo));
  const talkerTex = canvasTexture(talkerAtlas.canvas);
  disposables.push(talkerTex);
  if (layout.talkers.length) {
    const geom = new THREE.PlaneGeometry(0.075, 0.1);
    geom.translate(0, 0.05, 0);
    const mat = createAtlasMaterial(talkerTex, cellUv(talkerAtlas.grid, 0).scale, {
      roughness: 0.5,
      side: THREE.DoubleSide,
      selfLight: 0.25,
      cheap,
    });
    const mesh = instanced(geom, mat, layout.talkers.length);
    mesh.name = "shelf-talkers";
    mesh.castShadow = castShadow;
    const cells = geom.getAttribute("aCell") as THREE.InstancedBufferAttribute;
    layout.talkers.forEach((t, i) => {
      _q.setFromAxisAngle(THREE.Object3D.DEFAULT_UP, t.yaw + Math.PI / 2);
      _m.compose(_p.set(t.x, t.y, t.z), _q, _s.set(1, 1, 1));
      mesh.setMatrixAt(i, _m);
      const uv = cellUv(talkerAtlas.grid, talkerAtlas.index.get(t.promo) ?? 0);
      cells.setXY(i, uv.offset[0], uv.offset[1]);
    });
    mesh.instanceMatrix.needsUpdate = true;
    group.add(mesh);
    disposables.push(mesh, geom, mat);
  }

  let cancelAssets = () => {};
  return {
    group,
    atlases: [labelAtlas, tagAtlas, talkerAtlas],
    textures: [labelTex, tagTex, talkerTex],
    setDetail: (fine) => {
      for (const l of lods) l.mesh.geometry = fine ? l.fine : l.coarse;
    },
    loadAssets: (onReady) => {
      cancelAssets();
      const stopPhotos = photos.load();
      const stopScans = [...scans].map(([url, targets]) => loadScannedProducts(url, targets, cheap, onReady));
      cancelAssets = () => { stopPhotos(); stopScans.forEach((stop) => stop()); };
      return cancelAssets;
    },
    dispose: () => {
      cancelAssets();
      photos.dispose();
      for (const d of disposables) d.dispose();
    },
  };
}
