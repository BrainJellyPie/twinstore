/// <reference types="node" />
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { expect, it } from "vitest";
import { classifyProduct } from "../productCatalog";
import { produceVariation } from "../produceVariation";

interface ProductModel {
  nodes: { name: string; mesh: number }[];
  meshes: { primitives: { attributes: { POSITION: number; NORMAL: number }; indices: number }[] }[];
  accessors: { count: number; min?: number[]; max?: number[]; bufferView: number; byteOffset?: number }[];
  bufferViews: { byteOffset: number; byteStride?: number }[];
}

it.each([
  ["produce/bananas", [["bananas-coarse", 300], ["bananas-fine", 1600]]],
  ["produce/avocado", [["avocado-coarse", 200], ["avocado-fine", 1000]]],
  ["produce/lemon", [["lemon-coarse", 200], ["lemon-fine", 1000]]],
  ["produce/onion", [["onion-coarse", 250], ["onion-fine", 1400]]],
  ["produce/ginger", [["ginger-coarse", 300], ["ginger-fine", 1400]]],
  ["produce/asian-pear", [["asian-pear-coarse", 300], ["asian-pear-fine", 1400]]],
  ["produce/kiwi", [["kiwi-coarse", 240], ["kiwi-fine", 1200]]],
  ["produce/sweet-potato", [["sweet-potato-coarse", 240], ["sweet-potato-fine", 1200]]],
  ["produce/apples", [["apple-coarse", 200], ["apple-fine", 1000], ["apple-pair-coarse", 400], ["apple-pair-fine", 2000]]],
  ["products/watering-can", [["watering-can-coarse", 500], ["watering-can-fine", 2500]]],
  ["products/croissant", [["croissant-coarse", 300], ["croissant-fine", 1500]]],
  ["products/terracotta-pot", [["pot-coarse", 300], ["pot-fine", 1500]]],
] as const)("ships bounded %s LODs with unit normals and a bottom-centred unit footprint", (asset, lods) => {
  const data = readFileSync(`public/assets/${asset}.glb`);
  const length = data.readUInt32LE(12);
  const model = JSON.parse(data.subarray(20, 20 + length).toString()) as ProductModel;
  for (const [name, budget] of lods) {
    const node = model.nodes.find((node) => node.name === name)!;
    expect(node).toBeDefined();
    const primitive = model.meshes[node.mesh]!.primitives[0]!;
    expect(model.accessors[primitive.indices]!.count / 3).toBeLessThanOrEqual(budget);
    const position = model.accessors[primitive.attributes.POSITION]!;
    position.min!.forEach((value, axis) => expect(value).toBeCloseTo([-0.5, 0, -0.5][axis]!, 5));
    position.max!.forEach((value, axis) => expect(value).toBeCloseTo([0.5, 1, 0.5][axis]!, 5));
    if (asset.startsWith("produce/")) {
      const kind = name.startsWith("ginger") ? "ginger" : name.startsWith("asian-pear") ? "asianPear" : name.startsWith("sweet-potato") ? "sweetPotato" : name.startsWith("kiwi") ? "kiwi" : name.startsWith("onion") ? "onion" : name.startsWith("lemon") ? "lemon" : name.startsWith("avocado") ? "avocado" : name.startsWith("bananas") ? "banana" : name.startsWith("apple-pair") ? "applePair" : "apple";
      const spec = classifyProduct(kind === "ginger" ? "Ginger Root" : kind === "asianPear" ? "Asian Pear" : kind === "sweetPotato" ? "Sweet Potato" : kind === "kiwi" ? "Kiwi" : kind === "onion" ? "Yellow Onions" : kind === "lemon" ? "Lemons" : kind === "avocado" ? "Avocados" : kind === "banana" ? "Bananas" : kind === "applePair" ? "Apples 2pk" : "Apples");
      const view = model.bufferViews[position.bufferView]!;
      const offset = 28 + length + view.byteOffset + (position.byteOffset ?? 0);
      let maxX = 0, maxZ = 0;
      for (let sample = 0; sample < 32; sample++) {
        const variation = produceVariation(kind, `${kind}|${sample}|0|0`)!;
        const sin = Math.sin(variation.yaw), cos = Math.cos(variation.yaw);
        for (let i = 0; i < position.count; i++) {
          const start = offset + i * (view.byteStride ?? 12);
          const x = data.readFloatLE(start) * spec.w * variation.scale;
          const z = data.readFloatLE(start + 8) * spec.d * variation.scale;
          maxX = Math.max(maxX, Math.abs(x * cos + z * sin));
          maxZ = Math.max(maxZ, Math.abs(-x * sin + z * cos));
        }
      }
      expect(maxX).toBeLessThanOrEqual(spec.w / 2 + 1e-7);
      expect(maxZ).toBeLessThanOrEqual(spec.d / 2 + 1e-7);
    }
    if (name.startsWith("apple-pair")) {
      const view = model.bufferViews[position.bufferView]!;
      const offset = 28 + length + view.byteOffset + (position.byteOffset ?? 0);
      const xs = Array.from({ length: position.count }, (_, i) => data.readFloatLE(offset + i * (view.byteStride ?? 12)));
      expect(xs.some((x) => x < 0)).toBe(true);
      expect(xs.some((x) => x > 0)).toBe(true);
      // The two apples retain a physical gap rather than forming one stretched fruit.
      expect(Math.min(...xs.map(Math.abs))).toBeGreaterThan(0.014);
    }
    const normal = model.accessors[primitive.attributes.NORMAL]!;
    const view = model.bufferViews[normal.bufferView]!;
    const offset = 28 + length + view.byteOffset + (normal.byteOffset ?? 0);
    for (let i = 0; i < normal.count; i++) {
      const start = offset + i * (view.byteStride ?? 12);
      expect(Math.hypot(data.readFloatLE(start), data.readFloatLE(start + 4), data.readFloatLE(start + 8))).toBeCloseTo(1, 4);
    }
  }
});

it.each(["onion", "kiwi", "sweet-potato", "asian-pear", "ginger"])("retains the %s scan's original JPEG bytes and recorded output hash", kind => {
  const data = readFileSync(`public/assets/produce/${kind}.glb`);
  const manifest = JSON.parse(readFileSync(`public/assets/produce/${kind}-sources.json`, "utf8")) as {
    files: { file: string; bytes: number; sha256: string }[]; outputs: { bytes: number; sha256: string }[];
  };
  expect(data.length).toBe(manifest.outputs[0]!.bytes);
  expect(createHash("sha256").update(data).digest("hex")).toBe(manifest.outputs[0]!.sha256);
  const length = data.readUInt32LE(12);
  const model = JSON.parse(data.subarray(20, 20 + length).toString()) as {
    images: { name: string; mimeType: string; bufferView: number }[];
    bufferViews: { byteOffset: number; byteLength: number }[];
  };
  expect(model.images).toHaveLength(3);
  for (const image of model.images) {
    expect(image.mimeType).toBe("image/jpeg");
    const view = model.bufferViews[image.bufferView]!;
    const bytes = data.subarray(28 + length + view.byteOffset, 28 + length + view.byteOffset + view.byteLength);
    const record = manifest.files.find(file => file.file === `textures/${image.name}.jpg`)!;
    expect(bytes.length).toBe(record.bytes);
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(record.sha256);
  }
});
