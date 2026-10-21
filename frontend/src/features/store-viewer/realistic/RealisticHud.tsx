import { Aperture, ChevronLeft, ChevronRight, Download, Eye, Loader2, X } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import { useSimulationStore, type GraphicsMode } from "@/stores/simulationStore";
import { useRealisticSettings } from "./graphicsSettings";
import type { GraphicsQuality } from "./constants";
import { usePhotoMode } from "./photoModeStore";

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

  const photo = usePhotoMode();
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
      {realistic && photo.status !== "off" && <PhotoPanel />}
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
              <ToggleGroupItem value="medium" className="h-6 px-2 text-[0.8rem]" title="Textured surfaces and soft shadows">
                Medium
              </ToggleGroupItem>
              <ToggleGroupItem value="high" className="h-6 px-2 text-[0.8rem]" title="Detailed surfaces, ambient occlusion, HDR lighting and reflections">
                High
              </ToggleGroupItem>
            </ToggleGroup>
            <Button
              variant={photo.status === "off" ? "outline" : "default"}
              size="sm"
              className="h-6 gap-1 px-2 text-[0.8rem]"
              disabled={!ready}
              onClick={() => (photo.status === "off" ? photo.start() : photo.stop())}
              title="Path-trace this view into a photoreal still (global illumination, soft shadows, real glass)"
            >
              <Aperture className="size-3.5" /> Photo
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

const TARGETS = [64, 256, 1024];

// Progress of the path-traced still, sample budget, save and exit.
function PhotoPanel() {
  const photo = usePhotoMode();
  const pct = photo.status === "building" ? photo.progress : Math.min(1, photo.samples / photo.target);
  return (
    <div className="glass w-72 space-y-2 rounded-xl px-3 py-2.5 text-[0.8rem] text-foreground" role="status">
      <div className="flex items-center gap-2">
        {photo.status === "building" || photo.status === "tracing" ? <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-hidden /> : <Aperture className="size-3.5 text-muted-foreground" aria-hidden />}
        <span className="flex-1 font-medium">
          {photo.status === "building" && "Preparing the scene for path tracing…"}
          {photo.status === "tracing" && `Path tracing · ${photo.samples} / ${photo.target} samples`}
          {photo.status === "done" && `Photo ready · ${photo.samples} samples`}
          {photo.status === "error" && "Photo mode failed"}
        </span>
        <Button variant="ghost" size="sm" className="size-6 p-0" onClick={photo.stop} aria-label="Leave photo mode"><X className="size-3.5" /></Button>
      </div>
      {photo.status === "error" ? (
        <p className="text-[0.75rem] text-destructive">{photo.error}</p>
      ) : (
        <span className="block h-1 overflow-hidden rounded-full bg-foreground/[0.08]">
          <span className="block h-full bg-primary transition-[width]" style={{ width: `${Math.max(3, pct * 100)}%` }} />
        </span>
      )}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-muted-foreground">Samples</span>
        <ToggleGroup type="single" value={String(photo.target)} onValueChange={(v) => v && photo.setTarget(Number(v))} variant="outline" size="sm" aria-label="Sample budget">
          {TARGETS.map((t) => <ToggleGroupItem key={t} value={String(t)} className="h-6 px-2 text-[0.75rem]">{t}</ToggleGroupItem>)}
        </ToggleGroup>
        {photo.perspective && (
          <label className="flex items-center gap-1 text-[0.75rem] text-muted-foreground" title="Depth of field: focus on what is at the centre of the view">
            <input type="checkbox" checked={photo.dof} onChange={(e) => photo.setDof(e.target.checked)} /> DoF
            {photo.dof && (
              <select value={photo.fStop} onChange={(e) => photo.setDof(true, Number(e.target.value))} className="h-5 rounded border bg-card px-0.5 text-[0.7rem]" aria-label="Aperture">
                {[1.4, 2.8, 5.6].map((f) => <option key={f} value={f}>f/{f}</option>)}
              </select>
            )}
          </label>
        )}
        <label className="ml-auto flex items-center gap-1 text-[0.75rem] text-muted-foreground" title="Edge-aware smoothing; strongest while samples are few">
          <input type="checkbox" checked={photo.denoise} onChange={(e) => photo.setDenoise(e.target.checked)} /> Denoise
        </label>
        <Button size="sm" className="ml-auto h-6 gap-1 px-2 text-[0.8rem]" disabled={photo.status !== "tracing" && photo.status !== "done"} onClick={photo.save}>
          <Download className="size-3.5" /> PNG
        </Button>
      </div>
      {photo.triangles > 0 && <p className="text-[0.7rem] text-muted-foreground">{(photo.triangles / 1e6).toFixed(2)} M triangles · orbit or zoom to re-frame (restarts the samples)</p>}
    </div>
  );
}
