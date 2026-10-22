// Run in a disposable directory seeded by library-photos-browser-seed.py.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.PHOTO_TEST_ORIGIN || 'http://127.0.0.1:18771';
const pid = 'proj_67916afd', sid = 'setup_photos_fixture';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } }), errors = [];
  page.setDefaultTimeout(30000);
  await page.addInitScript(() => localStorage.setItem('parastore.graphicsMode', 'classic'));
  page.on('pageerror', error => errors.push(error.message));
  const source = await (await page.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  // Start with the real existing image-upload screen; disable optional model reading explicitly.
  await page.goto(`${origin}/marketing/${pid}`);
  await page.getByRole('tab', { name: 'Products', exact: true }).click();
  await page.getByLabel('Name packs from what they say', { exact: true }).uncheck();
  await page.getByLabel('Remove a plain background', { exact: true }).uncheck();
  await page.locator('input[type=file]').setInputFiles('synthetic-tea.png');
  await page.getByRole('img', { name: 'synthetic tea', exact: true }).waitFor();
  const assets = await (await page.request.get(`${origin}/api/projects/${pid}/lab/packages`)).json();
  assert.equal(assets.length, 1);
  await page.goto(`${origin}/projects/${pid}`);
  await page.locator(`[data-layout-id="${sid}"]`).click();
  await page.getByRole('button', { name: 'Use library photos', exact: true }).click();
  await page.getByRole('combobox', { name: 'Photo for tea', exact: true }).selectOption(assets[0].asset_id);
  await page.getByRole('button', { name: 'Preview product photos', exact: true }).click();
  const save = page.getByRole('button', { name: 'Save layout with photos', exact: true });
  await save.waitFor();
  assert((await page.getByRole('region', { name: 'Product photo preview' }).innerText()).includes('Products: 1 · Placements: 2'));
  assert(await page.getByAltText('Saved photo for tea', { exact: true }).evaluate(img => img.complete && img.naturalWidth > 0));
  const reachable = () => save.evaluate(button => {
    const r = button.getBoundingClientRect(), d = button.closest('[role="dialog"]').getBoundingClientRect();
    const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return r.top >= Math.max(0, d.top) && r.bottom <= Math.min(innerHeight, d.bottom)
      && r.left >= Math.max(0, d.left) && r.right <= Math.min(innerWidth, d.right) && !!hit && button.contains(hit);
  });
  for (const viewport of [{ width: 1280, height: 900 }, { width: 1280, height: 640 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport); await page.waitForTimeout(300);
    const d = await page.getByRole('dialog').boundingBox(); assert(d);
    await page.mouse.move(d.x + d.width - 15, d.y + d.height / 2);
    for (let n = 0; n < 15 && !await reachable(); n++) { await page.mouse.wheel(0, 1200); await page.waitForTimeout(150); }
    assert(await reachable(), `Save reachable at ${viewport.width} x ${viewport.height}`);
    await page.screenshot({ path: `library-photos-${viewport.width}x${viewport.height}.png` });
  }
  let accepted;
  await page.route('**/library-photos/save', async route => { accepted = await (await route.fetch()).json(); await route.abort(); }, { times: 1 });
  await save.click();
  await page.getByRole('button', { name: 'Retry saving photo layout', exact: true }).click();
  await page.getByRole('button', { name: 'Open photo layout', exact: true }).click();
  assert(accepted?.setup_id);
  await page.locator(`[data-layout-id="${accepted.setup_id}"][aria-selected="true"]`).waitFor();
  await page.request.delete(`${origin}/api/projects/${pid}/lab/packages/${assets[0].asset_id}`);
  const draft = await (await page.request.get(`${origin}/api/projects/${pid}/setups/${accepted.setup_id}`)).json();
  let imageCount = 0;
  for (const rack of draft.store.racks) for (const slot of rack.slots) for (const item of slot.items) if (item.sku === 'tea') {
    assert.equal((await page.request.get(`${origin}${item.image_url}`)).status(), 200); imageCount++;
    item.image_url = null;
  }
  assert.equal(imageCount, 2); assert.deepEqual(draft.store, source.store);
  assert.deepEqual((await (await page.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, source.store);
  assert.equal(draft.parentId, sid); assert.deepEqual(errors, []);
  console.log(JSON.stringify({ accepted, originalPreserved: true, savedPhotosSurviveLibraryDeletion: true, actualUploadUI: true, viewportChecks: 3, pageErrors: errors }));
} finally { await browser.close(); }
