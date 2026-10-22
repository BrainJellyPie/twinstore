// Real UI/API on the disposable setup_copy_i18n fixture; no model calls.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from '../frontend/node_modules/typescript/lib/typescript.js';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const code = ts.transpileModule(fs.readFileSync(new URL('../frontend/src/shared/i18n/rackCopyMessages.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { rackCopyMessages } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const origin = process.env.PHOTO_TEST_ORIGIN || 'http://127.0.0.1:18774';
const pid = 'proj_67916afd', sid = 'setup_copy_i18n';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
const results = [];
try {
  const api = await browser.newContext();
  const original = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  assert(original.store, 'Seed a disposable rack-copy fixture first');
  for (const [index, locale] of ['en', 'ko', 'zh', 'ja', 'es', 'fr'].entries()) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale });
    await context.addInitScript(code => { localStorage.setItem('twinstore.locale', code); localStorage.setItem('parastore.graphicsMode', 'classic'); }, locale);
    const page = await context.newPage(); page.setDefaultTimeout(30000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const t = (key, values = {}) => rackCopyMessages[key][index].replace(/\{(\w+)\}/g, (_, name) => values[name]);
    await page.goto(`${origin}/projects/${pid}`);
    await page.locator(`[data-layout-id="${sid}"]`).click();
    await page.getByRole('button', { name: t('copyTitle'), exact: true }).click();
    const dialog = page.getByRole('dialog');
    await page.getByRole('combobox', { name: t('copyFrom'), exact: true }).selectOption('shelf');
    await page.getByRole('checkbox', { name: t('copyToRack', { id: 'empty' }), exact: true }).check();
    assert(await page.getByRole('checkbox', { name: t('copyToRack', { id: 'shelf' }), exact: true }).isDisabled());
    await page.getByText(t('copyReasonSource'), { exact: true }).waitFor();
    await page.getByRole('button', { name: t('copyPreview'), exact: true }).click();
    const save = page.getByRole('button', { name: t('copySave'), exact: true }); await save.waitFor();
    const preview = page.getByRole('region', { name: t('copyPreviewTitle'), exact: true });
    assert((await preview.innerText()).includes('Tea'));
    await preview.getByText(t('copySection', { block: 1, face: t('fixtureSouth'), level: 1 }), { exact: true }).waitFor();
    for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 640 }]) {
      await page.setViewportSize(viewport); await save.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `rack-copy-${locale}-${viewport.width}.png` });
      const overflow = await dialog.evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
      assert(overflow.scrollWidth <= overflow.width + 1, `${locale}: dialog overflow: ${JSON.stringify(overflow)}`);
      assert(await save.evaluate(el => {
        const r = el.getBoundingClientRect(); const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        return r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth && !!hit && el.contains(hit);
      }), `${locale}: save reachable at ${viewport.width}`);
    }
    const savedResponse = page.waitForResponse(r => r.url().endsWith('/rack-copy/save') && r.request().method() === 'POST');
    await save.click(); const response = await savedResponse;
    assert(response.ok()); const saved = await response.json();
    assert.equal(response.request().postDataJSON().source_rack_id, 'shelf');
    assert.deepEqual(response.request().postDataJSON().target_rack_ids, ['empty']);
    await page.getByRole('button', { name: t('copyOpen'), exact: true }).click();
    await page.locator(`[data-layout-id="${saved.setup_id}"][aria-selected="true"]`).waitFor();
    const child = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${saved.setup_id}`)).json();
    const expected = structuredClone(original.store);
    expected.racks.find(r => r.id === 'empty').slots = structuredClone(expected.racks.find(r => r.id === 'shelf').slots);
    assert.deepEqual(child.store, expected); assert.deepEqual(errors, []);
    results.push({ locale, viewports: 2, setup_id: saved.setup_id, exactSlots: true, sourceDataPreserved: true, pageErrors: errors });
    await context.close();
  }
  assert.deepEqual((await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, original.store);
  await api.close(); console.log(JSON.stringify(results));
} finally { await browser.close(); }
