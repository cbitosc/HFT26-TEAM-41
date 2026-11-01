# Upscales an asset sheet 4x with Real-ESRGAN, for scripts/cut-greek.mjs:
#   uv run --no-project --with onnxruntime --with numpy --with pillow \
#     python -I scripts/upscale-sheets.py <model.onnx> <in.png> <out.png>
# Model: RealESRGAN_x4plus_anime_4B32F.onnx from
# https://huggingface.co/xiongjie/lightweight-real-ESRGAN-anime (line-art weights).
# Runs in 192 px tiles with a 16 px overlap; about a minute per sheet on a laptop CPU.
import sys, time
import numpy as np
import onnxruntime as ort
from PIL import Image

model, src, dst = sys.argv[1:4]
sess = ort.InferenceSession(model, providers=["CPUExecutionProvider"])
inp = sess.get_inputs()[0].name
img = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32) / 255.0
H, W, _ = img.shape
T, P, S = 192, 16, 4
out = np.zeros((H * S, W * S, 3), np.float32)
t0 = time.time()
for y in range(0, H, T):
    for x in range(0, W, T):
        y0, x0 = max(0, y - P), max(0, x - P)
        y1, x1 = min(H, y + T + P), min(W, x + T + P)
        tile = img[y0:y1, x0:x1].transpose(2, 0, 1)[None]
        res = sess.run(None, {inp: tile})[0][0].transpose(1, 2, 0)
        ty, tx = (y - y0) * S, (x - x0) * S
        hh, ww = min(T, H - y) * S, min(T, W - x) * S
        out[y * S : y * S + hh, x * S : x * S + ww] = res[ty : ty + hh, tx : tx + ww]
    print(f"row {y}/{H} {time.time() - t0:.0f}s", flush=True)
Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst)
print("done", dst, out.shape)
