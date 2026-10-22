// Real UI/API on the disposable fixture made by starter-fill-browser-seed.py.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from '../frontend/node_modules/typescript/lib/typescript.js';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
async function catalog(file, key) {
  const source = fs.readFileSync(new URL(`../frontend/src/shared/i18n/${file}`, import.meta.url), 'utf8')
    .replace(/^import .*;\n/gm, '').replace(/^\s*\.\.\.\w+,\n/gm, '');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  return (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`))[key];
}
const messages = { ...await catalog('messages.ts', 'messages'), ...await catalog('messages/layout.ts', 'layoutMessages'), ...await catalog('floorPlanMessages.ts', 'floorPlanMessages'), ...await catalog('floorCompareMessages.ts', 'floorCompareMessages'), ...await catalog('optionsFileMessages.ts', 'optionsFileMessages'), ...await catalog('starterCategoryMessages.ts', 'starterCategoryMessages'), ...await catalog('messages/studio.ts', 'studioMessages') };
const origin = process.env.AREA_TEST_ORIGIN || 'http://127.0.0.1:18775';
const pid = 'proj_67916afd', sid = 'setup_starter_fixture';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
const results = [];
try {
  const api = await browser.newContext();
  const original = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  const formats = await (await api.request.get(`${origin}/api/store-templates`)).json();
  const format = formats.find(f => f.id === 'fashion_boutique'); assert(format?.categories?.length > 1);
  for (const [index, locale] of ['en', 'ko', 'zh', 'ja', 'es', 'fr'].entries()) {
    if (process.env.AREA_TEST_LOCALES && !process.env.AREA_TEST_LOCALES.split(',').includes(locale)) continue;
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale, acceptDownloads: true });
    await context.addInitScript(code => { localStorage.setItem('twinstore.locale', code); localStorage.setItem('parastore.graphicsMode', 'classic'); }, locale);
    const page = await context.newPage(); page.setDefaultTimeout(30000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    if (process.env.AREA_TEST_TRACE) page.on('request', request => { if (request.url().endsWith('/store-templates/preview')) console.log(JSON.stringify({ previewRequest: request.postDataJSON() })); });
    const t = (key, values = {}) => messages[key][index].replace(/\{(\w+)\}/g, (_, name) => typeof values[name] === 'number' ? new Intl.NumberFormat(locale).format(values[name]) : values[name]);
    await page.goto(`${origin}/projects/${pid}`);
    await page.locator(`[data-layout-id="${sid}"]`).click();
    await page.getByRole('button', { name: t('newLayout'), exact: true }).click();
    const name = `Areas ${locale} 茶 & <Books> 🛒`;
    await page.getByRole('radio', { name: t('multiFloorLayout'), exact: true }).check();
    await page.getByLabel(t('buildingNameLabel'), { exact: true }).fill(name);
    const initialPreview = page.waitForResponse(r => r.url().endsWith('/store-templates/preview') && r.request().method() === 'POST' && r.request().postDataJSON().template_id === 'fashion_boutique');
    await page.getByRole('button', { name: t('layBuilding_cafe_shop'), exact: true }).click();
    assert((await initialPreview).ok());
    if (process.env.AREA_TEST_TRACE) console.log(JSON.stringify({ expectedFormatGrid: format.grid }));
    const customize = page.getByRole('button', { name: t('customizeLayout'), exact: true });
    if (await customize.isVisible()) await customize.click();
    await page.getByLabel(t('layAreaStartingPoint'), { exact: true }).selectOption('pickup');
    await page.getByRole('button', { name: t('layAddReservedArea'), exact: true }).click();
    const areaName = 'Pickup / 茶 & <Books> 🛒';
    await page.getByLabel(t('layAreaNameLabel', { number: 1 }), { exact: true }).fill(areaName);
    const previewResponse = page.waitForResponse(r => r.url().endsWith('/store-templates/preview') && r.request().method() === 'POST' && r.request().postDataJSON().reserved_areas?.[0]?.x === 1 && r.request().postDataJSON().reserved_areas?.[0]?.y === format.grid[1] - 3);
    await page.getByRole('button', { name: t('layMoveAreaToPosition', { number: 1, position: t('layAreaPos_front_left') }), exact: true }).click();
    const expectedArea = { label: areaName, x: 1, y: format.grid[1] - 3, width: 3, height: 2 };
    const previewResult = await previewResponse; assert(previewResult.ok());
    const preview = await previewResult.json(); assert(preview.racks?.length);
    assert.deepEqual(previewResult.request().postDataJSON().reserved_areas, [expectedArea]);
    await page.getByRole('button', { name: t('planExpand'), exact: true }).click();
    const expanded = page.getByRole('dialog', { name: t('planDetails'), exact: true });
    const downloadEvent = page.waitForEvent('download');
    await expanded.getByRole('button', { name: t('planDownload'), exact: true }).click();
    const svg = fs.readFileSync(await (await downloadEvent).path(), 'utf8');
    assert(svg.includes('Pickup / 茶 &amp; &lt;Books&gt; 🛒')); assert(svg.includes(t('planCounter')));
    await page.keyboard.press('Escape');
    assert.equal(await page.getByLabel(t('layAreaNameLabel', { number: 1 }), { exact: true }).inputValue(), areaName);
    const optionsDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: t('optionsExportBuilding'), exact: true }).click();
    const preset = JSON.parse(fs.readFileSync(await (await optionsDownload).path(), 'utf8'));
    assert.equal(preset.floors.length, 2);
    assert.deepEqual(preset.floors[0].layout.reserved_areas, [expectedArea]);
    for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 640 }]) {
      await page.setViewportSize(viewport);
      await page.getByLabel(t('layAreaNameLabel', { number: 1 }), { exact: true }).scrollIntoViewIfNeeded();
      const dialog = page.getByRole('dialog', { name: t('addLayoutTitle'), exact: true });
      const box = await dialog.evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
      assert(box.scrollWidth <= box.width + 1, `${locale} design dialog overflow`);
      await page.screenshot({ path: `reserved-${locale}-${viewport.width}.png` });
    }
    await page.getByRole('button', { name: t('layReviewAllFloors'), exact: true }).click();
    const review = page.getByRole('dialog', { name: t('layReviewBuildingFloors'), exact: true });
    await review.getByText(t('layFloorPreviewsReady', { ready: 2, total: 2 }), { exact: true }).waitFor();
    assert.equal(await review.getByRole('img', { name: t('planPreviewImage'), exact: true }).count(), 2);
    await review.getByText(t('layReservedAreaCount', { count: 1 }), { exact: false }).waitFor();
    await review.getByText(t('layReservedAreaCount', { count: 0 }), { exact: false }).waitFor();
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 640 });
      const box = await review.evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
      assert(box.scrollWidth <= box.width + 1, `${locale} floor review overflow`);
      await page.screenshot({ path: `reserved-review-${locale}-${width}.png` });
    }
    await page.keyboard.press('Escape');
    const savedResponse = page.waitForResponse(r => r.url().endsWith('/setups/generate-building') && r.request().method() === 'POST');
    await page.getByTestId('add-layout-submit').click();
    const response = await savedResponse; assert(response.ok()); const saved = await response.json();
    assert.deepEqual(response.request().postDataJSON().floors[0].layout.reserved_areas, [expectedArea]);
    assert.equal(saved.setups.length, 2);
    const firstId = saved.setups[0].id;
    await page.locator(`[data-layout-id="${firstId}"][aria-selected="true"]`).waitFor();
    const child = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${firstId}`)).json();
    assert.equal(child.building.name, name);
    assert.equal(child.building.label, preset.floors[0].label);
    assert.deepEqual(child.store.weekly_schedule, preview.weekly_schedule);
    assert(preview.racks.some(r => r.slots.some(s => s.items.some(item => item.image_url))));
    assert.deepEqual(child.store.racks, preview.racks);
    assert.deepEqual(errors, []);
    const result = { locale, viewports: 2, setup_id: firstId, areaSettingsPreserved: true, svgLocalized: true, previewMatchesSaved: true }; results.push(result); console.log(JSON.stringify(result));
    await context.close();
  }
  assert.deepEqual((await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, original.store);
  await api.close(); console.log(JSON.stringify(results));
} finally { await browser.close(); }
