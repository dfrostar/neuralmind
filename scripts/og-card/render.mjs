/**
 * Render the social preview card (card.html) to PNG.
 *
 * Outputs:
 *   site/public/social-preview.png          2400x1260  (site OG image, 2x of 1200x630)
 *   scripts/og-card/github-social-preview.png 2560x1280 (upload manually at
 *     GitHub repo Settings -> Social preview; there is no API for that slot)
 *
 * Claims gate: every number literal listed in REQUIRED_CANON must appear in
 * site/claims.json, or the render refuses to run. This is the pixel-side
 * counterpart of tests/test_site_claims.py — the previous hand-made image
 * shipped an unsourced "40-70x" because no guard could read pixels.
 *
 * Usage:
 *   npm i --no-save playwright-core   (once, anywhere on PATH resolution)
 *   node scripts/og-card/render.mjs
 *
 * The Chromium binary is resolved from $OG_CHROME, or Playwright's default
 * install. On Claude Code on the web, /opt/pw-browsers holds a ready one.
 */
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { chromium } from 'playwright-core';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..', '..');

// --- claims gate -----------------------------------------------------------
// Numbers rendered by card.html. If you change the card's copy, change this
// list to match — the point is that both must trace to site/claims.json.
const REQUIRED_CANON = ['93.75', '45', '257'];

const claims = readFileSync(join(repo, 'site', 'claims.json'), 'utf8');
const card = readFileSync(join(here, 'card.html'), 'utf8');
for (const n of REQUIRED_CANON) {
  if (!card.includes(n)) {
    throw new Error(`card.html no longer contains "${n}" — update REQUIRED_CANON to match the card`);
  }
  if (!claims.includes(n)) {
    throw new Error(`"${n}" is rendered on the card but has no entry in site/claims.json — add the claim first`);
  }
}
// Any OTHER number on the card that isn't canon is a bug waiting to ship.
// Cheap sweep: digit-runs in the card's visible text must be canon-listed
// (font sizes etc. live in <style>, which is stripped first).
const visible = card
  .replace(/<style>[\s\S]*?<\/style>/, '')
  .replace(/<svg[\s\S]*?<\/svg>/g, '')
  .replace(/<!--[\s\S]*?-->/g, '')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&#\d+;/g, ' '); // numeric character refs (en dash, ×) are not claims
const numbers = [...new Set(visible.match(/\d+(?:\.\d+)?/g) ?? [])];
for (const n of numbers) {
  if (!claims.includes(n)) {
    throw new Error(`card.html renders "${n}" which is not in site/claims.json — unsourced numbers do not ship`);
  }
}
console.log(`claims gate: ${numbers.join(', ')} all present in site/claims.json`);

// --- chromium --------------------------------------------------------------
function findChrome() {
  if (process.env.OG_CHROME) return process.env.OG_CHROME;
  const pw = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (pw && existsSync(pw)) {
    for (const d of readdirSync(pw)) {
      const p = join(pw, d, 'chrome-linux', 'chrome');
      if (d.startsWith('chromium-') && existsSync(p)) return p;
    }
  }
  return undefined; // let playwright-core try its own default
}

// --- render ----------------------------------------------------------------
const targets = [
  { w: 1200, h: 630, out: join(repo, 'site', 'public', 'social-preview.png') },
  { w: 1280, h: 640, out: join(here, 'github-social-preview.png') },
];

const browser = await chromium.launch({ executablePath: findChrome(), args: ['--no-sandbox'] });
for (const { w, h, out } of targets) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
  await page.goto('file://' + join(here, 'card.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: out });
  console.log(`${out}  (${w * 2}x${h * 2})`);
  await page.close();
}
await browser.close();
