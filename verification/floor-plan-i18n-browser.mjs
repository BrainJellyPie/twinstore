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
const messages = { ...await catalog('messages.ts', 'messages'), ...await catalog('floorPlanMessages.ts', 'floorPlanMessages'), ...await catalog('floorCompareMessages.ts', 'floorCompareMessages') };
const origin = process.env.FLOOR_TEST_ORIGIN || 'http://127.0.0.1:18775';
const pid = 'proj_67916afd', sid = 'setup_starter_fixture';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
const results = [];
try {
  const api = await browser.newContext();
  const original = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  assert(original.store, 'Seed the disposable fixture first');
  for (const [index, locale] of ['en', 'ko', 'zh', 'ja', 'es', 'fr'].entries()) {
    if (process.env.FLOOR_TEST_LOCALES && !process.env.FLOOR_TEST_LOCALES.split(',').includes(locale)) continue;
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale, acceptDownloads: true });
    await context.addInitScript(code => { localStorage.setItem('twinstore.locale', code); localStorage.setItem('parastore.graphicsMode', 'classic'); }, locale);
    const page = await context.newPage(); page.setDefaultTimeout(30000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const t = (key, values = {}) => messages[key][index].replace(/\{(\w+)\}/g, (_, name) => typeof values[name] === 'number' ? new Intl.NumberFormat(locale).format(values[name]) : values[name]);
    await page.goto(`${origin}/projects/${pid}`);
    await page.locator(`[data-layout-id="${sid}"]`).click();
    await page.getByRole('button', { name: t('newLayout'), exact: true }).click();
    const name = `Floor ${locale} 茶 & <Books> 🛒`;
    await page.getByLabel(t('layoutNameLabel'), { exact: true }).fill(name);
    const previewResponse = page.waitForResponse(r => r.url().includes('/store-templates/preview') && r.request().method() === 'POST');
    await page.getByRole('radio', { name: t('generateLayoutFromTemplate'), exact: true }).check();
    const preview = await (await previewResponse).json(); assert(preview.racks?.length);
    await page.getByRole('button', { name: t('planExpand'), exact: true }).click();
    const details = page.getByRole('dialog', { name: t('planDetails'), exact: true });
    await details.waitFor();
    await page.getByRole('button', { name: t('planZoomIn'), exact: true }).click();
    assert((await details.innerText()).includes(new Intl.NumberFormat(locale, { style: 'percent' }).format(1.5)));
    for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 640 }]) {
      await page.setViewportSize(viewport);
      const downloadButton = page.getByRole('button', { name: t('planDownload'), exact: true });
      await downloadButton.scrollIntoViewIfNeeded();
      const overflow = await details.evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
      assert(overflow.scrollWidth <= overflow.width + 1, `${locale} dialog overflow`);
      assert(await downloadButton.evaluate(el => { const r = el.getBoundingClientRect(); const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return r.top >= 0 && r.bottom <= innerHeight && !!hit && el.contains(hit); }), `${locale} download not reachable`);
      await page.screenshot({ path: `floor-i18n-${locale}-${viewport.width}.png` });
    }
    const downloadEvent = page.waitForEvent('download');
    await page.getByRole('button', { name: t('planDownload'), exact: true }).click();
    const download = await downloadEvent;
    const text = fs.readFileSync(await download.path(), 'utf8');
    const metadata = await page.evaluate(xml => { const root = new DOMParser().parseFromString(xml, 'image/svg+xml'); return { error: !!root.querySelector('parsererror,script,foreignObject'), title: root.querySelector('title')?.textContent, description: root.querySelector('desc')?.textContent, style: root.documentElement.getAttribute('style') }; }, text);
    assert(!metadata.error && metadata.style === null);
    assert.equal(metadata.title, t('planExportTitle', { name: preview.name, width: preview.grid_size[0], height: preview.grid_size[1] }));
    assert(metadata.description.includes(t('planLegend', { inLabel: t('planIn'), outLabel: t('planOut') })));
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: t('compareWithDefault'), exact: true }).click();
    const comparison = page.getByRole('dialog', { name: t('planCompareTitle'), exact: true });
    await comparison.getByRole('table', { name: t('planCompareTable'), exact: true }).waitFor();
    await comparison.getByRole('region', { name: t('planCompareCurrent'), exact: true }).getByRole('button', { name: t('planExpand'), exact: true }).click();
    await details.waitFor();
    await page.keyboard.press('Escape'); await comparison.waitFor();
    await page.keyboard.press('Escape');
    assert.equal(await page.getByLabel(t('layoutNameLabel'), { exact: true }).inputValue(), name);
    const savedResponse = page.waitForResponse(r => r.url().endsWith('/setups/generate') && r.request().method() === 'POST');
    await page.getByTestId('add-layout-submit').click();
    const response = await savedResponse; assert(response.ok()); const saved = await response.json();
    await page.locator(`[data-layout-id="${saved.id}"][aria-selected="true"]`).waitFor();
    const child = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${saved.id}`)).json();
    assert.equal(child.name, name);
    // Setup reads intentionally enrich exact SKUs with the project's existing photos.
    const originals = new Map(original.store.racks.flatMap(r => r.slots.flatMap(s => s.items)).map(item => [item.sku, item.image_url]));
    const previewItems = new Map(preview.racks.flatMap(r => r.slots.flatMap(s => s.items)).map(item => [item.sku, item]));
    for (const item of child.store.racks.flatMap(r => r.slots.flatMap(s => s.items))) {
      if (item.image_url !== previewItems.get(item.sku)?.image_url) assert.equal(item.image_url, originals.get(item.sku));
    }
    const withoutResolvedPhotos = racks => racks.map(rack => ({ ...rack, slots: rack.slots.map(slot => ({ ...slot, items: slot.items.map(({ image_url: _photo, ...item }) => item) })) }));
    assert.deepEqual(withoutResolvedPhotos(child.store.racks), withoutResolvedPhotos(preview.racks));
    assert.deepEqual(child.store.grid_size, preview.grid_size);
    assert.deepEqual(errors, []);
    results.push({ locale, viewports: 2, setup_id: saved.id, namePreserved: true, svgLocalized: true, previewMatchesSaved: true });
    await context.close();
  }
  assert.deepEqual((await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, original.store);
  await api.close(); console.log(JSON.stringify(results));
} finally { await browser.close(); }
