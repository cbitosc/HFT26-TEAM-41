// Cuts single engravings out of the team's asset sheets into public/greek/.
//   node scripts/cut-greek.mjs [sheet dir, default ~/greek] [4x sheet dir, default <sheet dir>/x4]
// Resolution: each crop is 4x the sheet. The source is a blend of the sheet upscaled
// with Lanczos and sharpened (keeps the stipple and hatching) and the same sheet
// upscaled by Real-ESRGAN (scripts/upscale-sheets.py; crisp outlines). Without the 4x
// sheets it falls back to Lanczos alone.
// Each asset gives two alpha masks, coloured by CSS (components/fx.tsx Engraving), so
// light and dark themes share them:
//   <name>-ink.webp  the line work
//   <name>-sil.webp  the figure's silhouette, filled with the page colour so layered
//                    figures hide what's behind them
// "iso" assets are isolated by flood-filling the ink from a seed point, which drops
// neighbouring drawings that the crop rectangle catches; "rect" assets are scenes,
// kept whole with feathered edges.
import sharp from "sharp";
import { existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const SRC = process.argv[2] ?? join(homedir(), "greek");
const SRC4 = process.argv[3] ?? join(SRC, "x4");
const OUT = new URL("../public/greek/", import.meta.url).pathname;
const SHEETS = {
  c2: "Indigo Greco-Roman Engraving Collection-2.png",
  s1: "Classical Blue Engraving Asset Sheet-1.png",
};
const K = 4; // upscale factor
const ESRGAN_SHARE = 0.35; // of the blended source

// [name, sheet, x, y, w, h, mode, seed?, exclude?] in sheet pixels; seed and the exclude
// rectangles ([x, y, w, h], ink there is dropped) are relative to the crop.
const ASSETS = [
  ["athena", "c2", 418, 12, 314, 488, "iso", [172, 240], [[0, 236, 56, 110], [82, 450, 34, 38]]],
  ["pegasus", "c2", 1146, 10, 372, 340, "iso", [190, 150]],
  ["sun", "c2", 974, 8, 168, 164, "iso"],
  ["moon", "c2", 1034, 218, 108, 142, "iso", [40, 70]],
  ["sky", "c2", 1294, 276, 224, 226, "iso"],
  ["arch", "c2", 856, 468, 238, 286, "rect"],
  ["helmet", "c2", 72, 504, 128, 196, "iso"],
  ["ionic", "c2", 192, 576, 146, 116, "iso"],
  ["corinthian", "c2", 348, 580, 132, 128, "iso"],
  ["column", "c2", 486, 580, 96, 202, "iso"],
  ["ship", "c2", 478, 752, 350, 170, "rect"],
  ["amphora", "c2", 203, 692, 138, 176, "rect", null, [[116, 136, 22, 40]]],
  ["bull", "c2", 1360, 638, 160, 166, "iso", [80, 60]],
  ["hermes", "c2", 214, 8, 232, 260, "iso", [120, 130]],
  ["wreath", "s1", 381, 750, 140, 132, "iso", [20, 60]],
  ["wreath-bow", "s1", 231, 743, 140, 140, "iso", [20, 60]],
  ["scroll", "s1", 753, 588, 128, 174, "iso"],
  ["compass", "s1", 866, 620, 134, 154, "iso"],
  ["torch", "s1", 703, 586, 56, 176, "iso"],
  ["aegis", "s1", 548, 598, 160, 160, "iso"],
  ["coast", "s1", 888, 456, 644, 236, "rect", null, [[0, 160, 122, 76], [152, 170, 200, 66]]],
];

function maxFilter(src, w, h, r, min = false) {
  const tmp = new Uint8Array(w * h);
  const out = new Uint8Array(w * h);
  const pick = min ? Math.min : Math.max;
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let v = min ? 1 : 0;
      for (let k = Math.max(0, x - r); k <= Math.min(w - 1, x + r); k++) v = pick(v, src[y * w + k]);
      tmp[y * w + x] = v;
    }
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let v = min ? 1 : 0;
      for (let k = Math.max(0, y - r); k <= Math.min(h - 1, y + r); k++) v = pick(v, tmp[k * w + x]);
      out[y * w + x] = v;
    }
  return out;
}

function boxBlur(src, w, h, r) {
  const tmp = new Float32Array(w * h);
  const out = new Float32Array(w * h);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let s = 0;
      let c = 0;
      for (let k = Math.max(0, x - r); k <= Math.min(w - 1, x + r); k++, c++) s += src[y * w + k];
      tmp[y * w + x] = s / c;
    }
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      let s = 0;
      let c = 0;
      for (let k = Math.max(0, y - r); k <= Math.min(h - 1, y + r); k++, c++) s += tmp[k * w + x];
      out[y * w + x] = s / c;
    }
  return out;
}

function flood(mask, w, h, starts, want) {
  const seen = new Uint8Array(w * h);
  const stack = starts.filter((i) => mask[i] === want);
  for (const i of stack) seen[i] = 1;
  while (stack.length) {
    const i = stack.pop();
    const x = i % w;
    const y = (i / w) | 0;
    for (const j of [x > 0 ? i - 1 : -1, x < w - 1 ? i + 1 : -1, y > 0 ? i - w : -1, y < h - 1 ? i + w : -1]) {
      if (j >= 0 && !seen[j] && mask[j] === want) {
        seen[j] = 1;
        stack.push(j);
      }
    }
  }
  return seen;
}

function percentile(arr, p) {
  const s = Float32Array.from(arr).sort();
  return s[Math.floor((s.length - 1) * p)];
}

async function cut([name, sheet, x, y, w, h, mode, seed, exclude = []]) {
  const W = w * K;
  const H = h * K;
  const n = W * H;
  const gray = (img) => img.removeAlpha().greyscale().raw().toBuffer();
  const lan = await gray(
    sharp(join(SRC, SHEETS[sheet]))
      .extract({ left: x, top: y, width: w, height: h })
      .resize(W, H, { kernel: "lanczos3" })
      .sharpen({ sigma: 1.2, m1: 1, m2: 2 }),
  );
  const big = join(SRC4, SHEETS[sheet]);
  const esr = existsSync(big) ? await gray(sharp(big).extract({ left: x * K, top: y * K, width: W, height: H })) : lan;
  const lum = new Float32Array(n);
  for (let i = 0; i < n; i++) lum[i] = lan[i] * (1 - ESRGAN_SHARE) + esr[i] * ESRGAN_SHARE;
  const paper = percentile(lum, 0.97);
  const dark = Math.min(percentile(lum, 0.01), 90);
  const ink = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    let v = (paper - 6 - lum[i]) / (paper - 6 - dark);
    v = Math.max(0, Math.min(1, v));
    ink[i] = v < 0.05 ? 0 : Math.pow(v, 0.85);
  }
  for (const [ex, ey, ew, eh] of exclude)
    for (let j = ey * K; j < (ey + eh) * K; j++) for (let i = ex * K; i < (ex + ew) * K; i++) ink[j * W + i] = 0;

  let sil = new Float32Array(n).fill(1);
  if (mode === "iso") {
    const bin = new Uint8Array(n);
    for (let i = 0; i < n; i++) bin[i] = ink[i] > 0.2 ? 1 : 0;
    const d = 4 * K;
    const grown = maxFilter(bin, W, H, d);
    const [sx, sy] = seed ?? [w / 2, h / 2];
    // Seed on the nearest inked pixel to the requested point.
    let best = -1;
    let bd = Infinity;
    for (let i = 0; i < n; i++) {
      if (!grown[i]) continue;
      const dx = (i % W) - sx * K;
      const dy = ((i / W) | 0) - sy * K;
      const dd = dx * dx + dy * dy;
      if (dd < bd) {
        bd = dd;
        best = i;
      }
    }
    const region = flood(grown, W, H, [best], 1);
    // Holes: whatever the outside can't reach is inside the figure.
    const border = [];
    for (let i = 0; i < W; i++) border.push(i, (H - 1) * W + i);
    for (let j = 0; j < H; j++) border.push(j * W, j * W + W - 1);
    const outside = flood(region, W, H, border, 0);
    let solid = new Uint8Array(n);
    for (let i = 0; i < n; i++) solid[i] = outside[i] ? 0 : 1;
    solid = maxFilter(solid, W, H, d - K, true); // shrink back to the line work
    for (let i = 0; i < n; i++) if (!region[i]) ink[i] = 0;
    // Box blur so the silhouette edge is antialiased.
    sil = boxBlur(Float32Array.from(solid), W, H, K);
  } else {
    const f = Math.round(Math.min(W, H) * 0.06);
    for (let j = 0; j < H; j++)
      for (let i = 0; i < W; i++) {
        const e = Math.min(i, j, W - 1 - i, H - 1 - j) / f;
        const s = Math.min(1, e);
        sil[j * W + i] = s * s * (3 - 2 * s);
      }
    for (let i = 0; i < n; i++) ink[i] *= sil[i];
  }

  const raw = { raw: { width: W, height: H, channels: 4 } };
  const alpha = (f) => {
    const b = Buffer.alloc(n * 4, 255);
    for (let i = 0; i < n; i++) b[i * 4 + 3] = Math.round(Math.min(1, f(i)) * 255);
    return b;
  };
  await sharp(alpha((i) => ink[i]), raw).webp({ quality: 50, alphaQuality: 88 }).toFile(join(OUT, `${name}-ink.webp`));
  await sharp(alpha((i) => Math.max(sil[i], ink[i])), raw)
    .webp({ quality: 50, alphaQuality: 70 })
    .toFile(join(OUT, `${name}-sil.webp`));
  return `${name} ${W}x${H}`;
}

mkdirSync(OUT, { recursive: true });
const only = process.env.ONLY?.split(",");
for (const a of ASSETS) if (!only || only.includes(a[0])) console.log(await cut(a));
