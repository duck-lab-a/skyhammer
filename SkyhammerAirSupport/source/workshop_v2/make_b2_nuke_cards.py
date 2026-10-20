"""The B-2 description cards with the tactical nuke (2026-10-17): two stills side by side - the
carpet bombs on the left, the nuke on the right - split by a slanted amber line, in the frame and
lettering of make_photo_cards.py (corner ticks, the name in the lower left, the weapon chips).

Usage: <python with Pillow + numpy> make_b2_nuke_cards.py
Reads the stills from Downloads\\Skyhammer_스크린샷\\2026-10-17_전술핵\\src and writes
main_04_b2_nuke.jpg / vanilla_04_b2_nuke.jpg (1272 x 716) to ..\\설명문용 next to it.
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC = Path.home() / 'Downloads' / 'Skyhammer_스크린샷' / '2026-10-17_전술핵' / 'src'
OUT = SRC.parent / '설명문용'
W, H, S = 1272, 716, 3
LINE = '#4B5355'; TEXT = '#E2E5E2'; MUTED = '#C4CACB'; AMBER = '#DCB65E'
CYAN = (82, 196, 214)
FONTS = Path('C:/Windows/Fonts')


def font(size, weight=400, width=100, mono=False):
    f = ImageFont.truetype(str(FONTS / ('consola.ttf' if mono else 'bahnschrift.ttf')), round(size * S))
    if not mono: f.set_variation_by_axes([weight, width])
    return f
def P(v): return round(v * S)
def smooth(t): t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)

yy, xx = np.mgrid[0:H, 0:W] / np.array([H, W])[:, None, None]
FADE = 0.78 * smooth((0.80 - xx) / 0.55) * smooth((yy - 0.42) / 0.45)        # (the old cards' fade)
# (2026-10-17, the user: the dark on the left hid the B-2's shadow) only a light shade right behind
# the lettering in the lower left
SHADE = 0.55 * smooth((0.36 - xx) / 0.16) * smooth((yy - 0.66) / 0.16)


def place(path, zoom, ox, oy, patch=None, unfade=False):
    """the still scaled to the card's width x zoom, shifted by (ox, oy) card pixels, cut to the card;
    patch = (box, dy): the box (still pixels) covered with the same-sized piece dy pixels above it"""
    im = Image.open(path).convert('RGB')
    if unfade:
        # an old card already carries FADE: divided back out (its lettering is cut off by the shift)
        a = np.asarray(im, dtype=np.float32) / (1 - FADE[..., None])
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if patch:
        (x0, y0, x1, y1), dy = patch
        im.paste(im.crop((x0, y0 - dy, x1, y1 - dy)), (x0, y0))
    z = W / im.width * zoom
    im = im.resize((round(im.width * z), round(im.height * z)), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (W, H))
    canvas.paste(im, (-round(ox), -round(oy)))
    return canvas


def split(left, right, top_x=700, bottom_x=600):
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).polygon([(top_x, 0), (W, 0), (W, H), (bottom_x, H)], fill=255)
    out = left.copy()
    out.paste(right, (0, 0), mask)
    return out, (top_x, bottom_x)


def card(photo, seam, num, name, sub, callsign, chips, size=76):
    ph = np.asarray(photo, dtype=np.float32)
    bg = Image.fromarray((ph * (1 - SHADE[..., None])).astype(np.uint8))
    lay = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    def rect(box, fill=None, outline=None, width=1):
        d.rectangle(tuple(P(v) for v in box), fill=fill, outline=outline, width=max(1, P(width)))
    def text(s, x, y, f, fill=TEXT, anchor='ls'):
        d.text((P(x), P(y)), s, font=f, fill=fill, anchor=anchor)
        return d.textlength(s, font=f) / S
    # the seam between the two stills
    top_x, bottom_x = seam
    d.line([(P(top_x), 0), (P(bottom_x), P(H))], fill=AMBER, width=P(2.2))
    rect((0.5, 0.5, W - 1.5, H - 1.5), outline=LINE, width=1.5)
    for cx, cy, sx, sy in ((0, 0, 1, 1), (W, 0, -1, 1), (0, H, 1, -1), (W, H, -1, -1)):
        for lx, ly in ((40, 4), (4, 40)):
            xa, xb = sorted((cx, cx + sx * lx)); ya, yb = sorted((cy, cy + sy * ly))
            rect((xa, ya, xb, yb), fill=AMBER)
    x0, base = 40, H - 86
    cf = font(15, 600, 90)
    x = x0
    for c in chips:
        tw = d.textlength(c, font=cf) / S
        rect((x, base + 22, x + tw + 22, base + 52), fill=(16, 20, 22, 200), outline=LINE, width=1)
        text(c, x + 11, base + 37, cf, anchor='lm')
        x += tw + 30
    tw = text(name, x0 - 3, base, font(size, 700, 85), fill=AMBER)
    if sub: text(sub, x0 - 3 + tw + 16, base, font(30, 500, 90), fill=TEXT)
    top = base - size + 2
    text(f'{num}', x0, top, font(17, mono=True), fill=CYAN)
    text(callsign, x0 + 36, top, font(17, mono=True), fill=MUTED)
    lay = lay.resize((W, H), Image.Resampling.LANCZOS)
    bg.paste(lay, (0, 0), lay)
    return bg


OUT.mkdir(exist_ok=True)
CHIPS = ['BOMBS x20', 'TACTICAL NUKE']
# main (Viewpoint): the B-2 dropping its bombs | the mushroom cloud
left = place(SRC / 'main_b2_bombs.png', 1.15, 280, 0)
right = place(SRC / 'main_nuke_cloud.jpg', 1.4, -121, 0)
photo, seam = split(left, right)
card(photo, seam, '04', 'B-2', 'SPIRIT', 'TITAN 0-1', CHIPS).save(OUT / 'main_04_b2_nuke.jpg', quality=90, optimize=True, progressive=True)
# vanilla: the old vanilla card's bombing still | the nuke countdown with the B-2's shadow
# (the old card moved left so its B-2 shadow on the road shows; its old lettering goes off the edge)
left = place(SRC / 'vanilla-04-b2.jpg', 1.0, 330, 0, unfade=True)
# (the game's skill bar above the countdown band covered with the roof and road just above it)
right = place(SRC / 'vanilla_nuke_countdown.png', 1.0, -407, 0, patch=((1024, 940, 1304, 1004), 64))
photo, seam = split(left, right)
card(photo, seam, '04', 'B-2', 'SPIRIT', 'TITAN 0-1', CHIPS).save(OUT / 'vanilla_04_b2_nuke.jpg', quality=90, optimize=True, progressive=True)
for n in ('main_04_b2_nuke.jpg', 'vanilla_04_b2_nuke.jpg'):
    print(n, Image.open(OUT / n).size, (OUT / n).stat().st_size // 1024, 'KB')
