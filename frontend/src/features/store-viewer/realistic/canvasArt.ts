// Procedural canvas art for Realistic mode: product label atlas, price tags,
// shelf talkers, signage, floor/ceiling/pavement textures and soft AO decals.
// Product photos, when available, are layered onto the placeholder label atlas.

import { formatMoney } from "@/shared/utils/money";
import { atlasGrid, cellPixel, LABEL_U0, type AtlasGrid } from "./atlasLayout";
import {
  classifyProduct,
  hash01,
  luminance,
  productPalette,
  shade,
  splitLabel,
  type PackageSpec,
} from "./productCatalog";

export const FONT_STACK = '"Geist Variable", "Helvetica Neue", Helvetica, Arial, sans-serif';

function makeCanvas(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  if (!ctx) throw new Error("2D canvas unavailable");
  return [c, ctx];
}

// Largest font size (≤ maxPx) at which `text` fits in maxW.
function fitFont(ctx: CanvasRenderingContext2D, text: string, maxW: number, maxPx: number, weight = 700): number {
  ctx.font = `${weight} ${maxPx}px ${FONT_STACK}`;
  const w = ctx.measureText(text).width;
  const px = w > maxW ? Math.max(6, Math.floor((maxPx * maxW) / w)) : maxPx;
  ctx.font = `${weight} ${px}px ${FONT_STACK}`;
  return px;
}

// Two-line wrap for detail text.
function wrap2(ctx: CanvasRenderingContext2D, text: string, maxW: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const lines: string[] = [];
  let line = "";
  for (const w of words) {
    const cand = line ? `${line} ${w}` : w;
    if (ctx.measureText(cand).width <= maxW || !line) {
      line = cand;
    } else {
      lines.push(line);
      line = w;
      if (lines.length === 2) break;
    }
  }
  if (lines.length < 2 && line) lines.push(line);
  return lines.slice(0, 2);
}

// ---------------------------------------------------------------------------
// Product label atlas

function liquidColor(name: string, base: string): string {
  const n = name.toLowerCase();
  if (/water|seltzer|smartwater|sparkling mineral/.test(n)) return "#cfe6f3";
  if (/cola|coke|pepsi|dr pepper|coffee|mocha|frappuccino|cold brew/.test(n)) return "#3a1d10";
  if (/tea\b/.test(n)) return "#9a5b1d";
  if (/orange|mango/.test(n)) return "#f29a1e";
  if (/lemonade|lemon/.test(n)) return "#f2e27a";
  if (/milk|protein|core power|muscle milk|yogurt|vanilla/.test(n)) return "#f1ece2";
  return shade(base, -0.15);
}

interface LabelGeometry {
  // Physical label width (m) — the full wrap for cylinders.
  physW: number;
  physH: number;
  // Physical width of the printed front panel.
  panelW: number;
}

function labelGeometry(spec: PackageSpec): LabelGeometry {
  const circ = Math.PI * spec.w;
  switch (spec.kind) {
    case "bottle":
      return { physW: circ, physH: spec.h * 0.36, panelW: Math.min(circ, spec.w * 1.25) };
    case "can":
    case "tube":
      return { physW: circ, physH: spec.h * 0.86, panelW: Math.min(circ, spec.w * 1.2) };
    case "jar":
      return { physW: circ, physH: spec.h * 0.55, panelW: Math.min(circ, spec.w * 1.2) };
    case "cup":
    case "pint":
      // Shared between the wrap and the printed lid — compromise aspect.
      return { physW: spec.w * 1.6, physH: spec.h, panelW: spec.w * 1.6 };
    default:
      return { physW: spec.w, physH: spec.h * 0.92, panelW: spec.w };
  }
}

function drawLabelCell(ctx: CanvasRenderingContext2D, x0: number, y0: number, cw: number, ch: number, name: string) {
  const spec = classifyProduct(name);
  const pal = productPalette(name);
  const text = splitLabel(name);
  const body = spec.kind === "bottle" && spec.category === "drink" ? liquidColor(name, pal.base) : pal.base;
  const accent = spec.kind === "can" || spec.kind === "tube" ? "#c9cdd2" : pal.accent;

  ctx.save();
  ctx.beginPath();
  ctx.rect(x0, y0, cw, ch);
  ctx.clip();
  // Flat-colour zones (body lower half, accent/cap upper half).
  const zoneW = Math.round(cw * LABEL_U0);
  ctx.fillStyle = body;
  ctx.fillRect(x0, y0 + ch / 2, zoneW, ch / 2);
  ctx.fillStyle = accent;
  ctx.fillRect(x0, y0, zoneW, ch / 2);

  // Label area.
  const lx = x0 + zoneW;
  const lw = cw - zoneW;
  ctx.fillStyle = pal.base;
  ctx.fillRect(lx, y0, lw, ch);

  const geo = labelGeometry(spec);
  const panelPx = (lw * Math.min(geo.panelW, geo.physW)) / geo.physW;
  // Horizontal squash so glyphs keep their aspect once wrapped onto the package.
  const kx = (lw * geo.physH) / (ch * geo.physW);
  const vw = panelPx / kx; // virtual panel width
  const vh = ch;

  // Wrap-around decoration outside the panel (cylinders).
  if (panelPx < lw - 2) {
    ctx.fillStyle = shade(pal.base, -0.12);
    ctx.fillRect(lx, y0 + ch * 0.78, lw, ch * 0.1);
    ctx.fillStyle = pal.accent;
    ctx.fillRect(lx, y0 + ch * 0.12, lw, ch * 0.06);
  }

  ctx.translate(lx + (lw - panelPx) / 2, y0);
  ctx.scale(kx, 1);

  const accentInk = luminance(pal.accent) > 0.42 ? "#1b1d22" : "#ffffff";
  let brandY = vh * 0.42;
  let brandInk = pal.ink;
  switch (pal.style) {
    case 0: {
      ctx.fillStyle = pal.accent;
      ctx.fillRect(0, vh * 0.26, vw, vh * 0.32);
      brandInk = accentInk;
      break;
    }
    case 1: {
      ctx.fillStyle = pal.accent;
      ctx.beginPath();
      ctx.moveTo(0, vh * 0.72);
      ctx.quadraticCurveTo(vw * 0.55, vh * 0.48, vw, vh * 0.62);
      ctx.lineTo(vw, vh);
      ctx.lineTo(0, vh);
      ctx.closePath();
      ctx.fill();
      brandY = vh * 0.36;
      break;
    }
    case 2: {
      ctx.fillStyle = shade(pal.base, 0.22);
      ctx.beginPath();
      ctx.ellipse(vw / 2, vh * 0.42, vw * 0.44, vh * 0.28, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = pal.accent;
      ctx.lineWidth = vh * 0.035;
      ctx.stroke();
      brandInk = luminance(shade(pal.base, 0.22)) > 0.42 ? "#1b1d22" : "#ffffff";
      break;
    }
    default: {
      ctx.fillStyle = pal.accent;
      ctx.fillRect(0, 0, vw, vh * 0.16);
      ctx.fillRect(0, vh * 0.86, vw, vh * 0.14);
      break;
    }
  }

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = brandInk;
  const brandPx = fitFont(ctx, text.brand, vw * 0.9, vh * 0.24, 800);
  ctx.fillText(text.brand, vw / 2, brandY, vw * 0.94);

  if (text.detail) {
    ctx.fillStyle = pal.style === 1 ? accentInk : pal.ink;
    const detailPx = Math.max(7, Math.min(brandPx * 0.62, vh * 0.12));
    ctx.font = `600 ${detailPx}px ${FONT_STACK}`;
    const lines = wrap2(ctx, text.detail, vw * 0.9);
    lines.forEach((ln, i) => {
      const y = vh * 0.66 + i * detailPx * 1.05;
      fitFont(ctx, ln, vw * 0.92, detailPx, 600);
      ctx.fillText(ln, vw / 2, y, vw * 0.94);
    });
  }
  if (text.size) {
    ctx.fillStyle = pal.style === 3 ? accentInk : pal.ink;
    fitFont(ctx, text.size, vw * 0.5, vh * 0.085, 600);
    ctx.textAlign = "right";
    ctx.fillText(text.size, vw * 0.94, vh * 0.92);
  }
  ctx.restore();
}

export interface Atlas {
  canvas: HTMLCanvasElement;
  grid: AtlasGrid;
  index: Map<string, number>;
  // Re-draw (e.g. once the web font has loaded).
  redraw: () => void;
}

export function createLabelAtlas(labels: { key: string; name: string }[], cellPx = 128): Atlas {
  const unique = [...new Map(labels.map((label) => [label.key, label])).values()];
  const grid = atlasGrid(unique.length, cellPx, cellPx);
  const [canvas, ctx] = makeCanvas(grid.width, grid.height);
  const index = new Map<string, number>();
  unique.forEach((label, i) => index.set(label.key, i));
  const redraw = () => {
    ctx.clearRect(0, 0, grid.width, grid.height);
    unique.forEach((label, i) => {
      const [px, py] = cellPixel(grid, i);
      drawLabelCell(ctx, px, py, grid.cellW, grid.cellH, label.name);
    });
  };
  redraw();
  return { canvas, grid, index, redraw };
}

// ---------------------------------------------------------------------------
// Price tags and shelf talkers

export function tagKey(price: number, promo: string): string {
  return `${price}|${promo ? 1 : 0}`;
}

function drawTag(ctx: CanvasRenderingContext2D, x0: number, y0: number, w: number, h: number, price: number, promo: boolean, currency: string) {
  ctx.save();
  ctx.translate(x0, y0);
  ctx.fillStyle = promo ? "#ffd21f" : "#fbfbf8";
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = promo ? "#d7141a" : "#0f6e78";
  ctx.fillRect(0, 0, w, h * 0.16);
  const text = formatMoney(price, currency);
  ctx.fillStyle = promo ? "#c8102e" : "#15171a";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  fitFont(ctx, text, w * 0.94, h * 0.64, 800);
  ctx.fillText(text, w / 2, h * 0.54);
  // Faux barcode.
  ctx.fillStyle = "#2a2d31";
  let bx = w * 0.08;
  let i = 0;
  while (bx < w * 0.42) {
    const bw = 1 + ((price >> i) & 1);
    ctx.fillRect(bx, h * 0.84, bw, h * 0.1);
    bx += bw + 1.5;
    i = (i + 1) % 12;
  }
  ctx.strokeStyle = "rgba(0,0,0,0.25)";
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, w - 2, h - 2);
  ctx.restore();
}

export function createTagAtlas(entries: { price: number; promo: string }[], currency: string): Atlas {
  const keys = new Map<string, { price: number; promo: boolean }>();
  for (const e of entries) keys.set(tagKey(e.price, e.promo), { price: e.price, promo: !!e.promo });
  const list = [...keys.entries()];
  const grid = atlasGrid(list.length, 128, 64, 2048);
  const [canvas, ctx] = makeCanvas(grid.width, grid.height);
  const index = new Map<string, number>();
  list.forEach(([k], i) => index.set(k, i));
  const redraw = () => {
    ctx.clearRect(0, 0, grid.width, grid.height);
    list.forEach(([, v], i) => {
      const [px, py] = cellPixel(grid, i);
      drawTag(ctx, px, py, grid.cellW, grid.cellH, v.price, v.promo, currency);
    });
  };
  redraw();
  return { canvas, grid, index, redraw };
}

export function createTalkerAtlas(promos: string[]): Atlas {
  const unique = [...new Set(promos.filter(Boolean))];
  const grid = atlasGrid(Math.max(1, unique.length), 96, 128, 2048);
  const [canvas, ctx] = makeCanvas(grid.width, grid.height);
  const index = new Map<string, number>();
  unique.forEach((p, i) => index.set(p, i));
  const redraw = () => {
    ctx.clearRect(0, 0, grid.width, grid.height);
    unique.forEach((p, i) => {
      const [px, py] = cellPixel(grid, i);
      const w = grid.cellW;
      const h = grid.cellH;
      ctx.save();
      ctx.translate(px, py);
      ctx.fillStyle = "#d9121f";
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "#ffd21f";
      ctx.fillRect(0, h * 0.7, w, h * 0.3);
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      fitFont(ctx, "SALE", w * 0.86, h * 0.26, 900);
      ctx.fillText("SALE", w / 2, h * 0.2);
      ctx.font = `700 ${h * 0.14}px ${FONT_STACK}`;
      const lines = wrap2(ctx, p, w * 0.88);
      lines.forEach((ln, li) => {
        fitFont(ctx, ln, w * 0.9, h * 0.14, 700);
        ctx.fillText(ln, w / 2, h * 0.43 + li * h * 0.14);
      });
      ctx.fillStyle = "#c8102e";
      fitFont(ctx, "DEAL", w * 0.7, h * 0.16, 900);
      ctx.fillText("DEAL", w / 2, h * 0.85);
      ctx.restore();
    });
  };
  redraw();
  return { canvas, grid, index, redraw };
}

// ---------------------------------------------------------------------------
// Signage

export function signText(rackName: string, fallback: string): string {
  const t = rackName.replace(/\s*[#-]?\d+$/, "").trim();
  return (t || fallback).toUpperCase();
}

export type SignStyle = "header" | "fridge" | "wall" | "exit";

export function signKey(text: string, style: SignStyle): string {
  return `${style}|${text}`;
}

export function createSignAtlas(signs: { text: string; style: SignStyle }[]): Atlas {
  const keys = new Map<string, { text: string; style: SignStyle }>();
  for (const s of signs) keys.set(signKey(s.text, s.style), s);
  const list = [...keys.entries()];
  const grid = atlasGrid(Math.max(1, list.length), 512, 96, 4096);
  const [canvas, ctx] = makeCanvas(grid.width, grid.height);
  const index = new Map<string, number>();
  list.forEach(([k], i) => index.set(k, i));
  const redraw = () => {
    ctx.clearRect(0, 0, grid.width, grid.height);
    list.forEach(([, s], i) => {
      const [px, py] = cellPixel(grid, i);
      const w = grid.cellW;
      const h = grid.cellH;
      ctx.save();
      ctx.translate(px, py);
      if (s.style === "fridge") {
        const g = ctx.createLinearGradient(0, 0, 0, h);
        g.addColorStop(0, "#1b2733");
        g.addColorStop(1, "#0d141b");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = "#e8f6ff";
      } else if (s.style === "exit") {
        ctx.fillStyle = "#0a8f43";
        ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = "#ffffff";
      } else if (s.style === "wall") {
        ctx.fillStyle = "#0f6e78";
        ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = "#ffffff";
      } else {
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, w, h);
        ctx.fillStyle = "#0f6e78";
        ctx.fillRect(0, 0, h * 0.18, h);
        ctx.fillRect(w - h * 0.18, 0, h * 0.18, h);
        ctx.fillStyle = "#f4c542";
        ctx.fillRect(0, h * 0.86, w, h * 0.14);
        ctx.fillStyle = "#14363a";
      }
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      fitFont(ctx, s.text, w * 0.8, h * 0.56, 800);
      ctx.fillText(s.text, w / 2, h * 0.47);
      ctx.restore();
    });
  };
  redraw();
  return { canvas, grid, index, redraw };
}

// ---------------------------------------------------------------------------
// Surfaces

// Light-grey porcelain tiles: colour + roughness canvases covering `units`×`units`
// world units with 0.5-unit tiles.
export function createFloorCanvases(units = 4, px = 1024): { color: HTMLCanvasElement; rough: HTMLCanvasElement } {
  const [color, c] = makeCanvas(px, px);
  const [rough, r] = makeCanvas(px, px);
  const tiles = units * 2;
  const tp = px / tiles;
  const grout = Math.max(2, Math.round(tp * 0.025));
  c.fillStyle = "#a9adb1";
  c.fillRect(0, 0, px, px);
  r.fillStyle = "#e0e0e0";
  r.fillRect(0, 0, px, px);
  for (let ty = 0; ty < tiles; ty++) {
    for (let tx = 0; tx < tiles; tx++) {
      const key = `${tx},${ty}`;
      const tone = 214 + Math.round((hash01(key, 11) - 0.5) * 10);
      c.fillStyle = `rgb(${tone},${tone + 1},${tone + 1})`;
      c.fillRect(tx * tp + grout / 2, ty * tp + grout / 2, tp - grout, tp - grout);
      const rv = 70 + Math.round(hash01(key, 12) * 30);
      r.fillStyle = `rgb(${rv},${rv},${rv})`;
      r.fillRect(tx * tp + grout / 2, ty * tp + grout / 2, tp - grout, tp - grout);
      // Soft cloudy variation inside the tile.
      for (let k = 0; k < 3; k++) {
        const gx = tx * tp + hash01(key, 20 + k) * tp;
        const gy = ty * tp + hash01(key, 30 + k) * tp;
        const rad = tp * (0.25 + hash01(key, 40 + k) * 0.35);
        const g = c.createRadialGradient(gx, gy, 0, gx, gy, rad);
        const a = 0.035 + hash01(key, 50 + k) * 0.03;
        g.addColorStop(0, hash01(key, 60 + k) > 0.5 ? `rgba(255,255,255,${a})` : `rgba(120,124,128,${a})`);
        g.addColorStop(1, "rgba(0,0,0,0)");
        c.fillStyle = g;
        c.save();
        c.beginPath();
        c.rect(tx * tp + grout / 2, ty * tp + grout / 2, tp - grout, tp - grout);
        c.clip();
        c.fillRect(gx - rad, gy - rad, rad * 2, rad * 2);
        c.restore();
      }
    }
  }
  // Fine speckle (terrazzo-like grain).
  const n = Math.round(px * px * 0.004);
  for (let i = 0; i < n; i++) {
    const x = hash01(`s${i}`, 1) * px;
    const y = hash01(`s${i}`, 2) * px;
    const v = hash01(`s${i}`, 3);
    c.fillStyle = v > 0.5 ? "rgba(255,255,255,0.35)" : "rgba(90,94,98,0.22)";
    c.fillRect(x, y, 1.2, 1.2);
  }
  return { color, rough };
}

export function createCeilingCanvas(px = 512): HTMLCanvasElement {
  // 2×2 world units, 0.5-unit acoustic tiles in a T-bar grid.
  const [cv, c] = makeCanvas(px, px);
  c.fillStyle = "#eceeef";
  c.fillRect(0, 0, px, px);
  const tp = px / 4;
  for (let i = 0; i < 2600; i++) {
    c.fillStyle = "rgba(150,155,160,0.25)";
    c.fillRect(hash01(`c${i}`, 1) * px, hash01(`c${i}`, 2) * px, 1.4, 1.4);
  }
  c.fillStyle = "#c9cdd1";
  for (let k = 0; k <= 4; k++) {
    c.fillRect(k * tp - 2, 0, 4, px);
    c.fillRect(0, k * tp - 2, px, 4);
  }
  return cv;
}

// Soft rounded-rectangle shadow (white RGB, alpha falloff) for fake contact AO.
export function createAoCanvas(px = 128): HTMLCanvasElement {
  const [cv, c] = makeCanvas(px, px);
  const img = c.createImageData(px, px);
  for (let y = 0; y < px; y++) {
    for (let x = 0; x < px; x++) {
      const dx = Math.max(0, Math.abs((x + 0.5) / px - 0.5) * 2 - 0.55) / 0.45;
      const dy = Math.max(0, Math.abs((y + 0.5) / px - 0.5) * 2 - 0.55) / 0.45;
      const d = Math.min(1, Math.sqrt(dx * dx + dy * dy));
      const a = (1 - d) * (1 - d);
      const i = (y * px + x) * 4;
      img.data[i] = 0;
      img.data[i + 1] = 0;
      img.data[i + 2] = 0;
      img.data[i + 3] = Math.round(a * 255);
    }
  }
  c.putImageData(img, 0, 0);
  return cv;
}

// Vertical wood-grain laminate for the counter front.
export function createWoodCanvas(px = 256): HTMLCanvasElement {
  const [cv, c] = makeCanvas(px, px);
  c.fillStyle = "#9b7350";
  c.fillRect(0, 0, px, px);
  for (let i = 0; i < 90; i++) {
    const x = hash01(`w${i}`, 1) * px;
    const w = 1 + hash01(`w${i}`, 2) * 3;
    const dark = hash01(`w${i}`, 3) > 0.5;
    c.fillStyle = dark ? "rgba(70,45,25,0.18)" : "rgba(220,180,140,0.12)";
    c.fillRect(x, 0, w, px);
  }
  for (let k = 0; k < 4; k++) {
    c.fillStyle = "rgba(60,40,22,0.35)";
    c.fillRect((k * px) / 4, 0, 2, px);
  }
  return cv;
}
