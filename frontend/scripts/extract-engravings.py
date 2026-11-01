"""Cut engravings out of the asset sheets as white-on-alpha masks (ink density -> alpha)."""
import sys, os, numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
I = sys.argv[1]; OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
sheets = {k: np.asarray(Image.open(f"{I}/{k}.png").convert("RGB")).astype(float) for k in (1, 3)}
paper = {k: np.median(v.reshape(-1, 3), axis=0) for k, v in sheets.items()}
CROPS = {
  # name: (sheet, x0, y0, x1, y1, keep_all)
  "atlas": (3, 778, 118, 992, 478, False),
  "hermes-bust": (3, 212, 8, 458, 282, False),
  "apollo-bust": (3, 8, 8, 228, 278, False),
  "muse-bust": (3, 612, 8, 765, 190, False),
  "athena": (3, 438, 8, 702, 505, False),
  "sun": (3, 962, 8, 1142, 222, False),
  "moon": (3, 1028, 218, 1138, 362, False),
  "pegasus-flight": (3, 1142, 8, 1532, 352, False),
  "starchart": (3, 1292, 266, 1532, 502, False),
  "arch": (3, 856, 466, 1104, 755, False),
  "ruins-sea": (3, 572, 476, 864, 735, False),
  "ship": (3, 466, 742, 824, 935, False),
  "lion": (3, 1312, 496, 1512, 608, False),
  "cliff-stairs": (3, 1106, 362, 1302, 684, False),
  "poseidon-young": (3, 1098, 682, 1362, 955, False),
  "bull-head": (3, 1356, 636, 1532, 828, False),
  "cherub": (3, 882, 748, 1102, 918, False),
  "nike-flight": (3, 8, 262, 342, 520, False),
  "column-ionic": (3, 486, 576, 584, 784, False),
  "column-corinth": (3, 346, 576, 482, 712, False),
  "temple-hill": (3, 196, 340, 594, 556, False),
  "busts-zeus": (1, 712, 6, 862, 178, False),
  "athena-helm-bust": (1, 582, 6, 708, 192, False),
  "pythia-bust": (1, 326, 6, 452, 178, False),
  "hermes-flight": (1, 12, 142, 232, 452, False),
  "poseidon": (1, 356, 186, 712, 432, False),
  "pegasus": (1, 588, 166, 892, 408, False),
  "minotaur": (1, 886, 316, 1128, 458, False),
  "hydra": (1, 1002, 176, 1142, 308, False),
  "serpent": (1, 1114, 282, 1294, 452, False),
  "griffin": (1, 1292, 212, 1532, 480, False),
  "nike": (1, 1116, 6, 1402, 292, False),
  "parthenon": (1, 6, 424, 304, 600, False),
  "panorama": (1, 893, 456, 1532, 692, False),
  "garden-arch": (1, 606, 412, 896, 600, False),
  "scroll": (1, 752, 588, 878, 758, False),
  "lyre": (1, 336, 602, 438, 748, False),
  "helmet": (1, 438, 600, 548, 748, False),
  "medusa": (1, 545, 600, 684, 750, False),
  "torch": (1, 704, 584, 768, 762, False),
  "compass": (1, 866, 630, 1004, 770, False),
  "starchart-1": (1, 1040, 630, 1234, 820, False),
  "sky-dome": (1, 1254, 696, 1510, 784, False),
  "wreath": (1, 230, 754, 350, 884, False),
  "wreath-2": (1, 380, 754, 494, 884, False),
  "column-1": (1, 6, 786, 114, 1018, False),
  "column-2": (1, 140, 810, 240, 1018, False),
  "cherub-head": (1, 446, 876, 624, 944, False),
  "key-strip": (1, 966, 926, 1204, 952, False),
  "wave-strip": (1, 966, 986, 1204, 1018, False),
  "palm": (1, 1162, 796, 1272, 1014, False),
  "cypress": (1, 1272, 812, 1344, 1014, False),
  "olive-tree": (1, 1362, 876, 1484, 1014, False),
  "star": (1, 742, 760, 812, 830, False),
}
def alpha_of(a, p):
    d = np.sqrt(((a - p) ** 2).sum(-1))
    return np.clip((d - 22) / 230, 0, 1) ** 0.9
ERASE = {  # sheet-coordinate rectangles to blank out before the crop (neighbouring art)
  "apollo-bust": [(8, 8, 62, 64)],
  "pegasus-flight": [(1462, 8, 1532, 136), (1380, 8, 1532, 54), (1450, 40, 1475, 96), (1424, 40, 1452, 64), (1468, 226, 1532, 304)],
  "minotaur": [(886, 316, 962, 352)],
  "panorama": [("c", 1138, 724, 100), (893, 612, 1012, 692)],
  "temple-hill": [(552, 340, 594, 436)],
}
ONLY = set(sys.argv[3:])
for name, (k, x0, y0, x1, y1, keep_all) in CROPS.items():
    if ONLY and name not in ONLY: continue
    a = sheets[k][y0:y1, x0:x1]
    al = alpha_of(a, paper[k])
    for r in ERASE.get(name, []):
        if r[0] == "c":
            yy, xx = np.mgrid[y0:y1, x0:x1]
            al[(xx - r[1]) ** 2 + (yy - r[2]) ** 2 < r[3] ** 2] = 0
            continue
        ex0, ey0, ex1, ey1 = r
        al[max(ey0 - y0, 0):max(ey1 - y0, 0), max(ex0 - x0, 0):max(ex1 - x0, 0)] = 0
    if not keep_all:
        ink = ndimage.binary_dilation(al > 0.12, iterations=4)
        lab, n = ndimage.label(ink)
        if n > 1:
            sizes = ndimage.sum(ink, lab, range(1, n + 1))
            big = sizes.argmax() + 1
            keep = np.zeros(n + 1, bool); keep[big] = True
            border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
            for i, s in enumerate(sizes, 1):
                if i not in border and s > 0.002 * sizes.max(): keep[i] = True
            al = al * keep[lab]
    # trim to content
    ys, xs = np.where(al > 0.05)
    al = al[max(ys.min() - 4, 0): ys.max() + 5, max(xs.min() - 4, 0): xs.max() + 5]
    A = Image.fromarray((al * 255).astype(np.uint8), "L")
    A = A.resize((A.width * 2, A.height * 2), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.2, 60, 2))
    img = Image.new("LA", A.size, 255); img.putalpha(A)
    img.save(f"{OUT}/{name}.webp", lossless=True, quality=100, method=6)
    print(name, A.size, os.path.getsize(f"{OUT}/{name}.webp") // 1024, "KB")
