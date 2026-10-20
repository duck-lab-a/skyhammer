"""Two 2x2 grids of the description photo cards (all four aircraft), one per edition, for a
simple forum post. Reads Downloads\\Skyhammer_스크린샷\\설명문용 (make_photo_cards.py output),
writes Downloads\\Skyhammer_스크린샷\\디시\\1_뷰포인트판.jpg and 2_바닐라판.jpg.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SHOTS = Path.home() / 'Downloads' / 'Skyhammer_스크린샷'
CARDS, OUT = SHOTS / '설명문용', SHOTS / '디시'
CW, CH, GAP, HEAD = 800, 450, 8, 64
W, H = 2 * CW + 3 * GAP, HEAD + 2 * CH + 2 * GAP
BG = '#101416'; TEXT = '#E2E5E2'; MUTED = '#A2AAAB'; AMBER = '#DCB65E'


def font(size, weight=400, width=100):
    f = ImageFont.truetype('C:/Windows/Fonts/bahnschrift.ttf', size)
    f.set_variation_by_axes([weight, width])
    return f


def grid(prefix, title, sub, dst):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 3), fill=AMBER)
    tw = d.textlength(title, font=font(30, 700, 85))
    d.text((GAP + 6, HEAD / 2 + 2), title, font=font(30, 700, 85), fill=AMBER, anchor='lm')
    d.text((GAP + 6 + tw + 14, HEAD / 2 + 4), sub, font=font(19, 500, 90), fill=MUTED, anchor='lm')
    for i, key in enumerate(('01_apache', '02_a10', '03_ac130', '04_b2')):
        card = Image.open(CARDS / f'{prefix}{key}.jpg').convert('RGB').resize((CW, CH), Image.Resampling.LANCZOS)
        im.paste(card, (GAP + (i % 2) * (CW + GAP), HEAD + (i // 2) * (CH + GAP)))
    im.save(dst, quality=88, optimize=True, progressive=True)
    print(dst.name, im.size, dst.stat().st_size // 1024, 'KB')


def thor(dst):
    # the THOR add-on: its orbit scene and the rod camera, side by side under the same header
    src = Path(r'C:\Users\user\Zomboid\mods\SkyhammerThor\source\workshop\1920x1080')
    h = HEAD + CH + GAP
    im = Image.new('RGB', (W, h), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 3), fill=AMBER)
    title = 'THOR ADD-ON'
    tw = d.textlength(title, font=font(30, 700, 85))
    d.text((GAP + 6, HEAD / 2 + 2), title, font=font(30, 700, 85), fill=AMBER, anchor='lm')
    d.text((GAP + 6 + tw + 14, HEAD / 2 + 4), 'RODS FROM GOD  //  50-TILE KILL RADIUS  //  BOTH EDITIONS',
           font=font(19, 500, 90), fill=MUTED, anchor='lm')
    for i, name in enumerate(('02_orbit.jpg', '04_rod_cam.jpg')):
        shot = Image.open(src / name).convert('RGB').resize((CW, CH), Image.Resampling.LANCZOS)
        im.paste(shot, (GAP + i * (CW + GAP), HEAD))
    im.save(dst, quality=88, optimize=True, progressive=True)
    print(dst.name, im.size, dst.stat().st_size // 1024, 'KB')


OUT.mkdir(exist_ok=True)
thor(OUT / '3_THOR.jpg')
grid('main_', 'VIEWPOINT EDITION', '3D AIRCRAFT  //  SINGLE PLAYER', OUT / '1_뷰포인트판.jpg')
grid('vanilla_', 'VANILLA EDITION', 'GROUND SHADOWS  //  NO OTHER MODS  //  MULTIPLAYER', OUT / '2_바닐라판.jpg')
