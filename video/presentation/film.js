// Revue de Presse — présentation (60 s). Pure function of time: window.seek(t) paints frame t.
// Timing is in beats (u, 100 BPM) on the measured grid; docs/shotlist.md is the plan this follows.
// Every screen is a REAL capture of the app (assets/film/, see tools/), never redrawn UI.
import * as M from './lib/motion.js';

const { W, H, FORMAT, E, prog, lerp, clamp, springU, springKeys, SPRING, wobble, font, layout, glyph, text, fill, rrect, hash01, shake, U } = M;

// Brand tokens (assets/brand.json + the site's CSS): ink, paper, one accent (the logo's highlighter).
const C = {
  ink: '#0B1020', ink2: '#161D33', ink3: '#27304D', paper: '#FFFDF8', white: '#FFFFFF',
  amber: '#FBBF24', slate3: '#CAD5E2', slate4: '#90A1B9', slate5: '#62748E', text: '#0F172B',
  logoA: '#6366F1', logoB: '#1E1B4B',
};
const DISPLAY = 'Display', UI = 'UI';
const P = FORMAT.portrait;
const SAFE = FORMAT.safe;
const pick = FORMAT.pick;

// ---------------------------------------------------------------- data loaded in init()
let VO = { words: [], phrases: [] };
const norm = (w) => w.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9']/g, '');
// beat at which a given word of a VO phrase starts (fallback: the phrase's own beat)
function wu(label, word, fallback) {
  const n = norm(word);
  const ws = VO.words.filter((x) => x.label === label);
  const w = ws.find((x) => norm(x.w) === n) || ws.find((x) => norm(x.w).startsWith(n));
  return w ? U(w.t0) : fallback;
}

// ---------------------------------------------------------------- hits (sfx.mjs voices each one)
const HITS = [
  [0, 'first page slams', 'impact', { gain: 0.55 }],
  ...[3, 4, 5, 6, 7, 8].map((i) => [(i - 2) * 0.5, `page ${i + 1} lands`, 'thud', { gain: 0.16 + 0.02 * (i % 3), pitch: 90 + 14 * (i % 4), to: 52 }]),
  [12.0, 'marker stretches into a band', 'whoosh', { len: 0.5, from: 500, to: 3200, gain: 0.22 }],
  [13.2, 'logo pops', 'pop', { pitch: 'F5', to: 'C6' }],
  [19.5, 'push to the app', 'whoosh', { len: 0.45, from: 2400, to: 600 }],
  [20.0, 'phone lands', 'thud', { gain: 0.3 }],
  ...[0, 1, 2, 3, 4, 5].map((i) => [20.95 + i * 0.5, `page ${i + 1} into the phone`, 'tick', { pitch: 900 + i * 120 }]),
  [24.25, 'drop zone slides in', 'whoosh', { len: 0.35, from: 3000, to: 900, gain: 0.2 }],
  [25.0, 'documents card', 'pop', { pitch: 'A4', gain: 0.25 }],
  [26.25, 'launch button', 'pop', { pitch: 'C5', to: 'F5' }],
  [27.0, 'button pressed', 'click', { gain: 0.4 }],
  [27.55, 'zoom through the button', 'whoosh', { len: 0.4, from: 400, to: 4000 }],
  [28.0, 'analysis card', 'thud', { gain: 0.3 }],
  [33.25, 'step: summaries', 'blip', { pitch: 'A5' }],
  [36.0, 'step: key points', 'blip', { pitch: 'C6' }],
  [38.6, 'step: drafting', 'blip', { pitch: 'E6' }],
  [40.0, 'the review lands', 'thud', { gain: 0.5 }],
  [43.0, 'masthead docks into the sheet', 'whoosh', { len: 0.4, from: 1800, to: 700, gain: 0.2 }],
  [46.0, 'rubric 1', 'pop', { pitch: 'C5' }],
  [46.5, 'rubric 2', 'pop', { pitch: 'E5' }],
  [47.0, 'rubric 3', 'pop', { pitch: 'G5' }],
  ...[0, 1, 2, 3, 4].map((i) => [48 + i * 0.18, `row ${i + 1} in upload order`, 'tick', { pitch: 1400 - i * 60, gain: 0.16 }]),
  [49.6, 'rows re-rank', 'whoosh', { len: 0.3, from: 900, to: 2600, gain: 0.18 }],
  ...[0, 1, 2, 3, 4].map((i) => [50.7 + i * 0.12, `rank ${i + 1}`, 'blip', { pitch: ['F5', 'A5', 'C6', 'D6', 'F6'][i], gain: 0.14 }]),
  [55.6, 'marker wipe', 'whoosh', { len: 0.45, from: 600, to: 3600 }],
  [56.0, 'card: legal risk', 'pop', { pitch: 'D5' }],
  [58.25, 'card: fake news', 'pop', { pitch: 'F5' }],
  [60.0, 'card: competitor', 'pop', { pitch: 'A5' }],
  [63.0, 'cards line up', 'whoosh', { len: 0.35, from: 2000, to: 800, gain: 0.18 }],
  [64.0, 'filters slide in', 'tick'],
  [67.7, 'push to export', 'whoosh', { len: 0.45, from: 2400, to: 600 }],
  [68.3, 'toolbar lands', 'click', { gain: 0.3 }],
  [72.5, 'pdf page 3 flies out', 'whoosh', { len: 0.25, from: 3000, to: 1200, gain: 0.16 }],
  [73.0, 'pdf page 2 flies out', 'whoosh', { len: 0.25, from: 3200, to: 1300, gain: 0.16 }],
  [73.5, 'pdf page 1 flies out', 'whoosh', { len: 0.25, from: 3400, to: 1400, gain: 0.18 }],
  [75.7, 'push to the team', 'whoosh', { len: 0.45, from: 2400, to: 600 }],
  [76.5, 'team card', 'thud', { gain: 0.22 }],
  [78.5, 'categories card', 'pop', { pitch: 'G5' }],
  [83.3, 'marker wipe to the end card', 'whoosh', { len: 0.5, from: 600, to: 3600 }],
  [84.0, 'logo lockup', 'thud', { gain: 0.3 }],
  [90.5, 'trial badge', 'pop', { pitch: 'C6', gain: 0.25 }],
  [91.0, 'url', 'tick'],
];
// word-synced hits are added in init(), once the VO edit is known

// ---------------------------------------------------------------- drawing helpers

function grid(ctx, alpha = 0.045, step = 44) {
  ctx.save();
  ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = 0.5; x < W; x += step) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
  for (let y = 0.5; y < H; y += step) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
  ctx.stroke();
  ctx.restore();
}
function inkBg(ctx) {
  fill(ctx, C.ink);
  const g = ctx.createRadialGradient(W * 0.62, H * 0.42, 0, W * 0.62, H * 0.42, Math.max(W, H) * 0.75);
  g.addColorStop(0, '#16203F');
  g.addColorStop(1, C.ink);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
  grid(ctx);
}
function paperBg(ctx) { fill(ctx, C.paper); }

// A real capture, centred on (cx, cy), width w, with rotation / scale, rounded and shadowed.
function card(ctx, img, cx, cy, w, { rot = 0, s = 1, r = 18, shadow = 0.22, blur = 44, oy = 18, alpha = 1, bg = '#FFFFFF' } = {}) {
  if (!img || s <= 0.001 || alpha <= 0) return null;
  const h = (w * img.height) / img.width;
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.translate(cx, cy);
  ctx.rotate(rot);
  ctx.scale(s, s);
  if (shadow > 0) {
    ctx.save();
    ctx.shadowColor = `rgba(11,16,32,${shadow})`;
    ctx.shadowBlur = blur;
    ctx.shadowOffsetY = oy;
    rrect(ctx, -w / 2, -h / 2, w, h, r);
    ctx.fillStyle = bg;
    ctx.fill();
    ctx.restore();
  }
  rrect(ctx, -w / 2, -h / 2, w, h, r);
  ctx.clip();
  ctx.drawImage(img, -w / 2, -h / 2, w, h);
  ctx.restore();
  return { w, h };
}

// The brand gesture: a highlighter stroke drawn left to right (p 0..1), a little slanted.
function markerPath(ctx, x, y, w, h, p) {
  const ww = Math.max(0, w * clamp(p));
  const sk = h * 0.16;
  ctx.beginPath();
  ctx.moveTo(x + sk, y);
  ctx.lineTo(x + ww, y + h * 0.05);
  ctx.quadraticCurveTo(x + ww + h * 0.22, y + h * 0.5, x + ww - sk * 0.5, y + h);
  ctx.lineTo(x - sk * 0.2, y + h * 0.95);
  ctx.quadraticCurveTo(x - h * 0.18, y + h * 0.48, x + sk, y);
  ctx.closePath();
}
function marker(ctx, x, y, w, h, p, color = C.amber) {
  if (p <= 0) return;
  ctx.save();
  markerPath(ctx, x, y, w, h, p);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.restore();
}

// A line of words, each rising into place from under its baseline as it is said.
// words: [{ s: 'Chaque', u: beat, color? }]. Returns the line width.
function wordLine(ctx, words, x, y, size, weight, family, color, u, { align = 'left', track = 0, gap = 0.27, exitU = null, cfg = SPRING.snappy } = {}) {
  const f = font(size, weight, family);
  ctx.font = f;
  ctx.letterSpacing = `${track}px`;
  const widths = words.map((w) => ctx.measureText(w.s).width);
  ctx.letterSpacing = '0px';
  const space = size * gap;
  const total = widths.reduce((a, b) => a + b, 0) + space * (words.length - 1);
  let cx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x;
  const ex = exitU == null ? 0 : E.inBack(prog(u, exitU, exitU + 0.45), 1.3);
  if (ex >= 1) return total;
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, y - size * 1.15, W, size * 1.5);
  ctx.clip();
  words.forEach((w, i) => {
    const k = springU(u, w.u, cfg);
    if (k > 0) text(ctx, w.s, cx, y + (1 - k) * size * 1.05 - ex * size * 1.5, f, w.color || color, 'left', track);
    cx += widths[i] + space;
  });
  ctx.restore();
  return total;
}

// The brand mark (assets/logo/icon_0.svg, same geometry): gradient square, white rules and the
// amber highlighted line. parts: square / lines scales 0..1, bar rect override for the morph.
function logo(ctx, x, y, size, { sq = 1, lines = [1, 1, 1], bar = null, alpha = 1 } = {}) {
  const k = size / 32;
  ctx.save();
  ctx.globalAlpha *= alpha;
  if (sq > 0) {
    ctx.save();
    ctx.translate(x + 16 * k, y + 16 * k);
    ctx.scale(sq, sq);
    const g = ctx.createLinearGradient(-16 * k, -16 * k, 16 * k, 16 * k);
    g.addColorStop(0, C.logoA);
    g.addColorStop(1, C.logoB);
    rrect(ctx, -16 * k, -16 * k, 32 * k, 32 * k, 8 * k);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.restore();
  }
  const b = bar || { x: x + 6.5 * k, y: y + 13.1 * k, w: 19 * k, h: 5.8 * k };
  rrect(ctx, b.x, b.y, b.w, b.h, 1.6 * k);
  ctx.fillStyle = C.amber;
  ctx.fill();
  const rule = (x0, yy, len, color, p) => {
    if (p <= 0) return;
    ctx.beginPath();
    ctx.moveTo(x + x0 * k, y + yy * k);
    ctx.lineTo(x + (x0 + len * clamp(p)) * k, y + yy * k);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.2 * k;
    ctx.lineCap = 'round';
    ctx.stroke();
  };
  ctx.globalAlpha *= 1;
  rule(9, 9.6, 14, 'rgba(255,255,255,0.85)', lines[0]);
  rule(9, 16, 14, C.logoB, lines[1]);
  rule(9, 22.4, 9, 'rgba(255,255,255,0.85)', lines[2]);
  ctx.restore();
}
const logoBar = (x, y, size) => ({ x: x + (6.5 * size) / 32, y: y + (13.1 * size) / 32, w: (19 * size) / 32, h: (5.8 * size) / 32 });

function phone(ctx, img, cx, cy, w, h, { rot = 0, s = 1 } = {}) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rot);
  ctx.scale(s, s);
  ctx.save();
  ctx.shadowColor = 'rgba(11,16,32,0.35)';
  ctx.shadowBlur = 60;
  ctx.shadowOffsetY = 28;
  rrect(ctx, -w / 2, -h / 2, w, h, w * 0.15);
  ctx.fillStyle = C.ink;
  ctx.fill();
  ctx.restore();
  const b = w * 0.032;
  rrect(ctx, -w / 2 + b, -h / 2 + b, w - 2 * b, h - 2 * b, w * 0.12);
  ctx.save();
  ctx.clip();
  const sw = w - 2 * b, sh = (sw * img.height) / img.width;
  ctx.drawImage(img, -sw / 2, -h / 2 + b, sw, sh);
  ctx.restore();
  rrect(ctx, -w * 0.13, -h / 2 + b * 1.6, w * 0.26, w * 0.065, w * 0.04);
  ctx.fillStyle = C.ink;
  ctx.fill();
  ctx.restore();
}

// ---------------------------------------------------------------- S1–S2 hook: the morning pile + the question (u 0–13)
const PAGE_KEYS = ['page_01', 'page_02', 'page_03', 'page_04', 'page_05', 'page_06', 'page_07', 'page_08', 'page_09'];
function sceneHook(ctx, u, IMG) {
  inkBg(ctx);
  const [pcx, pcy] = pick({ '16x9': [1345, 560], '9x16': [540, 650] });
  const ph = pick({ '16x9': 600, '9x16': 620 });
  const spread = pick({ '16x9': [430, 220], '9x16': [430, 250] });
  const pull = E.inOutCubic(prog(u, 0.15, 2.8));
  const cam = lerp(pick({ '16x9': 1.38, '9x16': 1.16 }), 1, pull) * (1 + 0.06 * E.inOutSine(prog(u, 2.8, 8)) + 0.08 * E.inOutCubic(prog(u, 7, 12.5)));
  const fx0 = pcx + (hash01(2, 3) - 0.5) * spread[0], fy0 = pcy + (hash01(2, 7) - 0.5) * spread[1];
  const focusX = lerp(fx0, pcx, pull), focusY = lerp(fy0, pcy, pull);
  ctx.save();
  // frame 0: the slamming page sits in the middle of the frame, then the pile slides to its place
  ctx.translate(P ? pcx : lerp(W / 2, pcx, pull), P ? pcy : lerp(H / 2, pcy, pull));
  ctx.scale(cam, cam);
  ctx.translate(-focusX, -focusY);
  const landed = Math.floor(clamp(u / 0.5, 0, 6));
  shake(ctx, u, landed * 0.5, landed === 0 ? 16 : 5, 3 + landed, 0.14);
  PAGE_KEYS.forEach((key, i) => {
    const img = IMG[key];
    const L = (i - 2) * 0.5;               // two pages already on the desk at frame 0
    const fall = prog(u, L - 0.42, L);
    if (fall <= 0 || !img) return;
    const e = E.inQuad(fall);
    const tx = pcx + (hash01(i, 3) - 0.5) * spread[0];
    const ty = pcy + (hash01(i, 7) - 0.5) * spread[1];
    const rot = (hash01(i, 11) - 0.5) * 0.32;
    const x = lerp(tx + (hash01(i, 13) - 0.5) * 420, tx, e);
    const y = lerp(ty - H * 0.8, ty, e);
    const sq = 0.03 * wobble(u - L, 2.6, 7);
    const sc = lerp(1.4, 1, e) * (1 + sq);
    const r = rot + (1 - e) * 0.4 * (hash01(i, 17) > 0.5 ? 1 : -1);
    const w = (ph * img.width) / img.height;
    card(ctx, img, x, y, w, { rot: r, s: sc, r: 4, shadow: 0.5, blur: 26 + (1 - e) * 60, oy: 10 + (1 - e) * 50, bg: '#F3EEE2' });
  });
  ctx.restore();

  // the pile steps back for the question
  const dim = 0.66 * E.inOutCubic(prog(u, 6.8, 8.0));
  if (dim > 0) { ctx.fillStyle = `rgba(11,16,32,${dim})`; ctx.fillRect(0, 0, W, H); }

  // A: « Chaque matin, des dizaines de journaux. »
  if (u < 8.2) {
    const size = pick({ '16x9': 96, '9x16': 92 });
    const x = SAFE.x;
    const y0 = pick({ '16x9': 430, '9x16': 1262 });
    const lh = size * 1.08;
    const lines = [
      [['Chaque', 'Chaque'], ['matin,', 'matin']],
      [['des', 'des'], ['dizaines', 'dizaines']],
      [['de', 'de'], ['journaux.', 'journaux']],
    ];
    lines.forEach((ln, li) => {
      const words = ln.map(([s, w], k) => ({ s, u: wu('A', w, 1 + li * 1.5 + k * 0.4) - 0.12 }));
      wordLine(ctx, words, x, y0 + li * lh, size, 600, DISPLAY, C.white, u, { exitU: 6.85 + li * 0.07 });
    });
  }

  // B: « Lesquels comptent vraiment pour votre entreprise ? »
  if (u >= 7.2) questionTitle(ctx, u);
}

function questionGeom(ctx) {
  const big = pick({ '16x9': 176, '9x16': 158 });
  const x = SAFE.x;
  const yBig = pick({ '16x9': 640, '9x16': 1050 });
  const f = font(big, 700, DISPLAY);
  const L = layout(ctx, 'vraiment', f, -0.01 * big);
  return { big, x, yBig, f, w: L.width, rect: { x: x - big * 0.1, y: yBig - big * 0.66, w: L.width + big * 0.2, h: big * 0.82 } };
}
function questionTitle(ctx, u) {
  const g = questionGeom(ctx);
  const exitU = 11.95;
  const size1 = pick({ '16x9': 92, '9x16': 84 });
  const y1 = g.yBig - g.big * 1.0;
  wordLine(ctx, [{ s: 'Lesquels', u: wu('B', 'Lesquels', 7.5) - 0.12 }, { s: 'comptent', u: wu('B', 'comptent', 8.2) - 0.12 }],
    g.x, y1, size1, 600, DISPLAY, C.white, u, { exitU });
  const uV = wu('B', 'vraiment', 8.8);
  const p = E.outCubic(prog(u, uV - 0.05, uV + 0.6));
  // the marker under "vraiment" (stretched by the brand scene from u 12)
  if (u < 12.0) marker(ctx, g.rect.x, g.rect.y, g.rect.w, g.rect.h, p);
  const k = springU(u, uV - 0.15, SPRING.snappy);
  const ex = E.inBack(prog(u, exitU + 0.05, exitU + 0.5), 1.3);
  if (k > 0 && u < 12.6) {
    const y = g.yBig + (1 - k) * g.big * 0.9 - ex * g.big * 1.6;
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, g.yBig - g.big * 1.05 - ex * g.big * 1.6, W, g.big * 1.4);
    ctx.clip();
    text(ctx, 'vraiment', g.x, y, g.f, C.white, 'left', -0.01 * g.big);
    // where the marker has passed, the word is ink on amber
    ctx.save();
    markerPath(ctx, g.rect.x, g.rect.y, g.rect.w, g.rect.h, u < 12.0 ? p : 1);
    ctx.clip();
    text(ctx, 'vraiment', g.x, y, g.f, C.ink, 'left', -0.01 * g.big);
    ctx.restore();
    ctx.restore();
  }
  const size3 = pick({ '16x9': 52, '9x16': 50 });
  wordLine(ctx, [
    { s: 'pour', u: wu('B', 'pour', 9.6) - 0.1 },
    { s: 'votre', u: wu('B', 'votre', 9.8) - 0.1 },
    { s: 'entreprise ?', u: wu('B', 'entreprise', 10.1) - 0.1 },
  ], g.x + 6, g.yBig + size3 * 1.9, size3, 500, UI, C.slate3, u, { exitU: exitU + 0.1, gap: 0.28 });
}

// ---------------------------------------------------------------- S3 brand (u 12–20.4)
function brandGeom() {
  if (P) {
    const ls = 190;
    return { ls, lx: W / 2 - ls / 2, ly: 290, wx: W / 2, wy: 620, wsize: 108, align: 'center', sub: 684, tx: W / 2, ty: [850, 930], tsize: 62,
      clip: [540, 1235, 640, 0.025] };
  }
  const ls = 176;
  return { ls, lx: 130, ly: 170, wx: 130 + ls + 40, wy: 170 + ls * 0.68, wsize: 132, align: 'left', sub: 170 + ls * 0.68 + 60, tx: 130, ty: [600, 686], tsize: 66,
    clip: [1535, 700, 680, 0.03] };
}
function sceneBrand(ctx, u, IMG) {
  const b = brandGeom();
  const bar = logoBar(b.lx, b.ly, b.ls);
  // 12.0–12.55: the question's marker stretches into a full-width band (over the hook)
  const qg = questionGeom(ctx);
  const full = { x: -80, y: H / 2 - pick({ '16x9': 70, '9x16': 80 }), w: W + 160, h: pick({ '16x9': 140, '9x16': 160 }) };
  const e1 = E.inOutCubic(prog(u, 12.0, 12.55));
  const e2 = E.inOutCubic(prog(u, 12.6, 13.25));
  const lerpR = (a, c, t) => ({ x: lerp(a.x, c.x, t), y: lerp(a.y, c.y, t), w: lerp(a.w, c.w, t), h: lerp(a.h, c.h, t) });
  const band = e2 > 0 ? lerpR(full, bar, e2) : lerpR(qg.rect, full, e1);
  if (u >= 12.55) inkBg(ctx);
  if (u < 13.25) {
    marker(ctx, band.x, band.y, band.w, band.h, 1);
    if (u < 12.55) return;
  }
  // logo assembles around the bar
  const sq = springU(u, 13.15, SPRING.bouncy);
  const lines = [0, 1, 2].map((i) => E.outCubic(prog(u, 13.45 + i * 0.12, 13.75 + i * 0.12)));
  if (u >= 13.15) logo(ctx, b.lx, b.ly, b.ls, { sq, lines });
  // wordmark, per glyph
  const uRevue = wu('C', 'Revue', 13.47);
  const f = font(b.wsize, 600, DISPLAY);
  const L = layout(ctx, 'Revue de Presse', f, -0.015 * b.wsize);
  const x0 = b.align === 'center' ? b.wx - L.width / 2 : b.wx;
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, b.wy - b.wsize * 1.05, W, b.wsize * 1.35);
  ctx.clip();
  L.glyphs.forEach((g, j) => {
    const k = springU(u, uRevue - 0.1 + j * 0.022, SPRING.snappy);
    if (k <= 0) return;
    glyph(ctx, g.ch, x0 + g.cx, b.wy + (1 - k) * b.wsize, f, C.white);
  });
  ctx.restore();
  // logo subtitle (the site's own words)
  wordLine(ctx, [{ s: 'Veille média augmentée par l’IA', u: 14.3 }], b.align === 'center' ? b.wx : x0 + 4, b.sub + 6, pick({ '16x9': 42, '9x16': 40 }), 500, UI, C.slate4, u, { align: b.align });
  // the site's headline: « Votre revue de presse, analysée en quelques minutes. »
  const t1 = ['Votre', 'revue', 'de', 'presse,'].map((s, i) => ({ s, u: 15.0 + i * 0.16 }));
  const t2 = [['analysée', C.amber], ['en', null], ['quelques', null], ['minutes.', null]].map(([s, c], i) => ({ s, u: wu('C', 'quelques', 16.4) - 0.6 + i * 0.2, color: c || undefined }));
  wordLine(ctx, t1, b.tx, b.ty[0], b.tsize, 500, DISPLAY, C.white, u, { align: b.align });
  wordLine(ctx, t2, b.tx, b.ty[1], b.tsize, 500, DISPLAY, C.white, u, { align: b.align });
  // the site's own illustration: a clipping whose sensitive passages are highlighted
  const kc = springU(u, 14.55, SPRING.gentle);
  if (kc > 0 && IMG.clipping) {
    const [cx, cy, cw, cr] = b.clip;
    const img = IMG.clipping;
    const ch = (cw * img.height) / img.width;
    ctx.save();
    ctx.translate(cx + (1 - kc) * (P ? 0 : 420), cy + (1 - kc) * (P ? 520 : 140) + Math.sin(u * 0.4) * 5);
    ctx.rotate(cr + (1 - kc) * 0.12);
    ctx.shadowColor = 'rgba(0,0,0,0.5)';
    ctx.shadowBlur = 60;
    ctx.shadowOffsetY = 26;
    ctx.drawImage(img, -cw / 2, -ch / 2, cw, ch);
    ctx.restore();
  }
}

// ---------------------------------------------------------------- S4 upload (u 19.4–28.1)
function sceneUpload(ctx, u, IMG) {
  paperBg(ctx);
  // the zoom-through the launch button at the end
  const z = E.inCubic(prog(u, 27.45, 28.05));
  const btn = pick({ '16x9': [1350, 965], '9x16': [540, 1395] });
  ctx.save();
  if (!P) {
    // « Photographiez les unes avec votre téléphone » : close on the phone; « ou déposez vos PDF » : pull back
    const [cz, cx, cy] = springKeys(u, [[19.5, [1.22, 560, 560]], [24.1, [1.32, 1350, 380]], [25.9, [1, 960, 540]]], SPRING.gentle);
    ctx.translate(960, 540);
    ctx.scale(cz, cz);
    ctx.translate(-cx, -cy);
  }
  if (z > 0) { ctx.translate(btn[0], btn[1]); ctx.scale(1 + z * 7, 1 + z * 7); ctx.translate(-btn[0], -btn[1]); }

  // phone with the real mobile upload screen
  const [phx, phy, phw, phh] = pick({ '16x9': [500, 555, 420, 890], '9x16': [540, 820, 540, 1140] });
  const kp = springU(u, 19.9, SPRING.gentle);
  phone(ctx, IMG.m_upload, phx, lerp(phy + H * 0.75, phy, kp), phw, phh, { rot: lerp(-0.16, -0.045, kp) });
  // the morning's pages fly into the phone (photographed)
  for (let i = 0; i < 6; i++) {
    const img = IMG[PAGE_KEYS[i]];
    const a = 20.45 + i * 0.5;
    const p = prog(u, a, a + 0.55);
    if (p <= 0 || p >= 1 || !img) continue;
    const e = E.inOutCubic(p);
    const sx = -220, sy = pick({ '16x9': 180 + hash01(i, 5) * 700, '9x16': 300 + hash01(i, 5) * 900 });
    const ex = phx, ey = phy - phh * 0.08;
    const cx = lerp(sx, ex, e), cy = lerp(sy, ey, e) - Math.sin(Math.PI * e) * 160;
    const s = lerp(1, 0.12, E.inCubic(p));
    const w = pick({ '16x9': 400, '9x16': 360 });
    card(ctx, img, cx, cy, w, { rot: (1 - e) * (hash01(i, 9) - 0.5) * 0.8, s, r: 4, shadow: 0.3, blur: 30, bg: '#F3EEE2' });
  }
  // desktop: drop zone, then the documents grid, then the launch button
  if (P) {
    const kd = springU(u, 24.2, SPRING.snappy);
    if (kd > 0) card(ctx, IMG.upload_dropzone, 540, lerp(H + 300, 1180, kd), 960, { r: 22, rot: 0.01 });
  } else {
    const kd = springU(u, 24.2, SPRING.snappy);
    if (kd > 0) card(ctx, IMG.upload_dropzone, lerp(W + 560, 1350, kd), 335, 1010, { r: 24 });
    const kg = springU(u, 24.95, SPRING.snappy);
    if (kg > 0) card(ctx, IMG.upload_docs, 1350, lerp(H + 380, 835, kg), 1010, { r: 24 });
  }
  const kb = springU(u, 26.2, SPRING.bouncy);
  if (kb > 0) {
    const press = 1 - 0.07 * Math.sin(Math.PI * prog(u, 27.0, 27.25));
    card(ctx, IMG.upload_launch, btn[0], btn[1], pick({ '16x9': 560, '9x16': 620 }), { s: lerp(0.6, 1, kb) * press, r: 26, shadow: 0.3, blur: 40, bg: '#5B50E8' });
  }
  ctx.restore();
}

// ---------------------------------------------------------------- S5 the analysis, timelapse of the real progress screen (u 28–40)
// progress_NN.jpg = every other real capture: step 1 = 0..14, step 2 = 15..22, step 3 = 23..34, step 4 = 35..46
const PROG_KEYS = [[28, 1], [33.0, 14], [33.25, 15], [35.9, 22], [36.0, 23], [38.5, 34], [38.7, 35], [40, 46]];
function sceneAI(ctx, u, IMG) {
  paperBg(ctx);
  let idx = 1;
  for (let i = 1; i < PROG_KEYS.length; i++) {
    const [u0, f0] = PROG_KEYS[i - 1], [u1, f1] = PROG_KEYS[i];
    if (u >= u0 && u < u1) { idx = Math.floor(lerp(f0, f1, (u - u0) / (u1 - u0))); break; }
    if (u >= u1) idx = f1;
  }
  const img = IMG[`progress_${String(clamp(idx, 0, 46)).padStart(2, '0')}`];
  if (!img) return;
  const cw = pick({ '16x9': 1720, '9x16': 1000 });
  const ch = (cw * img.height) / img.width;
  const zoomIn = pick({ '16x9': 1.32, '9x16': 2.2 });
  const fx = pick({ '16x9': 0.36, '9x16': 0.3 });
  const [kx, ky, kz] = springKeys(u, [
    [28, [0.5, 0.5, 1.0]], [28.6, [fx, 0.44, zoomIn]], [33.25, [fx, 0.6, zoomIn]], [36, [fx, 0.75, zoomIn]],
    [38.6, [fx, 0.86, zoomIn]], [39.25, [0.5, 0.5, pick({ '16x9': 1.04, '9x16': 1.1 })]],
  ], SPRING.gentle);
  const enter = springU(u, 27.95, SPRING.snappy);
  const cy = pick({ '16x9': 560, '9x16': 870 });
  ctx.save();
  ctx.translate(W / 2, cy);
  ctx.scale(kz * lerp(0.9, 1, enter), kz * lerp(0.9, 1, enter));
  ctx.translate(-(kx - 0.5) * cw, -(ky - 0.5) * ch);
  card(ctx, img, 0, 0, cw, { r: 30, shadow: 0.16, blur: 60, oy: 24 });
  ctx.restore();
}

// ---------------------------------------------------------------- S6 the review (u 40–56.5)
const UPLOAD_ORDER = [4, 2, 0, 1, 3];       // general press, in the order the pages were dropped
let GEO = null;                             // assets/film/geometry.json
function sceneReview(ctx, u, IMG) {
  inkBg(ctx);
  // the hero moment keeps moving until the masthead docks
  const hero = 1 + 0.06 * E.inOutSine(prog(u, 40.3, 43.0)) * (1 - E.inOutCubic(prog(u, 43.0, 43.9)));
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(hero, hero);
  ctx.translate(-W / 2, -H / 2);
  const art = P ? IMG.m_review : IMG.review_article;
  const g = P ? GEO['m_review.jpg'] : GEO['review_article.png'];
  const win = pick({ '16x9': { x: 80, y: 60, w: 860, h: 960 }, '9x16': { x: 60, y: 250, w: 960, h: 1240 } });
  const k = win.w / art.width;
  const [mx0, my0, mx1, my1] = [g.navy.x[0], g.navy.runs[0][0], g.navy.x[1], g.navy.runs[0][1]];
  const scroll0 = P ? my0 - 60 : 0;
  const scrollY = M.kf(u, P
    ? [[44.4, scroll0], [47.5, scroll0 + 330], [51, scroll0 + 620], [56.5, scroll0 + 980]]
    : [[44.4, 0], [47.5, 380], [51, 1460], [56.5, 2050]], E.inOutSine);
  // the docked masthead position (inside the sheet)
  const dock = { x: win.x + mx0 * k, y: win.y + (my0 - scrollY) * k, w: (mx1 - mx0) * k };
  // standalone masthead: lands at u40, docks at u43
  const mw = pick({ '16x9': 1180, '9x16': 960 });
  const mImg = IMG.masthead;
  const land = springU(u, 39.92, SPRING.bouncy);
  const sq = 0.05 * wobble(u - 40.15, 2.4, 6);
  const dk = E.inOutCubic(prog(u, 43.0, 43.9));
  const cx0 = W / 2, cy0 = pick({ '16x9': 470, '9x16': 640 });
  const mh = (mw * mImg.height) / mImg.width;
  // the sheet window grows out of the masthead
  if (dk > 0) {
    const r0 = { x: cx0 - mw / 2, y: cy0 - mh / 2, w: mw, h: mh };
    const rw = { x: lerp(r0.x, win.x, dk), y: lerp(r0.y, win.y, dk), w: lerp(r0.w, win.w, dk), h: lerp(r0.h, win.h, dk) };
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.45)';
    ctx.shadowBlur = 50;
    ctx.shadowOffsetY = 20;
    rrect(ctx, rw.x, rw.y, rw.w, rw.h, 22);
    ctx.fillStyle = C.paper;
    ctx.fill();
    ctx.restore();
    ctx.save();
    rrect(ctx, rw.x, rw.y, rw.w, rw.h, 22);
    ctx.clip();
    // align the article's masthead with the moving masthead
    const mwNow = lerp(mw, dock.w, dk);
    const kk = mwNow / (mx1 - mx0);
    const mxNow = lerp(cx0 - mw / 2, dock.x, dk);
    const myNow = lerp(cy0 - mh / 2, dock.y, dk);
    ctx.drawImage(art, mxNow - mx0 * kk, myNow - (dk < 1 ? my0 : my0) * kk, art.width * kk, art.height * kk);
    ctx.restore();
  }
  if (dk < 1) {
    const s = lerp(1.0, dock.w / mw, dk);
    const cx = lerp(cx0, dock.x + dock.w / 2, dk);
    const cy = lerp(cy0 - (1 - land) * H * 0.6, dock.y + (mh * s) / 2, dk);
    ctx.save();
    ctx.translate(cx, cy + mh / 2);
    ctx.scale(1 + sq, 1 - sq);
    ctx.translate(-cx, -(cy + mh / 2));
    card(ctx, mImg, cx, cy, mw, { s, r: 18, shadow: dk > 0 ? 0 : 0.5, blur: 60, oy: 26, bg: '#1A237E' });
    ctx.restore();
  }

  // the three rubric banners, as said: « par rubrique »
  const bw = pick({ '16x9': 840, '9x16': 900 });
  const bx = pick({ '16x9': 1410, '9x16': 540 });
  const by = pick({ '16x9': [235, 318, 401], '9x16': [960, 1040, 1120] });
  const bOut = P ? E.inBack(prog(u, 47.8, 48.3), 1.4) : 0;
  if (P) {
    const kp = E.outCubic(prog(u, 45.7, 46.2));
    if (kp > 0) {
      ctx.save();
      ctx.globalAlpha = 0.88 * kp;
      rrect(ctx, 40, 860, W - 80, 600, 28);
      ctx.fillStyle = C.ink;
      ctx.fill();
      ctx.restore();
    }
  }
  [0, 1, 2].forEach((i) => {
    const kb = springU(u, 45.9 + i * 0.5, SPRING.bouncy);
    if (kb <= 0) return;
    card(ctx, IMG[`banner_${i}`], bx + (1 - kb) * 140 - bOut * W, by[i], bw, { s: lerp(0.7, 1, kb), r: 12, shadow: 0.35, blur: 30, oy: 10, bg: '#1A237E' });
  });

  // the ranking: rows appear in upload order, then sort into the review's order
  if (u >= 47.7) ranking(ctx, u, IMG);
  ctx.restore();
}

function ranking(ctx, u, IMG) {
  const rw = pick({ '16x9': 840, '9x16': 900 });
  const rh = pick({ '16x9': 80, '9x16': 74 });
  const gap = pick({ '16x9': 13, '9x16': 16 });
  const x0 = pick({ '16x9': 1410 - 420, '9x16': 90 });
  const yTop = pick({ '16x9': 548, '9x16': 980 });
  const slotY = (j) => yTop + j * (rh + gap);
  // caption swaps from upload order to the review's order
  const capY = yTop - pick({ '16x9': 34, '9x16': 40 });
  const capSize = pick({ '16x9': 26, '9x16': 26 });
  const sw = E.inOutCubic(prog(u, 49.45, 49.85));
  ctx.save();
  ctx.beginPath();
  ctx.rect(x0 - 10, capY - capSize * 1.3, rw + 20, capSize * 1.7);
  ctx.clip();
  const kc = springU(u, 47.75, SPRING.snappy);
  text(ctx, 'ORDRE DE DÉPÔT DES PAGES', x0, capY + (1 - kc) * 40 - sw * 40, font(capSize, 600, UI), C.slate4, 'left', 2.5);
  if (sw > 0) text(ctx, 'LA REVUE : DU PLUS LU AU MOINS CONNU', x0, capY + (1 - sw) * 40, font(capSize, 600, UI), C.amber, 'left', 2.5);
  ctx.restore();
  // rows; the ones moving up are drawn last (they pass in front)
  const rows = [0, 1, 2, 3, 4].map((n) => {
    const from = UPLOAD_ORDER.indexOf(n), to = n;
    const appear = springU(u, 48 + from * 0.18, SPRING.snappy);
    const move = springU(u, 49.6 + Math.abs(from - to) * 0.04, { stiffness: 210, damping: 22 });
    return { n, from, to, appear, move, y: lerp(slotY(from), slotY(to), move) };
  }).sort((a, b) => (a.to - a.from) - (b.to - b.from)).reverse();
  for (const r of rows) {
    if (r.appear <= 0) continue;
    const lift = (r.to < r.from ? 1 : 0) * Math.sin(Math.PI * clamp(r.move)) * 0.04;
    const s = lerp(0.9, 1, r.appear) * (1 + lift);
    const x = x0 + (1 - r.appear) * 80;
    ctx.save();
    ctx.translate(x + rw / 2, r.y + rh / 2);
    ctx.scale(s, s);
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.35)';
    ctx.shadowBlur = 18 + lift * 300;
    ctx.shadowOffsetY = 6 + lift * 120;
    rrect(ctx, -rw / 2, -rh / 2, rw, rh, 14);
    ctx.fillStyle = C.paper;
    ctx.fill();
    ctx.restore();
    const img = IMG[`name_${r.n}`];
    const nh = rh * 0.56;
    const nw = (nh * img.width) / img.height;
    ctx.drawImage(img, -rw / 2 + rh * 1.05, -nh / 2, nw, nh);
    // rank number, once sorted
    const kn = springU(u, 50.7 + r.to * 0.12, SPRING.bouncy);
    if (kn > 0) {
      ctx.save();
      ctx.translate(-rw / 2 + rh * 0.52, 0);
      ctx.scale(kn, kn);
      ctx.beginPath();
      ctx.arc(0, 0, rh * 0.32, 0, Math.PI * 2);
      ctx.fillStyle = C.amber;
      ctx.fill();
      ctx.textBaseline = 'middle';
      text(ctx, String(r.to + 1), 0, rh * 0.02, font(rh * 0.4, 700, DISPLAY), C.ink, 'center');
      ctx.textBaseline = 'alphabetic';
      ctx.restore();
    }
    ctx.restore();
  }
}

// ---------------------------------------------------------------- S7 key points (u 55.6–68.5)
function sceneKeypoints(ctx, u, IMG) {
  paperBg(ctx);
  const cards = [
    { key: 'hl_risque_detournement', at: wu('G1', 'Risques', 56) - 0.05 },
    { key: 'hl_intox_video', at: wu('G2', 'intox', 58.25) - 0.05 },
    { key: 'hl_concurrent_transcam', at: wu('G3', 'annonces', 60) - 0.05 },
  ];
  // fanned as they are named, then (« surlignés et expliqués ») the legal-risk card comes forward
  const fan = pick({
    '16x9': [[560, 560, -0.06], [985, 515, 0.03], [1405, 575, 0.065]],
    '9x16': [[540, 740, -0.035], [540, 990, 0.03], [540, 1240, -0.02]],
  });
  const focus = pick({
    '16x9': [[960, 500, 0, 1.38], [1560, 640, 0.08, 0.86], [360, 640, -0.08, 0.86]],
    '9x16': [[540, 800, 0, 1.1], [540, 1270, 0.03, 0.9], [540, 1300, -0.03, 0.9]],
  });
  const cw = pick({ '16x9': 700, '9x16': 820 });
  const fk = springU(u, wu('G4', 'surlignes', 64.5) - 0.35, SPRING.gentle);
  const order = fk > 0.02 ? [2, 1, 0] : [0, 1, 2];
  for (const i of order) {
    const c = cards[i];
    const k = springU(u, c.at, SPRING.snappy);
    if (k <= 0) continue;
    const [fx, fy, fr] = fan[i];
    const [ax, ay, ar, as] = focus[i];
    const x = lerp(fx, ax, fk), y = lerp(fy, ay, fk), r = lerp(fr, ar, fk), s = lerp(1, as, fk);
    const enterX = P ? 0 : (1 - k) * 260;
    const enterY = (1 - k) * (P ? 760 : 560);
    card(ctx, IMG[c.key], x + enterX, y + enterY, cw, { s, rot: r + (1 - k) * (i % 2 ? 0.2 : -0.2), r: 22, shadow: i === 0 ? 0.2 + 0.12 * fk : 0.2, blur: 50, oy: 22 });
  }
  // the real filter chips: every passage is classified
  const kc = springU(u, 63.95, SPRING.snappy);
  if (kc > 0) {
    const [chx, chy] = pick({ '16x9': [960, 935], '9x16': [540, 320] });
    card(ctx, IMG.chips, chx, chy + (1 - kc) * (P ? -300 : 300), pick({ '16x9': 700, '9x16': 800 }), { r: 18, shadow: 0.16, blur: 30, oy: 10 });
  }
}

// ---------------------------------------------------------------- S8 export (u 67.7–76.5)
function sceneExport(ctx, u, IMG) {
  inkBg(ctx);
  const tb = IMG.actions;
  const tw = pick({ '16x9': 1020, '9x16': 940 });
  const th = (tw * tb.height) / tb.width;
  const [tcx, tcy] = pick({ '16x9': [960, 190], '9x16': [540, 360] });
  const kt = springU(u, 68.2, SPRING.snappy);
  const uWord = wu('H1', 'Word', 70.6), uPdf = wu('H1', 'PDF', 71.9);
  const bumpW = 0.045 * Math.sin(Math.PI * prog(u, uWord - 0.05, uWord + 0.4));
  const pull = 1 - 0.05 * E.inOutSine(prog(u, 73.8, 76.4));
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(pull, pull);
  ctx.translate(-W / 2, -H / 2);
  if (kt > 0) {
    const y = tcy - (1 - kt) * 260;
    // a light plate behind the real buttons (they were captured on the page background)
    ctx.save();
    ctx.translate(tcx, y);
    ctx.scale(1 + bumpW, 1 + bumpW);
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.4)';
    ctx.shadowBlur = 40;
    ctx.shadowOffsetY = 14;
    rrect(ctx, -tw / 2 - 22, -th / 2 - 22, tw + 44, th + 44, 26);
    ctx.fillStyle = '#F7F8FB';
    ctx.fill();
    ctx.restore();
    // left part (Copier le texte + Word) as is; the PDF button presses on « PDF »
    const split = 0.648;                    // where the PDF button starts in actions.png
    const press = 1 - 0.07 * Math.sin(Math.PI * prog(u, uPdf - 0.05, uPdf + 0.3));
    ctx.drawImage(tb, 0, 0, tb.width * split, tb.height, -tw / 2, -th / 2, tw * split, th);
    ctx.save();
    const px = -tw / 2 + tw * split, pw = tw * (1 - split);
    ctx.translate(px + pw / 2, 0);
    ctx.scale(press, press);
    ctx.drawImage(tb, tb.width * split, 0, tb.width * (1 - split), tb.height, -pw / 2, -th / 2, pw, th);
    ctx.restore();
    ctx.restore();
  }
  // the real exported PDF fans out of the button
  const ph = pick({ '16x9': 700, '9x16': 800 });
  const from = [tcx + tw * 0.33, tcy];
  const fanPos = pick({
    '16x9': [[640, 690, -0.12, 'pdf_3'], [1280, 690, 0.12, 'pdf_2'], [960, 660, 0, 'pdf_1']],
    '9x16': [[330, 1020, -0.1, 'pdf_3'], [750, 1020, 0.1, 'pdf_2'], [540, 990, 0, 'pdf_1']],
  });
  fanPos.forEach(([x, y, r, key], i) => {
    const k = springU(u, 72.45 + i * 0.5, { stiffness: 190, damping: 17 });
    if (k <= 0) return;
    const img = IMG[key];
    const w = (ph * img.width) / img.height;
    const cx = lerp(from[0], x, k), cy = lerp(from[1], y, k);
    card(ctx, img, cx, cy, w, { rot: r * k + (1 - k) * 0.5, s: lerp(0.15, 1, Math.min(1, k * 1.3)), r: 6, shadow: 0.45, blur: 50, oy: 24 });
  });
  ctx.restore();
}

// ---------------------------------------------------------------- S9 team + categories (u 75.7–84.4)
function sceneTeam(ctx, u, IMG) {
  paperBg(ctx);
  const push = 1 + 0.06 * E.inOutSine(prog(u, 77, 84.4));
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(push, push);
  ctx.translate(-W / 2, -H / 2);
  const drift = 3.2 * E.inOutSine(prog(u, 78.5, 84.4));
  const kt = springU(u, wu('I1', 'Invitez', 76.5) - 0.1, SPRING.snappy);
  const kc = springU(u, wu('I2', 'choisissez', 78.6) - 0.15, SPRING.snappy);
  if (P) {
    if (kt > 0) card(ctx, IMG.team_members, 540 - (1 - kt) * 900, 560 - drift * 12, 960, { rot: -0.02, r: 24, shadow: 0.2, blur: 50, oy: 20 });
    const tiltP = 0.05 * wobble(u - (wu('I2', 'choisissez', 78.6) + 0.15), 1.6, 3.5);
    if (kc > 0) card(ctx, IMG.cat_custom, 560 + (1 - kc) * 900, 1110 + drift * 10, 600, { rot: 0.03 + tiltP, r: 22, shadow: 0.22, blur: 50, oy: 20 });
  } else {
    if (kt > 0) card(ctx, IMG.team_members, 680 - (1 - kt) * 1400 - drift * 14, 520, 1140, { rot: -0.025, r: 26, shadow: 0.2, blur: 50, oy: 20 });
    const tilt = 0.05 * wobble(u - (wu('I2', 'choisissez', 78.6) + 0.15), 1.6, 3.5);
    if (kc > 0) card(ctx, IMG.cat_custom, 1505 + (1 - kc) * 900 + drift * 12, 548, 490, { rot: 0.035 + tilt, r: 24, shadow: 0.22, blur: 50, oy: 20 });
  }
  ctx.restore();
}

// ---------------------------------------------------------------- S10 end card (u 83.3–100)
const WHATSAPP = '+237 693 42 79 13';
function sceneEnd(ctx, u, IMG) {
  inkBg(ctx);
  const left = !P;
  const x0 = left ? 150 : W / 2;
  const align = left ? 'left' : 'center';
  // the deliverable, on the right (16:9 only)
  if (left) {
    const kp = springU(u, 84.4, SPRING.gentle);
    if (kp > 0) card(ctx, IMG.pdf_1, 1530 + (1 - kp) * 520, 545 + Math.sin(u * 0.15) * 4, 580, { rot: lerp(0.25, 0.06, kp), r: 6, shadow: 0.5, blur: 60, oy: 26 });
  }
  // logo + wordmark
  const ls = left ? 132 : 128;
  const ws = left ? 112 : 90;
  const fW = font(ws, 600, DISPLAY);
  const LW = layout(ctx, 'Revue de Presse', fW, -0.015 * ws);
  const lockW = ls + 32 + LW.width;
  const lx = left ? x0 : W / 2 - lockW / 2;
  const ly = left ? 96 : 380;
  const kl = springU(u, 83.7, SPRING.bouncy);
  if (kl > 0) {
    ctx.save();
    ctx.translate(lx + ls / 2, ly + ls / 2);
    ctx.scale(kl, kl);
    ctx.translate(-(lx + ls / 2), -(ly + ls / 2));
    logo(ctx, lx, ly, ls);
    ctx.restore();
  }
  const wx = lx + ls + 32, wy = ly + ls * 0.71;
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, wy - ws * 1.05, W, ws * 1.35);
  ctx.clip();
  LW.glyphs.forEach((g, j) => {
    const k = springU(u, 83.8 + j * 0.02, SPRING.snappy);
    if (k > 0) glyph(ctx, g.ch, wx + g.cx, wy + (1 - k) * ws, fW, C.white);
  });
  ctx.restore();

  // slogan: « Votre veille média, augmentée par l'IA. » — the marker on « augmentée par l'IA »
  const ss = left ? 88 : 70;
  const sy1 = left ? 390 : 680, sy2 = sy1 + ss * 1.16;
  wordLine(ctx, ['Votre', 'veille', 'média,'].map((s, i) => ({ s, u: wu('J2', s.replace(',', ''), 86 + i * 0.4) - 0.1 })), x0, sy1, ss, 500, DISPLAY, C.white, u, { align });
  const uAug = wu('J2', 'augmentee', 88.3);
  const fS = font(ss, 500, DISPLAY);
  const L2 = layout(ctx, 'augmentée par l’IA.', fS, 0);
  const l2x = left ? x0 : W / 2 - L2.width / 2;
  const mp = E.outCubic(prog(u, uAug + 0.1, uAug + 1.0));
  const mrect = { x: l2x - ss * 0.12, y: sy2 - ss * 0.8, w: L2.width - ss * 0.15, h: ss * 1.0 };
  marker(ctx, mrect.x, mrect.y, mrect.w, mrect.h, mp);
  const w2 = [['augmentée', 'augmentee'], ['par', 'par'], ['l’IA.', "l'ia"]].map(([s, w], i) => ({ s, u: wu('J2', w, 88.3 + i * 0.4) - 0.1 }));
  wordLine(ctx, w2, l2x, sy2, ss, 500, DISPLAY, C.white, u, { gap: 0.25 });
  if (mp > 0) {
    ctx.save();
    markerPath(ctx, mrect.x, mrect.y, mrect.w, mrect.h, mp);
    ctx.clip();
    wordLine(ctx, w2, l2x, sy2, ss, 500, DISPLAY, C.ink, u, { gap: 0.25 });
    ctx.restore();
  }

  // call to action: the real trial badge, the address, WhatsApp for a demo
  const uK = wu('K', 'Sept', 90.5);
  const kb = springU(u, uK - 0.1, SPRING.bouncy);
  const badge = IMG.badge_trial;
  const bh = left ? 64 : 66;
  const bw = (bh * badge.width) / badge.height;
  const by = left ? 600 : 900;
  if (kb > 0) {
    const bx = left ? x0 + bw / 2 : W / 2;
    card(ctx, badge, bx, by + bh / 2, bw, { s: lerp(0.6, 1, kb), r: bh / 2, shadow: 0.25, blur: 24, oy: 8, bg: '#FFF8E1' });
  }
  const urlSize = left ? 70 : 70;
  const uy = by + bh + (left ? 100 : 120);
  wordLine(ctx, [{ s: 'presse.mirlab.cloud', u: uK + 0.4 }], x0, uy, urlSize, 700, UI, C.white, u, { align });
  const uWa = wu('K', 'demo', 92.4);
  const labSize = left ? 40 : 40;
  const numSize = left ? 74 : 72;
  const ly1 = uy + (left ? 96 : 116);
  wordLine(ctx, [{ s: 'Une démo ? Écrivez-nous sur WhatsApp', u: uWa - 0.2 }], x0, ly1, labSize, 500, UI, C.slate3, u, { align });
  wordLine(ctx, [{ s: WHATSAPP, u: uWa + 0.15 }], x0, ly1 + numSize * 1.18, numSize, 700, UI, C.amber, u, { align, track: 1 });
  // honesty note about the demo pages
  const kd = springU(u, 92.8, SPRING.gentle);
  if (kd > 0) {
    ctx.save();
    ctx.globalAlpha = clamp(kd);
    text(ctx, 'Démonstration réalisée avec des pages de presse fictives.', x0, SAFE.y + SAFE.h - 4, font(28, 400, UI), C.slate4, align);
    ctx.restore();
  }
}

// ---------------------------------------------------------------- scene list + transitions
const SCENES = [
  { a: 0, b: 13.3, fn: sceneHook },
  { a: 12.0, b: 20.3, fn: sceneBrand },
  { a: 19.45, b: 28.06, fn: sceneUpload, in: 'push', dur: 0.75 },
  { a: 28.0, b: 40, fn: sceneAI },
  { a: 40, b: 56.4, fn: sceneReview },
  { a: 55.6, b: 68.5, fn: sceneKeypoints, in: 'wipe', dur: 0.75 },
  { a: 67.7, b: 76.5, fn: sceneExport, in: 'push', dur: 0.75 },
  { a: 75.7, b: 84.4, fn: sceneTeam, in: 'push', dur: 0.75 },
  { a: 83.3, b: 101, fn: sceneEnd, in: 'wipe', dur: 0.85 },
];

function draw(ctx, u, t, IMG) {
  for (let i = 0; i < SCENES.length; i++) {
    const s = SCENES[i];
    if (u < s.a || u >= s.b) continue;
    const next = SCENES[i + 1];
    let dx = 0;
    if (s.in === 'push') dx += (1 - E.inOutCubic(prog(u, s.a, s.a + s.dur))) * W;
    if (next && next.in === 'push' && u >= next.a) dx -= E.inOutCubic(prog(u, next.a, next.a + next.dur)) * W;
    ctx.save();
    if (dx) ctx.translate(dx, 0);
    if (s.in === 'wipe' && u < s.a + s.dur) {
      // a highlighter band sweeps across; the new scene is revealed behind it
      const band = pick({ '16x9': 220, '9x16': 200 });
      const p = E.inOutCubic(prog(u, s.a, s.a + s.dur));
      const edge = lerp(-band * 1.5, W + band * 1.5, p);
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(0, 0); ctx.lineTo(edge - band * 0.5, 0); ctx.lineTo(edge - band * 0.5 - band * 0.4, H); ctx.lineTo(0, H); ctx.closePath();
      ctx.clip();
      s.fn(ctx, u, IMG);
      ctx.restore();
      ctx.beginPath();
      ctx.moveTo(edge - band * 0.5, 0); ctx.lineTo(edge + band * 0.5, 0); ctx.lineTo(edge + band * 0.5 - band * 0.4, H); ctx.lineTo(edge - band * 0.5 - band * 0.4, H); ctx.closePath();
      ctx.fillStyle = C.amber;
      ctx.fill();
    } else {
      s.fn(ctx, u, IMG);
    }
    ctx.restore();
  }
}

// ---------------------------------------------------------------- images + harness
const IMAGES = {};
for (const k of PAGE_KEYS) IMAGES[k] = `assets/film/${k}.jpg`;
for (let i = 0; i <= 46; i++) IMAGES[`progress_${String(i).padStart(2, '0')}`] = `assets/film/progress_${String(i).padStart(2, '0')}.jpg`;
for (const k of ['m_upload', 'upload_dropzone', 'upload_docs', 'upload_launch', 'review_article', 'masthead', 'banner_0', 'banner_1', 'banner_2',
  'name_0', 'name_1', 'name_2', 'name_3', 'name_4', 'hl_risque_detournement', 'hl_intox_video', 'hl_concurrent_transcam', 'chips',
  'actions', 'team_members', 'cat_custom', 'badge_trial']) IMAGES[k] = `assets/film/${k}.png`;
for (const k of ['m_review', 'pdf_1', 'pdf_2', 'pdf_3']) IMAGES[k] = `assets/film/${k}.jpg`;
IMAGES.clipping = 'assets/film/clipping_cut.png';

M.film({
  fonts: [font(100, 500, DISPLAY), font(100, 600, DISPLAY), font(100, 700, DISPLAY), font(40, 400, UI), font(40, 500, UI), font(40, 600, UI), font(40, 700, UI)],
  images: IMAGES,
  hits: HITS,
  async init() {
    [VO, GEO] = await Promise.all([
      fetch('vo_words.json').then((r) => r.json()),
      fetch('assets/film/geometry.json').then((r) => r.json()),
    ]);
    // word-synced accents
    HITS.push(
      [wu('B', 'vraiment', 8.8), 'marker under « vraiment »', 'whoosh', { len: 0.3, from: 1500, to: 5000, gain: 0.2 }],
      [wu('H1', 'Word', 70.6), 'Word button', 'tick', { gain: 0.3 }],
      [wu('H1', 'PDF', 71.9), 'PDF button pressed', 'click', { gain: 0.4 }],
      [wu('J2', 'augmentee', 88.3) + 0.1, 'marker on the slogan', 'whoosh', { len: 0.3, from: 1500, to: 5000, gain: 0.18 }],
      [wu('K', 'demo', 92.4) - 0.2, 'WhatsApp line', 'pop', { pitch: 'E5', gain: 0.22 }],
    );
    HITS.sort((a, b) => a[0] - b[0]);
  },
  draw,
});
