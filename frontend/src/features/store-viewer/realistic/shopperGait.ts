import { M } from "./constants";

// Metres of root travel in the pinned Rocketbox walk clips before the converter
// removes horizontal motion. Reproduce with scripts/measure_rocketbox_gait.py.
const WALK_DISTANCE = { female: 1.5966254519809726, male: 1.4958643913269043 };

export function shopperWalkTimeScale(url: string, walkSpeed: number | undefined, playbackSpeed: number, clipDuration: number): number {
  // Standalone previews do not have a route velocity.
  if (walkSpeed === undefined) return 1;
  if (!Number.isFinite(walkSpeed) || walkSpeed <= 0 || !Number.isFinite(playbackSpeed) || playbackSpeed <= 0
    || !Number.isFinite(clipDuration) || clipDuration <= 0) return 0;
  const family = /\/(female|male)-\d+\.glb$/.exec(url)?.[1];
  if (family !== "female" && family !== "male") return 1;
  const rate = walkSpeed * playbackSpeed * clipDuration / (M * WALK_DISTANCE[family]);
  // Match real-time travel where possible; compressed simulation time must not
  // turn the legs into a blur. Facial and stationary motion keep their own rate.
  return Math.min(1.75, Math.max(0.2, rate));
}
