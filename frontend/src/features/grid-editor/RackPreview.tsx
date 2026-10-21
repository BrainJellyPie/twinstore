import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import type { Rack, RackType } from "@/shared/types/domain";
import { marketAssetFor } from "@/shared/utils/assetMap";
import { useGlbModel } from "@/shared/hooks/useGlbModel";
import { uniformScaleToTile } from "@/shared/utils/glbHelpers";
import { CounterGhost } from "@/features/store-viewer/components/AssetFixture";
import { DiningTable } from "@/features/store-viewer/components/DiningTable";

interface RackPreviewProps {
  type: RackType;
  designVariant: "a" | "b" | "c";
  rotation: 0 | 90 | 180 | 270;
}

function PreviewMesh({ url }: { url: string }) {
  const { clone, bbox, offset } = useGlbModel(url);
  const scale = uniformScaleToTile(bbox);
  return (
    <group scale={scale}>
      <primitive object={clone} position={offset} />
    </group>
  );
}

export function RackPreview({ type, designVariant, rotation }: RackPreviewProps) {
  // marketAssetFor reads only type + design_variant.
  const stub = { type, design_variant: designVariant } as unknown as Rack;
  const url = marketAssetFor(stub);
  if (!url && type !== "table") return null;

  // Mirror AssetFixture's rotation sign so the preview matches the 3D scene.
  const groupRot = (-rotation * Math.PI) / 180;

  return (
    <div className="mx-auto aspect-square w-full max-w-48 overflow-hidden rounded-md border bg-muted/40">
      <Canvas
        orthographic
        camera={{ zoom: type === "table" ? 65 : 110, position: [2.5, 2, 3], near: -10, far: 20 }}
        dpr={[1, 2]}
      >
        <ambientLight intensity={1.15} />
        <hemisphereLight args={["#ffffff", "#e0dccf", 0.5]} />
        <directionalLight position={[3, 5, 2]} intensity={0.5} />
        <Suspense fallback={null}>
          {/* PreviewMesh is bottom-aligned at y=0; lift the camera target to the
              asset's vertical midpoint by translating the group down ~0.5 unit. */}
          <group position={[0, -0.5, 0]} rotation={[0, groupRot, 0]}>
            {type === "table" ? <DiningTable width={2} depth={2} /> : <PreviewMesh url={url!} />}
            {type === "counter" && designVariant === "b" && <CounterGhost />}
          </group>
        </Suspense>
      </Canvas>
    </div>
  );
}
