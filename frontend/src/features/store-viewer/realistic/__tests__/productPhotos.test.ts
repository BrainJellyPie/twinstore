// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { atlasGrid } from "../atlasLayout";
import type { Atlas } from "../canvasArt";
import { attachProductPhotos, productLabelKey, type ProductLabelSource } from "../productPhotos";

function setup(sources: ProductLabelSource[]) {
  const images: FakeImage[] = [];
  class FakeImage {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    crossOrigin = "";
    naturalWidth = 120;
    naturalHeight = 240;
    src = "";
    constructor() { images.push(this); }
    removeAttribute() { this.src = ""; }
  }
  vi.stubGlobal("Image", FakeImage);
  const drawImage = vi.fn();
  const context = {
    drawImage, fillRect: vi.fn(), getImageData: () => ({ data: new Uint8ClampedArray([220, 220, 220, 255]) }),
  } as unknown as CanvasRenderingContext2D;
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    (() => context) as unknown as HTMLCanvasElement["getContext"],
  );
  const placeholder = vi.fn();
  const atlas: Atlas = {
    canvas: document.createElement("canvas"), grid: atlasGrid(sources.length),
    index: new Map(sources.map((source, index) => [productLabelKey(source), index])), redraw: placeholder,
  };
  const onUpdate = vi.fn();
  const photos = attachProductPhotos(atlas, sources, onUpdate);
  return { images, atlas, onUpdate, photos, drawImage, placeholder };
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("product photographs", () => {
  it("keeps different packaging versions separate and restores loaded photos after font redraws", () => {
    const a: ProductLabelSource = { name: "Cereal", kind: "box", imageUrl: "/api/images/a?v=1" };
    const b = { ...a, imageUrl: "/api/images/a?v=2" };
    const { images, atlas, photos, onUpdate, drawImage, placeholder } = setup([a, b]);
    expect(productLabelKey(a)).not.toBe(productLabelKey(b));
    photos.load();
    expect(images).toHaveLength(2);
    expect(images[0]!.src).toContain("/api/images/a?v=1");
    expect(images[0]!.crossOrigin).toBe("anonymous");
    images[0]!.onload!();
    expect(onUpdate).toHaveBeenCalledOnce();
    drawImage.mockClear();
    atlas.redraw();
    expect(placeholder).toHaveBeenCalledOnce();
    expect(drawImage).toHaveBeenCalledOnce(); // Only the loaded version overlays its placeholder.
    photos.dispose();
  });

  it("limits concurrent decodes, deduplicates URLs, and keeps failed images on their placeholder", () => {
    const sources: ProductLabelSource[] = Array.from({ length: 7 }, (_, i) => ({
      name: `Product ${i}`, kind: "box", imageUrl: `/api/images/${Math.max(0, i - 1)}`,
    }));
    const { images, photos, onUpdate } = setup(sources);
    photos.load();
    expect(images).toHaveLength(4);
    images[0]!.onerror!();
    expect(images).toHaveLength(5);
    images[1]!.onerror!();
    expect(images).toHaveLength(6); // Seven products share six URLs.
    expect(onUpdate).not.toHaveBeenCalled();
    photos.dispose();
    expect(images.every((image) => image.onload === null && image.onerror === null)).toBe(true);
  });

  it("ignores a completed request after cleanup and can load again on StrictMode remount", () => {
    const source: ProductLabelSource = { name: "Water", kind: "bottle", imageUrl: "/api/images/water" };
    const { images, atlas, photos, onUpdate, drawImage } = setup([source]);
    const cancel = photos.load();
    const late = images[0]!.onload!;
    cancel();
    photos.dispose();
    late();
    expect(onUpdate).not.toHaveBeenCalled();
    photos.load();
    images[1]!.onload!();
    expect(onUpdate).toHaveBeenCalledOnce();
    drawImage.mockClear();
    atlas.redraw();
    expect(drawImage).toHaveBeenCalledOnce();
    photos.dispose();
  });
});
