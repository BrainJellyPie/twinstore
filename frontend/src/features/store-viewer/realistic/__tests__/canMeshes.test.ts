// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import { buildProductMeshes } from "../productMeshes";
import { buildPhotoScene } from "../photoScene";
import { createPackageGeometry } from "../productGeometries";
import type { ProductInstance, ProductLayout } from "../productLayout";

vi.mock("../canvasArt", async importOriginal => {
  const original = await importOriginal<typeof import("../canvasArt")>();
  const { atlasGrid } = await import("../atlasLayout");
  const atlas = (keys: string[], size = 128) => ({
    canvas: document.createElement("canvas"), grid: atlasGrid(keys.length, size),
    index: new Map(keys.map((key, i) => [key, i])), redraw: vi.fn(),
  });
  return { ...original,
    createLabelAtlas: (labels: { key: string }[], size: number) => atlas([...new Set(labels.map(label => label.key))], size),
    createTagAtlas: () => atlas([]), createTalkerAtlas: () => atlas([]),
  };
});
beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    (() => ({ drawImage: vi.fn() })) as unknown as HTMLCanvasElement["getContext"],
  );
});
afterEach(() => vi.restoreAllMocks());

const cans: ProductInstance[] = Array.from({ length: 16 }, (_, i) => ({
  name: `Soda Can ${i % 3}`, imageUrl: `/api/images/can-${i % 4}`, kind: "can", x: i * 0.12, y: (i % 3) * 0.2, z: i * 0.03,
  yaw: (i % 4) * Math.PI / 2, flat: i % 2 === 0, sx: 0.05 + (i % 3) * 0.01, sy: 0.12 + (i % 2) * 0.04, sz: 0.05,
}));
const layout: ProductLayout = { products: cans, tags: [], talkers: [] };
const build = (cheap = false, products = cans) => buildProductMeshes({ ...layout, products }, "USD", 128, true, 2, cheap);
const canMesh = (built: ReturnType<typeof build>, name = "pkg-can") => built.group.getObjectByName(name) as THREE.InstancedMesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;

it.each([false, true])("keeps end caps aligned with upright, flat and rotated labels at fine detail %s", fine => {
  const built = build();
  try {
    built.setDetail(fine);
    const body = canMesh(built), metal = canMesh(built, "pkg-can-metal");
    expect(body.count).toBe(cans.length); expect(metal.count).toBe(cans.length);
    expect(Array.from(metal.instanceMatrix.array)).toEqual(Array.from(body.instanceMatrix.array));
    expect(metal.instanceMatrix.array).not.toBe(body.instanceMatrix.array);
    expect(Array.from(metal.geometry.getAttribute("aCell").array)).toEqual(Array.from(body.geometry.getAttribute("aCell").array));
    expect(metal.geometry.getAttribute("aCell").array).not.toBe(body.geometry.getAttribute("aCell").array);
    expect(new Set(Array.from(body.geometry.getAttribute("aCell").array)).size).toBeGreaterThan(2);
    expect(metal.material.map).toBe(body.material.map);
    expect(body.material.metalness).toBe(0); expect(metal.material.metalness).toBe(1);
    expect(metal.material.roughness).toBeLessThan(body.material.roughness);
    const whole = createPackageGeometry("can", fine ? 1 : 0);
    expect(body.geometry.index!.count + metal.geometry.index!.count).toBe(whole.index!.count);
    whole.dispose();
  } finally { built.dispose(); }
});

it("uses one additional batch only in High stores containing cans", () => {
  const high = build(), medium = build(true), empty = build(false, []);
  const bottles = build(false, cans.map(can => ({ ...can, kind: "bottle" })));
  try {
    expect(high.group.children).toHaveLength(2);
    expect(medium.group.children).toHaveLength(1);
    expect(empty.group.children).toHaveLength(0);
    expect(bottles.group.children).toHaveLength(1);
    expect(medium.group.getObjectByName("pkg-can-metal")).toBeUndefined();
    expect(bottles.group.getObjectByName("pkg-can-metal")).toBeUndefined();
    expect(high.textures).toHaveLength(medium.textures.length);
  } finally { [high, medium, empty, bottles].forEach(built => built.dispose()); }
});

it.each([false, true])("preserves both can finishes and atlas cells in Photo mode at fine detail %s", fine => {
  const built = build(); built.setDetail(fine);
  const live = new THREE.Scene(); live.add(built.group);
  const resources = new Set<{ dispose: () => void }>(built.textures);
  for (const detail of [false, true]) {
    built.setDetail(detail);
    for (const object of built.group.children) {
      const mesh = object as THREE.InstancedMesh;
      resources.add(mesh); resources.add(mesh.geometry); resources.add(mesh.material as THREE.Material);
    }
  }
  built.setDetail(fine);
  const disposed = [...resources].map(resource => vi.spyOn(resource, "dispose"));
  const photo = buildPhotoScene(live, { width: 4, depth: 5, background: null });
  try {
    const baked = photo.scene.children.filter(object => object instanceof THREE.Mesh) as THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>[];
    expect(baked).toHaveLength(2);
    for (const name of ["pkg-can", "pkg-can-metal"]) {
      const source = canMesh(built, name);
      const copy = baked.find(mesh => mesh.material.metalness === source.material.metalness)!;
      expect(copy.material).not.toBe(source.material);
      expect(copy.material.map).toBe(source.material.map);
      const index = source.geometry.index!, uv = source.geometry.getAttribute("uv");
      const cell = source.geometry.getAttribute("aCell"), scale = source.material.userData.atlasCellScale as THREE.Vector2;
      const copied = copy.geometry.getAttribute("uv");
      expect(copied.count).toBe(index.count * cans.length);
      for (let instance = 0; instance < cans.length; instance++) for (let k = 0; k < index.count; k++) {
        expect(copied.getX(instance * index.count + k)).toBeCloseTo(cell.getX(instance) + uv.getX(index.getX(k)) * scale.x, 6);
        expect(copied.getY(instance * index.count + k)).toBeCloseTo(cell.getY(instance) + uv.getY(index.getX(k)) * scale.y, 6);
      }
    }
  } finally { photo.dispose(); }
  disposed.forEach(dispose => expect(dispose).not.toHaveBeenCalled());
  built.dispose();
  disposed.forEach(dispose => expect(dispose).toHaveBeenCalledOnce());
});
