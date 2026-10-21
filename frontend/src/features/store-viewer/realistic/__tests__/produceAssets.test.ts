/// <reference types="node" />
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

interface ProduceModel {
  nodes: { name: string; mesh: number }[];
  meshes: { primitives: { attributes: { POSITION: number; NORMAL: number }; indices: number }[] }[];
  accessors: { count: number; min?: number[]; max?: number[]; bufferView: number; byteOffset?: number }[];
  bufferViews: { byteOffset: number; byteStride?: number }[];
}

it("ships bounded banana LODs with unit normals and a bottom-centred unit footprint", () => {
  const data = readFileSync("public/assets/produce/bananas.glb");
  const length = data.readUInt32LE(12);
  const model = JSON.parse(data.subarray(20, 20 + length).toString()) as ProduceModel;
  for (const [name, budget] of [["bananas-coarse", 300], ["bananas-fine", 1600]] as const) {
    const node = model.nodes.find((node) => node.name === name)!;
    expect(node).toBeDefined();
    const primitive = model.meshes[node.mesh]!.primitives[0]!;
    expect(model.accessors[primitive.indices]!.count / 3).toBeLessThanOrEqual(budget);
    const position = model.accessors[primitive.attributes.POSITION]!;
    expect(position.min).toEqual([-0.5, 0, -0.5]);
    expect(position.max).toEqual([0.5, 1, 0.5]);
    const normal = model.accessors[primitive.attributes.NORMAL]!;
    const view = model.bufferViews[normal.bufferView]!;
    const offset = 28 + length + view.byteOffset + (normal.byteOffset ?? 0);
    for (let i = 0; i < normal.count; i++) {
      const start = offset + i * (view.byteStride ?? 12);
      expect(Math.hypot(data.readFloatLE(start), data.readFloatLE(start + 4), data.readFloatLE(start + 8))).toBeCloseTo(1, 4);
    }
  }
});
