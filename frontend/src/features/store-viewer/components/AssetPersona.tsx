import { Suspense, useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, useAnimations } from "@react-three/drei";
import { ErrorBoundary } from "react-error-boundary";
import * as THREE from "three";
import type { TimelineEvent } from "@/shared/types/domain";
import { characterAssetFor, characterAnimationPhase, realisticCharacterAssetFor } from "@/shared/utils/assetMap";
import { useGlbModel } from "@/shared/hooks/useGlbModel";
import { formatMoney } from "@/shared/utils/money";
import { useSimulationStore } from "@/stores/simulationStore";
import { useI18n } from "@/shared/i18n/i18n";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { M, PERSONA_SCALE } from "../realistic/constants";
import { angleDelta } from "../realistic/shopperPose";
import { shopperBlinkWeight } from "../realistic/shopperBlink";
import { shopperGazeOffset } from "../realistic/shopperGaze";
import { shopperWalkTimeScale } from "../realistic/shopperGait";

const CHARACTER_TARGET_HEIGHT = 0.6;

function animationFor(isMoving: boolean, event: TimelineEvent | null): string {
  if (event?.action === "buy") return "interact-right";
  if (event?.action === "pay") return "jump";
  if (isMoving) return "walk";
  return "idle";
}

interface SpeechBubbleProps {
  event: TimelineEvent;
}

function SpeechBubble({ event }: SpeechBubbleProps) {
  const { t } = useI18n();
  const isBuy = event.action === "buy";
  const isPay = event.action === "pay";
  const currency = useSimulationStore((s) => s.currency);
  const qty = event.quantity ?? 1;
  const price = `${qty > 1 ? `${qty}× ` : ""}${formatMoney(event.price, currency)}`;
  const text =
    isBuy && event.product_name
      ? `💰 ${event.product_name} · ${price}`
      : isPay
        ? `💳 ${event.description || t("bubblePay")}`
        : event.description;
  const bg = isBuy ? "rgba(255, 240, 200, 0.95)" : isPay ? "rgba(220, 240, 255, 0.95)" : "rgba(255,255,255,0.92)";
  const border = isBuy ? "#d4a42a" : isPay ? "#3b82c4" : "#ccc";
  return (
    <Html position={[0, CHARACTER_TARGET_HEIGHT + 0.55, 0]} center zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
      <div
        style={{
          padding: "4px 8px",
          background: bg,
          border: `1px solid ${border}`,
          borderRadius: 6,
          fontSize: 11,
          color: "#333",
          boxShadow: "0 2px 6px rgba(0,0,0,0.18)",
          whiteSpace: "nowrap",
        }}
      >
        {text}
      </div>
    </Html>
  );
}

interface AssetPersonaProps {
  personaId: string;
  gender?: string;
  facing: number;
  isMoving: boolean;
  walkSpeed?: number;
  color: string;
  label: string;
  event: TimelineEvent | null;
  highlighted?: boolean;
  dimmed?: boolean;
}

interface CharacterMeshProps {
  url: string;
  animName: string;
  realistic: boolean;
  personaId: string;
  walkSpeed?: number;
}

function UnavailableCharacter({ realistic, color }: { realistic: boolean; color: string }) {
  return (
    <group name="shopper-placeholder" scale={realistic ? M / PERSONA_SCALE : CHARACTER_TARGET_HEIGHT / 1.75}>
      <mesh position={[0, 1, 0]} castShadow receiveShadow>
        <capsuleGeometry args={[0.2, 0.6, 4, 8]} />
        <meshStandardMaterial color={color} roughness={0.9} />
      </mesh>
      <mesh position={[0, 1.625, 0]} castShadow receiveShadow>
        <sphereGeometry args={[0.125, 12, 8]} />
        <meshStandardMaterial color="#c5c8ca" roughness={0.9} />
      </mesh>
      {[-1, 1].map((side) => (
        <group key={side}>
          <mesh position={[side * 0.1, 0.3, 0]} castShadow receiveShadow>
            <cylinderGeometry args={[0.07, 0.07, 0.6, 8]} />
            <meshStandardMaterial color={color} roughness={0.9} />
          </mesh>
          <mesh position={[side * 0.25, 1.05, 0]} castShadow receiveShadow>
            <capsuleGeometry args={[0.055, 0.55, 4, 8]} />
            <meshStandardMaterial color={color} roughness={0.9} />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function CharacterMesh({ url, animName, realistic, personaId, walkSpeed }: CharacterMeshProps) {
  const { clone, bbox, offset, animations } = useGlbModel(url, {
    skinned: true,
    castShadow: true,
    receiveShadow: realistic,
  });
  const rawH = bbox.size.y > 0.001 ? bbox.size.y : 1;
  // Rocketbox is authored in metres. Preserve each avatar's actual height;
  // PersonaRig applies the parent scale to labels and the whole shopper group.
  const scale = realistic ? M / PERSONA_SCALE : CHARACTER_TARGET_HEIGHT / rawH;

  const { actions, mixer } = useAnimations(animations, clone);
  const previousAction = useRef<THREE.AnimationAction | null>(null);
  const motionBlend = useRef<{
    elapsed: number;
    entries: { action: THREE.AnimationAction; from: number; to: number }[];
  } | null>(null);
  // Set weights before useAnimations advances the mixer at the default priority.
  useFrame((_, delta) => {
    const blend = motionBlend.current;
    if (!blend || !usePlaybackControlStore.getState().playing) return;
    blend.elapsed += delta;
    const progress = Math.min(blend.elapsed / 0.15, 1);
    for (const { action, from, to } of blend.entries) action.setEffectiveWeight(from + (to - from) * progress);
    if (progress === 1) {
      for (const { action, to } of blend.entries) if (to === 0) action.stop();
      motionBlend.current = null;
    }
  }, -1);
  const playing = usePlaybackControlStore((s) => s.playing);
  const playbackSpeed = usePlaybackControlStore((s) => s.speed);
  const facialTargets = useMemo(() => {
    const targets: { weights: number[]; indices: Partial<Record<"blink" | "lookLeft" | "lookRight" | "lookUp" | "lookDown", number>> }[] = [];
    if (realistic) clone.traverse((object) => {
      if (!(object instanceof THREE.Mesh)) return;
      if (object.morphTargetDictionary && object.morphTargetInfluences) {
        targets.push({ weights: object.morphTargetInfluences, indices: object.morphTargetDictionary });
      }
    });
    return targets;
  }, [clone, realistic]);
  const facialTime = useRef(0);
  const blinkPhase = characterAnimationPhase(`${personaId}:blink`);
  const gazePhase = characterAnimationPhase(`${personaId}:gaze`);
  useFrame((_, delta) => {
    if (!realistic || !usePlaybackControlStore.getState().playing) return;
    // A delta cap would stretch blinks and fixations on slow frames.
    facialTime.current += delta;
    const blink = shopperBlinkWeight(facialTime.current, blinkPhase);
    // Gaze shapes include eyelid movement. Fade them under a blink so the
    // independent authored deformations cannot pull a closed eyelid open.
    const horizontal = shopperGazeOffset(facialTime.current, gazePhase) * (1 - blink);
    const vertical = shopperGazeOffset(facialTime.current, gazePhase, true) * (1 - blink);
    for (const { weights, indices } of facialTargets) {
      if (indices.blink !== undefined) weights[indices.blink] = blink;
      if (indices.lookLeft !== undefined) weights[indices.lookLeft] = Math.max(0, -horizontal);
      if (indices.lookRight !== undefined) weights[indices.lookRight] = Math.max(0, horizontal);
      if (indices.lookDown !== undefined) weights[indices.lookDown] = Math.max(0, -vertical);
      if (indices.lookUp !== undefined) weights[indices.lookUp] = Math.max(0, vertical);
    }
  });

  useEffect(() => {
    mixer.timeScale = realistic && !playing ? 0 : 1;
  }, [mixer, playing, realistic]);

  useEffect(() => {
    const walk = actions.walk;
    if (walk) walk.setEffectiveTimeScale(realistic ? shopperWalkTimeScale(url, walkSpeed, playbackSpeed, walk.getClip().duration) : 1);
  }, [actions, realistic, url, walkSpeed, playbackSpeed]);

  useEffect(() => () => {
    mixer.stopAllAction();
    // No uncacheRoot: useAnimations keeps its actions and replays them after a
    // remount (StrictMode), and three.js cannot rebind an uncached action's
    // bindings. The mixer is per shopper and is collected with it.
    previousAction.current = null;
    motionBlend.current = null;
    const skeletons = new Set<THREE.Skeleton>();
    clone.traverse((object) => {
      if (object instanceof THREE.SkinnedMesh) skeletons.add(object.skeleton);
    });
    // SkeletonUtils gives each shopper their own GPU bone texture. The cached
    // model still owns the geometry and PBR textures shared by the crowd.
    for (const skeleton of skeletons) skeleton.dispose();
  }, [clone, mixer]);

  useEffect(() => {
    const action = actions[animName];
    if (!action) return;
    const previous = previousAction.current;
    const paused = realistic && !usePlaybackControlStore.getState().playing;
    motionBlend.current = null;
    if (realistic && previous && previous !== action && !paused) {
      // Capture every visible contribution before changing the target. Starting
      // a new crossFadeFrom(previous) would reset that action's weight to one.
      const entries = Object.values(actions).flatMap(other => {
        if (!other) return [];
        const from = other.enabled && other.isScheduled() ? other.getEffectiveWeight() : 0;
        if (from === 0 && other !== action) { other.stop(); return []; }
        return [{ action: other, from, to: other === action ? 1 : 0 }];
      });
      if (!action.enabled || !action.isScheduled()) {
        action.reset();
        action.time = action.getClip().duration * characterAnimationPhase(personaId);
      }
      action.play();
      for (const entry of entries) entry.action.stopFading().setEffectiveWeight(entry.from);
      motionBlend.current = { elapsed: 0, entries };
    } else {
      // Initial poses and paused seeks must not retain earlier contributors.
      if (realistic) mixer.stopAllAction();
      action.reset().stopFading().setEffectiveWeight(1).play();
      if (realistic) action.time = action.getClip().duration * characterAnimationPhase(personaId);
      else if (previous && previous !== action) action.crossFadeFrom(previous, 0.15, false);
    }
    // A paused mixer cannot advance a fade from zero weight. Apply the first
    // pose immediately so newly loaded shoppers never remain in their bind pose.
    mixer.update(0);
    previousAction.current = action;
  }, [animName, actions, mixer, realistic, personaId]);

  return (
    <group scale={scale}>
      <primitive object={clone} position={offset} />
    </group>
  );
}

export function AssetPersona({
  personaId,
  gender,
  facing,
  isMoving,
  walkSpeed,
  color,
  label,
  event,
  highlighted,
  dimmed,
}: AssetPersonaProps) {
  const realistic = useSimulationStore((s) => s.graphicsMode === "realistic");
  // Once the day shows Closed, a shopper still finishing up keeps no speech bubble on screen.
  const closed = useSimulationMetricsStore((s) => s.finished);
  const url = realistic ? realisticCharacterAssetFor(personaId, gender) : characterAssetFor(personaId, gender);
  const scale = highlighted && !realistic ? 1.2 : 1;
  const idleName = characterAnimationPhase(`${personaId}:idle-motion`) < 0.5 ? "idle" : "wait";
  const animName = realistic
    ? (isMoving ? "walk" : event?.action === "browse" ? "browse" : idleName)
    : animationFor(isMoving, event);
  const isPaying = !realistic && event?.action === "pay";

  const bounceRef = useRef<THREE.Group>(null);
  const turnRef = useRef<THREE.Group>(null);
  const turnReady = useRef(false);
  useFrame((_, delta) => {
    const turn = turnRef.current;
    if (turn) {
      if (!turnReady.current || !realistic || !usePlaybackControlStore.getState().playing) {
        turn.rotation.y = facing;
        turnReady.current = true;
      } else {
        turn.rotation.y += angleDelta(turn.rotation.y, facing) * (1 - Math.exp(-12 * delta));
      }
    }
    if (!bounceRef.current) return;
    if (isPaying) {
      const t = (performance.now() % 400) / 400;
      bounceRef.current.position.y = Math.sin(t * Math.PI) * 0.12;
    } else {
      bounceRef.current.position.y = 0;
    }
  });

  return (
    <group scale={scale}>
      <group ref={bounceRef}>
      <group ref={turnRef} name="shopper-heading">
        <ErrorBoundary key={url} fallback={<UnavailableCharacter realistic={realistic} color={color} />}>
          <Suspense fallback={null}>
            <CharacterMesh url={url} animName={animName} realistic={realistic} personaId={personaId} walkSpeed={walkSpeed} />
          </Suspense>
        </ErrorBoundary>
      </group>
      {highlighted && (
        <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.35, 0.45, 32]} />
          <meshBasicMaterial color={color} transparent opacity={0.8} />
        </mesh>
      )}
      <Html position={[0, CHARACTER_TARGET_HEIGHT + 0.15, 0]} center zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color,
            whiteSpace: "nowrap",
            textShadow: "0 0 3px #fff, 0 0 3px #fff, 0 0 3px #fff",
            opacity: dimmed ? 0.4 : 1,
          }}
        >
          {label}
        </div>
      </Html>
      {event?.description && !dimmed && !closed && <SpeechBubble event={event} />}
      </group>
    </group>
  );
}
