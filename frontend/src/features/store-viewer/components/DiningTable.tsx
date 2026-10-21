import { useMemo } from "react";
import { diningTableParts } from "../realistic/diningTable";

export function DiningTable({ width, depth, hovered = false }: { width: number; depth: number; hovered?: boolean }) {
  const parts = useMemo(() => diningTableParts(width, depth), [width, depth]);
  return <group>{parts.map((part, i) => <mesh key={i} position={part.position} castShadow receiveShadow>
    <boxGeometry args={part.size} />
    <meshStandardMaterial color={part.material === "wood" ? "#b77d49" : "#48434a"}
      roughness={0.65} emissive="#ffffff" emissiveIntensity={hovered ? 0.15 : 0} />
  </mesh>)}</group>;
}
