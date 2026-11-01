// Cuts single engravings out of the team's asset sheets into public/greek/ for the landing
// page. Same method as showcase/scripts/cut-greek.mjs, plus the larger figures the landing
// uses (Atlas, Nike, Poseidon, Apollo, Hermes in flight, the lion and two scenes).
//   node scripts/cut-greek.mjs [sheet dir, default ~/greek]
// Each asset gives two files:
//   <name>.webp      parchment cutout: ink on paper, opaque inside the figure's
//                    silhouette, so layered figures hide what's behind them
//   <name>-ink.webp  ink only, as alpha: used as a CSS mask so the same line work
//                    can be printed in any colour (light ink on the night sections)
// "iso" assets are isolated by flood-filling the ink from a seed point, which drops
// neighbouring drawings that the crop rectangle catches; "rect" assets are scenes,
// kept whole with feathered edges.
import sharp from "sharp";
import { mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const SRC = process.argv[2] ?? join(homedir(), "greek");
const OUT = new URL("../public/greek/", import.meta.url).pathname;
const SHEETS = {
  c2: "Indigo Greco-Roman Engraving Collection-2.png",
  s1: "Classical Blue Engraving Asset Sheet-1.png",
};
const K = 2; // upscale factor
const INK = [27, 45, 143]; // --ink
const PAPER = [243, 238, 227]; // --paper

// [name, sheet, x, y, w, h, mode, seed?, exclude?] in sheet pixels; seed and the exclude
// rectangles ([x, y, w, h], ink there is dropped) are relative to the crop.
const ASSETS = [
  ["athena", "c2", 418, 0, 336, 500, "iso", [172, 252], [[0, 248, 56, 110], [82, 462, 34, 38]]],
  ["pegasus", "c2", 1146, 10, 372, 340, "iso", [190, 150]],
  ["sun", "c2", 962, 0, 214, 212, "iso", null, [[0, 0, 34, 50]]],
  ["moon", "c2", 1034, 218, 108, 142, "iso", [40, 70]],
  ["sky", "c2", 1294, 276, 224, 226, "iso"],
  ["arch", "c2", 856, 468, 238, 286, "rect"],
  ["helmet", "c2", 70, 504, 132, 190, "iso", null, [[0, 0, 34, 40]]],
  ["ionic", "c2", 192, 576, 146, 116, "iso"],
  ["corinthian", "c2", 348, 580, 132, 128, "iso"],
  ["column", "c2", 486, 580, 96, 202, "iso"],
  ["ship", "c2", 560, 750, 270, 160, "rect", null, [[0, 0, 16, 30]]],
  ["amphora", "c2", 203, 692, 138, 176, "rect", null, [[116, 136, 22, 40]]],
  ["bull", "c2", 1360, 638, 160, 166, "iso", [80, 60]],
  ["hermes", "c2", 214, 6, 238, 270, "iso", [130, 140], [[220, 180, 18, 50], [170, 252, 68, 24]]],
  ["wreath", "s1", 381, 750, 140, 132, "iso", [20, 60]],
  ["wreath-bow", "s1", 231, 743, 140, 140, "iso", [20, 60]],
  ["scroll", "s1", 753, 588, 128, 174, "iso"],
  ["compass", "s1", 866, 620, 134, 154, "iso"],
  ["torch", "s1", 703, 586, 56, 176, "iso"],
  ["aegis", "s1", 548, 598, 160, 160, "iso"],
  ["coast", "s1", 888, 456, 644, 236, "rect", null, [[0, 160, 122, 76], [152, 170, 200, 66]]],
  ["atlas", "c2", 752, 118, 248, 358, "iso", [118, 144], [[0, 272, 60, 86], [0, 34, 26, 140], [215, 128, 33, 104], [0, 0, 100, 8], [0, 296, 82, 62], [196, 330, 52, 28]]],
  ["parthenon", "c2", 262, 380, 226, 190, "rect"],
  ["ruins", "c2", 598, 478, 262, 278, "rect"],
  ["poseidon", "c2", 1100, 650, 252, 292, "iso", [130, 170], [[214, 250, 38, 42]]],
  ["lion", "c2", 1316, 500, 196, 126, "iso", [90, 60], [[146, 0, 50, 80]]],
  ["apollo", "c2", 20, 0, 214, 272, "iso", [120, 130], [[0, 0, 44, 64]]],
  ["hermes-fly", "s1", 0, 130, 234, 322, "iso", [110, 120], [[0, 0, 112, 44], [96, 292, 138, 30], [220, 40, 14, 150]]],
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
  const { data } = await sharp(join(SRC, SHEETS[sheet]))
    .extract({ left: x, top: y, width: w, height: h })
    .resize(W, H, { kernel: "lanczos3" })
    .removeAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  const n = W * H;
  const lum = new Float32Array(n);
  for (let i = 0; i < n; i++) lum[i] = 0.299 * data[i * 3] + 0.587 * data[i * 3 + 1] + 0.114 * data[i * 3 + 2];
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
    // 5x5 box blur so the silhouette edge is antialiased.
    for (let j = 0; j < H; j++)
      for (let i = 0; i < W; i++) {
        let s = 0;
        let c = 0;
        for (let dy = -2; dy <= 2; dy++)
          for (let dx = -2; dx <= 2; dx++) {
            const xx = i + dx;
            const yy = j + dy;
            if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
            s += solid[yy * W + xx];
            c++;
          }
        sil[j * W + i] = s / c;
      }
    // A figure that still touches its crop box fades out there instead of ending in a
    // straight line.
    const f = Math.max(2, Math.round(Math.min(W, H) * 0.035));
    for (let j = 0; j < H; j++)
      for (let i = 0; i < W; i++) {
        const e = Math.min(1, Math.min(i, j, W - 1 - i, H - 1 - j) / f);
        const k = e * e * (3 - 2 * e);
        sil[j * W + i] *= k;
        ink[j * W + i] *= k;
      }
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

  const cutout = Buffer.alloc(n * 4);
  const mask = Buffer.alloc(n * 4);
  for (let i = 0; i < n; i++) {
    const a = ink[i];
    for (let c = 0; c < 3; c++) {
      cutout[i * 4 + c] = Math.round(PAPER[c] + (INK[c] - PAPER[c]) * a);
      mask[i * 4 + c] = INK[c];
    }
    cutout[i * 4 + 3] = Math.round(Math.max(sil[i], a) * 255);
    mask[i * 4 + 3] = Math.round(a * 255);
  }
  const raw = { raw: { width: W, height: H, channels: 4 } };
  await sharp(cutout, raw).webp({ quality: 86, alphaQuality: 90 }).toFile(join(OUT, `${name}.webp`));
  await sharp(mask, raw).webp({ quality: 88, alphaQuality: 92 }).toFile(join(OUT, `${name}-ink.webp`));
  return `${name} ${W}x${H}`;
}

mkdirSync(OUT, { recursive: true });
const only = process.env.ONLY?.split(",");
for (const a of ASSETS) if (!only || only.includes(a[0])) console.log(await cut(a));
