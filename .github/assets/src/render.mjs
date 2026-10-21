// Renders the figure pages in this folder to PNGs in ../twinstore/ (white background, 2x).
//   node .github/assets/src/render.mjs [page.html ...]
// Needs Playwright with Chromium and the frontend's node_modules (fonts).
import { readdirSync, mkdirSync } from "node:fs";
import { dirname, join, basename } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));
let pw;
for (const from of [here, "/opt/node22/lib/node_modules/", "/opt/node-tools/node_modules/"]) {
  try { pw = createRequire(join(from, "x.js"))("playwright"); break; } catch { /* next */ }
}
const out = join(here, "..", "twinstore");
mkdirSync(out, { recursive: true });
const pages = process.argv.slice(2).length ? process.argv.slice(2) : readdirSync(here).filter((f) => f.endsWith(".html") && !f.startsWith("_") && !f.startsWith("promo"));

const browser = await pw.chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 2 });
page.on("console", (m) => { if (m.type() === "warning" || m.type() === "error") console.log(`  [${m.type()}]`, m.text()); });
for (const file of pages) {
  await page.goto(pathToFileURL(join(here, basename(file))).href);
  await page.waitForFunction(() => window.figureReady === true, null, { timeout: 15000 });
  const canvas = await page.$(".canvas");
  const name = basename(file, ".html") + ".png";
  await canvas.screenshot({ path: join(out, name) });
  console.log("figure", name);
}
await browser.close();
