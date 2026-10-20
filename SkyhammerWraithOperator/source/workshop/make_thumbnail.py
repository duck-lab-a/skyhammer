# Simple Workshop thumbnail: icon artwork on a dark panel, name underneath, series corner brackets.
# Writes thumbnail.png (1024) and preview.png (256).
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "..", "icon", "artwork.png")
S = 1024
ORANGE, BLUE, GRAY = (247, 154, 32), (30, 160, 240), (150, 156, 164)

# background: dark blue-gray with a soft light behind the head
yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
d = np.sqrt((xx - S / 2) ** 2 + (yy - S * 0.40) ** 2) / (S * 0.62)
t = np.clip(1 - d, 0, 1) ** 1.6
bg = np.stack([14 + 34 * t, 18 + 38 * t, 24 + 44 * t], -1)
img = Image.fromarray(bg.astype(np.uint8), "RGB").convert("RGBA")

art = Image.open(ART).convert("RGBA")
art = art.crop(art.getbbox())
k = 560 / max(art.size)
art = art.resize((round(art.width * k), round(art.height * k)), Image.LANCZOS)
shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
ax, ay = (S - art.width) // 2, 120
shadow.paste((0, 0, 0, 170), (ax + 14, ay + 20), art)
img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
img.alpha_composite(art, (ax, ay))

dr = ImageDraw.Draw(img)
FONT = "C:/Windows/Fonts/bahnschrift.ttf"


def font(size, style):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_name(style)
    return f


def center(text, y, f, fill, spacing=0):
    w = sum(dr.textlength(c, font=f) for c in text) + spacing * (len(text) - 1)
    x = (S - w) / 2
    for c in text:
        dr.text((x, y), c, font=f, fill=fill)
        x += dr.textlength(c, font=f) + spacing


center("WRAITH", 700, font(150, "Bold Condensed"), ORANGE, 6)
dr.rectangle([S / 2 - 90, 868, S / 2 + 90, 874], fill=BLUE)
center("OPERATOR", 890, font(78, "Bold"), (240, 236, 228), 10)

# small tag and corner brackets, as on the other Skyhammer thumbnails
dr.rectangle([60, 66, 78, 84], fill=(232, 72, 52))
dr.text((96, 58), "SKYHAMMER // OCCUPATION", font=font(34, "SemiBold"), fill=BLUE)
L, W, M = 70, 7, 26
for cx, cy, sx, sy in ((M, M, 1, 1), (S - M, M, -1, 1), (M, S - M, 1, -1), (S - M, S - M, -1, -1)):
    dr.rectangle([min(cx, cx + sx * L), min(cy, cy + sy * W), max(cx, cx + sx * L), max(cy, cy + sy * W)], fill=ORANGE)
    dr.rectangle([min(cx, cx + sx * W), min(cy, cy + sy * L), max(cx, cx + sx * W), max(cy, cy + sy * L)], fill=ORANGE)

img = img.convert("RGB")
img.save(os.path.join(HERE, "thumbnail.png"))
img.resize((256, 256), Image.LANCZOS).save(os.path.join(HERE, "preview.png"))
