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
const origin = process.env.INTERIOR_TEST_ORIGIN || 'http://127.0.0.1:18775';
const pid = 'proj_67916afd', sid = 'setup_starter_fixture';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
const results = [];
try {
  const api = await browser.newContext();
  const original = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  const formats = await (await api.request.get(`${origin}/api/store-templates`)).json();
  const format = formats.find(f => f.id === 'urban_cvs'); assert(format?.categories?.length > 1);
  for (const [index, locale] of ['en', 'ko', 'zh', 'ja', 'es', 'fr'].entries()) {
    if (process.env.INTERIOR_TEST_LOCALES && !process.env.INTERIOR_TEST_LOCALES.split(',').includes(locale)) continue;
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale, acceptDownloads: true });
    await context.addInitScript(code => { localStorage.setItem('twinstore.locale', code); localStorage.setItem('parastore.graphicsMode', 'classic'); }, locale);
    const page = await context.newPage(); page.setDefaultTimeout(30000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const t = (key, values = {}) => messages[key][index].replace(/\{(\w+)\}/g, (_, name) => typeof values[name] === 'number' ? new Intl.NumberFormat(locale).format(values[name]) : values[name]);
    await page.goto(`${origin}/projects/${pid}`);
    await page.locator(`[data-layout-id="${sid}"]`).click();
    await page.getByRole('button', { name: t('newLayout'), exact: true }).click();
    const name = `Design ${locale} 茶 & <Books> 🛒`;
    await page.getByLabel(t('layoutNameLabel'), { exact: true }).fill(name);
    await page.getByRole('radio', { name: t('generateLayoutFromTemplate'), exact: true }).check();
    await page.getByRole('button', { name: t('customizeLayout'), exact: true }).click();
    await page.getByLabel(t('layInteriorDesignRealistic'), { exact: true }).selectOption('botanical');
    await page.getByText(t('layCustomColors'), { exact: true }).click();
    async function setColor(key, value) {
      await page.getByLabel(t(key), { exact: true }).evaluate((input, next) => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, next);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }, value);
    }
    await setColor('layColor_wall', '#000000');
    await setColor('layColor_floor', '#e0d1ff');
    const previewResponse = page.waitForResponse(r => r.url().endsWith('/store-templates/preview') && r.request().method() === 'POST' && r.request().postDataJSON().design_colors?.accent === '#ff00ff');
    await setColor('layColor_accent', '#ff00ff');
    const preview = await (await previewResponse).json(); assert(preview.racks?.length);
    assert.equal(preview.design_theme, 'botanical');
    assert.equal(preview.design_colors.wall, '#000000');
    assert.equal(preview.design_colors.floor, '#e0d1ff');
    assert.equal(preview.design_colors.accent, '#ff00ff');
    await page.getByText(t('layCustomColorsCount', { count: 3 }), { exact: true }).waitFor();
    await page.getByRole('button', { name: t('planExpand'), exact: true }).click();
    const expanded = page.getByRole('dialog', { name: t('planDetails'), exact: true });
    const downloadEvent = page.waitForEvent('download');
    await expanded.getByRole('button', { name: t('planDownload'), exact: true }).click();
    const svg = fs.readFileSync(await (await downloadEvent).path(), 'utf8');
    assert(svg.includes('#e0d1ff')); assert(svg.includes(t('planCounter')));
    await page.keyboard.press('Escape');
    assert.equal(await page.getByLabel(t('layColor_wall'), { exact: true }).inputValue(), '#000000');
    const optionsDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: t('optionsExport'), exact: true }).click();
    const preset = JSON.parse(fs.readFileSync(await (await optionsDownload).path(), 'utf8'));
    assert.equal(preset.layout.design_theme, 'botanical');
    assert.deepEqual(preset.layout.design_colors, { wall: '#000000', floor: '#e0d1ff', accent: '#ff00ff' });
    for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 640 }]) {
      await page.setViewportSize(viewport);
      await page.getByLabel(t('layColor_floor'), { exact: true }).scrollIntoViewIfNeeded();
      const dialog = page.getByRole('dialog', { name: t('addLayoutTitle'), exact: true });
      const box = await dialog.evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
      assert(box.scrollWidth <= box.width + 1, `${locale} design dialog overflow`);
      await page.screenshot({ path: `interior-${locale}-${viewport.width}.png` });
    }
    const savedResponse = page.waitForResponse(r => r.url().endsWith('/setups/generate') && r.request().method() === 'POST');
    await page.getByTestId('add-layout-submit').click();
    const response = await savedResponse; assert(response.ok()); const saved = await response.json();
    assert.equal(response.request().postDataJSON().design_theme, 'botanical');
    await page.locator(`[data-layout-id="${saved.id}"][aria-selected="true"]`).waitFor();
    const child = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${saved.id}`)).json();
    assert.equal(child.name, name);
    assert.equal(child.store.design_theme, 'botanical');
    assert.equal(child.store.design_colors.floor, '#e0d1ff');
    assert.equal(child.store.design_colors.wall, '#000000');
    assert.equal(child.store.design_colors.accent, '#ff00ff');
    assert.deepEqual(child.store.weekly_schedule, preview.weekly_schedule);
    const withoutPhotos = racks => racks.map(r => ({ ...r, slots: r.slots.map(s => ({ ...s, items: s.items.map(({ image_url: _photo, ...item }) => item) })) }));
    assert.deepEqual(withoutPhotos(child.store.racks), withoutPhotos(preview.racks));
    assert.deepEqual(errors, []);
    const result = { locale, viewports: 2, setup_id: saved.id, colorsPreserved: true, svgLocalized: true, previewMatchesSaved: true }; results.push(result); console.log(JSON.stringify(result));
    await context.close();
  }
  assert.deepEqual((await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, original.store);
  await api.close(); console.log(JSON.stringify(results));
} finally { await browser.close(); }
