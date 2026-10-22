// Real UI/API checks on the disposable library-photos fixture; no model calls.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from '../frontend/node_modules/typescript/lib/typescript.js';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const code = ts.transpileModule(fs.readFileSync(new URL('../frontend/src/shared/i18n/bulkMessages.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { bulkMessages } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const origin = process.env.PHOTO_TEST_ORIGIN || 'http://127.0.0.1:18774';
const pid = 'proj_67916afd', sid = 'setup_photos_fixture';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
const results = [];
try {
  const api = await browser.newContext();
  const original = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  for (const [index, locale] of ['en', 'ko', 'zh', 'ja', 'es', 'fr'].entries()) {
    if (process.env.BULK_TEST_LOCALE && process.env.BULK_TEST_LOCALE !== locale) continue;
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale });
    await context.addInitScript(code => { localStorage.setItem('twinstore.locale', code); localStorage.setItem('parastore.graphicsMode', 'classic'); }, locale);
    const page = await context.newPage(); page.setDefaultTimeout(30000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const t = (key, values = {}) => bulkMessages[key][index].replace(/\{(\w+)\}/g, (_, name) => values[name]);
    await page.goto(`${origin}/projects/${pid}`);
    await page.locator(`[data-layout-id="${sid}"]`).click();
    await page.getByRole('button', { name: t('bulkTitle'), exact: true }).click();
    const dialog = page.getByRole('dialog');
    await page.getByLabel(t('productSelectSku', { sku: 'tea' }), { exact: true }).check();
    await page.getByLabel(t('bulkPrice'), { exact: true }).fill('1.005');
    await page.getByRole('button', { name: t('bulkSetPrices'), exact: true }).click();
    await page.getByRole('button', { name: t('bulkPreview'), exact: true }).click();
    const save = page.getByRole('button', { name: t('bulkSave'), exact: true }); await save.waitFor();
    assert((await page.getByRole('region', { name: t('bulkPreviewTitle') }).innerText()).includes('Tea'));
    for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 640 }]) {
      await page.setViewportSize(viewport); await save.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `bulk-${locale}-${viewport.width}.png` });
      const overflow = await dialog.evaluate(el => {
        const box = el.getBoundingClientRect();
        return { width: el.clientWidth, scrollWidth: el.scrollWidth, elements: [...el.querySelectorAll('*')].filter(e => !e.closest('table') && e.getBoundingClientRect().right > box.right).map(e => ({ tag: e.tagName, text: e.textContent.slice(0, 90), right: e.getBoundingClientRect().right, className: e.className })).slice(0, 12) };
      });
      assert(overflow.scrollWidth <= overflow.width + 1, `${locale}: dialog must not overflow horizontally: ${JSON.stringify(overflow)}`);
      assert(await save.evaluate(el => {
        const r = el.getBoundingClientRect(); const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        return r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth && !!hit && el.contains(hit);
      }), `${locale}: save reachable at ${viewport.width}`);
    }
    const savedResponse = page.waitForResponse(r => r.url().endsWith('/product-edits/save') && r.request().method() === 'POST');
    await save.click(); const response = await savedResponse;
    assert(response.ok()); const saved = await response.json();
    assert.deepEqual(response.request().postDataJSON().edits, [{ sku: 'tea', price: 101 }]);
    await page.getByRole('button', { name: t('bulkOpen'), exact: true }).click();
    await page.locator(`[data-layout-id="${saved.setup_id}"][aria-selected="true"]`).waitFor();
    const child = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${saved.setup_id}`)).json();
    let changed = 0;
    for (const rack of child.store.racks) for (const slot of rack.slots) for (const item of slot.items) if (item.sku === 'tea') {
      assert.equal(item.price, 101); item.price = 231; changed++;
    }
    assert.equal(changed, 2); assert.deepEqual(child.store, original.store); assert.deepEqual(errors, []);
    results.push({ locale, viewports: 2, setup_id: saved.setup_id, exactRounding: true, sourceDataPreserved: true, pageErrors: errors });
    await context.close();
  }
  assert.deepEqual((await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, original.store);
  await api.close(); console.log(JSON.stringify(results));
} finally { await browser.close(); }
