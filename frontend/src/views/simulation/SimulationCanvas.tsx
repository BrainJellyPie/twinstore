import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { Html } from "@react-three/drei";
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
import { useSimulationStore } from "@/stores/simulationStore";
import { RealisticStore } from "@/features/store-viewer/realistic/RealisticStore";
import { RealisticLighting } from "@/features/store-viewer/realistic/RealisticLighting";
import { RealisticEffects } from "@/features/store-viewer/realistic/RealisticEffects";
import { RealisticHud } from "@/features/store-viewer/realistic/RealisticHud";
import { PersonaRig } from "@/features/store-viewer/realistic/PersonaRig";
import { ShopperCamera } from "@/features/store-viewer/realistic/ShopperCamera";
import { StoreCameraControls } from "@/features/store-viewer/realistic/StoreCameraControls";
import { useRealisticSettings } from "@/features/store-viewer/realistic/graphicsSettings";
import { SceneGround } from "@/features/store-viewer/realistic/SceneGround";
import { GatedRenderer } from "@/features/store-viewer/realistic/GatedRenderer";
import { useSceneColors } from "@/features/store-viewer/realistic/useSceneColors";
import { EYE_HEIGHT, FLOOR_SLAB, type GraphicsQuality } from "@/features/store-viewer/realistic/constants";

function LoadingOverlay() {
  return (
    <Html center>
      <div className="glass rounded-xl px-4 py-2.5 text-[0.8rem] text-foreground">
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

function CompassLabels({ width, depth, lift = COMPASS_LIFT }: { width: number; depth: number; lift?: number }) {
  const labelClass = "select-none text-sm font-medium uppercase tracking-[0.18em]";
  const labels: { key: string; text: string; position: [number, number, number] }[] = [
    { key: "N", text: "North", position: [width / 2, lift, -COMPASS_MARGIN] },
    { key: "S", text: "South", position: [width / 2, 0, depth + COMPASS_MARGIN] },
    { key: "E", text: "East", position: [width + COMPASS_MARGIN, 0, depth / 2] },
    { key: "W", text: "West", position: [-COMPASS_MARGIN, lift, depth / 2] },
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
          <div className={labelClass} style={{ color: "var(--muted-foreground)", opacity: 0.45 }}>
            {l.text}
          </div>
        </Html>
      ))}
    </>
  );
}

interface SceneMode {
  realistic: boolean;
  quality: GraphicsQuality;
  hideCompass: boolean;
}

function StoreScene({
  width, depth, racks, doors, items,
  heatmapData, heatmapPalette, rackStats, currency, customers, personaNames, personaGenders, minTime, maxTime,
  availableDays, variationTexture, realistic, quality, hideCompass,
}: StoreSceneProps & SceneMode) {
  return (
    <group position={[-width / 2, 0, -depth / 2]}>
      {realistic ? (
        <RealisticStore width={width} depth={depth} racks={racks} currency={currency} quality={quality} />
      ) : (
        <>
          <SolidFloor width={width} depth={depth} />
          <Suspense fallback={null}>
            <AssetWall width={width} depth={depth} racks={racks} variationTexture={variationTexture} />
          </Suspense>
        </>
      )}
      {heatmapPalette && heatmapData && (
        <HeatmapOverlay data={heatmapData} palette={heatmapPalette} width={width} depth={depth} />
      )}
      {rackStats && <RackPerformanceLayer racks={items} stats={rackStats} currency={currency} />}
      <Suspense fallback={<LoadingOverlay />}>
        {!realistic && <AssetRug doors={doors} />}
        {!realistic &&
          items.map((f) => <AssetFixture key={f.id} rack={f} variationTexture={variationTexture} />)}
        {/* PersonaRig is rendered in both modes so PlaybackScene never remounts on a mode switch. */}
        <PersonaRig realistic={realistic}>
          <PlaybackScene
            customers={customers}
            personaNames={personaNames}
            personaGenders={personaGenders}
            minTime={minTime}
            maxTime={maxTime}
            availableDays={availableDays}
          />
        </PersonaRig>
      </Suspense>
      {!hideCompass && <CompassLabels width={width} depth={depth} lift={realistic ? 2.9 : COMPASS_LIFT} />}
    </group>
  );
}

export type SimulationCanvasProps = StoreSceneProps;

export function SimulationCanvas(props: SimulationCanvasProps) {
  const graphicsMode = useSimulationStore((s) => s.graphicsMode);
  const shopperViewOn = useSimulationStore((s) => s.shopperView);
  const quality = useRealisticSettings((s) => s.quality);
  const realistic = graphicsMode === "realistic";
  // Shopper view needs playback data; outside playback the iso camera stays.
  const shopperView = shopperViewOn && props.customers !== null;
  const colors = useSceneColors();
  return (
    <>
      <Canvas
        shadows="percentage"
        orthographic
        camera={{ zoom: 100, position: [17, 13, 22], near: -100, far: 200 }}
        style={{ background: "var(--scene)", position: "absolute", inset: 0 }}
        // Skip synchronous shader-status queries outside dev: they stall the main
        // thread while (software) GL compiles the realistic scene's programs.
        onCreated={({ gl }) => {
          gl.debug.checkShaderErrors = import.meta.env.DEV;
        }}
      >
        {/* The post stack ("high") tone-maps its input, so there the canvas stays
            transparent and the CSS --scene background shows through instead. */}
        {!(realistic && quality === "high") && <color attach="background" args={[colors.scene]} />}
        <fog attach="fog" args={[colors.scene, 34, 80]} />
        {realistic ? (
          <RealisticLighting width={props.width} depth={props.depth} quality={quality} dark={colors.dark} />
        ) : (
          <>
            <ambientLight intensity={colors.dark ? 0.95 : 1.15} color={colors.dark ? "#e6ebff" : "#ffffff"} />
            <hemisphereLight args={colors.dark ? ["#dfe6ff", "#3a4166", 0.5] : ["#ffffff", "#e0dccf", 0.5]} />
            <directionalLight
              position={[10, 20, 10]}
              intensity={colors.dark ? 0.6 : 0.7}
              color={colors.dark ? "#eef2ff" : "#ffffff"}
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
          </>
        )}
        <SceneGround color={colors.sceneFloor} y={realistic ? -FLOOR_SLAB - 0.003 : -0.02} />
        <StoreScene {...props} realistic={realistic} quality={quality} hideCompass={shopperView} />
        {realistic && quality === "high" && <RealisticEffects />}
        <GatedRenderer />
        <ShopperCamera
          active={shopperView}
          customers={props.customers}
          racks={props.racks}
          width={props.width}
          depth={props.depth}
          minTime={props.minTime}
          maxTime={props.maxTime}
          eyeHeight={EYE_HEIGHT[graphicsMode]}
        />
        <StoreCameraControls disabled={shopperView} maxZoom={realistic ? 420 : 140} />
      </Canvas>
      <RealisticHud personaNames={props.personaNames} showModeSwitch={props.customers === null} />
    </>
  );
}
