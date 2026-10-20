import { useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, useAnimations, useGLTF } from "@react-three/drei";
import * as THREE from "three";
import type { TimelineEvent } from "@/shared/types/domain";
import { characterAssetFor, ALL_CHARACTER_ASSETS } from "@/shared/utils/assetMap";
import { useGlbModel } from "@/shared/hooks/useGlbModel";
import { formatMoney } from "@/shared/utils/money";
import { useSimulationStore } from "@/stores/simulationStore";

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
}

function CharacterMesh({ url, animName }: CharacterMeshProps) {
  const { clone, bbox, offset, animations } = useGlbModel(url, {
    skinned: true,
    castShadow: true,
    receiveShadow: false,
  });
  const rawH = bbox.size.y > 0.001 ? bbox.size.y : 1;
  const scale = CHARACTER_TARGET_HEIGHT / rawH;

  const { actions } = useAnimations(animations, clone);

  useEffect(() => {
    const action = actions[animName];
    if (!action) return;
    action.reset().fadeIn(0.15).play();
    return () => {
      action.fadeOut(0.15);
    };
  }, [animName, actions]);

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
  const url = characterAssetFor(personaId, gender);
  const scale = highlighted ? 1.2 : 1;
  const animName = animationFor(isMoving, event);
  const isPaying = event?.action === "pay";

  const bounceRef = useRef<THREE.Group>(null);
  useFrame(() => {
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
      <group rotation={[0, facing, 0]}>
        <CharacterMesh url={url} animName={animName} />
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
