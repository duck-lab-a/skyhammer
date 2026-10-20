"""The Wraith Team's black tactical suit (WraithGear.TacticalSuit) texture, for the vanilla boilersuit models (bob/kate share one
UV layout). Taken from the on-hold SkyhammerWraithGear mod's make_jumpsuit.py, with the shoulder
patch moved to the LEFT upper arm, where unit patches are worn.

PZ characters face -Z, so +X is the wearer's right and -X the left. The patch is projected in 3D
onto the outside of the -X upper arm (so the sleeve UVs do not stretch it), upright and readable
from the wearer's left side.
Output: 42/media/textures/Wraith/Wraith_TacticalSuit.png. Logo: ../logo/wraith_logo_512.png.
usage: python make_jumpsuit.py   (the Codex runtime python: numpy, PIL)"""
from pathlib import Path
import numpy as np
from PIL import Image
from xparse import read_x

S = Path(__file__).resolve().parent
PZ = Path(r'C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid\media')
OUT = S.parents[1] / '42' / 'media' / 'textures' / 'Wraith'
LOGO = S.parent / 'logo' / 'wraith_logo_512.png'
N = 1024
BASE = np.array([36, 38, 41]) / 255          # charcoal, never pure black

# 1. The vanilla SWAT suit's fold shading, recoloured to charcoal.
src = Image.open(PZ / 'textures/clothes/boliersuit/Boilersuit_SWAT.png').convert('RGBA').resize((N, N), Image.LANCZOS)
a = np.asarray(src).astype(float) / 255
L = a[..., :3] @ np.array([0.299, 0.587, 0.114])
mask = a[..., 3] > 0.05
ref = np.median(L[mask])
shade = np.clip((L / ref) ** 1.15, 0.45, 1.7)
rng = np.random.default_rng(42)
grain = 1 + 0.035 * rng.standard_normal((N, N))
rgb = np.clip(BASE[None, None] * (shade * grain)[..., None], 0, 1)

# 2. The shoulder patch, projected through the 3D sleeve of the left (-X) arm.
logo = np.asarray(Image.open(LOGO).convert('RGBA').resize((512, 512), Image.LANCZOS)).astype(float) / 255
m = read_x(PZ / 'models_X/Skinned/Clothes/Bob_BoilerSuit.x')[0][0]
P, UV = m['pos'], m['uv']
X0, Z0, W = 0.190, 0.048, 0.066               # out along the arm, across the arm, patch size
painted = 0
for f in m['faces']:
    for i in range(1, len(f) - 1):
        t = [f[0], f[i], f[i + 1]]; p = P[t]; uv = UV[t] * N
        n = np.cross(p[1] - p[0], p[2] - p[0]); n /= np.linalg.norm(n) + 1e-12
        if p[:, 0].mean() > -0.13 or n[1] < -0.2: continue
        x0, y0 = np.floor(uv.min(0)).astype(int); x1, y1 = np.ceil(uv.max(0)).astype(int)
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        T = np.array([[uv[1, 0] - uv[0, 0], uv[2, 0] - uv[0, 0]], [uv[1, 1] - uv[0, 1], uv[2, 1] - uv[0, 1]]])
        if abs(np.linalg.det(T)) < 1e-9: continue
        bc = np.linalg.solve(T, np.stack([gx.ravel() - uv[0, 0], gy.ravel() - uv[0, 1]]))
        b1, b2 = bc; b0 = 1 - b1 - b2
        inside = (b0 > -0.02) & (b1 > -0.02) & (b2 > -0.02)
        q = b0[:, None] * p[0] + b1[:, None] * p[1] + b2[:, None] * p[2]
        # seen from the left (-X) side, the wearer's front (-Z) is on the viewer's left
        s_ = (q[:, 2] - (Z0 - W / 2)) / W          # image left = front of the arm
        t_ = (-q[:, 0] - (X0 - W / 2)) / W         # image top = shoulder end
        ok = inside & (s_ >= 0) & (s_ < 1) & (t_ >= 0) & (t_ < 1)
        px = gx.ravel()[ok].astype(int); py = gy.ravel()[ok].astype(int)
        keep = (px >= 0) & (px < N) & (py >= 0) & (py < N)
        px, py = px[keep], py[keep]
        lv = logo[(t_[ok][keep] * 511).astype(int), (s_[ok][keep] * 511).astype(int)]
        al = lv[:, 3:4]
        rgb[py, px] = rgb[py, px] * (1 - al) + lv[:, :3] * al * np.minimum(1.0, 0.85 + 0.15 * shade[py, px, None])
        painted += len(px)

out = np.clip(np.concatenate([rgb, a[..., 3:4]], -1), 0, 1)
OUT.mkdir(parents=True, exist_ok=True)
Image.fromarray((out * 255).round().astype(np.uint8), 'RGBA').save(OUT / 'Wraith_TacticalSuit.png')
print('patch texels', painted)
