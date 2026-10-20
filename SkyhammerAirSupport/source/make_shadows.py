# Ground-shadow textures for the vanilla (isometric) view, made from the same meshes the 3D
# aircraft use: the airframe seen from straight above, solid and softened at the edge, with the
# spinning parts (rotors, propellers) as faint discs.
# Output: 42/media/ui/SH_Shadow_<name>.png, square, nose to the top, starboard to the right;
# the texture spans 2*E metres (= tiles) where E is printed and copied into Skyhammer_Shadow.lua.
# usage: python make_shadows.py
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
MESHES = os.path.join(HERE, "java", "skyhammer", "aircraft")
OUT = os.path.join(HERE, "..", "42", "media", "ui")
SIZE = 256

# part id -> faint disc instead of the blades (main rotor, tail rotor, propellers)
SPINNERS = {"uh60": {1: 0.30, 2: 0.22}, "apache": {1: 0.30, 2: 0.22}, "ac130": {1: 0.22, 2: 0.22, 3: 0.22, 4: 0.22}}


def load(name):
    b = open(os.path.join(MESHES, name + ".mesh"), "rb").read()
    assert int.from_bytes(b[:4], "big") == 0x53484131
    n = int.from_bytes(b[4:8], "big")
    a = np.frombuffer(b, ">f4", n * 10, 8).reshape(-1, 10)
    return a[:, 0:3].astype(float), a[:, 9].astype(int)


for name in (sys.argv[1:] or ("ac130", "b2", "apache", "uh60", "a10")):
    P, part = load(name)
    E = float(np.abs(P[:, [0, 2]]).max()) * 1.06
    if name == "a10": E = math.ceil(E * 10) / 10  # exactly 9.3, matching the Lua contract
    px = lambda x, z: ((x / E + 1) / 2 * SIZE, (1 - (z / E + 1) / 2) * SIZE)   # +X right, +Z (nose) up
    body = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(body)
    spin = SPINNERS.get(name, {})
    for t in range(0, len(P), 3):
        if part[t] in spin:
            continue
        d.polygon([px(P[t + k][0], P[t + k][2]) for k in range(3)], fill=255)
    body = body.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(2.2))
    discs = Image.new("L", (SIZE, SIZE), 0)
    dd = ImageDraw.Draw(discs)
    for pid, alpha in spin.items():
        sel = P[part == pid]
        if not len(sel):
            continue
        if name == "uh60" and pid == 2:
            cx, cz = .57, -10.35
            rx, rz = 1.68 * np.sin(np.deg2rad(20)), 1.68
            (x0,y0),(x1,y1)=px(cx-rx,cz+rz),px(cx+rx,cz-rz)
            dd.ellipse([x0,y0,x1,y1],fill=int(255*alpha))
            continue
        cx, cz = sel[:, 0].mean(), sel[:, 2].mean()
        r = float(np.hypot(sel[:, 0] - cx, sel[:, 2] - cz).max())
        (x0, y0), (x1, y1) = px(cx - r, cz + r), px(cx + r, cz - r)
        dd.ellipse([x0, y0, x1, y1], fill=int(255 * alpha))
    discs = discs.filter(ImageFilter.GaussianBlur(3))
    a = np.maximum(np.asarray(body, float), np.asarray(discs, float))
    rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
    rgba[..., 3] = a.astype(np.uint8)
    out = os.path.join(OUT, "SH_Shadow_" + {"ac130": "AC130", "b2": "B2", "apache": "Apache", "uh60": "UH60", "a10": "A10"}[name] + ".png")
    Image.fromarray(rgba, "RGBA").save(out)
    print(f"{os.path.basename(out)}: half-extent E = {E:.2f} tiles")
