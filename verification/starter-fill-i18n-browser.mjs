// Real UI/API; first seed a fresh disposable directory with starter-fill-browser-seed.py.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from '../frontend/node_modules/typescript/lib/typescript.js';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
async function catalog(file, key) {
  const code = ts.transpileModule(fs.readFileSync(new URL(`../frontend/src/shared/i18n/${file}`, import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  return (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`))[key];
}
const messages = { ...await catalog('messages/store.ts', 'storeMessages'), ...await catalog('starterMessages.ts', 'starterMessages'), ...await catalog('bulkMessages.ts', 'bulkMessages'), ...await catalog('rackCopyMessages.ts', 'rackCopyMessages') };
const origin = process.env.STARTER_TEST_ORIGIN || 'http://127.0.0.1:18775';
const pid = 'proj_67916afd', sid = 'setup_starter_fixture';
const { sku } = JSON.parse(fs.readFileSync('fixture.json', 'utf8'));
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
const results = [];
try {
  const api = await browser.newContext();
  const original = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  const options = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}/starter-fill`)).json();
  assert(original.store && options.categories, 'Seed the disposable fixture first');
  for (const [index, locale] of ['en', 'ko', 'zh', 'ja', 'es', 'fr'].entries()) {
    if (process.env.STARTER_TEST_LOCALES && !process.env.STARTER_TEST_LOCALES.split(',').includes(locale)) continue;
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale });
    await context.addInitScript(code => { localStorage.setItem('twinstore.locale', code); localStorage.setItem('parastore.graphicsMode', 'classic'); }, locale);
    const page = await context.newPage(); page.setDefaultTimeout(30000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const t = (key, values = {}) => messages[key][index].replace(/\{(\w+)\}/g, (_, name) => values[name]);
    await page.goto(`${origin}/projects/${pid}`);
    await page.locator(`[data-layout-id="${sid}"]`).click();
    await page.getByRole('button', { name: t('starterEntry'), exact: true }).click();
    const dialog = page.getByRole('dialog');
    await page.getByText(t('starterAutoHelp'), { exact: true }).waitFor();
    await page.getByText(t('starterExamples', { editor: t('bulkTitle') }), { exact: true }).waitFor();
    await page.getByLabel(t('starterManualMode'), { exact: true }).check();
    assert(await page.getByRole('checkbox', { name: t('starterSelectRack', { rack: 'stocked' }), exact: true }).isDisabled());
    await page.getByText(t('copyReasonOccupied'), { exact: true }).waitFor();
    const categories = page.getByRole('combobox', { name: t('starterCategoryToApply'), exact: true });
    const categoryValues = await categories.locator('option').evaluateAll(els => els.map(el => el.value).filter(Boolean));
    assert.deepEqual(categoryValues, options.categories.map(c => c.key));
    await categories.selectOption('water_sports');
    await page.getByRole('button', { name: t('starterSelectShown'), exact: true }).click();
    const previewResponse = page.waitForResponse(r => r.url().endsWith('/starter-fill/preview') && r.request().method() === 'POST');
    await page.getByRole('button', { name: t('starterPreview'), exact: true }).click();
    const preview = await (await previewResponse).json();
    const save = page.getByRole('button', { name: t('starterSave'), exact: true }); await save.waitFor();
    const review = page.getByRole('region', { name: t('starterPreviewRegion'), exact: true });
    await review.locator('details').evaluateAll(els => els.forEach(el => { el.open = true; }));
    assert((await review.innerText()).includes('My water'));
    for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 640 }]) {
      await page.setViewportSize(viewport); await save.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `starter-i18n-${locale}-${viewport.width}.png` });
      const overflow = await dialog.evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
      assert(overflow.scrollWidth <= overflow.width + 1, `${locale}: overflow ${JSON.stringify(overflow)}`);
      const reachable = () => save.evaluate(el => {
        const r = el.getBoundingClientRect(), hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        return r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth && !!hit && el.contains(hit);
      });
      if (!await reachable()) {
        console.log(JSON.stringify({ locale, viewport, beforeScroll: await save.boundingBox(), dialog: await dialog.evaluate(el => ({ scrollTop: el.scrollTop, height: el.clientHeight, scrollHeight: el.scrollHeight })) }));
        const bounds = await dialog.boundingBox(); assert(bounds);
        await page.mouse.move(bounds.x + bounds.width - 15, bounds.y + bounds.height / 2);
        for (let step = 0; step < 15 && !await reachable(); step++) {
          await page.mouse.wheel(0, 1200); await page.waitForTimeout(150);
        }
      }
      assert(await reachable(), `${locale}: save reachable at ${viewport.width}`);
      await page.screenshot({ path: `starter-i18n-${locale}-${viewport.width}.png` });
    }
    let accepted;
    await page.route('**/starter-fill/save', async route => { accepted = await (await route.fetch()).json(); await route.abort(); }, { times: 1 });
    await save.click();
    const replayResponse = page.waitForResponse(r => r.url().endsWith('/starter-fill/save') && r.request().method() === 'POST');
    await page.getByRole('button', { name: t('starterRetrySave'), exact: true }).click();
    const response = await replayResponse; assert(response.ok()); const saved = await response.json();
    assert.deepEqual(saved, accepted);
    const body = response.request().postDataJSON();
    assert.deepEqual(body.assignments.map(r => r.category), ['water_sports', 'water_sports']);
    assert.equal(body.currency, 'USD');
    await page.getByRole('button', { name: t('starterOpen'), exact: true }).click();
    await page.locator(`[data-layout-id="${saved.setup_id}"][aria-selected="true"]`).waitFor();
    const child = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${saved.setup_id}`)).json();
    const items = store => store.racks.flatMap(r => r.slots.flatMap(s => s.items));
    assert.equal(items(child.store).length - items(original.store).length, preview.placements_added);
    const reused = items(child.store).filter(p => p.sku === sku);
    assert(reused.length > 1 && reused.every(p => p.name === 'My water' && p.price === 231 && p.promo === 'Local' && p.image_url));
    for (const rack of original.store.racks) {
      const copy = child.store.racks.find(r => r.id === rack.id);
      if (['empty', 'fridge'].includes(rack.id)) assert.deepEqual({ ...copy, slots: [] }, { ...rack, slots: [] });
      else assert.deepEqual(copy, rack);
    }
    assert.deepEqual(errors, []);
    results.push({ locale, viewports: 2, setup_id: saved.setup_id, categories: categoryValues.length, placements: preview.placements_added, replayedSave: true, originalPreserved: true });
    await context.close();
  }
  assert.deepEqual((await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, original.store);
  await api.close(); console.log(JSON.stringify(results));
} finally { await browser.close(); }
