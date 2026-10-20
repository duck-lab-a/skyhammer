# Tidies the Workshop description images (source/workshop_v2/desc_images/original, as downloaded
# from imgbb) into processed/: the Viewpoint edition's aircraft shots cropped to 16:9 without the
# debug text, side icons and minimap, framed like the Vanilla edition's shots; the terminal shots
# with the debug button covered. Run: <codex python> make_desc_images.py
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "original")
OUT = os.path.join(HERE, "processed")
os.makedirs(OUT, exist_ok=True)

W, H = 1280, 720                  # every aircraft shot
BAR = 24                          # the frame's bars, as on the Vanilla shots (34 px at 1920)
BAR_RGBA = (12, 16, 18, 215)
TEXT = (226, 229, 226)
ACCENT = (220, 182, 94)

def font(size, bold=False):
    for name in (("consolab.ttf" if bold else "consola.ttf"), "lucon.ttf", "cour.ttf"):
        try:
            return ImageFont.truetype(os.path.join(r"C:\Windows\Fonts", name), size)
        except OSError:
            pass
    return ImageFont.load_default()

def spaced(draw, xy, text, f, fill, gap=1):
    # letter-spaced line, like the Vanilla shots' bars
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + gap
    return x

def frame(img, edition, caption):
    img = img.convert("RGBA")
    W, H = img.size                   # (a shot kept at its own shape is 1280 wide, any height)
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    d.rectangle([0, 0, W, BAR], fill=BAR_RGBA)
    d.rectangle([0, H - BAR, W, H], fill=BAR_RGBA)
    f = font(13)
    ty = (BAR - 14) // 2
    spaced(d, (24, ty), "SKYHAMMER  /  " + edition, f, TEXT)
    right = "PROJECT ZOMBOID  |  BUILD 42"
    width = sum(d.textlength(c, font=f) + 1 for c in right)
    spaced(d, (W - 24 - width, ty), right, f, TEXT)
    num, name = caption
    x = spaced(d, (24, H - BAR + ty), num, f, ACCENT)
    spaced(d, (x, H - BAR + ty), "  /  " + name, f, TEXT)
    return Image.alpha_composite(img, over).convert("RGB")

def shot(src, box, edition, caption, out):
    im = Image.open(os.path.join(SRC, src)).convert("RGB").crop(box)
    im = im.resize((W, H), Image.LANCZOS)
    frame(im, edition, caption).save(os.path.join(OUT, out), quality=92)
    print(out, "from", src, box)

VP = "VIEWPOINT EDITION"
# crops: 16:9, clear of the left icon column, the debug text and the minimap (bottom right)
shot("n8qjPy2N_hel.jpg", (125, 40, 1685, 918), VP, ("02", "AH-64 APACHE"), "main_02_apache.jpg")
shot("GvrQb3yt_PZ-Skyhammer-1.jpg", (52, 0, 812, 428), VP, ("03", "AC-130 GUNSHIP"), "main_03_ac130.jpg")
shot("LXBhqpmF_2026-10-05-114417.png", (0, 100, 792, 546), VP, ("04", "B-2 SPIRIT"), "main_04_b2.jpg")

# the Vanilla edition's shots: inside their old bars, clear of the radio subtitle strip that
# hangs below the top bar, the minimap and the faint debug text (bottom right), reframed the same way
VA = "VANILLA + MULTIPLAYER"
shot("9HB3Ppj6_2.jpg", (0, 72, 1664, 1008), VA, ("02", "AH-64 APACHE"), "vanilla_02_apache.jpg")
shot("Y4TnPXnj_3.jpg", (0, 59, 815, 517), VA, ("03", "AC-130 GUNSHIP"), "vanilla_03_ac130.jpg")
shot("8nXmm3jx_4.jpg", (0, 35, 815, 493), VA, ("04", "B-2 SPIRIT"), "vanilla_04_b2.jpg")

# the killstreak points over the player's head (2026-10-06): 16:9, clear of the red counter at
# the left edge; one copy per edition
shot("shot_killstreak_points.png", (20, 60, 491, 325), VP, ("05", "KILLSTREAK POINTS"), "main_05_killstreak.jpg")
shot("shot_killstreak_points.png", (20, 60, 491, 325), VA, ("05", "KILLSTREAK POINTS"), "vanilla_05_killstreak.jpg")

# the Wraith Team add-on (2026-10-06): too wide and too square for 16:9 without losing the team
# or the helicopter, so kept at their own shape, 1280 wide, in the same frame
def shotKeep(src, edition, caption, out):
    im = Image.open(os.path.join(SRC, src)).convert("RGB")
    im = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
    frame(im, edition, caption).save(os.path.join(OUT, out), quality=92)
    print(out, "from", src, im.size)

WR = "WRAITH TEAM ADD-ON"
shotKeep("shot_wraith_team.webp", WR, ("01", "WRAITH SIX ON THE GROUND"), "wraith_01_team.jpg")
shotKeep("shot_wraith_ferryman.png", WR, ("02", "FERRYMAN THREE-TWO"), "wraith_02_ferryman.jpg")

# the terminal shots: the debug button (cooldown reset) covered with the header's own colour
def cover(src, box, out):
    im = Image.open(os.path.join(SRC, src)).convert("RGB")
    x0, y0, x1, y1 = box
    fill = im.getpixel((x0 - 6, (y0 + y1) // 2))
    ImageDraw.Draw(im).rectangle(box, fill=fill)
    im.save(os.path.join(OUT, out))
    print(out, "from", src, "covered", box, "with", fill)

cover("rRz9gJq6_2.png", (336, 2, 476, 27), "terminal_main.png")
cover("XZ3XzSB3_2026-10-05-112106.png", (338, 6, 478, 31), "terminal_wraith.png")
