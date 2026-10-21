import { useRef, useState, type RefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { TimelineEvent } from "@/shared/types/domain";
import type { PersonaFrame } from "../hooks/useSimulationLoop";
import { TrailLine } from "@/features/store-viewer/components/TrailLine";
import { AssetPersona } from "@/features/store-viewer/components/AssetPersona";

interface PersonaViewProps {
  id: string;
  frameMapRef: RefObject<Map<string, PersonaFrame>>;
  highlightId: string | null;
}

export function PersonaView({ id, frameMapRef, highlightId }: PersonaViewProps) {
  const initial = frameMapRef.current?.get(id);
  if (!initial) return null;

  const dimmed = highlightId != null && highlightId !== id;
  const emphasized = highlightId === id;

  return (
    <>
      <PersonaTrail
        id={id}
        frameMapRef={frameMapRef}
        color={initial.color}
        dimmed={dimmed}
        emphasized={emphasized}
        initialTrail={initial.trail}
      />
      <PersonaBody
        id={id}
        frameMapRef={frameMapRef}
        highlighted={emphasized}
        dimmed={dimmed}
        initial={initial}
      />
    </>
  );
}

interface PersonaTrailProps {
  id: string;
  frameMapRef: RefObject<Map<string, PersonaFrame>>;
  color: string;
  dimmed: boolean;
  emphasized: boolean;
  initialTrail: { x: number; y: number }[];
}

function PersonaTrail({ id, frameMapRef, color, dimmed, emphasized, initialTrail }: PersonaTrailProps) {
  const [trail, setTrail] = useState(initialTrail);

  const lastLenRef = useRef(initialTrail.length);
  const lastTailXRef = useRef(initialTrail[initialTrail.length - 1]?.x ?? Number.NaN);
  const lastTailYRef = useRef(initialTrail[initialTrail.length - 1]?.y ?? Number.NaN);

  useFrame(() => {
    const frame = frameMapRef.current?.get(id);
    if (!frame) return;
    const t = frame.trail;
    const tail = t[t.length - 1];
    const changed =
      t.length !== lastLenRef.current ||
      (tail !== undefined && (tail.x !== lastTailXRef.current || tail.y !== lastTailYRef.current));
    if (!changed) return;
    lastLenRef.current = t.length;
    if (tail) {
      lastTailXRef.current = tail.x;
      lastTailYRef.current = tail.y;
    }
    setTrail(t);
  });

  return <TrailLine trail={trail} color={color} dimmed={dimmed} emphasized={emphasized} />;
}

interface PersonaBodyProps {
  id: string;
  frameMapRef: RefObject<Map<string, PersonaFrame>>;
  highlighted: boolean;
  dimmed: boolean;
  initial: PersonaFrame;
}

function PersonaBody({ id, frameMapRef, highlighted, dimmed, initial }: PersonaBodyProps) {
  const groupRef = useRef<THREE.Group>(null);

  const [facing, setFacing] = useState(initial.facing);
  const [isMoving, setIsMoving] = useState(initial.isMoving);
  const [walkSpeed, setWalkSpeed] = useState(initial.walkSpeed);
  const [currentEvent, setCurrentEvent] = useState<TimelineEvent | null>(initial.currentEvent);

  const lastFacingRef = useRef(initial.facing);
  const lastMovingRef = useRef(initial.isMoving);
  const lastSpeedRef = useRef(initial.walkSpeed);
  const lastEventRef = useRef<TimelineEvent | null>(initial.currentEvent);

  useFrame(() => {
    const frame = frameMapRef.current?.get(id);
    if (!frame) return;

    if (groupRef.current) {
      groupRef.current.position.set(frame.x + 0.5, 0, frame.y + 0.5);
    }

    if (frame.facing !== lastFacingRef.current) {
      lastFacingRef.current = frame.facing;
      setFacing(frame.facing);
    }
    if (frame.isMoving !== lastMovingRef.current) {
      lastMovingRef.current = frame.isMoving;
      setIsMoving(frame.isMoving);
    }
    if (frame.walkSpeed !== lastSpeedRef.current) {
      lastSpeedRef.current = frame.walkSpeed;
      setWalkSpeed(frame.walkSpeed);
    }
    if (frame.currentEvent !== lastEventRef.current) {
      lastEventRef.current = frame.currentEvent;
      setCurrentEvent(frame.currentEvent);
    }
  });

  return (
    <group ref={groupRef} position={[initial.x + 0.5, 0, initial.y + 0.5]}>
      <AssetPersona
        personaId={id}
        gender={initial.gender}
        facing={facing}
        isMoving={isMoving}
        walkSpeed={walkSpeed}
        color={initial.color}
        label={initial.label}
        event={currentEvent}
        highlighted={highlighted}
        dimmed={dimmed}
      />
    </group>
  );
}
