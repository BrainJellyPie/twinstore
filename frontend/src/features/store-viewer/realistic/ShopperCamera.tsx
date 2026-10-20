import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { PerspectiveCamera } from "@react-three/drei";
import * as THREE from "three";
import type { CustomerResult, Rack } from "@/shared/types/domain";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { activeShoppers, angleDelta, type ShopperPose } from "./shopperPose";
import { createClock, stepClock } from "./playbackClock";
import { nearestPersona, personaRegistry } from "./personaRegistry";
import { useRealisticSettings, sameIds } from "./graphicsSettings";

interface Props {
  active: boolean;
  customers: CustomerResult[] | null;
  racks: Rack[];
  width: number;
  depth: number;
  minTime: number;
  maxTime: number;
  eyeHeight: number;
  fov?: number;
}

interface Smooth {
  init: boolean;
  x: number;
  z: number;
  yaw: number;
  pitch: number;
  id: string | null;
}

// First-person "shopper view": a perspective camera at eye height that follows
// a shopper (the selected one, else the first in the store), looking where they
// walk — or at the shelf face while they browse. With no shoppers it stands
// inside the entrance looking into the store. Reusable for egocentric renders:
// pose logic lives in shopperPose.ts and the clock in playbackClock.ts.
export function ShopperCamera({ active, customers, racks, width, depth, minTime, maxTime, eyeHeight, fov = 68 }: Props) {
  const cam = useRef<THREE.PerspectiveCamera>(null);
  const clock = useRef(createClock());
  const smooth = useRef<Smooth>({ init: false, x: 0, z: 0, yaw: 0, pitch: 0, id: null });
  const frameCount = useRef(0);
  const posesRef = useRef<ShopperPose[]>([]);

  // Inside-the-entrance fallback pose (store-local).
  const fallback = useMemo(() => {
    const door = racks.find((r) => r.type === "entrance") ?? racks.find((r) => r.type === "exit");
    const x = door ? door.position[0] + 0.5 : width / 2;
    const z = door ? door.position[1] + 0.5 : depth - 0.5;
    const yaw = Math.atan2(width / 2 - x, depth / 2 - z);
    return { x, z, yaw };
  }, [racks, width, depth]);

  useEffect(() => {
    if (active) return;
    personaRegistry.hideNear = null;
    smooth.current.init = false;
  }, [active]);

  useFrame((_, rawDelta) => {
    const delta = Math.min(rawDelta, 0.1);
    const ctrl = usePlaybackControlStore.getState();
    const metrics = useSimulationMetricsStore.getState();
    const t = stepClock(clock.current, delta, {
      playing: ctrl.playing,
      speed: ctrl.speed,
      day: ctrl.currentDay,
      currentMinute: metrics.currentMinute,
      finished: metrics.finished,
      minTime,
      maxTime,
    });
    if (!active || !cam.current) return;

    // Pose list refresh (every 4th frame is plenty for selection).
    frameCount.current = (frameCount.current + 1) % 4;
    if (frameCount.current === 0 || !posesRef.current.length) {
      posesRef.current = customers?.length ? activeShoppers(customers, ctrl.currentDay, t) : [];
      const ids = posesRef.current.map((p) => p.personaId);
      const settings = useRealisticSettings.getState();
      if (!sameIds(ids, settings.activeShopperIds)) settings.setActiveShopperIds(ids);
    }
    const followId = useSimulationStore.getState().followPersonaId;
    const poses = posesRef.current;
    const pose = poses.find((p) => p.personaId === followId) ?? poses[0] ?? null;

    let tx = fallback.x;
    let tz = fallback.z;
    let tyaw = fallback.yaw;
    let tpitch = 0.08;
    if (pose) {
      // Snap to the rendered persona when one is close (exact playback time).
      const i = nearestPersona(pose.x, pose.z, 1.2);
      tx = i >= 0 ? personaRegistry.xs[i]! : pose.x;
      tz = i >= 0 ? personaRegistry.zs[i]! : pose.z;
      tyaw = pose.lookYaw;
      tpitch = pose.pitch;
      personaRegistry.hideNear = { x: tx, z: tz };
    } else {
      personaRegistry.hideNear = null;
    }

    const s = smooth.current;
    const id = pose?.personaId ?? null;
    if (!s.init || s.id !== id) {
      // Jump cut when the followed shopper changes.
      s.init = true;
      s.id = id;
      s.x = tx;
      s.z = tz;
      s.yaw = tyaw;
      s.pitch = tpitch;
    } else {
      const kp = 1 - Math.exp(-delta * 7);
      const ky = 1 - Math.exp(-delta * 4);
      s.x += (tx - s.x) * kp;
      s.z += (tz - s.z) * kp;
      s.yaw += angleDelta(s.yaw, tyaw) * ky;
      s.pitch += (tpitch - s.pitch) * ky;
    }

    // Store group is offset by (-width/2, -depth/2).
    const wx = s.x - width / 2;
    const wz = s.z - depth / 2;
    // Eyes slightly forward of the body centre so the head isn't in view.
    const fx = Math.sin(s.yaw);
    const fz = Math.cos(s.yaw);
    const c = cam.current;
    c.position.set(wx + fx * 0.08, eyeHeight, wz + fz * 0.08);
    c.lookAt(wx + fx * 2, eyeHeight - Math.tan(s.pitch) * 2, wz + fz * 2);
  });

  if (!active) return null;
  return <PerspectiveCamera ref={cam} makeDefault fov={fov} near={0.03} far={80} />;
}
