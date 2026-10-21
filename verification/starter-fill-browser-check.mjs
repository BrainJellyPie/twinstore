// Run in the disposable directory seeded by starter-fill-browser-seed.py.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.STARTER_TEST_ORIGIN || 'http://127.0.0.1:18768';
const pid = 'proj_67916afd', sid = 'setup_starter_fixture';
const { sku } = JSON.parse(await readFile('fixture.json', 'utf8'));
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } }), errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const source = await (await page.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  await page.goto(`${origin}/projects/${pid}`);
  await page.locator(`[data-layout-id="${sid}"]`).click();
  await page.getByRole('button', { name: 'Fill empty shelves', exact: true }).click();
  assert(await page.getByLabel('Select rack stocked', { exact: true }).isDisabled());
  await page.getByRole('combobox', { name: 'Category to apply', exact: true }).selectOption('water_sports');
  await page.getByRole('button', { name: 'Select shown empty racks', exact: true }).click();
  await page.getByRole('button', { name: 'Preview starter products', exact: true }).click();
  const save = page.getByRole('button', { name: 'Save stocked layout', exact: true });
  await save.waitFor();
  assert((await page.getByRole('region', { name: 'Starter product preview' }).innerText()).includes('40 placements'));
  const reachable = () => save.evaluate(button => {
    const r = button.getBoundingClientRect(), d = button.closest('[role="dialog"]').getBoundingClientRect();
    const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return r.top >= Math.max(0, d.top) && r.bottom <= Math.min(innerHeight, d.bottom)
      && r.left >= Math.max(0, d.left) && r.right <= Math.min(innerWidth, d.right) && !!hit && button.contains(hit);
  });
  for (const viewport of [{ width: 1280, height: 900 }, { width: 1280, height: 640 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport); await page.waitForTimeout(300);
    const d = await page.getByRole('dialog').boundingBox(); assert(d);
    await page.mouse.move(d.x + d.width - 15, Math.min(viewport.height - 30, d.y + d.height - 25));
    for (let n = 0; n < 15 && !await reachable(); n++) { await page.mouse.wheel(0, 1200); await page.waitForTimeout(150); }
    console.log(JSON.stringify({ viewport, save: await save.boundingBox(), dialog: await page.getByRole('dialog').evaluate(el => ({ scrollTop: el.scrollTop, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, rect: el.getBoundingClientRect().toJSON() })) }));
    await page.screenshot({ path: `starter-${viewport.width}x${viewport.height}.png`, timeout: 15000 });
    assert(await reachable(), `Save reachable at ${viewport.width} x ${viewport.height}`);
  }
  // Lose one save response after the real API has committed, then repeat the same request.
  let accepted;
  await page.route('**/starter-fill/save', async route => { accepted = await (await route.fetch()).json(); await route.abort(); }, { times: 1 });
  await save.click();
  await page.getByRole('button', { name: 'Retry saving starter draft', exact: true }).click();
  await page.getByRole('button', { name: 'Open stocked layout', exact: true }).click();
  assert(accepted?.setup_id);
  await page.locator(`[data-layout-id="${accepted.setup_id}"][aria-selected="true"]`).waitFor();
  await page.getByRole('button', { name: 'Edit products together', exact: true }).click();
  await page.getByLabel('Search products or racks', { exact: true }).fill(sku);
  assert.equal(await page.getByLabel(`Name for ${sku}`, { exact: true }).inputValue(), 'My water');
  assert.equal(await page.getByLabel(`Price for ${sku}`, { exact: true }).inputValue(), '2.31');
  const draft = await (await page.request.get(`${origin}/api/projects/${pid}/setups/${accepted.setup_id}`)).json();
  const flatten = store => store.racks.flatMap(r => r.slots.flatMap(s => s.items));
  assert.equal(flatten(draft.store).length - flatten(source.store).length, 40);
  const reused = flatten(draft.store).filter(p => p.sku === sku);
  assert(reused.length > 1 && reused.every(p => p.price === 231 && p.name === 'My water' && p.image_url));
  for (const rack of source.store.racks) {
    const copy = draft.store.racks.find(r => r.id === rack.id);
    if (rack.id === 'empty' || rack.id === 'fridge') assert.deepEqual({ ...copy, slots: [] }, { ...rack, slots: [] });
    else assert.deepEqual(copy, rack);
  }
  assert.deepEqual((await (await page.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, source.store);
  assert.equal(draft.parentId, sid); assert.deepEqual(errors, []);
  console.log(JSON.stringify({ accepted, originalPreserved: true, existingProductsAndImagesPreserved: true, reusedPlacements: reused.length, pageErrors: errors }));
} finally { await browser.close(); }
