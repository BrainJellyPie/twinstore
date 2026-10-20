import { useMemo } from "react";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import { useSimulationStore } from "@/stores/simulationStore";
import type { FixturePlan } from "./fixtureSpecs";

interface Props {
  plans: FixturePlan[];
}

// Invisible per-rack hit volumes (hover / click → rack detail) plus a hover
// outline and name label. Visual meshes stay non-raycastable siblings, so a
// pointer test only touches these boxes.
function RackHitbox({ plan }: { plan: FixturePlan }) {
  const setHoveredRackId = useSimulationStore((s) => s.setHoveredRackId);
  const setSelectedRackId = useSimulationStore((s) => s.setSelectedRackId);
  const hovered = useSimulationStore((s) => s.hoveredRackId === plan.rack.id);
  const { fp } = plan;
  const h = plan.height + (plan.kind === "gondola" || plan.kind === "reachIn" ? 0.2 : 0.05);
  const w = fp.w - 0.04;
  const d = fp.d - 0.04;
  const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(w + 0.04, h + 0.02, d + 0.04)), [w, h, d]);

  return (
    <group position={[fp.cx, 0, fp.cz]}>
      <mesh
        position={[0, h / 2, 0]}
        onPointerEnter={(e) => {
          e.stopPropagation();
          setHoveredRackId(plan.rack.id);
        }}
        onPointerLeave={(e) => {
          e.stopPropagation();
          if (useSimulationStore.getState().hoveredRackId === plan.rack.id) setHoveredRackId(null);
        }}
        onClick={(e) => {
          e.stopPropagation();
          setSelectedRackId(plan.rack.id);
        }}
      >
        <boxGeometry args={[w, h, d]} />
        <meshBasicMaterial visible={false} />
      </mesh>
      {hovered && (
        <>
          <lineSegments geometry={edges} position={[0, h / 2, 0]} raycast={() => undefined}>
            <lineBasicMaterial color="#38bdf8" transparent opacity={0.9} depthTest={false} />
          </lineSegments>
          {plan.rack.rack_name && (
            <Html position={[0, h + 0.25, 0]} center style={{ pointerEvents: "none" }}>
              <div className="glass rounded-lg px-2 py-1 text-[0.8rem] font-medium whitespace-nowrap text-foreground">
                {plan.rack.rack_name}
              </div>
            </Html>
          )}
        </>
      )}
    </group>
  );
}

export function RackHitboxes({ plans }: Props) {
  return (
    <>
      {plans
        .filter((p) => p.kind !== "door" && p.kind !== "none")
        .map((p) => (
          <RackHitbox key={p.rack.id} plan={p} />
        ))}
    </>
  );
}
