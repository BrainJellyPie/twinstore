/// <reference types="node" />

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { ALL_REALISTIC_CHARACTER_ASSETS, characterAnimationPhase } from "@/shared/utils/assetMap";

interface Model {
  animations: { name: string; channels: { target: { node: number; path: string }; sampler: number }[]; samplers: { output: number }[] }[];
  accessors: { bufferView: number; byteOffset?: number; count: number; componentType: number; type: string; min?: number[]; max?: number[] }[];
  bufferViews: { byteOffset: number; byteStride?: number }[];
  materials: {
    name: string; alphaMode?: string; alphaCutoff?: number; normalTexture?: { index: number };
    pbrMetallicRoughness: { metallicFactor?: number; roughnessFactor?: number; metallicRoughnessTexture?: { index: number } };
  }[];
  textures: { source?: number; extensions?: { EXT_texture_webp?: { source: number } } }[];
  extensionsRequired: string[];
  images: { bufferView: number; mimeType: string }[];
  meshes: { extras: { targetNames: string[] }; primitives: { material: number; targets: { POSITION: number; NORMAL: number }[] }[] }[];
  nodes: { name?: string }[];
  skins: { joints: number[] }[];
}

describe("bundled shopper models", () => {
  for (const url of ALL_REALISTIC_CHARACTER_ASSETS) {
    it(`ships ${url} with stationary walking and browsing motions`, () => {
      const data = readFileSync(resolve("public", url.slice(1)));
      expect(data.readUInt32LE(0)).toBe(0x46546c67);
      const jsonLength = data.readUInt32LE(12);
      const model = JSON.parse(data.subarray(20, 20 + jsonLength).toString()) as Model;
      expect(model.animations.map((a) => a.name).sort()).toEqual(["browse", "idle", "walk"]);
      expect(model.skins[0]!.joints.length).toBeGreaterThan(50);
      expect(model.materials.filter((m) => m.normalTexture)).toHaveLength(2);
      const hair = model.materials.find((m) => m.name.includes("opacity"));
      if (hair) {
        expect(hair.alphaMode).toBe("MASK");
        expect(hair.alphaCutoff).toBeGreaterThan(0);
      }

      const binaryStart = 20 + jsonLength + 8;
      expect(model.extensionsRequired).toContain("EXT_texture_webp");
      for (const material of model.materials.filter((m) => m.normalTexture)) {
        const texture = model.textures[material.normalTexture!.index]!;
        expect(texture.source).toBeUndefined();
        const image = model.images[texture.extensions!.EXT_texture_webp!.source]!;
        expect(image.mimeType).toBe("image/webp");
        const imageStart = binaryStart + model.bufferViews[image.bufferView]!.byteOffset;
        expect(data.subarray(imageStart, imageStart + 4).toString()).toBe("RIFF");
        expect(data.subarray(imageStart + 8, imageStart + 12).toString()).toBe("WEBP");
        expect(data.subarray(imageStart + 12, imageStart + 16).toString()).toBe("VP8L"); // lossless codec
      }
      const facialShapes = ["blink", "lookLeft", "lookRight", "lookUp", "lookDown"];
      for (const mesh of model.meshes) expect(mesh.extras.targetNames).toEqual(facialShapes);
      const headPrimitive = model.meshes.flatMap((mesh) => mesh.primitives).find((p) => model.materials[p.material]!.name.includes("head"))!;
      expect(headPrimitive.targets).toHaveLength(facialShapes.length);
      for (const target of headPrimitive.targets) {
        const shape = model.accessors[target.POSITION]!;
        const deformation = Math.max(...[...shape.min!, ...shape.max!].map(Math.abs));
        expect(deformation).toBeGreaterThan(0.001);
        expect(deformation).toBeLessThan(0.05);
      }
      // Constant morph keys in body clips would silently overwrite runtime eye motion.
      expect(model.animations.flatMap((a) => a.channels).some((c) => c.target.path === "weights")).toBe(false);
      // Confirm the conversion embedded actual maps; an unbaked Blender node
      // graph can otherwise silently export the same flat roughness as before.
      const mapped = model.materials.filter((m) => m.pbrMetallicRoughness.metallicRoughnessTexture);
      expect(mapped).toHaveLength(2);
      for (const material of mapped) {
        const pbr = material.pbrMetallicRoughness;
        expect(pbr.metallicFactor).toBe(0);
        expect(pbr.roughnessFactor ?? 1).toBe(1);
        const texture = model.textures[pbr.metallicRoughnessTexture!.index]!;
        const image = model.images[texture.source!]!;
        expect(image.mimeType).toBe("image/png");
        const imageStart = binaryStart + model.bufferViews[image.bufferView]!.byteOffset;
        expect(data.subarray(imageStart + 1, imageStart + 4).toString()).toBe("PNG");
        expect(data.readUInt32BE(imageStart + 16)).toBe(512);
        expect(data.readUInt32BE(imageStart + 20)).toBe(512);
      }
      // Root locomotion belongs to the simulation. The exported armature may
      // bob vertically, but must not walk away from the shopper's grid tile.
      for (const motion of model.animations) {
        const channel = motion.channels.find((c) => model.nodes[c.target.node]?.name === "Bip01" && c.target.path === "translation")!;
        expect(channel).toBeDefined();
        const accessor = model.accessors[motion.samplers[channel.sampler]!.output]!;
        expect(accessor.componentType).toBe(5126);
        expect(accessor.type).toBe("VEC3");
        const view = model.bufferViews[accessor.bufferView]!;
        const offset = binaryStart + view.byteOffset + (accessor.byteOffset ?? 0);
        for (const axis of [0, 2]) {
          const positions = Array.from({ length: accessor.count }, (_, i) => data.readFloatLE(offset + i * (view.byteStride ?? 12) + axis * 4));
          expect(Math.max(...positions) - Math.min(...positions)).toBeLessThan(0.001);
        }
      }

      // A named clip alone is insufficient: the retargeted head must look around.
      const browse = model.animations.find((a) => a.name === "browse")!;
      const head = browse.channels.find((c) => model.nodes[c.target.node]?.name === "Bip01 Head" && c.target.path === "rotation")!;
      expect(head).toBeDefined();
      const rotations = model.accessors[browse.samplers[head.sampler]!.output]!;
      expect(rotations.type).toBe("VEC4");
      const rotationView = model.bufferViews[rotations.bufferView]!;
      const rotationOffset = binaryStart + rotationView.byteOffset + (rotations.byteOffset ?? 0);
      const quaternion = (i: number) => Array.from({ length: 4 }, (_, axis) =>
        data.readFloatLE(rotationOffset + i * (rotationView.byteStride ?? 16) + axis * 4));
      const first = quaternion(0);
      const spread = Array.from({ length: rotations.count }, (_, i) =>
        1 - Math.abs(quaternion(i).reduce((dot, value, axis) => dot + value * first[axis]!, 0)));
      expect(Math.max(...spread)).toBeGreaterThan(0.005);
    });
  }

  it("gives sequential shopper IDs repeatable, distinct motion phases", () => {
    const phases = Array.from({ length: 20 }, (_, i) => characterAnimationPhase(`shopper-${i}`));
    expect(new Set(phases).size).toBe(20);
    expect(Math.max(...phases) - Math.min(...phases)).toBeGreaterThan(0.8);
    expect(characterAnimationPhase("shopper-7")).toBe(phases[7]);
  });
});
