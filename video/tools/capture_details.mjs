// Close-ups of the REAL job page for the film: highlight cards, filter chips, review sections,
// export buttons. Same auth as capture_app.mjs (one fresh refresh token per context).
//
//   VIDEO_REFRESH_TOKEN_FILE=<file> node tools/capture_details.mjs
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const BASE = 'http://localhost:5174';
const OUT = path.resolve('presentation/assets/app/detail');
fs.mkdirSync(OUT, { recursive: true });
const jobUrl = fs.readFileSync(path.resolve('presentation/assets/app/job_url.txt'), 'utf8').trim();
const tokens = fs.readFileSync(process.env.VIDEO_REFRESH_TOKEN_FILE, 'utf8').trim().split(/\s+/);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 3, locale: 'fr-FR', timezoneId: 'Africa/Douala' });
await ctx.addCookies([{ name: 'refresh_token', value: tokens[0], domain: 'localhost', path: '/api/auth/', httpOnly: true, sameSite: 'Lax', secure: false }]);
const page = await ctx.newPage();
await page.goto(jobUrl);
await page.waitForLoadState('networkidle');
await page.evaluate(() => document.fonts.ready);
await sleep(1500);
// No hover/focus artefacts in close-ups.
await page.mouse.move(0, 0);

async function el(locator, name) {
  await locator.scrollIntoViewIfNeeded();
  await sleep(500);
  await locator.screenshot({ path: path.join(OUT, name) });
  console.log('shot', name);
}

const card = (category, text) => page.locator('article.rounded-2xl').filter({ hasText: category }).filter({ hasText: text }).first();
await el(card('Risque juridique', 'aurait détourné'), 'hl_risque_detournement.png');
await el(card('Risque juridique', 'conserver les données'), 'hl_risque_donnees.png');
await el(card('Intox potentielle', 'vidéo virale'), 'hl_intox_video.png');
await el(card('Annonce concurrent', 'TransCam'), 'hl_concurrent_transcam.png');
await el(card('Point important', 'Cacao'), 'hl_important_cacao.png');
await el(card('Point important', 'Extrême-Nord'), 'hl_important_extreme_nord.png');

// filter chips (the row holding « Tous · 24 »)
await el(page.getByRole('button', { name: /^Tous/ }).first().locator('xpath=..'), 'hl_chips.png');
const panel = page.locator('section.card').filter({ hasText: 'Points clés' }).first();
await el(panel, 'hl_panel_all.png');
for (const [chip, name] of [[/^Risque juridique/, 'hl_panel_risque.png'], [/^Intox potentielle/, 'hl_panel_intox.png'], [/^Annonce concurrent/, 'hl_panel_concurrent.png']]) {
  await page.getByRole('button', { name: chip }).first().click();
  await sleep(700);
  await page.mouse.move(0, 0);
  await el(panel, name);
}
await page.getByRole('button', { name: /^Tous/ }).first().click();

// review sheet pieces
const sheet = page.locator('article').filter({ hasText: 'REVUE DE PRESSE' }).first();
await el(sheet.locator('header').first(), 'sheet_masthead.png');
const sections = sheet.locator('section');
const n = await sections.count();
for (let i = 0; i < n; i++) await el(sections.nth(i), `sheet_section_${i}.png`);

// export actions
await el(page.getByRole('button', { name: /Exporter en PDF/ }).first().locator('xpath=..'), 'actions.png');
await page.screenshot({ path: path.join(OUT, 'job_top.png') });

await browser.close();
console.log('done');
