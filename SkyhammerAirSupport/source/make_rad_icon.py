# Draws media/ui/SH_Rad_Icon.png (128x128): the radiation trefoil, black on a yellow disc with a
# dark rim, supersampled 4x for smooth edges. Run with the Codex python: python -I make_rad_icon.py
import math, os
from PIL import Image, ImageDraw

S, K = 128, 4
N = S * K
img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
c = N / 2
d.ellipse([2 * K, 2 * K, N - 2 * K, N - 2 * K], fill=(20, 20, 20, 235))
d.ellipse([7 * K, 7 * K, N - 7 * K, N - 7 * K], fill=(245, 200, 30, 255))
black = (15, 15, 15, 255)
r_in, r_out = 15 * K, 50 * K
for k in range(3):
    a0 = math.radians(-90 + k * 120 - 30)
    a1 = math.radians(-90 + k * 120 + 30)
    pts = [(c + math.cos(a0) * r_in, c + math.sin(a0) * r_in)]
    for i in range(31):
        a = a0 + (a1 - a0) * i / 30
        pts.append((c + math.cos(a) * r_out, c + math.sin(a) * r_out))
    for i in range(31):
        a = a1 - (a1 - a0) * i / 30
        pts.append((c + math.cos(a) * r_in, c + math.sin(a) * r_in))
    d.polygon(pts, fill=black)
d.ellipse([c - 11 * K, c - 11 * K, c + 11 * K, c + 11 * K], fill=(245, 200, 30, 255))
d.ellipse([c - 8 * K, c - 8 * K, c + 8 * K, c + 8 * K], fill=black)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "42", "media", "ui", "SH_Rad_Icon.png")
img.resize((S, S), Image.LANCZOS).save(out)
print(os.path.abspath(out))
