/// <reference types="node" />

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { realisticCharacterAssetFor } from "@/shared/utils/assetMap";

interface Model {
  animations: { name: string; channels: { target: { node: number; path: string }; sampler: number }[]; samplers: { output: number }[] }[];
  accessors: { bufferView: number; byteOffset?: number; count: number; componentType: number; type: string }[];
  bufferViews: { byteOffset: number; byteStride?: number }[];
  materials: { name: string; alphaMode?: string; alphaCutoff?: number; normalTexture?: object }[];
  nodes: { name?: string }[];
  skins: { joints: number[] }[];
}

describe("bundled shopper models", () => {
  for (const gender of ["Female", "Male"]) {
    it(`ships a rigged ${gender} model with a stationary walking loop`, () => {
      const url = realisticCharacterAssetFor("shopper-1", gender);
      const data = readFileSync(resolve("public", url.slice(1)));
      expect(data.readUInt32LE(0)).toBe(0x46546c67);
      const jsonLength = data.readUInt32LE(12);
      const model = JSON.parse(data.subarray(20, 20 + jsonLength).toString()) as Model;
      expect(model.animations.map((a) => a.name).sort()).toEqual(["idle", "walk"]);
      expect(model.skins[0]!.joints.length).toBeGreaterThan(50);
      expect(model.materials.filter((m) => m.normalTexture)).toHaveLength(2);
      const hair = model.materials.find((m) => m.name.includes("opacity"));
      expect(hair?.alphaMode).toBe("MASK");
      expect(hair?.alphaCutoff).toBeGreaterThan(0);

      const walk = model.animations.find((a) => a.name === "walk")!;
      const binaryStart = 20 + jsonLength + 8;
      // Root locomotion belongs to the simulation. The exported armature may
      // bob vertically, but must not walk away from the shopper's grid tile.
      const channel = walk.channels.find((c) => model.nodes[c.target.node]?.name === "Bip01" && c.target.path === "translation")!;
      expect(channel).toBeDefined();
      const accessor = model.accessors[walk.samplers[channel.sampler]!.output]!;
      expect(accessor.componentType).toBe(5126);
      expect(accessor.type).toBe("VEC3");
      const view = model.bufferViews[accessor.bufferView]!;
      const offset = binaryStart + view.byteOffset + (accessor.byteOffset ?? 0);
      for (const axis of [0, 2]) {
        const positions = Array.from({ length: accessor.count }, (_, i) => data.readFloatLE(offset + i * (view.byteStride ?? 12) + axis * 4));
        expect(Math.max(...positions) - Math.min(...positions)).toBeLessThan(0.001);
      }
    });
  }
});
