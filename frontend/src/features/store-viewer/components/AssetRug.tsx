import type { Rack } from "@/shared/types/domain";
import { rackBounds, rackWorldCenter } from "@/shared/utils/grid";
import { useGlbModel } from "@/shared/hooks/useGlbModel";

const RUG_URL = "/assets/market/rugRectangle.glb";

interface RugInstanceProps {
  position: [number, number, number];
  tilesW: number;
  tilesD: number;
}

// Rugs are flat detail — non-uniform scale stretches per axis to match cell counts.
// Y is left near the original ratio (a thin sheet, effectively ~0).
function RugInstance({ position, tilesW, tilesD }: RugInstanceProps) {
  const { clone, bbox, offset } = useGlbModel(RUG_URL, {
    castShadow: false,
    receiveShadow: true,
  });
  const scaleX = tilesW / (bbox.size.x || 1);
  const scaleZ = tilesD / (bbox.size.z || 1);

  return (
    <group position={position}>
      <group scale={[scaleX, Math.min(scaleX, scaleZ), scaleZ]}>
        <primitive object={clone} position={offset} />
      </group>
    </group>
  );
}

interface AssetRugProps {
  doors: Rack[];
}

export function AssetRug({ doors }: AssetRugProps) {
  return (
    <>
      {doors.map((door) => {
        const { w, d } = rackBounds(door);
        const [cx, , cz] = rackWorldCenter(door);
        return (
          <RugInstance
            key={door.id}
            position={[cx, 0.01, cz]}
            tilesW={w}
            tilesD={d}
          />
        );
      })}
    </>
  );
}
