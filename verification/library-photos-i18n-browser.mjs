// Run against a disposable server seeded by library-photos-browser-seed.py.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from '../frontend/node_modules/typescript/lib/typescript.js';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const code = ts.transpileModule(fs.readFileSync(new URL('../frontend/src/shared/i18n/productMessages.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { productMessages } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const origin = process.env.PHOTO_TEST_ORIGIN || 'http://127.0.0.1:18774';
const pid = 'proj_67916afd', sid = 'setup_photos_fixture';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
const results = [];
try {
  const api = await browser.newContext();
  const upload = await api.request.post(`${origin}/api/projects/${pid}/lab/packages`, { multipart: {
    image: { name: 'synthetic-tea.png', mimeType: 'image/png', buffer: fs.readFileSync('synthetic-tea.png') },
    name: 'Tea <b>{sku}</b> 茶', sku: 'tea', remove_background: 'false',
  } });
  assert(upload.ok()); const asset = await upload.json();
  const original = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
  for (const [index, locale] of ['en', 'ko', 'zh', 'ja', 'es', 'fr'].entries()) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale });
    await context.addInitScript(code => { localStorage.setItem('twinstore.locale', code); localStorage.setItem('parastore.graphicsMode', 'classic'); }, locale);
    const page = await context.newPage(); page.setDefaultTimeout(30000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const t = (key, values = {}) => productMessages[key][index].replace(/\{(\w+)\}/g, (_, name) => values[name]);
    await page.goto(`${origin}/projects/${pid}`);
    await page.locator(`[data-layout-id="${sid}"]`).click();
    await page.getByRole('button', { name: t('photosTitle'), exact: true }).click();
    const dialog = page.getByRole('dialog');
    await page.getByRole('combobox', { name: t('photosForSku', { sku: 'tea' }), exact: true }).selectOption(asset.asset_id);
    assert((await dialog.innerText()).includes(t('photosHelp')));
    await page.getByRole('button', { name: t('photosPreview'), exact: true }).click();
    const save = page.getByRole('button', { name: t('photosSave'), exact: true });
    await save.waitFor();
    for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 640 }]) {
      await page.setViewportSize(viewport); await save.scrollIntoViewIfNeeded();
      assert(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1), `${locale}: dialog must not overflow horizontally`);
      assert(await save.evaluate(el => {
        const r = el.getBoundingClientRect(); const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        return r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth && !!hit && el.contains(hit);
      }), `${locale}: save reachable at ${viewport.width}`);
      await page.screenshot({ path: `photos-${locale}-${viewport.width}.png` });
    }
    const savedResponse = page.waitForResponse(r => r.url().endsWith('/library-photos/save') && r.request().method() === 'POST');
    await save.click(); const response = await savedResponse;
    assert(response.ok()); const saved = await response.json();
    const body = response.request().postDataJSON();
    assert.equal(body.assignments[0].sku, 'tea'); assert.equal(body.assignments[0].asset_id, asset.asset_id);
    assert.equal('locale' in body, false);
    await page.getByRole('button', { name: t('photosOpen'), exact: true }).click();
    await page.locator(`[data-layout-id="${saved.setup_id}"][aria-selected="true"]`).waitFor();
    const child = await (await api.request.get(`${origin}/api/projects/${pid}/setups/${saved.setup_id}`)).json();
    for (const rack of child.store.racks) for (const slot of rack.slots) for (const item of slot.items) if (item.sku === 'tea') {
      assert.equal((await api.request.get(`${origin}${item.image_url}`)).status(), 200); item.image_url = null;
    }
    assert.deepEqual(child.store, original.store); assert.deepEqual(errors, []);
    results.push({ locale, viewports: 2, setup_id: saved.setup_id, sourceDataPreserved: true, pageErrors: errors });
    await context.close();
  }
  assert.deepEqual((await (await api.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json()).store, original.store);
  await api.close(); console.log(JSON.stringify(results));
} finally { await browser.close(); }
