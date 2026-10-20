import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { WALL_THICKNESS } from "./constants";
import type { DoorSpec } from "./buildStore";
import type { ShellMaterials } from "./materials";
import { personaRegistry } from "./personaRegistry";

interface Props {
  doors: DoorSpec[];
  materials: ShellMaterials;
}

const noRaycast = () => undefined;

// Automatic sliding doors: two glass leaves that part when a shopper is near.
function SlidingDoor({ door, materials }: { door: DoorSpec; materials: ShellMaterials }) {
  const root = useRef<THREE.Group>(null);
  const left = useRef<THREE.Group>(null);
  const right = useRef<THREE.Group>(null);
  const open = useRef(0);
  // Doors in the low camera-side walls show only in the first-person view.
  const h = 1.98;
  const leafW = door.width / 2 - 0.05;
  const geoms = useMemo(
    () => ({
      glass: new THREE.PlaneGeometry(leafW - 0.04, h - 0.06),
      stile: new THREE.BoxGeometry(0.03, h, 0.03),
      rail: new THREE.BoxGeometry(leafW, 0.05, 0.03),
    }),
    [leafW, h],
  );

  useFrame(({ camera }, delta) => {
    if (root.current && !door.tall) root.current.visible = !(camera as THREE.OrthographicCamera).isOrthographicCamera;
    let target = 0;
    for (let i = 0; i < personaRegistry.count; i++) {
      const dx = personaRegistry.xs[i]! - door.x;
      const dz = personaRegistry.zs[i]! - door.z;
      if (dx * dx + dz * dz < 1.6 * 1.6) {
        target = 1;
        break;
      }
    }
    open.current += (target - open.current) * Math.min(1, delta * 4);
    const slide = open.current * (leafW - 0.04);
    if (left.current) left.current.position.x = -leafW / 2 - slide;
    if (right.current) right.current.position.x = leafW / 2 + slide;
  });

  const leaf = (
    <>
      <mesh geometry={geoms.glass} material={materials.glass} position={[0, h / 2, 0]} raycast={noRaycast} />
      <mesh geometry={geoms.stile} material={materials.aluminum} position={[-leafW / 2 + 0.015, h / 2, 0]} raycast={noRaycast} />
      <mesh geometry={geoms.stile} material={materials.aluminum} position={[leafW / 2 - 0.015, h / 2, 0]} raycast={noRaycast} />
      <mesh geometry={geoms.rail} material={materials.aluminum} position={[0, 0.025, 0]} raycast={noRaycast} />
      <mesh geometry={geoms.rail} material={materials.aluminum} position={[0, h - 0.025, 0]} raycast={noRaycast} />
    </>
  );

  return (
    <group ref={root} position={[door.x, 0, door.z]} rotation={[0, door.yaw, 0]} visible={door.tall}>
      <group ref={left} position={[-leafW / 2, 0, -WALL_THICKNESS * 0.1]}>
        {leaf}
      </group>
      <group ref={right} position={[leafW / 2, 0, WALL_THICKNESS * 0.1]}>
        {leaf}
      </group>
    </group>
  );
}

export function AutoDoors({ doors, materials }: Props) {
  return (
    <>
      {doors.map((d) => (
        <SlidingDoor key={d.key} door={d} materials={materials} />
      ))}
    </>
  );
}
