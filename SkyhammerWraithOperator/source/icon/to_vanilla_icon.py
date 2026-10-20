# Turn a large artwork (white or transparent background) into a vanilla-style 64x64 profession icon:
# cut the background, fit to 62 px, grayscale, light grain, 1px black outline.
import sys
import numpy as np
from PIL import Image, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
LIFT = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0   # raise the darkest tones a little
GAMMA = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0  # < 1 brightens the mid tones
im = Image.open(SRC).convert("RGBA")
a = np.array(im, np.float32)
rgb, al = a[..., :3], a[..., 3]

# background: anything near-white connected to the border (flood fill), or already transparent
if al.min() > 250:
    white = (rgb.min(-1) > 232)
    h, w = white.shape
    bg = np.zeros_like(white)
    stack = [(0, x) for x in range(w)] + [(h - 1, x) for x in range(w)] + [(y, 0) for y in range(h)] + [(y, w - 1) for y in range(h)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < h and 0 <= x < w and white[y, x] and not bg[y, x]:
            bg[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    al = np.where(bg, 0, 255).astype(np.float32)

# crop to content, pad to square
ys, xs = np.where(al > 0)
y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
gray = rgb.mean(-1)
g = gray[y0:y1, x0:x1]; m = al[y0:y1, x0:x1]
side = max(g.shape)
G = np.zeros((side, side), np.float32); M = np.zeros((side, side), np.float32)
oy, ox = (side - g.shape[0]) // 2, (side - g.shape[1]) // 2
G[oy:oy + g.shape[0], ox:ox + g.shape[1]] = g * (m / 255)
M[oy:oy + g.shape[0], ox:ox + g.shape[1]] = m

INNER = 62
gs = np.array(Image.fromarray(G.astype(np.uint8)).resize((INNER, INNER), Image.LANCZOS), np.float32)
ms = np.array(Image.fromarray(M.astype(np.uint8)).resize((INNER, INNER), Image.BOX), np.float32)
gs = np.where(ms > 0, np.clip(gs * 255 / np.maximum(ms, 1), 0, 255), 0)
A = ms >= 128
# auto-levels + gamma so the lights reach near-white like the vanilla icons
lo, hi = np.percentile(gs[A], 2), np.percentile(gs[A], 98)
gs = np.clip((gs - lo) / max(hi - lo, 1), 0, 1) ** GAMMA
gs = (LIFT + gs * (1 - LIFT)) * 240 + 8

rng = np.random.default_rng(5)
gs = np.clip(gs + rng.uniform(-1, 1, gs.shape) * (4 + 8 * gs / 255), 0, 255)

out = np.zeros((64, 64, 4), np.uint8)
sub = out[1:63, 1:63]
sub[A, :3] = gs[A, None].astype(np.uint8)
sub[A, 3] = 255
full = np.zeros((64, 64), bool); full[1:63, 1:63] = A
ring = np.zeros_like(full)
ring[1:, :] |= full[:-1, :]; ring[:-1, :] |= full[1:, :]; ring[:, 1:] |= full[:, :-1]; ring[:, :-1] |= full[:, 1:]
ring &= ~full
out[ring] = (8, 8, 8, 255)

img = Image.fromarray(out, "RGBA")
img.save(OUT)
