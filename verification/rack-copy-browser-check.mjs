// Run in the disposable directory seeded by rack-copy-browser-seed.py.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = process.env.RACK_COPY_TEST_ORIGIN || 'http://127.0.0.1:18770';
const pid = 'proj_67916afd', sid = 'setup_copy_fixture';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } }), errors = [];
  page.setDefaultTimeout(30000);
  // Use the supported classic renderer for stable software-GL UI checks.
  await page.addInitScript(() => localStorage.setItem('parastore.graphicsMode', 'classic'));
  page.on('pageerror', error => errors.push(error.message));
  const source = await (await page.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  await page.goto(`${origin}/projects/${pid}`);
  await page.locator(`[data-layout-id="${sid}"]`).click();
  await page.getByRole('button', { name: 'Reuse shelf products', exact: true }).click();
  await page.getByRole('combobox', { name: 'Copy products from', exact: true }).selectOption('source');
  assert(await page.getByLabel('Copy to rack fridge', { exact: true }).isDisabled());
  assert(await page.getByLabel('Copy to rack source', { exact: true }).isDisabled());
  await page.getByRole('button', { name: 'Select shown compatible shelves', exact: true }).click();
  await page.getByRole('button', { name: 'Preview shelf copies', exact: true }).click();
  const save = page.getByRole('button', { name: 'Save layout with shelf copies', exact: true });
  await save.waitFor();
  assert((await page.getByRole('region', { name: 'Shelf copy preview' }).innerText()).includes('2 destinations, 6 added placements'));
  assert((await page.getByRole('region', { name: 'Shelf copy preview' }).innerText()).includes('regular price 2.99 USD'));
  assert((await page.getByRole('region', { name: 'Shelf copy preview' }).innerText()).includes('image retained'));
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
    await page.screenshot({ path: `rack-copy-${viewport.width}x${viewport.height}.png` });
  }
  let accepted;
  await page.route('**/rack-copy/save', async route => { accepted = await (await route.fetch()).json(); await route.abort(); }, { times: 1 });
  await save.click();
  await page.getByRole('button', { name: 'Retry saving shelf copies', exact: true }).click();
  await page.getByRole('button', { name: 'Open copied layout', exact: true }).click();
  assert(accepted?.setup_id);
  await page.locator(`[data-layout-id="${accepted.setup_id}"][aria-selected="true"]`).waitFor();
  await page.getByRole('button', { name: 'Edit products together', exact: true }).click();
  await page.getByLabel('Search products or racks', { exact: true }).fill('tea');
  assert.equal(await page.getByLabel('Name for tea', { exact: true }).inputValue(), 'Tea');
  assert.equal(await page.getByLabel('Price for tea', { exact: true }).inputValue(), '2.31');
  const draft = await (await page.request.get(`${origin}/api/projects/${pid}/setups/${accepted.setup_id}`)).json();
  const rackSource = source.store.racks.find(r => r.id === 'source');
  assert(rackSource.slots[0].items[0].image_url);
  for (const rack of source.store.racks) {
    const copy = draft.store.racks.find(r => r.id === rack.id);
    if (['empty', 'empty2'].includes(rack.id)) {
      assert.deepEqual({ ...copy, slots: [] }, { ...rack, slots: [] });
      assert.deepEqual(copy.slots, rackSource.slots);
    } else assert.deepEqual(copy, rack);
  }
  assert.deepEqual((await (await page.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, source.store);
  assert.equal(draft.parentId, sid); assert.deepEqual(errors, []);
  console.log(JSON.stringify({ accepted, originalPreserved: true, exactProductOrderLevelsPricesAndImages: true, viewportChecks: 3, pageErrors: errors }));
} finally { await browser.close(); }
