"""Description photo cards: each gameplay still in the frame of SUPPORT-STRIP.png (palette,
Bahnschrift/Consolas, amber corner ticks), the aircraft name set large in the lower left over
a soft dark fade, with the number + callsign above it and the loadout chips below.
1272 wide, like the strip.

Usage: <python with Pillow + numpy> make_photo_cards.py
Reads the graded 1920x1080 stills from Downloads\\Skyhammer_스크린샷\\{본편,바닐라} and writes
the cards to Downloads\\Skyhammer_스크린샷\\설명문용 (same file names).
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SHOTS = Path.home() / 'Downloads' / 'Skyhammer_스크린샷'
OUT = SHOTS / '설명문용'
W, H, S = 1272, 716, 3
LINE = '#4B5355'; TEXT = '#E2E5E2'; MUTED = '#C4CACB'; AMBER = '#DCB65E'
CYAN = (82, 196, 214)
FONTS = Path('C:/Windows/Fonts')

CARDS = {
    '01_apache':   ('01', 'AH-64', 'APACHE',      'HELLHOUND 1-1', ['30MM', 'ROCKETS', 'FLARES']),
    '02_a10':      ('02', 'A-10',  'THUNDERBOLT', 'VALKYRIE 2-6',  ['GAU-8 30MM', 'GUN RUN']),
    '03_ac130':    ('03', 'AC-130', 'GUNSHIP',    'BANSHEE 2-1',   ['40MM', '105MM']),
    '04_b2':       ('04', 'B-2',   'SPIRIT',      'TITAN 0-1',     ['BOMBS x20']),
    # the terminal window fills the middle of its shot, so this title stays short and smaller
    '05_terminal': ('//', 'TERMINAL', '', 'AEGIS CONTROL', ['SENSOR MAP', 'MARK', 'CALL'], 56),
}


def font(size, weight=400, width=100, mono=False):
    f = ImageFont.truetype(str(FONTS / ('consola.ttf' if mono else 'bahnschrift.ttf')), round(size * S))
    if not mono: f.set_variation_by_axes([weight, width])
    return f
def P(v): return round(v * S)
def smooth(t): t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)

# dark fade in the lower left so the name reads on sky or grass alike
yy, xx = np.mgrid[0:H, 0:W] / np.array([H, W])[:, None, None]
FADE = 0.78 * smooth((0.80 - xx) / 0.55) * smooth((yy - 0.42) / 0.45)


def card(photo, num, name, sub, callsign, chips, size=76):
    ph = np.asarray(Image.open(photo).convert('RGB').resize((W, H), Image.Resampling.LANCZOS), dtype=np.float32)
    bg = Image.fromarray((ph * (1 - FADE[..., None])).astype(np.uint8))
    # text and frame drawn 3x on a transparent layer, then scaled down onto the photo
    lay = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    def rect(box, fill=None, outline=None, width=1):
        d.rectangle(tuple(P(v) for v in box), fill=fill, outline=outline, width=max(1, P(width)))
    def text(s, x, y, f, fill=TEXT, anchor='ls'):
        d.text((P(x), P(y)), s, font=f, fill=fill, anchor=anchor)
        return d.textlength(s, font=f) / S
    rect((0.5, 0.5, W - 1.5, H - 1.5), outline=LINE, width=1.5)
    for cx, cy, sx, sy in ((0, 0, 1, 1), (W, 0, -1, 1), (0, H, 1, -1), (W, H, -1, -1)):
        for lx, ly in ((40, 4), (4, 40)):
            xa, xb = sorted((cx, cx + sx * lx)); ya, yb = sorted((cy, cy + sy * ly))
            rect((xa, ya, xb, yb), fill=AMBER)
    x0, base = 40, H - 86
    # chips under the name
    cf = font(15, 600, 90)
    x = x0
    for c in chips:
        tw = d.textlength(c, font=cf) / S
        rect((x, base + 22, x + tw + 22, base + 52), fill=(16, 20, 22, 200), outline=LINE, width=1)
        text(c, x + 11, base + 37, cf, anchor='lm')
        x += tw + 30
    # the name, large; the sub-name beside it on the same baseline
    tw = text(name, x0 - 3, base, font(size, 700, 85), fill=AMBER)
    if sub: text(sub, x0 - 3 + tw + 16, base, font(30, 500, 90), fill=TEXT)
    # number + callsign above
    top = base - size + 2
    text(f'{num}', x0, top, font(17, mono=True), fill=CYAN)
    text(callsign, x0 + 36, top, font(17, mono=True), fill=MUTED)
    lay = lay.resize((W, H), Image.Resampling.LANCZOS)
    bg.paste(lay, (0, 0), lay)
    return bg


OUT.mkdir(exist_ok=True)
for folder, prefix in (('본편', 'main_'), ('바닐라', 'vanilla_')):
    for key, spec in CARDS.items():
        src = SHOTS / folder / f'{prefix}{key}.jpg'
        dst = OUT / src.name
        card(src, *spec).save(dst, quality=88, optimize=True, progressive=True)
        print(dst.name, f'{W}x{H}', dst.stat().st_size // 1024, 'KB')
