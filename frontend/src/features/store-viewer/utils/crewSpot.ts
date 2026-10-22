// Where a crew member stands in the store (world coordinates, as shoppers: tile x → x + 0.5) and which way they face.

import type { CustomerResult, Face, Rack } from "@/shared/types/domain";
import { lookYawForFace } from "../realistic/shopperPose";
import { rackBounds, rackWorldCenter } from "@/shared/utils/grid";
import type { CrewDoing } from "./crewAt";

export interface Spot { x: number; z: number; facing: number }

const NORMAL: Record<Face, [number, number]> = { E: [1, 0], W: [-1, 0], N: [0, -1], S: [0, 1] };
const GAP = 0.45;   // between a fixture's edge and where someone stands at it

/** For each till, the way to where its shoppers stand to pay (a unit vector); the cashier stands on the other side. */
export function shopperSides(tills: Rack[], customers: CustomerResult[]): Map<string, [number, number]> {
  const sums = new Map<string, [number, number, number]>();
  for (const customer of customers) {
    for (const event of customer.timeline) {
      if (event.action !== "pay" || !event.target_rack) continue;
      const sum = sums.get(event.target_rack) ?? [0, 0, 0];
      sums.set(event.target_rack, [sum[0] + event.x + 0.5, sum[1] + event.y + 0.5, sum[2] + 1]);
    }
  }
  const sides = new Map<string, [number, number]>();
  for (const till of tills) {
    const [cx, , cz] = rackWorldCenter(till);
    const sum = sums.get(till.id);
    const dx = sum ? sum[0] / sum[2] - cx : 0;
    const dz = sum ? sum[1] / sum[2] - cz : 1;
    const length = Math.hypot(dx, dz);
    sides.set(till.id, length > 1e-6 ? [dx / length, dz / length] : [0, 1]);
  }
  return sides;
}

function behind(till: Rack, side: [number, number]): Spot {
  const [cx, , cz] = rackWorldCenter(till);
  const { w, d } = rackBounds(till);
  const reach = Math.abs(side[0]) * w / 2 + Math.abs(side[1]) * d / 2 + GAP;
  return { x: cx - side[0] * reach, z: cz - side[1] * reach, facing: Math.atan2(side[0], side[1]) };
}

/** The spot for what a crew member is doing; null when there is nowhere sensible (an unknown fixture, no tills). */
export function crewSpot(doing: CrewDoing, racks: Map<string, Rack>, tills: Rack[], sides: Map<string, [number, number]>): Spot | null {
  if (doing.kind === "refill") {
    const rack = racks.get(doing.rackId);
    const face = doing.face as Face;
    if (!rack || !(face in NORMAL)) return null;
    const [cx, , cz] = rackWorldCenter(rack);
    const { w, d } = rackBounds(rack);
    const [nx, nz] = NORMAL[face];
    const reach = Math.abs(nx) * w / 2 + Math.abs(nz) * d / 2 + GAP;
    return { x: cx + nx * reach, z: cz + nz * reach, facing: lookYawForFace(face) };
  }
  const till = doing.kind === "till" ? racks.get(doing.rackId) : tills[doing.member];
  if (till) return behind(till, sides.get(till.id) ?? [0, 1]);
  // Waiting for work with no till of their own: beside the first cashier.
  const first = tills[0];
  if (!first) return null;
  const side = sides.get(first.id) ?? [0, 1];
  const spot = behind(first, side);
  const step = 0.6 * (doing.member - tills.length + 1);
  return { x: spot.x - side[1] * step, z: spot.z + side[0] * step, facing: spot.facing };
}
