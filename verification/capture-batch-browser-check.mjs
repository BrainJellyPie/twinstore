// Offline integration regression. See 2026-10-21-capture-batch-review.md for setup.
// PLAYWRIGHT_MODULE can point to an independently installed playwright/index.mjs.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.CAPTURE_TEST_ORIGIN || 'http://127.0.0.1:18765';
const pid = 'proj_67916afd';
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'],
});
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  async function preview() {
    await page.goto(`${origin}/capture/${pid}`);
    await page.getByRole('button', { name: 'Combine reviewed shelf photos' }).click();
    await page.getByRole('combobox', { name: /Base layout/ }).selectOption('setup_batch_base');
    await page.getByRole('button', { name: 'Select first 20 ready photos' }).click();
    await page.getByRole('button', { name: 'Preview combined layout' }).waitFor();
    await page.getByRole('button', { name: 'Preview combined layout' }).click();
    await page.getByRole('button', { name: 'Save combined draft' }).waitFor();
  }
  await preview();
  // Ordinary user scrolling must reach Save; Playwright's click auto-scroll hid this defect.
  const panel = page.getByRole('region', { name: 'Combine shelf photos' });
  const bounds = await panel.boundingBox();
  assert(bounds);
  await page.mouse.move(bounds.x + bounds.width / 2, Math.min(bounds.y + bounds.height - 20, 850));
  const save = page.getByRole('button', { name: 'Save combined draft' });
  let rect = await save.boundingBox();
  // A layout/font transition can consume the first wheel event; allow repeated user scrolling.
  for (let attempt = 0; attempt < 10 && !(rect && rect.y >= 0 && rect.y + rect.height <= 900); attempt++) {
    await page.mouse.wheel(0, 1600);
    await page.waitForTimeout(150);
    rect = await save.boundingBox();
  }
  console.log(JSON.stringify({panel: bounds, save: rect}));
  await page.screenshot({ path: 'capture-batch-desktop-preview.png' });
  assert(rect && rect.y >= 0 && rect.y + rect.height <= 900, 'Save must be reachable with ordinary scrolling');
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/captures/batch-save'));
  await save.click();
  const response = await responsePromise;
  assert(response.ok(), await response.text());
  const saved = await response.json();
  await page.getByText('Combined draft saved. Your source layout is unchanged.').waitFor();
  await page.getByRole('button', { name: 'Open combined layout' }).click();
  await page.waitForURL(`**/projects/${pid}`);
  const reloaded = await page.request.get(`${origin}/api/projects/${pid}/setups/${saved.setup_id}`);
  assert(reloaded.ok());
  const draft = await reloaded.json();
  const skus = [...new Set(draft.store.racks.flatMap(rack => rack.slots.flatMap(slot => slot.items.map(item => item.sku))))].sort();
  assert.deepEqual(skus, ['photo_sku0', 'photo_sku1']);
  assert.equal(draft.parentId, 'setup_batch_base');
  await page.setViewportSize({ width: 390, height: 844 });
  await preview();
  await save.scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'capture-batch-mobile-preview.png' });
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ saved, skus, desktopWheelReachable: true, mobilePreview: true, pageErrors: errors }));
} finally {
  await browser.close();
}
