// Unit package geometries (1×1×1 bounding box, base at y = 0, front = +Z) whose
// UVs address one cell of the label atlas: the printed label maps onto the label
// area, everything else samples the flat body/accent colour zones.

import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { LABEL_U0, ZONE_ACCENT, ZONE_BODY } from "./atlasLayout";
import type { PackageKind } from "./productCatalog";

const LABEL_U1 = 0.985;
const LABEL_V0 = 0.012;
const LABEL_V1 = 0.988;

function labelUv(u: number, v: number): [number, number] {
  return [LABEL_U0 + (LABEL_U1 - LABEL_U0) * u, LABEL_V0 + (LABEL_V1 - LABEL_V0) * v];
}

type Zone = "body" | "accent" | "label" | "lid";

interface ProfilePoint {
  r: number;
  y: number;
  zone: Zone;
  // Label v coordinate (only for zone "label").
  lv?: number;
}

// Surface of revolution around Y with per-ring UV zones. Rings at zone boundaries
// are duplicated by the caller so colours don't bleed across triangles.
function revolve(profile: ProfilePoint[], segments: number): THREE.BufferGeometry {
  const positions: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  const cols = segments + 1;
  for (const p of profile) {
    for (let j = 0; j <= segments; j++) {
      const s = j / segments;
      const theta = (s - 0.5) * Math.PI * 2;
      const x = p.r * Math.sin(theta);
      const z = p.r * Math.cos(theta);
      positions.push(x, p.y, z);
      let uv: [number, number];
      switch (p.zone) {
        case "label":
          uv = labelUv(s, p.lv ?? 0.5);
          break;
        case "lid":
          // Planar print on the lid: text upright when viewed from the front.
          uv = labelUv(0.5 + x * 0.95, 0.5 - z * 0.95);
          break;
        case "accent":
          uv = ZONE_ACCENT;
          break;
        default:
          uv = ZONE_BODY;
      }
      uvs.push(uv[0], uv[1]);
    }
  }
  for (let i = 0; i < profile.length - 1; i++) {
    for (let j = 0; j < segments; j++) {
      const a = i * cols + j;
      const b = a + cols;
      // Counter-clockwise seen from outside.
      indices.push(a, a + 1, b, b, a + 1, b + 1);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  g.setIndex(indices);
  g.computeVertexNormals();
  return g;
}

// Expand [r, y, zone] with duplicated rings wherever the zone changes.
function profile(points: [number, number, Zone][], labelY0 = 0, labelY1 = 1): ProfilePoint[] {
  const out: ProfilePoint[] = [];
  const lv = (y: number) => (y - labelY0) / Math.max(1e-6, labelY1 - labelY0);
  for (let i = 0; i < points.length; i++) {
    const [r, y, zone] = points[i]!;
    const prev = out[out.length - 1];
    if (prev && prev.zone !== zone && (prev.r !== r || prev.y !== y)) {
      out.push({ r: prev.r, y: prev.y, zone, lv: zone === "label" ? lv(prev.y) : undefined });
    }
    out.push({ r, y, zone, lv: zone === "label" ? lv(y) : undefined });
  }
  return out;
}

// Level of detail: 0 = isometric overview (few triangles — software GL renders
// thousands of instances), 1 = close-up / shopper view.
export type Lod = 0 | 1;

function bottle(lod: Lod): THREE.BufferGeometry {
  const L0 = 0.3;
  const L1 = 0.66;
  const pts: [number, number, Zone][] =
    lod === 0
      ? [
          [0.5, 0, "body"],
          [0.5, L0, "body"],
          [0.5, L0, "label"],
          [0.5, L1, "label"],
          [0.5, L1, "body"],
          [0.2, 0.86, "body"],
          [0.19, 0.88, "accent"],
          [0.0, 1.0, "accent"],
        ]
      : [
          [0, 0, "body"],
          [0.47, 0.0, "body"],
          [0.5, 0.04, "body"],
          [0.5, L0, "body"],
          [0.5, L0, "label"],
          [0.5, L1, "label"],
          [0.5, L1, "body"],
          [0.47, 0.72, "body"],
          [0.38, 0.79, "body"],
          [0.22, 0.85, "body"],
          [0.18, 0.87, "body"],
          [0.19, 0.88, "accent"],
          [0.19, 0.99, "accent"],
          [0.0, 1.0, "accent"],
        ];
  return revolve(profile(pts, L0, L1), lod === 0 ? 6 : 14);
}

function can(lod: Lod): THREE.BufferGeometry {
  const pts: [number, number, Zone][] =
    lod === 0
      ? [
          [0.5, 0, "label"],
          [0.5, 0.94, "label"],
          [0.44, 1.0, "accent"],
          [0.0, 1.0, "accent"],
        ]
      : [
          [0, 0, "accent"],
          [0.4, 0, "accent"],
          [0.5, 0.05, "accent"],
          [0.5, 0.06, "label"],
          [0.5, 0.92, "label"],
          [0.5, 0.93, "accent"],
          [0.42, 0.985, "accent"],
          [0.4, 1.0, "accent"],
          [0.0, 0.985, "accent"],
        ];
  return revolve(profile(pts, lod === 0 ? 0 : 0.06, lod === 0 ? 0.94 : 0.92), lod === 0 ? 6 : 14);
}

// Partition the existing surface without moving a vertex or adding triangles.
// Separate batches let the path tracer retain the same finishes as live mode.
export function createCanParts(lod: Lod): { body: THREE.BufferGeometry; metal: THREE.BufferGeometry } {
  const source = can(lod);
  const uv = source.getAttribute("uv");
  const index = source.index!;
  const bodyIndices: number[] = [], metalIndices: number[] = [];
  for (let i = 0; i < index.count; i += 3) {
    const triangle = [index.getX(i), index.getX(i + 1), index.getX(i + 2)];
    const isMetal = triangle.every(vertex =>
      Math.abs(uv.getX(vertex) - ZONE_ACCENT[0]) < 1e-6 && Math.abs(uv.getY(vertex) - ZONE_ACCENT[1]) < 1e-6,
    );
    (isMetal ? metalIndices : bodyIndices).push(...triangle);
  }
  const body = source.clone().setIndex(bodyIndices);
  const metal = source.clone().setIndex(metalIndices);
  source.dispose();
  return { body, metal };
}

function tube(lod: Lod): THREE.BufferGeometry {
  const pts: [number, number, Zone][] =
    lod === 0
      ? [
          [0.5, 0, "label"],
          [0.5, 0.93, "label"],
          [0.52, 0.93, "accent"],
          [0.52, 1.0, "accent"],
          [0.0, 1.0, "accent"],
        ]
      : [
          [0, 0, "accent"],
          [0.5, 0, "accent"],
          [0.5, 0.03, "label"],
          [0.5, 0.92, "label"],
          [0.52, 0.93, "accent"],
          [0.52, 1.0, "accent"],
          [0.0, 1.0, "accent"],
        ];
  return revolve(profile(pts, lod === 0 ? 0 : 0.03, lod === 0 ? 0.93 : 0.92), lod === 0 ? 6 : 14);
}

function jar(lod: Lod): THREE.BufferGeometry {
  const pts: [number, number, Zone][] =
    lod === 0
      ? [
          [0.5, 0, "body"],
          [0.5, 0.2, "body"],
          [0.5, 0.2, "label"],
          [0.5, 0.78, "label"],
          [0.47, 0.82, "accent"],
          [0.47, 1.0, "accent"],
          [0.0, 1.0, "accent"],
        ]
      : [
          [0, 0, "body"],
          [0.46, 0, "body"],
          [0.5, 0.05, "body"],
          [0.5, 0.2, "body"],
          [0.5, 0.2, "label"],
          [0.5, 0.75, "label"],
          [0.47, 0.8, "body"],
          [0.44, 0.83, "body"],
          [0.47, 0.84, "accent"],
          [0.47, 0.99, "accent"],
          [0.0, 1.0, "accent"],
        ];
  return revolve(profile(pts, 0.2, lod === 0 ? 0.78 : 0.75), lod === 0 ? 6 : 14);
}

function cup(rBottom: number, lod: Lod): THREE.BufferGeometry {
  const pts: [number, number, Zone][] = [
    ...(lod === 1 ? ([[0, 0, "body"], [rBottom, 0, "body"]] as [number, number, Zone][]) : []),
    [rBottom, 0, "label"],
    [0.48, 0.95, "label"],
    [0.5, 0.96, "accent"],
    [0.5, 1.0, "accent"],
    [0.5, 1.0, "lid"],
    [0.0, 1.0, "lid"],
  ];
  return revolve(profile(pts, 0, 0.95), lod === 0 ? 6 : 14);
}

function box(): THREE.BufferGeometry {
  const g = new THREE.BoxGeometry(1, 1, 1);
  g.translate(0, 0.5, 0);
  const uv = g.getAttribute("uv") as THREE.BufferAttribute;
  // Face order: +x, -x, +y, -y, +z, -z (4 vertices each).
  for (let face = 0; face < 6; face++) {
    for (let k = 0; k < 4; k++) {
      const i = face * 4 + k;
      if (face === 4 || face === 5) {
        const [u, v] = labelUv(uv.getX(i), uv.getY(i));
        uv.setXY(i, u, v);
      } else if (face === 2) {
        uv.setXY(i, ZONE_ACCENT[0], ZONE_ACCENT[1]);
      } else {
        uv.setXY(i, ZONE_BODY[0], ZONE_BODY[1]);
      }
    }
  }
  uv.needsUpdate = true;
  return g;
}

function perfumeBottle(): THREE.BufferGeometry {
  const body = box().scale(1, 0.72, 1);
  const neck = new THREE.BoxGeometry(0.24, 0.06, 0.24).translate(0, 0.75, 0);
  const cap = new THREE.BoxGeometry(0.45, 0.22, 0.55).translate(0, 0.89, 0);
  for (const part of [neck, cap]) {
    const uv = part.getAttribute("uv");
    for (let i = 0; i < uv.count; i++) uv.setXY(i, ZONE_ACCENT[0], ZONE_ACCENT[1]);
  }
  const geometry = mergeGeometries([body, neck, cap])!;
  body.dispose(); neck.dispose(); cap.dispose();
  return geometry;
}

function teaCup(lod: Lod): THREE.BufferGeometry {
  const body = revolve(profile([
    [0, 0, "body"], [0.35, 0, "body"], [0.35, 0, "label"],
    [0.48, 0.72, "label"], [0.5, 0.73, "accent"], [0.5, 0.76, "accent"], [0, 0.76, "accent"],
  ], 0, 0.72), lod === 0 ? 8 : 16);
  const straw = new THREE.CylinderGeometry(0.025, 0.025, 0.24, lod === 0 ? 6 : 10).translate(0.16, 0.88, 0);
  const uv = straw.getAttribute("uv");
  for (let i = 0; i < uv.count; i++) uv.setXY(i, ZONE_ACCENT[0], ZONE_ACCENT[1]);
  const geometry = mergeGeometries([body, straw])!;
  body.dispose(); straw.dispose();
  return geometry;
}

// Pillow bag: front and back surfaces bulge out and pinch to a seam on every
// edge; crimped seals top and bottom.
function bag(lod: Lod): THREE.BufferGeometry {
  const nx = lod === 0 ? 2 : 6;
  const ny = lod === 0 ? 2 : 6;
  const seal = 0.05;
  const positions: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  const surface = (side: 1 | -1) => {
    const base = positions.length / 3;
    for (let j = 0; j <= ny; j++) {
      for (let i = 0; i <= nx; i++) {
        const s = i / nx;
        const t = j / ny;
        const bulge =
          lod === 0 ? (s > 0 && s < 1 && t > 0 && t < 1 ? 1 : 0) : Math.pow(Math.sin(Math.PI * s), 0.45) * Math.pow(Math.sin(Math.PI * t), 0.55);
        positions.push(s - 0.5, seal + t * (1 - 2 * seal), side * 0.5 * bulge);
        if (side === 1) {
          const [u, v] = labelUv(s, t);
          uvs.push(u, v);
        } else {
          uvs.push(ZONE_BODY[0], ZONE_BODY[1]);
        }
      }
    }
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const a = base + j * (nx + 1) + i;
        const b = a + nx + 1;
        if (side === 1) indices.push(a, a + 1, b, a + 1, b + 1, b);
        else indices.push(a, b, a + 1, a + 1, b, b + 1);
      }
    }
  };
  surface(1);
  surface(-1);
  // Crimp seals (thin double-sided strips).
  const sealStrip = (y0: number, y1: number) => {
    const base = positions.length / 3;
    const q = [
      [-0.5, y0, 0.012],
      [0.5, y0, 0.012],
      [0.5, y1, 0.012],
      [-0.5, y1, 0.012],
      [-0.5, y0, -0.012],
      [0.5, y0, -0.012],
      [0.5, y1, -0.012],
      [-0.5, y1, -0.012],
    ];
    for (const p of q) {
      positions.push(p[0]!, p[1]!, p[2]!);
      uvs.push(ZONE_ACCENT[0], ZONE_ACCENT[1]);
    }
    indices.push(base, base + 1, base + 2, base, base + 2, base + 3);
    indices.push(base + 4, base + 6, base + 5, base + 4, base + 7, base + 6);
  };
  sealStrip(0, seal);
  sealStrip(1 - seal, 1);
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  g.setIndex(indices);
  g.computeVertexNormals();
  return g;
}

function banana(lod: Lod): THREE.BufferGeometry {
  const parts = [-0.22, 0, 0.22].map((x, index) => {
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(x, 0.85 - index * 0.04, -0.38),
      new THREE.Vector3(x - 0.05, 0.02, 0),
      new THREE.Vector3(x, 0.55 + index * 0.04, 0.4),
    );
    return new THREE.TubeGeometry(curve, lod ? 10 : 5, 0.11, lod ? 6 : 4, false);
  });
  const geometry = mergeGeometries(parts)!;
  parts.forEach((part) => part.dispose());
  geometry.computeBoundingBox();
  const box = geometry.boundingBox!;
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  geometry.translate(-center.x, -box.min.y, -center.z);
  geometry.scale(1 / size.x, 1 / size.y, 1 / size.z);
  const uv = geometry.getAttribute("uv");
  for (let i = 0; i < uv.count; i++) uv.setXY(i, ZONE_BODY[0], ZONE_BODY[1]);
  return geometry;
}

function onion(lod: Lod): THREE.BufferGeometry {
  return revolve(profile([
    [0, 0, "body"], [0.18, 0.025, "body"], [0.4, 0.12, "body"],
    [0.49, 0.3, "body"], [0.5, 0.45, "body"], [0.46, 0.6, "body"],
    [0.33, 0.72, "body"], [0.12, 0.82, "body"], [0.055, 0.9, "body"],
    [0.04, 0.98, "body"], [0, 1, "body"],
  ]), lod ? 20 : 10);
}

function kiwi(lod: Lod): THREE.BufferGeometry {
  const geometry = revolve(profile([
    [0, 0, "body"], [0.22, 0.025, "body"], [0.37, 0.10, "body"],
    [0.47, 0.25, "body"], [0.5, 0.5, "body"], [0.47, 0.75, "body"],
    [0.37, 0.90, "body"], [0.22, 0.975, "body"], [0, 1, "body"],
  ]), lod ? 20 : 10);
  geometry.rotateZ(Math.PI / 2);
  geometry.translate(0.5, 0.5, 0);
  return geometry;
}

function asianPear(lod: Lod): THREE.BufferGeometry {
  return revolve(profile([
    [0, 0, "body"], [0.2, 0.02, "body"], [0.4, 0.12, "body"],
    [0.49, 0.27, "body"], [0.5, 0.4, "body"], [0.45, 0.55, "body"],
    [0.3, 0.66, "body"], [0.08, 0.69, "body"], [0.025, 0.7, "body"],
    [0.023, 0.98, "body"], [0, 1, "body"],
  ]), lod ? 20 : 10);
}

function ginger(lod: Lod): THREE.BufferGeometry {
  const lobes = [
    [-0.05, 0.18, 0, 0.38, 0.18, 0.14, 0],
    [0.28, 0.19, 0.025, 0.2, 0.14, 0.15, 0.2],
    [-0.31, 0.17, 0.12, 0.17, 0.13, 0.18, -0.5],
    [-0.04, 0.22, -0.16, 0.17, 0.16, 0.2, 0.65],
    [0.15, 0.15, 0.18, 0.14, 0.1, 0.14, -0.3],
  ] as const;
  const parts = lobes.map(([x, y, z, sx, sy, sz, yaw]) =>
    new THREE.SphereGeometry(1, lod ? 10 : 6, lod ? 6 : 4)
      .scale(sx, sy, sz).rotateY(yaw).translate(x, y, z),
  );
  const geometry = mergeGeometries(parts)!;
  parts.forEach(part => part.dispose());
  geometry.computeBoundingBox();
  const box = geometry.boundingBox!, size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  geometry.translate(-center.x, -box.min.y, -center.z);
  geometry.scale(1 / size.x, 1 / size.y, 1 / size.z);
  const uv = geometry.getAttribute("uv");
  for (let i = 0; i < uv.count; i++) uv.setXY(i, ZONE_BODY[0], ZONE_BODY[1]);
  return geometry;
}

function sweetPotato(lod: Lod): THREE.BufferGeometry {
  const geometry = revolve(profile([
    [0, 0, "body"], [0.18, 0.025, "body"], [0.36, 0.1, "body"],
    [0.47, 0.25, "body"], [0.5, 0.4, "body"], [0.48, 0.55, "body"],
    [0.42, 0.7, "body"], [0.32, 0.85, "body"], [0.17, 0.95, "body"],
    [0.05, 0.99, "body"], [0, 1, "body"],
  ]), lod ? 20 : 10);
  geometry.rotateZ(Math.PI / 2);
  geometry.translate(0.5, 0.5, 0);
  return geometry;
}

function lemon(lod: Lod): THREE.BufferGeometry {
  const points: [number, number, Zone][] = [
    [0, 0, "body"], [0.07, 0.03, "body"], [0.12, 0.10, "body"],
    [0.33, 0.20, "body"], [0.46, 0.35, "body"], [0.5, 0.5, "body"],
    [0.46, 0.65, "body"], [0.33, 0.80, "body"], [0.12, 0.90, "body"],
    [0.07, 0.97, "body"], [0, 1, "body"],
  ];
  const geometry = revolve(profile(points), lod ? 20 : 10);
  geometry.rotateZ(Math.PI / 2);
  geometry.translate(0.5, 0.5, 0);
  return geometry;
}

function avocado(lod: Lod): THREE.BufferGeometry {
  const points: [number, number, Zone][] = [
    [0, 0, "body"], [0.30, 0.05, "body"], [0.46, 0.18, "body"],
    [0.5, 0.35, "body"], [0.45, 0.57, "body"], [0.32, 0.80, "body"],
    [0.18, 0.95, "body"], [0.06, 1, "body"], [0, 1, "body"],
  ];
  return revolve(profile(points), lod ? 20 : 10);
}

function apple(lod: Lod, pair: boolean): THREE.BufferGeometry {
  const base = new THREE.SphereGeometry(0.5, lod ? 16 : 8, lod ? 12 : 6);
  base.translate(0, 0.5, 0);
  const uv = base.getAttribute("uv");
  for (let i = 0; i < uv.count; i++) uv.setXY(i, ZONE_BODY[0], ZONE_BODY[1]);
  if (!pair) return base;
  const width = 0.09756 / 0.20112;
  const offset = (0.09756 + 0.006) / (2 * 0.20112);
  const halves = [-1, 1].map((sign) => base.clone().scale(width, 1, 1).translate(sign * offset, 0, 0));
  const geometry = mergeGeometries(halves)!;
  base.dispose();
  halves.forEach((half) => half.dispose());
  return geometry;
}

// Follow the outer wall over the rim and down the inside, leaving the top open.
function pot(lod: Lod): THREE.BufferGeometry {
  const points: [number, number, Zone][] = [
    [0, 0, "body"], [0.33, 0, "body"], [0.33, 0.08, "body"],
    [0.29, 0.1, "body"], [0.45, 0.85, "body"], [0.5, 0.86, "body"],
    [0.5, 1, "body"], [0.43, 1, "body"], [0.43, 0.86, "body"],
    [0.25, 0.12, "body"], [0, 0.12, "body"],
  ];
  return revolve(profile(points), lod ? 24 : 12);
}

function burgerBun(lod: Lod): THREE.BufferGeometry {
  const segments = lod ? 20 : 12;
  const dome = new THREE.SphereGeometry(0.5, segments, lod ? 6 : 4, 0, Math.PI * 2, 0, Math.PI / 2);
  const base = new THREE.CircleGeometry(0.5, segments).rotateX(Math.PI / 2);
  const geometry = mergeGeometries([dome, base])!;
  dome.dispose(); base.dispose();
  geometry.scale(1, 2, 1);
  const uv = geometry.getAttribute("uv");
  for (let i = 0; i < uv.count; i++) uv.setXY(i, ZONE_BODY[0], ZONE_BODY[1]);
  return geometry;
}

function croissant(lod: Lod): THREE.BufferGeometry {
  const points: [number, number, Zone][] = [
    [0, 0, "body"], [0.14, 0.04, "body"], [0.29, 0.18, "body"],
    [0.25, 0.23, "body"], [0.42, 0.34, "body"], [0.5, 0.5, "body"],
    [0.42, 0.66, "body"], [0.25, 0.77, "body"], [0.29, 0.82, "body"],
    [0.14, 0.96, "body"], [0, 1, "body"],
  ];
  // The scanned pastry lies on its side, with tapered tips along the shelf.
  return revolve(profile(points), lod ? 24 : 12).rotateZ(-Math.PI / 2).translate(-0.5, 0.5, 0);
}

function wateringCan(lod: Lod): THREE.BufferGeometry {
  const segments = lod ? 20 : 10;
  const body = new THREE.CylinderGeometry(0.082, 0.095, 0.16, segments).translate(-0.09, 0.08, 0);
  const lid = new THREE.CylinderGeometry(0.045, 0.082, 0.035, segments).translate(-0.09, 0.1775, 0);
  const start = new THREE.Vector3(-0.02, 0.035, 0), end = new THREE.Vector3(0.17, 0.16, 0);
  const spout = new THREE.TubeGeometry(new THREE.LineCurve3(start, end), 1, 0.012, lod ? 10 : 6, false);
  const rotation = new THREE.Quaternion().setFromUnitVectors(THREE.Object3D.DEFAULT_UP, end.clone().sub(start).normalize());
  const rose = new THREE.CylinderGeometry(0.027, 0.012, 0.035, segments).applyQuaternion(rotation).translate(end.x, end.y, end.z);
  const handle = new THREE.TorusGeometry(0.067, 0.006, lod ? 6 : 4, segments).translate(-0.185, 0.09, 0);
  const parts = [body, lid, spout, rose, handle];
  const geometry = mergeGeometries(parts)!;
  parts.forEach((part) => part.dispose());
  geometry.computeBoundingBox();
  const box = geometry.boundingBox!, size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  geometry.translate(-center.x, -box.min.y, -center.z);
  geometry.scale(1 / size.x, 1 / size.y, 1 / size.z);
  const uv = geometry.getAttribute("uv");
  for (let i = 0; i < uv.count; i++) uv.setXY(i, ZONE_BODY[0], ZONE_BODY[1]);
  return geometry;
}

export function createPackageGeometry(kind: PackageKind, lod: Lod = 1): THREE.BufferGeometry {
  switch (kind) {
    case "bottle":
      return bottle(lod);
    case "perfumeBottle":
      return perfumeBottle();
    case "teaCup":
      return teaCup(lod);
    case "can":
      return can(lod);
    case "tube":
      return tube(lod);
    case "jar":
      return jar(lod);
    case "cup":
      return cup(0.38, lod);
    case "pint":
      return cup(0.43, lod);
    case "bag":
      return bag(lod);
    case "wateringCan":
      return wateringCan(lod);
    case "croissant":
      return croissant(lod);
    case "burgerBun":
      return burgerBun(lod);
    case "pot":
      return pot(lod);
    case "banana":
      return banana(lod);
    case "avocado":
      return avocado(lod);
    case "lemon":
      return lemon(lod);
    case "onion":
      return onion(lod);
    case "kiwi":
      return kiwi(lod);
    case "asianPear":
      return asianPear(lod);
    case "ginger":
      return ginger(lod);
    case "sweetPotato":
      return sweetPotato(lod);
    case "apple":
    case "applePair":
      return apple(lod, kind === "applePair");
    default:
      return box();
  }
}

export const PACKAGE_KINDS: PackageKind[] = ["bottle", "perfumeBottle", "teaCup", "can", "cup", "pint", "jar", "tube", "box", "bag", "banana", "apple", "applePair", "avocado", "lemon", "onion", "kiwi", "sweetPotato", "asianPear", "ginger", "pot", "croissant", "burgerBun", "wateringCan"];
