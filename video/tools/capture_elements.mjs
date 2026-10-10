// Crisp (3x) element crops of the REAL app for close-ups in the film: newspaper headings of the
// review (for the ranking shot), rubric banners, masthead, export buttons, team, categories,
// the trial badge of the sign-up page, the upload page pieces.
//
//   VIDEO_REFRESH_TOKEN_FILE=<file> node tools/capture_elements.mjs
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE = 'http://localhost:5174';
const OUT = path.resolve('presentation/assets/app/el');
const PAGES = path.resolve('presentation/assets/pages');
fs.mkdirSync(OUT, { recursive: true });
const jobUrl = fs.readFileSync(path.resolve('presentation/assets/app/job_url.txt'), 'utf8').trim();
const tokens = fs.readFileSync(process.env.VIDEO_REFRESH_TOKEN_FILE, 'utf8').trim().split(/\s+/);
let next = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const opts = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 3, locale: 'fr-FR', timezoneId: 'Africa/Douala' };

const browser = await chromium.launch();
async function open(url, auth = true) {
  const ctx = await browser.newContext(opts);
  if (auth) await ctx.addCookies([{ name: 'refresh_token', value: tokens[next++], domain: 'localhost', path: '/api/auth/', httpOnly: true, sameSite: 'Lax', secure: false }]);
  const page = await ctx.newPage();
  await page.goto(url);
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  await sleep(1400);
  await page.mouse.move(0, 0);
  return { ctx, page };
}
async function el(locator, name) {
  await locator.scrollIntoViewIfNeeded();
  await sleep(400);
  await locator.screenshot({ path: path.join(OUT, name) });
  const box = await locator.boundingBox();
  console.log('shot', name, box && `${Math.round(box.width)}x${Math.round(box.height)}`);
}

// ---- the ready review
{
  const { ctx, page } = await open(jobUrl);
  const sheet = page.locator('article').filter({ hasText: 'REVUE DE PRESSE' }).first();
  await el(sheet.locator('header').first(), 'masthead.png');
  const banners = sheet.locator('section h2');
  for (let i = 0; i < await banners.count(); i++) await el(banners.nth(i), `banner_${i}.png`);
  const heads = sheet.locator('h3');
  const names = [];
  for (let i = 0; i < await heads.count(); i++) {
    const text = (await heads.nth(i).innerText()).replace(/^▶\s*/, '').trim();
    names.push(text);
    await el(heads.nth(i), `name_${i}.png`);
  }
  fs.writeFileSync(path.join(OUT, 'names.json'), JSON.stringify(names, null, 1));
  // one notice (heading + paragraph) for a readable close-up
  const firstArticle = sheet.locator('section article').first();
  await el(firstArticle, 'notice_0.png');
  await el(page.getByRole('button', { name: /Exporter en PDF/ }).first().locator('xpath=..'), 'actions.png');
  await el(page.getByRole('button', { name: /^Tous/ }).first().locator('xpath=..'), 'chips.png');
  await ctx.close();
}

// ---- team, categories
{
  const { ctx, page } = await open(`${BASE}/team`);
  await el(page.locator('section.card, div.card').filter({ hasText: 'Places utilisées' }).first(), 'team_members.png');
  await ctx.close();
}
{
  const { ctx, page } = await open(`${BASE}/categories`);
  await el(page.locator('article, div.card, section.card').filter({ hasText: 'Annonce concurrent' }).filter({ hasText: 'CONSIGNE' }).first(), 'cat_custom.png');
  const defaults = page.getByRole('heading', { name: 'Catégories par défaut' }).locator('xpath=ancestor::section[1]');
  await el(defaults, 'cat_defaults.png');
  await ctx.close();
}

// ---- sign-up page: the trial badge (public)
{
  const { ctx, page } = await open(`${BASE}/register`, false);
  await el(page.getByText(/jours d.essai gratuit/).first(), 'badge_trial.png');
  await ctx.close();
}

// ---- upload page with the 9 pages selected (files are uploaded as drafts; no review is launched)
{
  const { ctx, page } = await open(`${BASE}/upload`);
  const files = fs.readdirSync(PAGES).filter((f) => f.endsWith('.jpg')).sort()
    .map((f) => ({ name: f.replace(/^\d+-/, ''), mimeType: 'image/jpeg', buffer: fs.readFileSync(path.join(PAGES, f)) }));
  await page.locator('input[type=file][multiple]').setInputFiles(files);
  const launch = page.getByRole('button', { name: /Lancer l.analyse · 9 documents/ }).first();
  await launch.waitFor({ timeout: 120000 });
  await sleep(2500);
  await page.mouse.move(0, 0);
  await el(launch, 'upload_launch.png');
  await el(page.locator('section, div').filter({ hasText: /^Documents de la revue/ }).first(), 'upload_docs.png');
  await el(page.getByText('Glissez-déposez vos PDF et photos').locator('xpath=ancestor::div[contains(@class,"border-dashed")][1]'), 'upload_dropzone.png');
  await ctx.close();
}

await browser.close();
console.log('done');
