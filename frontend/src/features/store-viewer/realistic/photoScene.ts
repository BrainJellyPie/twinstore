// A static copy of the realistic store for the path tracer (Photo mode). The live scene uses things a
// path tracer cannot read — instanced packages that pick their label from an atlas in a vertex shader,
// a planar-reflection floor shader, unlit glass, a fake contact-shadow decal, hemisphere/ambient fill —
// so the copy bakes instances into plain geometry with their label UVs, swaps every material for its
// physically based equivalent, and lights the store the way a real one is lit: ceiling panels as
// area lights and daylight through the storefront glass.

import * as THREE from "three";
import { StaticGeometryGenerator } from "three-mesh-bvh";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { CEILING_HEIGHT } from "./constants";

export interface PhotoScene {
  scene: THREE.Scene;
  triangles: number;
  dispose: () => void;
}

const EMISSIVE_KEYS = new Set(["led", "ceilingLight", "screen", "exitSign"]);
const SKIP_KEYS = new Set(["ao"]);

function luminance(c: THREE.Color): number {
  return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;
}

function convertMaterial(m: THREE.Material, cache: Map<THREE.Material, THREE.Material | null>): THREE.Material | null {
  const hit = cache.get(m);
  if (hit !== undefined) return hit;
  let out: THREE.Material | null = null;
  if (!m.visible || SKIP_KEYS.has(m.name)) {
    out = null;
  } else if (m.name === "glass" || m.name === "lidGlass") {
    const src = m as THREE.MeshStandardMaterial;
    out = new THREE.MeshPhysicalMaterial({
      color: src.color, roughness: 0.03, metalness: 0, transmission: 1, ior: 1.5, thickness: 0.006, side: THREE.DoubleSide,
    });
  } else if ((m as THREE.MeshStandardMaterial).isMeshStandardMaterial) {
    // clone() drops onBeforeCompile (atlas cells, planar reflection): the path tracer reads plain PBR.
    const c = (m as THREE.MeshStandardMaterial).clone();
    c.envMap = null;
    if (m.name === "ceilingLight") c.emissiveIntensity = 2.5;
    out = c;
  } else if ((m as THREE.MeshLambertMaterial).isMeshLambertMaterial) {
    const src = m as THREE.MeshLambertMaterial;
    out = new THREE.MeshStandardMaterial({ color: src.color, map: src.map, roughness: 0.6, side: src.side });
  } else if ((m as THREE.MeshBasicMaterial).isMeshBasicMaterial) {
    const src = m as THREE.MeshBasicMaterial;
    if (src.transparent && src.opacity < 0.99) {
      out = null; // overlays: heatmaps, trails, decals
    } else if (luminance(src.color) > 1 || EMISSIVE_KEYS.has(m.name)) {
      out = new THREE.MeshStandardMaterial({ color: "#000000", emissive: src.color, emissiveIntensity: 1, emissiveMap: src.map });
    } else {
      out = new THREE.MeshStandardMaterial({ color: src.color, map: src.map, roughness: 0.9, side: src.side });
    }
  }
  if (out && out !== m) out.name = m.name;
  cache.set(m, out);
  return out;
}

const _inst = new THREE.Matrix4();
const _world = new THREE.Matrix4();
const _normal = new THREE.Matrix3();
const _v = new THREE.Vector3();

/** One geometry for all instances of an InstancedMesh, in world space, label UVs baked from `aCell`. */
function expandInstanced(mesh: THREE.InstancedMesh, cellScale: THREE.Vector2 | null): THREE.BufferGeometry {
  const src = mesh.geometry.index ? mesh.geometry.toNonIndexed() : mesh.geometry;
  const pos = src.getAttribute("position") as THREE.BufferAttribute;
  const nrm = src.getAttribute("normal") as THREE.BufferAttribute | undefined;
  const uv = src.getAttribute("uv") as THREE.BufferAttribute | undefined;
  const cell = mesh.geometry.getAttribute("aCell") as THREE.InstancedBufferAttribute | undefined;
  const n = pos.count;
  const count = mesh.count;
  const P = new Float32Array(n * count * 3);
  const N = new Float32Array(n * count * 3);
  const U = new Float32Array(n * count * 2);
  for (let i = 0; i < count; i++) {
    mesh.getMatrixAt(i, _inst);
    _world.multiplyMatrices(mesh.matrixWorld, _inst);
    _normal.getNormalMatrix(_world);
    const cu = cell ? cell.getX(i) : 0;
    const cv = cell ? cell.getY(i) : 0;
    for (let k = 0; k < n; k++) {
      const o = (i * n + k) * 3;
      _v.fromBufferAttribute(pos, k).applyMatrix4(_world);
      P[o] = _v.x; P[o + 1] = _v.y; P[o + 2] = _v.z;
      if (nrm) {
        _v.fromBufferAttribute(nrm, k).applyMatrix3(_normal).normalize();
        N[o] = _v.x; N[o + 1] = _v.y; N[o + 2] = _v.z;
      }
      if (uv) {
        const t = (i * n + k) * 2;
        U[t] = cellScale ? cu + uv.getX(k) * cellScale.x : uv.getX(k);
        U[t + 1] = cellScale ? cv + uv.getY(k) * cellScale.y : uv.getY(k);
      }
    }
  }
  if (src !== mesh.geometry) src.dispose();
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(P, 3));
  if (nrm) g.setAttribute("normal", new THREE.BufferAttribute(N, 3));
  else g.computeVertexNormals();
  g.setAttribute("uv", new THREE.BufferAttribute(U, 2));
  return g;
}

/** Plain geometry in world space with only the attributes the path tracer reads. */
function bakeMesh(mesh: THREE.Mesh): THREE.BufferGeometry {
  if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) {
    const gen = new StaticGeometryGenerator(mesh);
    gen.attributes = ["position", "normal", "uv"];
    gen.applyWorldTransforms = true;
    return gen.generate();
  }
  const g = new THREE.BufferGeometry();
  for (const name of ["position", "normal", "uv"]) {
    const a = mesh.geometry.getAttribute(name);
    // World-space baking must never transform the live scene's shared buffers.
    if (a) g.setAttribute(name, a.clone());
  }
  g.setIndex(mesh.geometry.index?.clone() ?? null);
  for (const group of mesh.geometry.groups) g.addGroup(group.start, group.count, group.materialIndex);
  g.applyMatrix4(mesh.matrixWorld);
  return g;
}

function daylight(): THREE.DataTexture {
  // Equirect sky: bright overcast above the horizon, warm pavement below.
  const w = 64;
  const h = 32;
  const data = new Float32Array(w * h * 4);
  const sky = new THREE.Color("#e3edf8");
  const horizon = new THREE.Color("#ffffff");
  const ground = new THREE.Color("#6f675c");
  const c = new THREE.Color();
  for (let y = 0; y < h; y++) {
    const t = 1 - y / (h - 1); // 1 = zenith
    if (t > 0.5) c.copy(horizon).lerp(sky, (t - 0.5) * 2).multiplyScalar(2.2);
    else c.copy(ground).lerp(horizon, Math.pow(t * 2, 3)).multiplyScalar(0.9);
    for (let x = 0; x < w; x++) {
      const o = (y * w + x) * 4;
      data[o] = c.r; data[o + 1] = c.g; data[o + 2] = c.b; data[o + 3] = 1;
    }
  }
  const tex = new THREE.DataTexture(data, w, h, THREE.RGBAFormat, THREE.FloatType);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  tex.magFilter = THREE.LinearFilter;
  tex.minFilter = THREE.LinearFilter;
  tex.needsUpdate = true;
  return tex;
}

/** Match buildStore's checkerboard panels in the centered store, facing down. */
function ceilingLights(width: number, depth: number, intensity: number): THREE.Group {
  const group = new THREE.Group();
  for (let x = 0; x < width; x++) {
    for (let z = 0; z < depth; z++) {
      if ((x + z) % 2 !== 0) continue;
      const light = new THREE.RectAreaLight("#fff7ee", intensity, 0.46, 0.46);
      light.position.set(x + 0.5 - width / 2, CEILING_HEIGHT - 0.02, z + 0.5 - depth / 2);
      light.rotation.x = -Math.PI / 2;
      group.add(light);
    }
  }
  return group;
}

export function buildPhotoScene(
  live: THREE.Scene,
  opts: { width: number; depth: number; background: THREE.Color | null; environment?: THREE.Texture | null },
): PhotoScene {
  live.updateMatrixWorld(true);
  const cache = new Map<THREE.Material, THREE.Material | null>();
  const owned: THREE.BufferGeometry[] = [];
  const buckets = new Map<THREE.Material, THREE.BufferGeometry[]>();
  const add = (mat: THREE.Material, g: THREE.BufferGeometry) => {
    const list = buckets.get(mat);
    if (list) list.push(g);
    else buckets.set(mat, [g]);
  };

  live.traverseVisible((o) => {
    const mesh = o as THREE.Mesh;
    if (!mesh.isMesh) return;
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const converted = mats.map((m) => convertMaterial(m, cache));
    if (converted.every((m) => m === null)) return;
    if ((mesh as THREE.InstancedMesh).isInstancedMesh) {
      const src = mats[0]!;
      const mat = converted[0];
      if (!mat || (mesh as THREE.InstancedMesh).count === 0) return;
      const scale = (src.userData.atlasCellScale as THREE.Vector2 | undefined) ?? null;
      add(mat, expandInstanced(mesh as THREE.InstancedMesh, scale));
      return;
    }
    const g = bakeMesh(mesh);
    if (mats.length === 1 || g.groups.length === 0) {
      const mat = converted[0];
      if (mat) {
        const flat = g.index ? g.toNonIndexed() : g;
        if (flat !== g) g.dispose();
        add(mat, flat);
      } else g.dispose();
      return;
    }
    // Multi-material: one geometry per group.
    const flat = g.index ? g.toNonIndexed() : g;
    for (const group of g.groups) {
      const mat = converted[group.materialIndex ?? 0];
      if (!mat) continue;
      const part = new THREE.BufferGeometry();
      for (const name of ["position", "normal", "uv"]) {
        const a = flat.getAttribute(name) as THREE.BufferAttribute | undefined;
        if (!a) continue;
        part.setAttribute(name, new THREE.BufferAttribute(a.array.slice(group.start * a.itemSize, (group.start + group.count) * a.itemSize), a.itemSize));
      }
      add(mat, part);
    }
    if (flat !== g) flat.dispose();
    g.dispose();
  });

  const scene = new THREE.Scene();
  let triangles = 0;
  for (const [mat, geoms] of buckets) {
    const ok = geoms.filter((g) => g.getAttribute("position"));
    // Every geometry gets the same attribute set so they merge.
    for (const g of ok) {
      if (!g.getAttribute("normal")) g.computeVertexNormals();
      if (!g.getAttribute("uv")) g.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(g.getAttribute("position").count * 2), 2));
      for (const name of Object.keys(g.attributes)) if (!["position", "normal", "uv"].includes(name)) g.deleteAttribute(name);
    }
    const merged = ok.length === 1 ? ok[0]! : mergeGeometries(ok, false);
    if (!merged) continue;
    owned.push(merged, ...ok);
    triangles += merged.getAttribute("position").count / 3;
    scene.add(new THREE.Mesh(merged, mat));
  }

  // The panels are 0.46 m squares on every other tile, so each needs a high luminance to light the floor.
  scene.add(ceilingLights(opts.width, opts.depth, 60));
  // The photographic interior HDR when it loaded (equirect, as the path tracer needs), else a sky.
  const env = opts.environment ?? daylight();
  scene.environment = env;
  // The interior HDR is warm; kept low it adds bounce and reflections without tinting the store.
  scene.environmentIntensity = opts.environment ? 0.55 : 1;
  scene.background = opts.background;

  return {
    scene,
    triangles: Math.round(triangles),
    dispose: () => {
      for (const g of new Set(owned)) g.dispose();
      for (const m of new Set(cache.values())) m?.dispose();
      env.dispose();
    },
  };
}
