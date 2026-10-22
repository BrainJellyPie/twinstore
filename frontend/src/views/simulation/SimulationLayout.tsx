import { useEffect, useMemo, type ReactNode } from "react";
import { useLoader } from "@react-three/fiber";
import * as THREE from "three";
import { TimeBar } from "@/features/playback/components/TimeBar";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationStore } from "@/stores/simulationStore";
import type { CustomerResult, Rack } from "@/shared/types/domain";
import type { EmptySpell, RackStats } from "@/shared/api/client";
import type { CrewPlan } from "@/features/store-viewer/utils/crewAt";
import type { RunHeatmaps } from "@/shared/queries/useRun";
import type { StoreAssets } from "@/features/store-viewer/hooks/useStoreAssets";
import { CanvasErrorBoundary } from "@/app/providers/CanvasErrorBoundary";
import { SimulationCanvas } from "./SimulationCanvas";
import { RackDetailPanel } from "@/features/dashboard/components/RackDetailPanel";
import { currencyCode } from "@/shared/utils/money";

const VARIATIONS = [
  "/assets/market/Textures/colormap.png",
  "/assets/market/Textures/variation-a.png",
  "/assets/market/Textures/variation-b.png",
] as const;

// storeId → variation texture. Called outside the Canvas so the outer
// Suspense (SimulationPage) owns the initial load in one go.
function useVariationTexture(storeId: string): THREE.Texture {
  const url = useMemo(() => {
    let hash = 0;
    for (let i = 0; i < storeId.length; i++) hash = (hash * 31 + storeId.charCodeAt(i)) | 0;
    return VARIATIONS[Math.abs(hash) % VARIATIONS.length]!;
  }, [storeId]);

  const base = useLoader(THREE.TextureLoader, url);

  // If SolidFloor's useLoader(colormap.png) suspends alone inside the Canvas, there
  // is no catcher inside the Canvas — the suspension bubbles to the outer Suspense
  // and the whole SimulationLayout unmount→remounts (visible flash). Preload it at
  // the outer boundary in case the variation differs from colormap.
  useLoader(THREE.TextureLoader, VARIATIONS[0]!);

  // useLoader caches/shares Texture instances by URL. Mutating settings (especially
  // flipY) here would break UV sampling in other components using the same URL
  // (e.g. SolidFloor's colormap.png). Clone into a separate instance to isolate
  // settings — the underlying image source is shared, so cost is minimal.
  return useMemo(() => {
    const t = base.clone();
    t.magFilter = THREE.NearestFilter;
    t.minFilter = THREE.NearestFilter;
    t.colorSpace = THREE.SRGBColorSpace;
    t.flipY = false;
    t.needsUpdate = true;
    return t;
  }, [base]);
}

interface Props {
  storeId: string;
  assets: StoreAssets;
  personaNames: Map<string, string>;
  personaGenders: Map<string, string>;
  customers: CustomerResult[] | null;
  heatmaps: RunHeatmaps | null;
  rackStats?: RackStats[] | null;
  // Shared-store runs: when each shelf face stood empty (shown on the floor during playback).
  emptySpells?: EmptySpell[] | null;
  // Crew runs: the crew's tasks, shown at the tills and shelves during playback.
  crew?: CrewPlan | null;
  mode: "ready" | "running" | "playback";
  // Extra controls floating over the canvas.
  overlay?: ReactNode;
  /** Playback only: ask the run analyst about a shelf picked on the floor. */
  onAskAboutRack?: (rack: Rack) => void;
}

export function SimulationLayout({
  storeId, assets, personaNames, personaGenders, customers, heatmaps, rackStats, emptySpells, crew, mode, overlay, onAskAboutRack,
}: Props) {
  const heatmapMode = useSimulationStore((s) => s.heatmapMode);
  const rackOverlayOn = useSimulationStore((s) => s.rackOverlayOn);
  const runCurrency = useSimulationStore((s) => s.currency);
  const currency = mode === "playback" ? runCurrency : currencyCode(assets.currency ?? undefined);
  const variationTexture = useVariationTexture(storeId);

  useEffect(() => {
    if (mode !== "playback") useSimulationStore.getState().setCurrency(currency);
  }, [mode, currency]);

  useEffect(() => {
    usePlaybackControlStore.getState().setAvailableDays(assets.availableDays);
  }, [assets.availableDays]);

  const selectedRackId = useSimulationStore((s) => s.selectedRackId);
  const setSelectedRackId = useSimulationStore((s) => s.setSelectedRackId);
  const selectedRack = useMemo(
    () => assets.racks.find((r) => r.id === selectedRackId) ?? null,
    [assets.racks, selectedRackId],
  );

  const showPlayback = mode === "playback";
  const layer = showPlayback && heatmaps && heatmapMode !== "off" ? heatmapMode : null;
  const heatmapData = layer ? heatmaps?.[layer] ?? null : null;

  return (
    <>
      <CanvasErrorBoundary>
        <SimulationCanvas
          designTheme={assets.designTheme}
          designColors={assets.designColors}
          width={assets.width}
          depth={assets.depth}
          racks={assets.racks}
          doors={assets.doors}
          items={assets.items}
          heatmapData={heatmapData}
          heatmapPalette={layer}
          rackStats={showPlayback && rackOverlayOn ? rackStats ?? null : null}
          emptySpells={showPlayback ? emptySpells ?? null : null}
          crew={showPlayback ? crew ?? null : null}
          currency={currency}
          customers={showPlayback ? customers : null}
          personaNames={personaNames}
          personaGenders={personaGenders}
          minTime={assets.minTime}
          maxTime={assets.maxTime}
          availableDays={assets.availableDays}
          variationTexture={variationTexture}
        />
      </CanvasErrorBoundary>
      {showPlayback && (
        <TimeBar
          minTime={assets.minTime}
          maxTime={assets.maxTime}
          hasDwell={!!heatmaps?.dwell}
          hasRackStats={!!rackStats?.length}
        />
      )}
      {overlay}
      {selectedRack && (
        <RackDetailPanel
          rack={selectedRack}
          open={true}
          onClose={() => setSelectedRackId(null)}
          onAsk={onAskAboutRack && selectedRack.slots.some((slot) => slot.items.length > 0)
            ? () => { onAskAboutRack(selectedRack); setSelectedRackId(null); } : undefined}
        />
      )}
    </>
  );
}
