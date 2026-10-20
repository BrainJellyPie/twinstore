import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { AssetFixture } from "@/features/store-viewer/components/AssetFixture";
import { AssetRug } from "@/features/store-viewer/components/AssetRug";
import { AssetWall } from "@/features/store-viewer/components/AssetWall";
import { SolidFloor } from "@/features/store-viewer/components/SolidFloor";
import { HeatmapOverlay } from "@/features/store-viewer/components/HeatmapOverlay";
import type { HeatmapPalette } from "@/features/store-viewer/utils/heatmapPalette";
import { RackPerformanceLayer } from "@/features/store-viewer/components/RackPerformanceLayer";
import { PlaybackScene } from "@/features/playback/components/PlaybackScene";
import type { Rack, CustomerResult } from "@/shared/types/domain";
import type { RackStats } from "@/shared/api/client";

function LoadingOverlay() {
  return (
    <Html center>
      <div className="rounded-lg bg-background/90 px-4 py-2.5 text-xs shadow-md">
        Loading assets…
      </div>
    </Html>
  );
}

interface StoreSceneProps {
  width: number;
  depth: number;
  racks: Rack[];
  doors: Rack[];
  items: Rack[];
  heatmapData: number[][] | null;
  heatmapPalette: HeatmapPalette | null; // null → heatmap hidden
  rackStats: RackStats[] | null; // non-null → rack KPI overlay shown
  currency: string;
  customers: CustomerResult[] | null;
  personaNames: Map<string, string>;
  personaGenders: Map<string, string>;
  minTime: number;
  maxTime: number;
  availableDays: number[];
  variationTexture: THREE.Texture | null;
}

// Cardinal labels are anchored to the grid axes, not to real-world geography.
// The grid editor's face convention (rotation 0 ⇒ front=S; 0:S, 90:W, 180:N, 270:E)
// gives +X=East / +Z=South in world space. With the fixed isometric camera at
// (+X, +Z), -Z lands at the top of the screen, hence "North" at the back wall.
const COMPASS_MARGIN = 1.5;
// North/West sides typically host walls that would occlude a floor-level label,
// so lift those two above wall height. South/East face the camera and stay at y=0.
const COMPASS_LIFT = 1.5;

function CompassLabels({ width, depth }: { width: number; depth: number }) {
  const labelClass = "select-none text-3xl font-medium text-muted-foreground/60";
  const labels: { key: string; text: string; position: [number, number, number] }[] = [
    { key: "N", text: "North", position: [width / 2, COMPASS_LIFT, -COMPASS_MARGIN] },
    { key: "S", text: "South", position: [width / 2, 0, depth + COMPASS_MARGIN] },
    { key: "E", text: "East", position: [width + COMPASS_MARGIN, 0, depth / 2] },
    { key: "W", text: "West", position: [-COMPASS_MARGIN, COMPASS_LIFT, depth / 2] },
  ];
  return (
    <>
      {labels.map((l) => (
        <Html
          key={l.key}
          position={l.position}
          center
          // drei's default zIndexRange ([16777271, 0]) overlays the labels on
          // top of every overlay. Flatten to 0 so any sibling outside the canvas
          // (TimeBar, panels, modals) stacks above by natural DOM order.
          zIndexRange={[0, 0]}
          style={{ pointerEvents: "none" }}
        >
          <div className={labelClass}>{l.text}</div>
        </Html>
      ))}
    </>
  );
}

function StoreScene({
  width, depth, racks, doors, items,
  heatmapData, heatmapPalette, rackStats, currency, customers, personaNames, personaGenders, minTime, maxTime,
  availableDays, variationTexture,
}: StoreSceneProps) {
  return (
    <group position={[-width / 2, 0, -depth / 2]}>
      <SolidFloor width={width} depth={depth} />
      <Suspense fallback={null}>
        <AssetWall width={width} depth={depth} racks={racks} variationTexture={variationTexture} />
      </Suspense>
      {heatmapPalette && heatmapData && (
        <HeatmapOverlay data={heatmapData} palette={heatmapPalette} width={width} depth={depth} />
      )}
      {rackStats && <RackPerformanceLayer racks={items} stats={rackStats} currency={currency} />}
      <Suspense fallback={<LoadingOverlay />}>
        <AssetRug doors={doors} />
        {items.map((f) => (
          <AssetFixture key={f.id} rack={f} variationTexture={variationTexture} />
        ))}
        <PlaybackScene
          customers={customers}
          personaNames={personaNames}
          personaGenders={personaGenders}
          minTime={minTime}
          maxTime={maxTime}
          availableDays={availableDays}
        />
      </Suspense>
      <CompassLabels width={width} depth={depth} />
    </group>
  );
}

export type SimulationCanvasProps = StoreSceneProps;

export function SimulationCanvas(props: SimulationCanvasProps) {
  return (
    <Canvas
      shadows="percentage"
      orthographic
      camera={{ zoom: 100, position: [17, 13, 22], near: -100, far: 200 }}
      style={{ background: "#ece3d6", position: "absolute", inset: 0 }}
    >
      <ambientLight intensity={1.15} />
      <hemisphereLight args={["#ffffff", "#e0dccf", 0.5]} />
      <directionalLight
        position={[10, 20, 10]}
        intensity={0.7}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-25}
        shadow-camera-right={25}
        shadow-camera-top={25}
        shadow-camera-bottom={-25}
        shadow-camera-near={0.1}
        shadow-camera-far={80}
        shadow-bias={-0.0005}
      />
      <StoreScene {...props} />
      <OrbitControls enableRotate={false} target={[0, 0.5, 0]} enablePan enableZoom minZoom={20} maxZoom={140} />
    </Canvas>
  );
}
