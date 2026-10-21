import { useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import type { Rack } from "@/shared/types/domain";
import { useGlbModel } from "@/shared/hooks/useGlbModel";
import { computeBbox } from "@/shared/utils/glbHelpers";

const WALL_URL = "/assets/market/wall.glb";
const WALL_CORNER_URL = "/assets/market/wall-corner.glb";
const WALL_DOOR_URL = "/assets/market/wall-door-rotate.glb";

// Compute a shared scale from wall.glb. All wall parts (corner, door) must use this
// scale so sizes match. We do not use useGlbModel here because we need a measurement
// probe, not a render clone.
function useWallScale() {
  const { scene } = useGLTF(WALL_URL);
  return useMemo(() => {
    const probe = scene.clone(true);
    probe.updateMatrixWorld(true);
    const { size } = computeBbox(probe);
    const longest = Math.max(size.x, size.z) || 1;
    const thin = Math.min(size.x, size.z) || 0.1;
    const scale = 1 / longest;
    return { scale, thickness: thin * scale };
  }, [scene]);
}

interface WallPieceProps {
  url: string;
  position: [number, number, number];
  rotationY: number;
  scale: number;
  overrideMap?: THREE.Texture | null;
}

function WallPiece({ url, position, rotationY, scale, overrideMap }: WallPieceProps) {
  const { clone, offset } = useGlbModel(url, { overrideMap });

  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      <group scale={scale}>
        <primitive object={clone} position={offset} />
      </group>
    </group>
  );
}

interface AssetWallProps {
  width: number;
  depth: number;
  racks: Rack[];
  variationTexture?: THREE.Texture | null;
}

export function AssetWall({ width, depth, racks, variationTexture }: AssetWallProps) {
  const { scale, thickness } = useWallScale();

  const doorCells = useMemo(() => {
    const set = new Set<string>();
    for (const f of racks) {
      if (f.type !== "entrance" && f.type !== "exit") continue;
      const [gx, gy] = f.position;
      for (let row = 0; row < f.shape.length; row++) {
        const arr = f.shape[row];
        if (!arr) continue;
        for (let col = 0; col < arr.length; col++) {
          if (arr[col]) set.add(`${gx + col},${gy + row}`);
        }
      }
    }
    return set;
  }, [racks]);

  const pieces: { key: string; url: string; position: [number, number, number]; rotationY: number }[] = [];

  // Push the wall body center outside the grid boundary by ~thickness so trim/detail
  // doesn't clip into the floor.
  const wallCenterOffset = thickness * 0.5;

  // Corner piece sits at the outer corner of the two walls, centered on the virtual
  // (-1, -1) cell.
  pieces.push({
    key: "corner-0-0",
    url: WALL_CORNER_URL,
    position: [-wallCenterOffset * 0.67, 0, -wallCenterOffset * 0.67],
    rotationY: Math.PI / 2,
  });

  for (let x = 0; x < width; x++) {
    const isDoor = doorCells.has(`${x},0`);
    pieces.push({
      key: `north-${x}`,
      url: isDoor ? WALL_DOOR_URL : WALL_URL,
      position: [x + 0.5, 0, -wallCenterOffset],
      rotationY: 0,
    });
  }

  for (let y = 0; y < depth; y++) {
    const isDoor = doorCells.has(`0,${y}`);
    pieces.push({
      key: `west-${y}`,
      url: isDoor ? WALL_DOOR_URL : WALL_URL,
      position: [-wallCenterOffset, 0, y + 0.5],
      rotationY: Math.PI / 2,
    });
  }

  return (
    <group>
      {pieces.map((p) => (
        <WallPiece
          key={p.key}
          url={p.url}
          position={p.position}
          rotationY={p.rotationY}
          scale={scale}
          overrideMap={variationTexture}
        />
      ))}
    </group>
  );
}
