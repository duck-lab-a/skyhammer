"""Draws media/ui/SH_Icon_Thor.png (64x64) in the style of ODIN's tab icon: a dark square,
corner brackets in Asgard's cyan, and a white silhouette: the weapon
satellite with its two panels, and a rod falling from it with a short glow trail.
Drawn at 4x and scaled down for smooth edges. Run with the codex python (PIL)."""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "42", "media", "ui", "SH_Icon_Thor.png")
S = 4
W = 64 * S
BG, BG2 = (17, 19, 22, 255), (24, 27, 31, 255)
ACCENT = (59, 124, 143, 255)   # Asgard's cyan, as on ODIN's icon
WHITE = (226, 226, 221, 255)

im = Image.new("RGBA", (W, W), BG)
d = ImageDraw.Draw(im)
d.rectangle([2 * S, 2 * S, W - 2 * S - 1, W - 2 * S - 1], fill=BG2)
# corner brackets
L, T = 9 * S, 2 * S
def box(x0, y0, x1, y1):
    d.rectangle([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], fill=ACCENT)


for cx, cy, sx, sy in ((2, 2, 1, 1), (61, 2, -1, 1), (2, 61, 1, -1), (61, 61, -1, -1)):
    x, y = cx * S, cy * S
    box(x, y, x + sx * L, y + sy * T)      # along the edge
    box(x, y, x + sx * T, y + sy * L)      # down the side


def r(x0, y0, x1, y1, c=WHITE):
    d.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=c)


# the satellite: body, panels with their struts, a dish on top
r(27, 13, 37, 25)
r(9, 16, 24, 22)
r(40, 16, 55, 22)
r(24, 18, 27, 20)
r(37, 18, 40, 20)
for x in (14, 19, 45, 50):
    r(x, 16, x, 22, BG2)
d.ellipse([29 * S, 7 * S, 35 * S, 12 * S], fill=WHITE)
r(31.5, 11, 32.5, 13)
# the rod falling, a little apart from the body, with its trail fading above it
for i, a in enumerate((70, 120, 170, 220)):
    r(31, 28 + i * 3, 33, 30 + i * 3, (226, 226, 221, a))
r(30.5, 41, 33.5, 53)
d.polygon([(30.5 * S, 53 * S), (33.5 * S, 53 * S), (32 * S, 57 * S)], fill=WHITE)

im = im.resize((64, 64), Image.LANCZOS)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
im.save(OUT)
print("wrote", os.path.normpath(OUT))
