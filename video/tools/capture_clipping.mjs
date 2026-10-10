// The brand's own illustration from the sign-in page (a clipping with highlighted passages and its
// « Risque juridique » / « Intox potentielle » tags), captured with a margin for the floating tags.
import path from 'node:path';
import { chromium } from 'playwright';

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 3, locale: 'fr-FR' });
const page = await ctx.newPage();
await page.goto('http://localhost:5174/login');
await page.waitForLoadState('networkidle');
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(1500);
const el = page.getByText('Le Quotidien').locator('xpath=ancestor::div[contains(@class,"max-w-md")][1]');
const b = await el.boundingBox();
const m = 34;
await page.screenshot({ path: path.resolve('presentation/assets/film/clipping.png'), clip: { x: b.x - m, y: b.y - m, width: b.width + 2 * m, height: b.height + 2 * m } });
console.log('clipping', Math.round(b.width), Math.round(b.height));
await browser.close();
