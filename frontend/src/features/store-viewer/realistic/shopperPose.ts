// Shopper pose at an arbitrary playback time, computed straight from a
// customer's timeline (same interpolation as useSimulationLoop). Pure, so an
// offline renderer can place an egocentric camera for any (customer, time) pair
// without running the playback loop.

import type { CustomerResult, Face, TimelineEvent } from "@/shared/types/domain";
import { parseTimeToSeconds } from "@/features/playback/utils/playback";

export interface ShopperPose {
  personaId: string;
  // Tile-centre world coordinates (store-local; grid x → x + 0.5, grid y → z + 0.5).
  x: number;
  z: number;
  // Direction of travel / last travel, as a three.js yaw (atan2(dx, dz)).
  heading: number;
  // Where the eyes point: towards the shelf while browsing/buying, else heading.
  lookYaw: number;
  // Downward pitch (radians, positive = looking down).
  pitch: number;
  moving: boolean;
  event: TimelineEvent | null;
}

const LOOK_AT_FACE: Record<Face, number> = {
  // Shopper stands on the face side of the rack and looks back against the normal.
  S: Math.atan2(0, -1), // looking -Z
  N: Math.atan2(0, 1), // looking +Z
  E: Math.atan2(-1, 0), // looking -X
  W: Math.atan2(1, 0), // looking +X
};

export function lookYawForFace(face: Face): number {
  return LOOK_AT_FACE[face];
}

export function facingForEvent(heading: number, moving: boolean, event: Pick<TimelineEvent, "action" | "face">): number {
  return !moving && (event.action === "browse" || event.action === "buy") && event.face
    ? LOOK_AT_FACE[event.face]
    : heading;
}

export function positionBetweenEvents(prev: TimelineEvent, next: TimelineEvent | null, time: number): { x: number; y: number; moving: boolean; speed: number } {
  if (!next || next.elapsed_sec <= prev.elapsed_sec || (next.x === prev.x && next.y === prev.y)) {
    return { x: prev.x, y: prev.y, moving: false, speed: 0 };
  }
  // These timestamps mark the start of a stop. Wander-glance timestamps mark
  // its end in timeline_builder, so their duration must not be applied again.
  const stopped = prev.action === "browse" || prev.action === "buy" || prev.action === "pay";
  const dwell = stopped && Number.isFinite(prev.duration) ? Math.max(0, prev.duration) : 0;
  const departure = Math.min(next.elapsed_sec, prev.elapsed_sec + dwell);
  const moving = time >= departure && departure < next.elapsed_sec;
  const fraction = moving ? Math.min(1, (time - departure) / (next.elapsed_sec - departure)) : 0;
  const speed = moving ? Math.hypot(next.x - prev.x, next.y - prev.y) / (next.elapsed_sec - departure) : 0;
  return { x: prev.x + (next.x - prev.x) * fraction, y: prev.y + (next.y - prev.y) * fraction, moving, speed };
}

export function shopperPoseAt(customer: CustomerResult, timeSec: number): ShopperPose | null {
  const tl = customer.timeline;
  if (!tl.length) return null;
  const rel = timeSec - parseTimeToSeconds(customer.arrival_time);
  if (rel < 0) return null;

  // Last event with elapsed_sec <= rel (binary search; timelines are sorted).
  let lo = 0;
  let hi = tl.length - 1;
  let prevIdx = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (tl[mid]!.elapsed_sec <= rel) {
      prevIdx = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  if (prevIdx < 0) return null;
  const prev = tl[prevIdx]!;
  if (prev.action === "exit") return null;

  const next = prevIdx + 1 < tl.length ? tl[prevIdx + 1]! : null;
  const { x, y, moving } = positionBetweenEvents(prev, next, rel);

  let heading = 0;
  if (moving) {
    heading = Math.atan2(next!.x - prev.x, next!.y - prev.y);
  } else {
    for (let i = prevIdx; i > 0; i--) {
      const a = tl[i - 1]!;
      const b = tl[i]!;
      if (a.x !== b.x || a.y !== b.y) {
        heading = Math.atan2(b.x - a.x, b.y - a.y);
        break;
      }
    }
  }

  const browsing = !moving && (prev.action === "browse" || prev.action === "buy") && !!prev.face;
  const lookYaw = facingForEvent(heading, moving, prev);
  return {
    personaId: customer.persona_id,
    x: x + 0.5,
    z: y + 0.5,
    heading,
    lookYaw,
    pitch: browsing ? 0.2 : 0.1,
    moving,
    event: prev,
  };
}

// Shoppers in the store at `timeSec`, in timeline order (same order as playback).
export function activeShoppers(customers: CustomerResult[], day: number, timeSec: number): ShopperPose[] {
  const out: ShopperPose[] = [];
  for (const c of customers) {
    if ((c.day ?? 1) !== day) continue;
    const pose = shopperPoseAt(c, timeSec);
    if (pose) out.push(pose);
  }
  return out;
}

// Shortest signed angular difference b - a, in (-π, π].
export function angleDelta(a: number, b: number): number {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d <= -Math.PI) d += Math.PI * 2;
  return d;
}
