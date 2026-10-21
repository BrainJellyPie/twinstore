// Renders icon.html to the PNG sizes the launchers need. Needs Playwright with Chromium:
//   node launcher/icon/render.mjs            (writes launcher/icon/png/*.png)
// then `python3 launcher/icon/pack.py` turns them into twinstore.ico and TwinStore.icns.
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
let pw;
for (const from of [here, "/opt/node22/lib/node_modules/", "/opt/node-tools/node_modules/"]) {
  try { pw = createRequire(join(from, "x.js"))("playwright"); break; } catch { /* next */ }
}
pw ??= require("playwright");

const out = join(here, "png");
mkdirSync(out, { recursive: true });
const browser = await pw.chromium.launch();
const page = await browser.newPage({ viewport: { width: 1024, height: 1024 } });
const url = pathToFileURL(join(here, "icon.html")).href;

// [file, variant, small, size]
const jobs = [
  ["mac-1024.png", "mac", false, 1024],
  ["flat-1024.png", "flat", false, 1024],
  ["flat-small-1024.png", "flat", true, 1024],
];
for (const [file, variant, small] of jobs) {
  await page.goto(`${url}?variant=${variant}${small ? "&small=1" : ""}`);
  await page.waitForTimeout(150);
  await page.screenshot({ path: join(out, file), omitBackground: true });
  console.log("icon", file);
}
await browser.close();
