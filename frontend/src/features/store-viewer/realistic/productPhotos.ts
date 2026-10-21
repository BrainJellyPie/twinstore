import { resolveImageUrl } from "@/shared/api/images";
import { cellPixel, LABEL_U0 } from "./atlasLayout";
import type { Atlas } from "./canvasArt";
import { productPalette, type PackageKind } from "./productCatalog";

export interface ProductLabelSource {
  name: string;
  imageUrl?: string | null;
  kind: PackageKind;
}

// Distinct photos of the same named product must not share a cell (package A/B).
export function productLabelKey(source: Pick<ProductLabelSource, "name" | "imageUrl">): string {
  return JSON.stringify([source.name, source.imageUrl ?? ""]);
}

// Crop a front packshot to the printed band on cylindrical package geometry,
// avoiding a second cap/bottle silhouette printed inside the label itself.
const LABEL_BAND: Partial<Record<PackageKind, [number, number]>> = {
  bottle: [0.3, 0.66], jar: [0.2, 0.75], can: [0.06, 0.92],
  tube: [0.03, 0.92], cup: [0, 0.95], pint: [0, 0.95],
};

function photoSwatch(image: HTMLImageElement, y: number, fallback: string): string {
  const sample = document.createElement("canvas");
  sample.width = sample.height = 1;
  const context = sample.getContext("2d")!;
  context.drawImage(image, image.naturalWidth * 0.4, image.naturalHeight * y,
    image.naturalWidth * 0.2, image.naturalHeight * 0.08, 0, 0, 1, 1);
  const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data;
  return a !== undefined && a > 200 ? `rgb(${r}, ${g}, ${b})` : fallback;
}

export function attachProductPhotos(atlas: Atlas, sources: ProductLabelSource[], onUpdate: () => void) {
  const unique = new Map(sources.map((source) => [productLabelKey(source), source]));
  const thumbnails = new Map<string, HTMLCanvasElement>();
  const proceduralRedraw = atlas.redraw;
  const ctx = atlas.canvas.getContext("2d")!;
  const draw = (key: string, thumbnail: HTMLCanvasElement) => {
    const index = atlas.index.get(key);
    if (index === undefined) return;
    const [x, y] = cellPixel(atlas.grid, index);
    ctx.drawImage(thumbnail, x, y, atlas.grid.cellW, atlas.grid.cellH);
  };
  const redraw = () => {
    proceduralRedraw();
    for (const [key, thumbnail] of thumbnails) draw(key, thumbnail);
  };
  atlas.redraw = redraw;

  let cancel = () => {};
  const load = () => {
    cancel();
    atlas.redraw = redraw;
    let alive = true;
    // A single decoded image can supply many facings and several label cells.
    const byUrl = new Map<string, { key: string; source: ProductLabelSource }[]>();
    for (const [key, source] of unique) {
      const url = resolveImageUrl(source.imageUrl);
      if (!url || thumbnails.has(key)) continue;
      const entries = byUrl.get(url) ?? [];
      entries.push({ key, source });
      byUrl.set(url, entries);
    }
    const queue = [...byUrl.entries()];
    const active = new Set<HTMLImageElement>();
    let next = 0;
    const pump = () => {
      while (alive && active.size < 4 && next < queue.length) {
        const [url, entries] = queue[next++]!;
        const image = new Image();
        image.crossOrigin = "anonymous";
        active.add(image);
        const finish = () => {
          image.onload = image.onerror = null;
          image.removeAttribute("src");
          active.delete(image);
          pump();
        };
        image.onload = () => {
          if (!alive) return;
          if (image.naturalWidth > 0 && image.naturalHeight > 0) {
            for (const { key, source } of entries) {
              const thumbnail = document.createElement("canvas");
              thumbnail.width = atlas.grid.cellW;
              thumbnail.height = atlas.grid.cellH;
              const target = thumbnail.getContext("2d")!;
              const palette = productPalette(source.name);
              const zoneWidth = Math.round(thumbnail.width * LABEL_U0);
              target.fillStyle = palette.base;
              target.fillRect(0, 0, thumbnail.width, thumbnail.height);
              target.fillStyle = photoSwatch(image, 0.86, palette.base);
              target.fillRect(0, thumbnail.height / 2, zoneWidth, thumbnail.height / 2);
              target.fillStyle = source.kind === "can" || source.kind === "tube"
                ? "#c9cdd2" : photoSwatch(image, 0.06, palette.accent);
              target.fillRect(0, 0, zoneWidth, thumbnail.height / 2);
              const [bottom, top] = LABEL_BAND[source.kind] ?? [0, 1];
              target.drawImage(image, 0, image.naturalHeight * (1 - top), image.naturalWidth,
                image.naturalHeight * (top - bottom), zoneWidth, 0, thumbnail.width - zoneWidth, thumbnail.height);
              thumbnails.set(key, thumbnail);
              draw(key, thumbnail);
            }
            onUpdate();
          }
          finish();
        };
        // CORS/404/invalid images leave the readable procedural label in place.
        image.onerror = finish;
        image.src = url;
      }
    };
    cancel = () => {
      alive = false;
      for (const image of active) {
        image.onload = image.onerror = null;
        image.removeAttribute("src");
      }
      active.clear();
    };
    pump();
    return cancel;
  };

  return {
    load,
    dispose: () => {
      cancel();
      thumbnails.clear();
      atlas.redraw = proceduralRedraw;
    },
  };
}
