import { createRequire } from "module";
import { pathToFileURL } from "url";
const require = createRequire("/opt/node22/lib/node_modules/");
let pw; try { pw = require("playwright"); } catch { pw = await import("/opt/node-tools/node_modules/playwright/index.mjs"); }
const [src, out] = process.argv.slice(2);
const browser = await pw.chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(src).href, { waitUntil: "load" });
await page.evaluate(() => document.fonts.ready);
await page.pdf({ path: out, format: "A4", printBackground: true, displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate: "<div style='font:8px Inter,sans-serif;color:#8a90a3;width:100%;padding:0 16mm;display:flex;justify-content:space-between'><span>TwinStore technical report</span><span class='pageNumber'></span></div>",
  margin: { top: "16mm", bottom: "18mm", left: "16mm", right: "16mm" } });
await browser.close();
console.log("pdf", out);
