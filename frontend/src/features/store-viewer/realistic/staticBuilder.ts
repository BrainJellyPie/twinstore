// Collects primitive parts (boxes, cylinders, quads) per material and merges
// them into one geometry per material, so the whole procedural store renders in
// a handful of draw calls.

import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

export type MatKey =
  | "wall"
  | "band"
  | "bandLine"
  | "trim"
  | "cut"
  | "plinth"
  | "metalWhite"
  | "metalGrey"
  | "backPanel"
  | "kick"
  | "rail"
  | "darkMetal"
  | "fridgeShell"
  | "fridgeInterior"
  | "wire"
  | "chrome"
  | "led"
  | "glass"
  | "lidGlass"
  | "freezerBody"
  | "freezerInterior"
  | "bumper"
  | "wood"
  | "counterTop"
  | "black"
  | "screen"
  | "mat"
  | "aluminum"
  | "pavement"
  | "curb"
  | "ceiling"
  | "ceilingLight"
  | "exitSign"
  | "plant"
  | "pot"
  | "sign"
  | "ao";

function toIndexed(g: THREE.BufferGeometry): THREE.BufferGeometry {
  const count = g.getAttribute("position").count;
  const idx = new Array<number>(count);
  for (let i = 0; i < count; i++) idx[i] = i;
  g.setIndex(idx);
  return g;
}

export class StaticBuilder {
  private parts = new Map<MatKey, THREE.BufferGeometry[]>();
  private frame = new THREE.Matrix4();
  private tmp = new THREE.Matrix4();
  private q = new THREE.Quaternion();
  private e = new THREE.Euler();
  private s = new THREE.Vector3();
  private p = new THREE.Vector3();

  // Subsequent parts are placed in a frame at (x, 0, z) rotated by yaw.
  setFrame(x: number, z: number, yaw: number, y = 0): this {
    this.frame.makeRotationY(yaw).setPosition(x, y, z);
    return this;
  }

  resetFrame(): this {
    this.frame.identity();
    return this;
  }

  add(mat: MatKey, geom: THREE.BufferGeometry, local: THREE.Matrix4): this {
    geom.applyMatrix4(this.tmp.multiplyMatrices(this.frame, local));
    const list = this.parts.get(mat);
    if (list) list.push(geom);
    else this.parts.set(mat, [geom]);
    return this;
  }

  sphere(mat: MatKey, r: number, x: number, y: number, z: number, sy = 1, detail = 1): this {
    const g = new THREE.IcosahedronGeometry(r, detail);
    // Icosahedron is non-indexed; merge requires consistent indexing.
    const indexed = g.index ? g : toIndexed(g);
    return this.add(mat, indexed, this.local(x, y, z, 0, 0, 0, 1, sy, 1));
  }

  private local(x: number, y: number, z: number, rx = 0, ry = 0, rz = 0, sx = 1, sy = 1, sz = 1): THREE.Matrix4 {
    this.e.set(rx, ry, rz);
    this.q.setFromEuler(this.e);
    this.p.set(x, y, z);
    this.s.set(sx, sy, sz);
    return new THREE.Matrix4().compose(this.p, this.q, this.s);
  }

  // Axis-aligned box (in the current frame) given its centre.
  box(mat: MatKey, w: number, h: number, d: number, x: number, y: number, z: number, rx = 0, ry = 0, rz = 0): this {
    if (w <= 0 || h <= 0 || d <= 0) return this;
    return this.add(mat, new THREE.BoxGeometry(w, h, d), this.local(x, y, z, rx, ry, rz));
  }

  // Box from min corner to max corner.
  span(mat: MatKey, x0: number, y0: number, z0: number, x1: number, y1: number, z1: number): this {
    return this.box(mat, Math.abs(x1 - x0), Math.abs(y1 - y0), Math.abs(z1 - z0), (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
  }

  cylinder(mat: MatKey, rTop: number, rBottom: number, h: number, x: number, y: number, z: number, segments = 12, rx = 0, rz = 0): this {
    return this.add(mat, new THREE.CylinderGeometry(rTop, rBottom, h, segments), this.local(x, y, z, rx, 0, rz));
  }

  // Quad facing +Z in its own rotation; uv rectangle optional (atlas cells).
  quad(
    mat: MatKey,
    w: number,
    h: number,
    x: number,
    y: number,
    z: number,
    ry = 0,
    rx = 0,
    uv?: { offset: [number, number]; scale: [number, number] },
  ): this {
    const g = new THREE.PlaneGeometry(w, h);
    if (uv) {
      const a = g.getAttribute("uv") as THREE.BufferAttribute;
      for (let i = 0; i < a.count; i++) {
        a.setXY(i, uv.offset[0] + a.getX(i) * uv.scale[0], uv.offset[1] + a.getY(i) * uv.scale[1]);
      }
    }
    return this.add(mat, g, this.local(x, y, z, rx, ry, 0));
  }

  has(mat: MatKey): boolean {
    return (this.parts.get(mat)?.length ?? 0) > 0;
  }

  build(): Map<MatKey, THREE.BufferGeometry> {
    const out = new Map<MatKey, THREE.BufferGeometry>();
    for (const [mat, list] of this.parts) {
      const merged = mergeGeometries(list, false);
      for (const g of list) g.dispose();
      if (merged) {
        merged.computeBoundingSphere();
        merged.computeBoundingBox();
        out.set(mat, merged);
      }
    }
    this.parts.clear();
    return out;
  }
}
