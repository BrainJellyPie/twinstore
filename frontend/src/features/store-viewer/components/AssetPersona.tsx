import { Suspense, useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, useAnimations, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import type { TimelineEvent } from "@/shared/types/domain";
import { characterAssetFor, characterAnimationPhase, realisticCharacterAssetFor, ALL_CHARACTER_ASSETS } from "@/shared/utils/assetMap";
import { useGlbModel } from "@/shared/hooks/useGlbModel";
import { formatMoney } from "@/shared/utils/money";
import { useSimulationStore } from "@/stores/simulationStore";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { M, PERSONA_SCALE } from "../realistic/constants";
import { angleDelta } from "../realistic/shopperPose";
import { shopperBlinkWeight } from "../realistic/shopperBlink";
import { shopperGazeOffset } from "../realistic/shopperGaze";

ALL_CHARACTER_ASSETS.forEach((url) => useGLTF.preload(url));

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
  const isBuy = event.action === "buy";
  const isPay = event.action === "pay";
  const currency = useSimulationStore((s) => s.currency);
  const qty = event.quantity ?? 1;
  const price = `${qty > 1 ? `${qty}× ` : ""}${formatMoney(event.price, currency)}`;
  const text =
    isBuy && event.product_name
      ? `💰 ${event.product_name} · ${price}`
      : isPay
        ? `💳 ${event.description || "Pay"}`
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
}

function CharacterMesh({ url, animName, realistic, personaId }: CharacterMeshProps) {
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
  const playing = usePlaybackControlStore((s) => s.playing);
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
    facialTime.current += Math.min(delta, 0.1);
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

  useEffect(() => () => {
    mixer.stopAllAction();
    mixer.uncacheRoot(clone);
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
    action.reset().stopFading().setEffectiveWeight(1).play();
    if (realistic) action.time = action.getClip().duration * characterAnimationPhase(personaId);
    if (previous && previous !== action) {
      if (!realistic || usePlaybackControlStore.getState().playing) action.crossFadeFrom(previous, 0.15, false);
      else previous.stop();
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
  color,
  label,
  event,
  highlighted,
  dimmed,
}: AssetPersonaProps) {
  const realistic = useSimulationStore((s) => s.graphicsMode === "realistic");
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
        turn.rotation.y += angleDelta(turn.rotation.y, facing) * (1 - Math.exp(-12 * Math.min(delta, 0.1)));
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
        <Suspense fallback={null}>
          <CharacterMesh key={url} url={url} animName={animName} realistic={realistic} personaId={personaId} />
        </Suspense>
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
      {event && !dimmed && <SpeechBubble event={event} />}
      </group>
    </group>
  );
}
