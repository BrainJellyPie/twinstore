// Renders promo.html frame by frame and encodes it with ffmpeg:
//   node .github/assets/src/render-video.mjs [--fps 30] [--from 0] [--to 55.2] [--stills 2,12,24]
// Writes ../twinstore/twinstore-promo.mp4, a ~23 s WebP teaser of highlights and a poster frame. Needs Playwright
// (Chromium), ffmpeg on PATH and the frontend's node_modules (fonts).
import { mkdirSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";

const here = dirname(fileURLToPath(import.meta.url));
const arg = (name, dflt) => { const i = process.argv.indexOf(`--${name}`); return i > 0 ? process.argv[i + 1] : dflt; };
let pw;
for (const from of [here, "/opt/node22/lib/node_modules/", "/opt/node-tools/node_modules/"]) {
  try { pw = createRequire(join(from, "x.js"))("playwright"); break; } catch { /* next */ }
}
const out = join(here, "..", "twinstore");
const frames = arg("frames", join(tmpdir(), "twinstore-promo-frames"));
const fps = Number(arg("fps", "30"));
rmSync(frames, { recursive: true, force: true });
mkdirSync(frames, { recursive: true });

const browser = await pw.chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(join(here, "promo.html")).href);
await page.waitForFunction(() => window.promoReady === true);
const duration = await page.evaluate(() => window.DURATION);
const from = Number(arg("from", "0")), to = Number(arg("to", String(duration)));

const stills = arg("stills", "");
if (stills) {
  for (const s of stills.split(",")) {
    await page.evaluate((t) => window.seek(t), Number(s));
    await page.waitForTimeout(60);
    await page.screenshot({ path: join(frames, `still-${s}.jpg`), type: "jpeg", quality: 90 });
    console.log("still", s);
  }
  await browser.close();
  process.exit(0);
}

const stage = await page.$("#stage");
const count = Math.round((to - from) * fps);
for (let i = 0; i < count; i++) {
  await page.evaluate((t) => window.seek(t), from + i / fps);
  await stage.screenshot({ path: join(frames, `${String(i).padStart(5, "0")}.jpg`), type: "jpeg", quality: 93 });
  if (i % 150 === 0) console.log(`frame ${i}/${count}`);
}
await page.evaluate((t) => window.seek(t), 52.7);
await stage.screenshot({ path: join(out, "twinstore-promo-poster.jpg"), type: "jpeg", quality: 90 });
await browser.close();

const ff = (args) => execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", ...args], { stdio: "inherit" });
ff(["-framerate", String(fps), "-i", join(frames, "%05d.jpg"), "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", join(out, "twinstore-promo.mp4")]);
// teaser for the README: highlights of seven scenes, animated WebP (GitHub plays it inline)
const cuts = [[0.3, 4.0], [10.2, 13.6], [17.2, 20.4], [22.2, 25.6], [33.4, 36.8], [45.1, 48.4], [50.6, 54.0]];
const trims = cuts.map(([a, b], i) => `[0:v]trim=${a}:${b},setpts=PTS-STARTPTS[c${i}]`).join(";");
const concat = cuts.map((_, i) => `[c${i}]`).join("") + `concat=n=${cuts.length}:v=1,fps=15,scale=800:-1:flags=lanczos[v]`;
ff(["-i", join(out, "twinstore-promo.mp4"), "-filter_complex", `${trims};${concat}`, "-map", "[v]", "-c:v", "libwebp_anim", "-lossless", "0", "-q:v", "88", "-preset", "picture", "-compression_level", "4", "-loop", "0", join(out, "twinstore-teaser.webp")]);
console.log("wrote twinstore-promo.mp4, twinstore-teaser.webp, twinstore-promo-poster.jpg");
