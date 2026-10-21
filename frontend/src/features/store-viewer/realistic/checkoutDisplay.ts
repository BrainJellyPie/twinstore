import { atlasGrid, cellPixel, cellUv } from "./atlasLayout";

// One shared texture for the cashier, customer and card-reader displays.
// This is decorative idle artwork, independent of simulation transactions.
export const CHECKOUT_DISPLAY_GRID = atlasGrid(3, 256, 128);

export function checkoutDisplayUv(index: 0 | 1 | 2) {
  const { offset, scale } = cellUv(CHECKOUT_DISPLAY_GRID, index);
  const u = 2 / CHECKOUT_DISPLAY_GRID.width;
  const v = 2 / CHECKOUT_DISPLAY_GRID.height;
  // Keep linear filtering away from the neighbouring display's pixels.
  return { offset: [offset[0] + u, offset[1] + v] as [number, number], scale: [scale[0] - 2 * u, scale[1] - 2 * v] as [number, number] };
}

export function createCheckoutDisplayCanvas(): HTMLCanvasElement {
  const grid = CHECKOUT_DISPLAY_GRID;
  const canvas = document.createElement("canvas");
  canvas.width = grid.width;
  canvas.height = grid.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2D canvas unavailable");
  ctx.fillStyle = "#101b24";
  ctx.fillRect(0, 0, grid.width, grid.height);
  const panel = (x: number, y: number, w: number, h: number, color: string, radius = 3) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, radius);
    ctx.fill();
  };

  // Cashier: a receipt pane and a grid of product-category tiles.
  ctx.fillStyle = "#153b43";
  ctx.fillRect(0, 0, 256, 22);
  ctx.font = "bold 11px Arial, sans-serif";
  ctx.fillStyle = "#e1eeeb";
  ctx.fillText("TwinStore", 12, 15);
  panel(12, 30, 96, 85, "#dbe3e1");
  for (let i = 0; i < 4; i++) {
    panel(20, 39 + i * 15, 8, 8, ["#759e6d", "#c6a15b", "#95aab2", "#ad7963"][i]!, 2);
    panel(34, 40 + i * 15, 42 - i * 5, 3, "#6c7b7c", 1);
    panel(34, 46 + i * 15, 27, 2, "#a3afad", 1);
  }
  panel(20, 105, 80, 2, "#a3afad", 1);
  const colors = ["#789f74", "#d0b471", "#9cafba", "#b9927b", "#919a76", "#a68eab"];
  for (let i = 0; i < 6; i++) {
    const x = 118 + (i % 3) * 42, y = 30 + Math.floor(i / 3) * 43;
    panel(x, y, 36, 36, "#29414b");
    panel(x + 10, y + 6, 16, 17, colors[i]!, 4);
    panel(x + 6, y + 28, 24, 2, "#b2c1c4", 1);
  }
  panel(118, 106, 120, 9, "#538f87", 2);

  // Customer: a quiet branded idle screen, without invented totals or orders.
  const [cx, cy] = cellPixel(grid, 1);
  ctx.save();
  ctx.translate(cx, cy);
  ctx.fillStyle = "#16383f";
  ctx.fillRect(0, 0, 256, 128);
  panel(24, 31, 48, 48, "#76aba0", 10);
  ctx.strokeStyle = "#16383f";
  ctx.lineWidth = 3;
  ctx.strokeRect(36, 46, 24, 21);
  ctx.beginPath();
  ctx.arc(48, 46, 7, Math.PI, 0);
  ctx.stroke();
  ctx.fillStyle = "#e0eeea";
  ctx.font = "bold 23px Arial, sans-serif";
  ctx.fillText("TwinStore", 88, 63);
  panel(88, 76, 122, 3, "#6d9695", 1);
  panel(24, 108, 208, 2, "#31565b", 1);
  ctx.restore();

  // Card reader: the standard visual metaphor of a contactless idle display.
  const [rx, ry] = cellPixel(grid, 2);
  ctx.save();
  ctx.translate(rx, ry);
  ctx.fillStyle = "#122c35";
  ctx.fillRect(0, 0, 256, 128);
  // The physical reader is nearly square; compensate for the wide atlas cell.
  ctx.scale(256 / 154, 1);
  panel(33, 34, 50, 32, "#8db8b5", 4);
  panel(33, 43, 50, 6, "#284952", 0);
  ctx.strokeStyle = "#9bc4bc";
  ctx.lineWidth = 3;
  for (const radius of [10, 18, 26]) {
    ctx.beginPath();
    ctx.arc(86, 50, radius, -Math.PI / 3, Math.PI / 3);
    ctx.stroke();
  }
  panel(38, 96, 78, 3, "#608b8f", 1);
  ctx.restore();
  return canvas;
}
