// Built UI on a disposable real project; generation responses are synthetic and intercepted.
// No model/download/simulation may reach the backend in this check.
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
const messages = { ...await catalog('messages.ts', 'messages'), ...await catalog('feedbackMessages.ts', 'feedbackMessages'), ...await catalog('messages/store.ts', 'storeMessages') };
const origin = process.env.GENERATION_TEST_ORIGIN || 'http://127.0.0.1:18775';
const pid = 'proj_67916afd', sid = 'setup_starter_fixture';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader'] });
const results = [];
try {
  for (const [index, locale] of ['en', 'ko', 'zh', 'ja', 'es', 'fr'].entries()) {
    if (process.env.GENERATION_TEST_LOCALES && !process.env.GENERATION_TEST_LOCALES.split(',').includes(locale)) continue;
    const t = (key, values = {}) => messages[key][index].replace(/\{(\w+)\}/g, (_, name) => typeof values[name] === 'number' ? new Intl.NumberFormat(locale).format(values[name]) : values[name]);
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale });
    await context.addInitScript(code => { localStorage.setItem('twinstore.locale', code); localStorage.setItem('parastore.graphicsMode', 'classic'); }, locale);
    const original = await (await context.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json();
    const modelSetup = await (await context.request.get(`${origin}/api/system/models`)).json();
    modelSetup.cloud_providers = [];
    modelSetup.local = { ...modelSetup.local, state: 'off', downloaded: false, progress: null };
    let starts = 0;
    const model = 'provider/<Tea> 茶 {count}';
    const confirm = {
      model, local: false, days: 1, visitors_per_day: { '1': 1 },
      all: { per_day: 1, customers: 1, requests: 1, minutes: 1, cost_usd: null },
      sample: { per_day: 1, customers: 1, requests: 1, minutes: 1, cost_usd: 0.004 },
    };
    const job = { gen_id: 'gen_copy_fixture', setup_id: sid, kind: 'persona', status: 'running', error: null, progress: { confirm }, created_at: null, updated_at: null };
    let current = job;
    const answers = [], unexpectedMutations = [];
    await context.route('**/api/**', async route => {
      const req = route.request(), path = new URL(req.url()).pathname;
      if (path === '/api/system/models' && req.method() === 'GET') return route.fulfill({ json: modelSetup });
      if (path === '/api/system/local-model/start' && req.method() === 'POST') {
        starts++;
        if (starts === 1) return route.fulfill({ status: 503, json: { detail: 'Synthetic download failure <raw> 茶 {size}' } });
        modelSetup.local = { ...modelSetup.local, state: 'starting' };
        return route.fulfill({ json: modelSetup.local });
      }
      if (path.startsWith(`/api/projects/${pid}/setups/${sid}/generations`) && req.method() === 'GET') {
        return route.fulfill({ json: path.endsWith('/status') ? current : [current] });
      }
      if (path === `/api/projects/${pid}/setups/${sid}/generations/gen_copy_fixture/confirm` && req.method() === 'POST') {
        const payload = req.postDataJSON(); answers.push(payload); assert.equal(payload.choice, 'sample');
        if (answers.length === 1) return route.fulfill({ status: 503, json: { detail: 'Synthetic failure <raw> 茶 {count}' } });
        current = { ...job, progress: { written: 1, total: 1 } };
        return route.fulfill({ json: current });
      }
      if (!['GET', 'HEAD'].includes(req.method())) {
        unexpectedMutations.push({ path, method: req.method() });
        return route.fulfill({ status: 500, json: { detail: 'Unexpected mutation blocked by verification' } });
      }
      return route.continue();
    });
    const page = await context.newPage(); page.setDefaultTimeout(30000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${origin}/projects/${pid}`);
    await page.locator(`[data-layout-id="${sid}"]`).click();
    const dialog = page.getByRole('alertdialog', { name: t('genConfirmTitle'), exact: true });
    await dialog.waitFor();
    assert((await dialog.textContent()).includes(t('genConfirmEstimate', { visitors: t('visitorADay', { count: 1 }), days: 1 })));
    assert((await dialog.textContent()).includes(model));
    assert.equal(await page.locator('tea').count(), 0);
    assert.deepEqual(answers, []);
    await page.keyboard.press('Escape'); assert(await dialog.isVisible());
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 640 });
      const box = await dialog.evaluate(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }));
      assert(box.scrollWidth <= box.width + 1, `${locale}: dialog overflow`);
      await page.screenshot({ path: `generation-${locale}-${width}.png` });
    }
    const sample = dialog.getByRole('button', { name: new RegExp(t('genWriteSample', { count: 1 }).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) });
    await sample.click();
    await dialog.getByRole('alert').waitFor();
    assert((await dialog.getByRole('alert').textContent()).includes(t('genConfirmFailed')));
    assert((await dialog.getByRole('alert').textContent()).includes('Synthetic failure <raw> 茶 {count}'));
    await sample.click();
    await dialog.waitFor({ state: 'hidden' });
    await page.getByText(t('writingCustomers', { written: 1, total: 1 }), { exact: true }).waitFor();
    assert.deepEqual(answers, [{ choice: 'sample' }, { choice: 'sample' }]);
    assert.equal(starts, 0, 'No model start or download without an explicit click');
    current = { ...job, status: 'failed', progress: null, error: 'Synthetic generation failure <raw> 茶' };
    await page.getByRole('heading', { name: t('personaGenerationFailed'), exact: true }).waitFor();
    const needsModel = page.getByTestId('needs-model');
    await needsModel.getByText(t('needsModelHint'), { exact: true }).waitFor();
    assert.equal(await needsModel.getByRole('link').count(), 0, 'Parent recovery screen already has model settings');
    const download = needsModel.getByRole('button', { name: t('downloadLocal', { size: modelSetup.plan.model.download_gb }), exact: true });
    await download.click();
    await needsModel.getByText(t('requestFailed'), { exact: true }).waitFor();
    await needsModel.getByText(t('requestDetails'), { exact: true }).click();
    await needsModel.getByText('Synthetic download failure <raw> 茶 {size}', { exact: true }).waitFor();
    assert.equal(starts, 1);
    await page.setViewportSize({ width: 390, height: 844 });
    await needsModel.scrollIntoViewIfNeeded();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    await page.screenshot({ path: `model-recovery-${locale}-390.png` });
    await download.click();
    await needsModel.getByText(t('localStateStarting'), { exact: true }).waitFor();
    assert.equal(starts, 2); assert.equal(await needsModel.getByRole('alert').count(), 0);
    assert.deepEqual(unexpectedMutations, []); assert.deepEqual(errors, []);
    assert.deepEqual(await (await context.request.get(`${origin}/api/projects/${pid}/setups/${sid}`)).json(), original);
    results.push({ locale, viewports: 2, exactChoice: true, failureRetry: true, explicitModelStartOnly: true, originalPreserved: true });
    console.log(JSON.stringify(results.at(-1))); await context.close();
  }
} finally { await browser.close(); }
console.log(JSON.stringify(results));
