import { Aperture, ChevronLeft, ChevronRight, Download, Eye, Loader2, Scan, X } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import { useSimulationStore, type GraphicsMode } from "@/stores/simulationStore";
import { useRealisticSettings } from "./graphicsSettings";
import type { GraphicsQuality } from "./constants";
import { usePhotoMode } from "./photoModeStore";
import { useI18n } from "@/shared/i18n/i18n";

interface Props {
  personaNames: Map<string, string>;
  // Outside playback the TimeBar (which carries the Classic/Realistic switch) is
  // hidden, so the HUD offers it instead.
  showModeSwitch: boolean;
  shopperViewActive: boolean;
  onFitStore: () => void;
}

// Small overlay in the canvas' bottom-right corner: render quality, and the
// shopper picker while the shopper view is on.
export function RealisticHud({ personaNames, showModeSwitch, shopperViewActive, onFitStore }: Props) {
  const { t } = useI18n();
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

  const current = followPersonaId && ids.includes(followPersonaId) ? followPersonaId : (ids[0] ?? null);
  const idx = current ? ids.indexOf(current) : -1;
  const step = (dir: 1 | -1) => {
    if (!ids.length) return;
    const next = ids[(idx + dir + ids.length) % ids.length]!;
    setFollowPersonaId(next);
  };

  return (
    <div className="pointer-events-none absolute right-4 bottom-4 left-4 z-10 flex flex-col items-end gap-2 [&>*]:pointer-events-auto">
      {realistic && !ready && (
        <div className="glass flex items-center gap-2 rounded-xl px-3 py-1.5 text-[0.8rem] text-muted-foreground" role="status">
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
          {t("hudBuilding")}
        </div>
      )}
      {realistic && photo.status !== "off" && <PhotoPanel />}
      {realistic && shopperView && (
        <div className="flex items-center gap-1 glass rounded-xl px-2 py-1.5 text-[0.8rem] text-foreground">
          <Eye className="size-3 text-muted-foreground" aria-hidden />
          <Button variant="ghost" size="sm" className="size-6 p-0" disabled={ids.length < 2} onClick={() => step(-1)} aria-label={t("hudPreviousShopper")}>
            <ChevronLeft className="size-3" />
          </Button>
          <span className="max-w-[180px] truncate font-medium" data-testid="shopper-name">
            {current ? (personaNames.get(current) ?? current) : t("hudNoShopper")}
          </span>
          <Button variant="ghost" size="sm" className="size-6 p-0" disabled={ids.length < 2} onClick={() => step(1)} aria-label={t("hudNextShopper")}>
            <ChevronRight className="size-3" />
          </Button>
        </div>
      )}
      <Button variant="outline" size="sm" className="glass gap-1.5" disabled={shopperViewActive || photo.status !== "off"} onClick={onFitStore}>
        <Scan className="size-3.5" aria-hidden /> {t("hudFitStore")}
      </Button>
      {(realistic || showModeSwitch) && <div className="flex flex-wrap justify-end items-center gap-2 glass rounded-xl px-2 py-1.5 text-foreground">
        {showModeSwitch && (
          <ToggleGroup
            type="single"
            value={graphicsMode}
            onValueChange={(v) => v && setGraphicsMode(v as GraphicsMode)}
            variant="outline"
            size="sm"
            aria-label={t("pbGraphics")}
          >
            <ToggleGroupItem value="classic" className="h-6 px-2 text-[0.8rem]">{t("pbClassic")}</ToggleGroupItem>
            <ToggleGroupItem value="realistic" className="h-6 px-2 text-[0.8rem]">{t("pbRealistic")}</ToggleGroupItem>
          </ToggleGroup>
        )}
        {realistic && (
          <>
            <span className="text-[0.8rem] text-muted-foreground">{t("hudQuality")}</span>
            <ToggleGroup
              type="single"
              value={quality}
              onValueChange={(v) => v && setQuality(v as GraphicsQuality)}
              variant="outline"
              size="sm"
              aria-label={t("hudRenderQuality")}
            >
              <ToggleGroupItem value="medium" className="h-6 px-2 text-[0.8rem]" title={t("hudMediumHint")}>
                {t("hudMedium")}
              </ToggleGroupItem>
              <ToggleGroupItem value="high" className="h-6 px-2 text-[0.8rem]" title={t("hudHighHint")}>
                {t("hudHigh")}
              </ToggleGroupItem>
            </ToggleGroup>
            <Button
              variant={photo.status === "off" ? "outline" : "default"}
              size="sm"
              className="h-6 gap-1 px-2 text-[0.8rem]"
              disabled={!ready}
              onClick={() => (photo.status === "off" ? photo.start() : photo.stop())}
              title={t("hudPhotoHint")}
            >
              <Aperture className="size-3.5" /> {t("hudPhoto")}
            </Button>
          </>
        )}
      </div>}
    </div>
  );
}

const TARGETS = [64, 256, 1024];

// Progress of the path-traced still, sample budget, save and exit.
function PhotoPanel() {
  const { locale, t } = useI18n();
  const photo = usePhotoMode();
  const pct = photo.status === "building" ? photo.progress : Math.min(1, photo.samples / photo.target);
  return (
    <div className="glass w-72 space-y-2 rounded-xl px-3 py-2.5 text-[0.8rem] text-foreground" role="status">
      <div className="flex items-center gap-2">
        {photo.status === "building" || photo.status === "tracing" ? <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-hidden /> : <Aperture className="size-3.5 text-muted-foreground" aria-hidden />}
        <span className="flex-1 font-medium">
          {photo.status === "building" && t("hudPhotoPreparing")}
          {photo.status === "tracing" && t("hudPhotoTracing", { samples: photo.samples, target: photo.target })}
          {photo.status === "done" && t("hudPhotoReady", { samples: photo.samples })}
          {photo.status === "error" && t("hudPhotoFailed")}
        </span>
        <Button variant="ghost" size="sm" className="size-6 p-0" onClick={photo.stop} aria-label={t("hudLeavePhoto")}><X className="size-3.5" /></Button>
      </div>
      {photo.status === "error" ? (
        <p role="alert" className="text-[0.75rem] text-destructive">{photo.error}</p>
      ) : (
        <span className="block h-1 overflow-hidden rounded-full bg-foreground/[0.08]">
          <span className="block h-full bg-primary transition-[width]" style={{ width: `${Math.max(3, pct * 100)}%` }} />
        </span>
      )}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-muted-foreground">{t("hudSamples")}</span>
        <ToggleGroup type="single" value={String(photo.target)} onValueChange={(v) => v && photo.setTarget(Number(v))} variant="outline" size="sm" aria-label={t("hudSampleBudget")}>
          {TARGETS.map((t) => <ToggleGroupItem key={t} value={String(t)} className="h-6 px-2 text-[0.75rem]">{t}</ToggleGroupItem>)}
        </ToggleGroup>
        {photo.perspective && (
          <label className="flex items-center gap-1 text-[0.75rem] text-muted-foreground" title={t("hudDofHint")}>
            <input type="checkbox" checked={photo.dof} onChange={(e) => photo.setDof(e.target.checked)} /> {t("hudDof")}
            {photo.dof && (
              <select value={photo.fStop} onChange={(e) => photo.setDof(true, Number(e.target.value))} className="h-5 rounded border bg-card px-0.5 text-[0.7rem]" aria-label={t("hudAperture")}>
                {[1.4, 2.8, 5.6].map((f) => <option key={f} value={f}>f/{f}</option>)}
              </select>
            )}
          </label>
        )}
        <label className="ml-auto flex items-center gap-1 text-[0.75rem] text-muted-foreground" title={t("hudDenoiseHint")}>
          <input type="checkbox" checked={photo.denoise} onChange={(e) => photo.setDenoise(e.target.checked)} /> {t("hudDenoise")}
        </label>
        <Button size="sm" className="ml-auto h-6 gap-1 px-2 text-[0.8rem]" disabled={photo.status !== "tracing" && photo.status !== "done"} onClick={photo.save}>
          <Download className="size-3.5" /> PNG
        </Button>
      </div>
      {photo.triangles > 0 && <p className="text-[0.7rem] text-muted-foreground">{t("hudTriangles", { millions: new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(photo.triangles / 1e6) })}</p>}
    </div>
  );
}
