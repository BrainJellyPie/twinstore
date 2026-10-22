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
const messages = { ...await catalog('messages.ts', 'messages'), ...await catalog('templateStockHoursMessages.ts', 'templateStockHoursMessages'), ...await catalog('optionsFileMessages.ts', 'optionsFileMessages'), ...await catalog('starterCategoryMessages.ts', 'starterCategoryMessages'), ...await catalog('messages/studio.ts', 'studioMessages') };
const origin = process.env.TEMPLATE_TEST_ORIGIN || 'http://127.0.0.1:18775';
const pid = 'proj_67916afd', sid = 'setup_starter_fixture';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
const results = [];
try {
  const api = await browser.newContext();
  const original = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  const formats = await (await api.request.get(`${origin}/api/store-templates`)).json();
  const format = formats.find(f => f.id === 'urban_cvs'); assert(format?.categories?.length > 1);
  for (const [index, locale] of ['en', 'ko', 'zh', 'ja', 'es', 'fr'].entries()) {
    if (process.env.TEMPLATE_TEST_LOCALES && !process.env.TEMPLATE_TEST_LOCALES.split(',').includes(locale)) continue;
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale, acceptDownloads: true });
    await context.addInitScript(code => { localStorage.setItem('twinstore.locale', code); localStorage.setItem('parastore.graphicsMode', 'classic'); }, locale);
    const page = await context.newPage(); page.setDefaultTimeout(30000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const t = (key, values = {}) => messages[key][index].replace(/\{(\w+)\}/g, (_, name) => typeof values[name] === 'number' ? new Intl.NumberFormat(locale).format(values[name]) : values[name]);
    await page.goto(`${origin}/projects/${pid}`);
    await page.locator(`[data-layout-id="${sid}"]`).click();
    await page.getByRole('button', { name: t('newLayout'), exact: true }).click();
    const name = `Options ${locale} 茶 & <Books> 🛒`;
    await page.getByLabel(t('layoutNameLabel'), { exact: true }).fill(name);
    await page.getByRole('radio', { name: t('generateLayoutFromTemplate'), exact: true }).check();
    await page.getByRole('button', { name: t('customizeLayout'), exact: true }).click();
    await page.getByText(t('templateHoursSummary', { count: 7 - (format.closed_days?.length || 0) }), { exact: true }).click();
    await page.getByRole('checkbox', { name: t('templateHoursIndividual'), exact: true }).check();
    const monday = new Intl.DateTimeFormat(locale, { weekday: 'long', timeZone: 'UTC' }).format(new Date(Date.UTC(2024, 0, 1)));
    await page.getByLabel(t('templateDayOpening', { day: monday }), { exact: true }).fill('0');
    await page.getByLabel(t('templateDayClosing', { day: monday }), { exact: true }).fill('24');
    await page.getByText(t('templateCategoriesSummary', { included: format.categories.length, total: format.categories.length }), { exact: true }).click();
    await page.getByLabel(t('templateProductsPerCategory'), { exact: true }).fill('4');
    await page.getByRole('checkbox', { name: t('capCatSoftDrinks'), exact: true }).uncheck();
    await page.getByLabel(t('templateProductsFor', { category: t('capCatWaterSports') }), { exact: true }).fill('2');
    const previewResponse = page.waitForResponse(r => r.url().endsWith('/store-templates/preview') && r.request().method() === 'POST' && r.request().postDataJSON().seed === -7);
    const seedInput = page.getByLabel(t('templateSeed'), { exact: true });
    await seedInput.fill('-7');
    const preview = await (await previewResponse).json(); assert(preview.racks?.length);
    await page.getByText(t('templatePreviewCounters', { counters: preview.racks.filter(rack => rack.type === 'counter').length }), { exact: true }).waitFor();
    const downloadEvent = page.waitForEvent('download');
    await page.getByRole('button', { name: t('optionsExport'), exact: true }).click();
    const file = await (await downloadEvent).path(); const preset = JSON.parse(fs.readFileSync(file, 'utf8'));
    assert.equal(preset.format, 'twinstore-layout-options'); assert.equal(preset.layout.seed, -7);
    assert.deepEqual(preset.layout.excluded_categories, ['soft_drinks']);
    assert.equal(preset.layout.products_per_category, 4); assert.deepEqual(preset.layout.category_product_limits, { water_sports: 2 });
    assert.deepEqual(preset.layout.weekly_hours[0], { day: 1, is_open: true, open_hour: 0, close_hour: 24 });
    assert(!('source_setup_id' in preset.layout));
    await seedInput.fill('0');
    const validationResponse = page.waitForResponse(r => r.url().endsWith('/store-templates/preset/validate'));
    await page.getByLabel(t('optionsLayoutFile'), { exact: true }).setInputFiles(file);
    assert((await validationResponse).ok());
    await page.waitForFunction(id => document.getElementById(id)?.value === '-7', await seedInput.getAttribute('id'));
    for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 640 }]) {
      await page.setViewportSize(viewport); await seedInput.scrollIntoViewIfNeeded();
      const dialog = page.getByRole('dialog', { name: t('addLayoutTitle'), exact: true });
      const overflow = await dialog.evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
      assert(overflow.scrollWidth <= overflow.width + 1, `${locale} options dialog overflow`);
      await page.screenshot({ path: `template-options-${locale}-${viewport.width}.png` });
      for (const key of ['templateHoursIndividual', 'templateProductsPerCategory', 'optionsExport']) {
        const control = key === 'templateHoursIndividual' ? page.getByRole('checkbox', { name: t(key), exact: true })
          : key === 'optionsExport' ? page.getByRole('button', { name: t(key), exact: true })
          : page.getByLabel(t(key), { exact: true });
        await control.scrollIntoViewIfNeeded();
        await page.screenshot({ path: `template-options-${locale}-${viewport.width}-${key}.png` });
      }
    }
    const savedResponse = page.waitForResponse(r => r.url().endsWith('/setups/generate') && r.request().method() === 'POST');
    await page.getByTestId('add-layout-submit').click();
    const response = await savedResponse; assert(response.ok()); const saved = await response.json();
    assert.equal(response.request().postDataJSON().seed, -7);
    await page.locator(`[data-layout-id="${saved.id}"][aria-selected="true"]`).waitFor();
    const child = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${saved.id}`)).json();
    assert.equal(child.name, name);
    assert.deepEqual(child.store.weekly_schedule, preview.weekly_schedule);
    const withoutPhotos = racks => racks.map(r => ({ ...r, slots: r.slots.map(s => ({ ...s, items: s.items.map(({ image_url: _photo, ...item }) => item) })) }));
    assert.deepEqual(withoutPhotos(child.store.racks), withoutPhotos(preview.racks));
    assert.deepEqual(errors, []);
    const result = { locale, viewports: 2, setup_id: saved.id, optionsRoundtrip: true, previewMatchesSaved: true }; results.push(result); console.log(JSON.stringify(result));
    await context.close();
  }
  assert.deepEqual((await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, original.store);
  await api.close(); console.log(JSON.stringify(results));
} finally { await browser.close(); }
