import { ChevronLeft, ChevronRight, Eye, Loader2 } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import { useSimulationStore, type GraphicsMode } from "@/stores/simulationStore";
import { useRealisticSettings } from "./graphicsSettings";
import type { GraphicsQuality } from "./constants";

interface Props {
  personaNames: Map<string, string>;
  // Outside playback the TimeBar (which carries the Classic/Realistic switch) is
  // hidden, so the HUD offers it instead.
  showModeSwitch: boolean;
}

// Small overlay in the canvas' bottom-right corner: render quality, and the
// shopper picker while the shopper view is on.
export function RealisticHud({ personaNames, showModeSwitch }: Props) {
  const graphicsMode = useSimulationStore((s) => s.graphicsMode);
  const setGraphicsMode = useSimulationStore((s) => s.setGraphicsMode);
  const shopperView = useSimulationStore((s) => s.shopperView);
  const followPersonaId = useSimulationStore((s) => s.followPersonaId);
  const setFollowPersonaId = useSimulationStore((s) => s.setFollowPersonaId);
  const quality = useRealisticSettings((s) => s.quality);
  const setQuality = useRealisticSettings((s) => s.setQuality);
  const ids = useRealisticSettings((s) => s.activeShopperIds);
  const ready = useRealisticSettings((s) => s.realisticReady);

  const realistic = graphicsMode === "realistic";
  if (!realistic && !showModeSwitch) return null;

  const current = followPersonaId && ids.includes(followPersonaId) ? followPersonaId : (ids[0] ?? null);
  const idx = current ? ids.indexOf(current) : -1;
  const step = (dir: 1 | -1) => {
    if (!ids.length) return;
    const next = ids[(idx + dir + ids.length) % ids.length]!;
    setFollowPersonaId(next);
  };

  return (
    <div className="pointer-events-auto absolute right-4 bottom-4 z-10 flex flex-col items-end gap-2">
      {realistic && !ready && (
        <div className="glass flex items-center gap-2 rounded-xl px-3 py-1.5 text-[0.8rem] text-muted-foreground" role="status">
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
          Building realistic store…
        </div>
      )}
      {realistic && shopperView && (
        <div className="flex items-center gap-1 glass rounded-xl px-2 py-1.5 text-[0.8rem] text-foreground">
          <Eye className="size-3 text-muted-foreground" aria-hidden />
          <Button variant="ghost" size="sm" className="size-6 p-0" disabled={ids.length < 2} onClick={() => step(-1)} aria-label="Previous shopper">
            <ChevronLeft className="size-3" />
          </Button>
          <span className="max-w-[180px] truncate font-medium" data-testid="shopper-name">
            {current ? (personaNames.get(current) ?? current) : "No shopper in store"}
          </span>
          <Button variant="ghost" size="sm" className="size-6 p-0" disabled={ids.length < 2} onClick={() => step(1)} aria-label="Next shopper">
            <ChevronRight className="size-3" />
          </Button>
        </div>
      )}
      <div className="flex items-center gap-2 glass rounded-xl px-2 py-1.5 text-foreground">
        {showModeSwitch && (
          <ToggleGroup
            type="single"
            value={graphicsMode}
            onValueChange={(v) => v && setGraphicsMode(v as GraphicsMode)}
            variant="outline"
            size="sm"
            aria-label="Graphics"
          >
            <ToggleGroupItem value="classic" className="h-6 px-2 text-[0.8rem]">Classic</ToggleGroupItem>
            <ToggleGroupItem value="realistic" className="h-6 px-2 text-[0.8rem]">Realistic</ToggleGroupItem>
          </ToggleGroup>
        )}
        {realistic && (
          <>
            <span className="text-[0.8rem] text-muted-foreground">Quality</span>
            <ToggleGroup
              type="single"
              value={quality}
              onValueChange={(v) => v && setQuality(v as GraphicsQuality)}
              variant="outline"
              size="sm"
              aria-label="Render quality"
            >
              <ToggleGroupItem value="medium" className="h-6 px-2 text-[0.8rem]" title="Soft shadows, fake contact AO">
                Medium
              </ToggleGroupItem>
              <ToggleGroupItem value="high" className="h-6 px-2 text-[0.8rem]" title="Adds GTAO, bloom, floor reflections, glass transmission">
                High
              </ToggleGroupItem>
            </ToggleGroup>
          </>
        )}
      </div>
    </div>
  );
}
