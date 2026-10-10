// Captures the REAL app screens (local dev server + local demo org « Votre Entreprise ») used by
// the presentation film. Nothing here draws UI: it drives the running app and screenshots it.
//
//   VIDEO_REFRESH_TOKEN_FILE=<file> node tools/capture_app.mjs [--skip-run] [--only public,desktop,mobile]
//
// Auth: a refresh-token cookie minted for the demo owner (no password typed anywhere).
// Writes presentation/assets/app/*.png (desktop 1440x900 @2x, mobile 390x844 @3x).
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE = 'http://localhost:5174';
const OUT = path.resolve('presentation/assets/app');
const PAGES = path.resolve('presentation/assets/pages');
const SKIP_RUN = process.argv.includes('--skip-run');
const onlyAt = process.argv.indexOf('--only');
const ONLY = onlyAt > 0 ? process.argv[onlyAt + 1].split(',') : ['public', 'desktop', 'mobile'];
fs.mkdirSync(path.join(OUT, 'progress'), { recursive: true });

// One token per browser context: refresh tokens rotate (the used one is blacklisted).
const tokens = fs.readFileSync(process.env.VIDEO_REFRESH_TOKEN_FILE, 'utf8').trim().split(/\s+/);
let nextToken = 0;
const cookie = () => ({ name: 'refresh_token', value: tokens[nextToken++], domain: 'localhost', path: '/api/auth/', httpOnly: true, sameSite: 'Lax', secure: false });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

// The order the pages were "photographed" in (the review re-ranks them).
const uploads = fs.readdirSync(PAGES).filter((f) => f.endsWith('.jpg')).sort()
  .map((f) => ({ name: f.replace(/^\d+-/, ''), mimeType: 'image/jpeg', buffer: fs.readFileSync(path.join(PAGES, f)) }));

const browser = await chromium.launch();
const desktop = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: 'fr-FR', timezoneId: 'Africa/Douala' };
const mobile = {
  viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true, locale: 'fr-FR', timezoneId: 'Africa/Douala',
  userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
};

async function settle(page, ms = 900) {
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await sleep(ms);   // let entrance animations finish
}
async function shot(page, name, opts = {}) {
  await page.screenshot({ path: path.join(OUT, name), ...opts });
  log('shot', name);
}

// ---------------------------------------------------------------- logged out (public pages)
if (ONLY.includes('public')) {
  const ctx = await browser.newContext(desktop);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/login`); await settle(page);
  await shot(page, 'login.png');
  await page.goto(`${BASE}/register`); await settle(page);
  await shot(page, 'register.png');
  await ctx.close();
}

// ---------------------------------------------------------------- desktop, logged in
let jobUrl = null;
if (!ONLY.includes('desktop')) jobUrl = fs.readFileSync(path.join(OUT, 'job_url.txt'), 'utf8').trim();
else {
  const ctx = await browser.newContext(desktop);
  await ctx.addCookies([cookie()]);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/dashboard`); await settle(page);
  await shot(page, 'dashboard_before.png');

  if (!SKIP_RUN) {
    await page.goto(`${BASE}/upload`); await settle(page);
    await shot(page, 'upload_empty.png');
    await page.locator('input[type=file][multiple]').setInputFiles(uploads);
    const launch = page.getByRole('button', { name: /Lancer l.analyse · 9 documents/ }).first();
    await launch.waitFor({ timeout: 120000 });
    await settle(page, 1500);
    await shot(page, 'upload_filled.png');
    await shot(page, 'upload_filled_full.png', { fullPage: true });
    await launch.click();
    await page.waitForURL(/\/jobs\/[0-9a-f-]+$/, { timeout: 60000 });
    jobUrl = page.url();
    fs.writeFileSync(path.join(OUT, 'job_url.txt'), jobUrl);
    log('job', jobUrl);

    const watcher = await ctx.newPage();
    let n = 0, dashboardDone = false;
    const t0 = Date.now();
    while (Date.now() - t0 < 20 * 60 * 1000) {
      await sleep(1500);
      const ready = await page.locator('text=Revue prête').count();
      await page.screenshot({ path: path.join(OUT, 'progress', `${String(n).padStart(3, '0')}.jpg`), type: 'jpeg', quality: 88 });
      n++;
      if (!dashboardDone && n === 25) {
        await watcher.goto(`${BASE}/dashboard`); await settle(watcher, 1500);
        await shot(watcher, 'dashboard_processing.png');
        dashboardDone = true;
      }
      if (ready) break;
    }
    log('progress frames', n);
  } else {
    jobUrl = fs.readFileSync(path.join(OUT, 'job_url.txt'), 'utf8').trim();
  }

  await page.goto(jobUrl); await settle(page, 1500);
  await shot(page, 'job_ready.png');
  await shot(page, 'job_ready_full.png', { fullPage: true });
  const article = page.locator('article').first();
  await article.screenshot({ path: path.join(OUT, 'review_article.png') }); log('shot review_article.png');
  const panel = page.locator('div.lg\\:sticky').first();
  if (await panel.count()) { await panel.screenshot({ path: path.join(OUT, 'highlights_panel.png') }); log('shot highlights_panel.png'); }

  for (const [route, name] of [['/dashboard', 'dashboard_after'], ['/categories', 'categories'], ['/team', 'team'], ['/billing', 'billing'], ['/settings', 'settings']]) {
    await page.goto(`${BASE}${route}`); await settle(page, 1200);
    await shot(page, `${name}.png`);
    await shot(page, `${name}_full.png`, { fullPage: true });
  }
  await ctx.close();
}

// ---------------------------------------------------------------- mobile, logged in (9:16 film)
if (ONLY.includes('mobile')) {
  const ctx = await browser.newContext(mobile);
  await ctx.addCookies([cookie()]);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/dashboard`); await settle(page);
  await shot(page, 'm_dashboard.png');
  await page.goto(jobUrl); await settle(page, 1500);
  await shot(page, 'm_review.png');
  await shot(page, 'm_review_full.png', { fullPage: true });
  for (const [label, name] of [[/Points clés/, 'm_highlights'], [/Documents/, 'm_documents']]) {
    await page.getByRole('tab', { name: label }).click();
    await settle(page, 900);
    await shot(page, `${name}.png`);
    await shot(page, `${name}_full.png`, { fullPage: true });
  }
  await page.goto(`${BASE}/upload`); await settle(page);
  await shot(page, 'm_upload_empty.png');
  await page.locator('input[type=file][multiple]').setInputFiles(uploads.slice(0, 6));
  await sleep(6000); await settle(page);
  await shot(page, 'm_upload_filled.png');
  await ctx.close();

  const out = await browser.newContext(mobile);
  const lp = await out.newPage();
  await lp.goto(`${BASE}/login`); await settle(lp);
  await shot(lp, 'm_login.png');
  await out.close();
}

await browser.close();
log('done');
