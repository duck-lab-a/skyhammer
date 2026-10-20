# The Workshop description's fallout (radiation) card, in the support strip's look
# (SUPPORT-STRIP.png). Read left to right, top to bottom: the zone, the dose it gives, getting
# it out (Prussian Blue), then the gear that keeps it out. EN and KO, 1272 px wide like the strip.
# Vanilla gear icons come from the game's UI2.pack (extracted to workshop_v2/icons), the "found in"
# symbols from its map symbols (media/ui/LootableMaps); the capsule and the warning icon are the mod's own.
# Run: <codex python> -I source/workshop_v2/make_fallout_card.py
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "..", "..", "42", "media")
ICONS = os.path.join(HERE, "icons")
SYMBOLS = r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid\media\ui\LootableMaps"
F = r"C:\Windows\Fonts"

BG = (16, 20, 22)
CARD = (23, 28, 30)
INNER = (19, 24, 26)
LINE = (52, 62, 66)
GOLD = (236, 195, 99)
CYAN = (84, 196, 206)
WHITE = (226, 230, 232)
GREY = (150, 160, 164)

W, H = 1272, 716

TEXT = {
    "en": {
        "title": "FALLOUT", "sub": "You nuked it. Now don't go for a stroll.",
        "zone": "HOT ZONE",
        "zonetxt": "Ground zero stays radioactive for days. Walk in and this sign pops up while the radio tells you to get out.",
        "dose": "YOUR DOSE",
        "dosetxt": "No number on screen: your sick moodle shows it. It piles up while you stay and halves each day once out. At the worst stage you keep losing health, even outside.",
        "bands": ["QUEASY", "WEAK, SLOW", "DYING"],
        "blue": "PRUSSIAN BLUE",
        "bluetxt": "Flushes the dose 3x faster for 8 h. Not a cure: get out first, then take it.",
        "found": "FOUND IN", "places": ["Pharmacy", "Hospital", "Army"],
        "prot": "DRESS FOR IT", "protsub": "how much radiation each piece keeps out",
        "gear": ["HAZMAT SUIT", "GAS MASK", "NBC MASK", "IMPROVISED MASK", "RESPIRATOR"],
        "foot": "Masks only work with a filter in. Stack them for up to 98%. A roof halves what gets through.",
    },
    "ko": {
        "title": "낙진", "sub": "핵은 떨궜고, 이제 산책은 금지",
        "zone": "출입 금지",
        "zonetxt": "폭심 주변은 한동안 방사능이 남습니다. 들어가면 이 마크가 뜨고, 무전으로 당장 나오라는 경고가 옵니다.",
        "dose": "피폭량",
        "dosetxt": "화면에 숫자는 없고 구역질 무들로 나타납니다. 안에 있으면 쌓이고, 나오면 하루에 절반씩 빠집니다. 마지막 단계에선 나와서도 체력이 깎입니다.",
        "bands": ["메스꺼움", "힘 빠짐·느려짐", "죽어 감"],
        "blue": "프러시안 블루",
        "bluetxt": "8시간 동안 피폭을 3배 빨리 빼 줍니다. 치료약은 아니니 먼저 나오고 드세요.",
        "found": "구하는 곳", "places": ["약국", "병원", "군부대"],
        "prot": "옷부터 갖춰 입고", "protsub": "방사능을 막아 주는 비율",
        "gear": ["방호복", "방독면", "NBC 마스크", "임시 방독면", "방진 마스크"],
        "foot": "마스크는 필터가 있어야 일합니다. 겹쳐 입으면 최대 98%, 지붕 아래면 새어 드는 것도 절반.",
    },
}
GEAR = [("Item_Hazmatsuit", 95), ("Item_GasMask", 70), ("Item_NBCMask", 70),
        ("Item_GasMask_Crafted_Filtre", 40), ("Item_Respirator_wFilter", 40)]


def font(lang, size, bold=False):
    if lang == "ko":
        return ImageFont.truetype(os.path.join(F, "malgunbd.ttf" if bold else "malgun.ttf"), size)
    f = ImageFont.truetype(os.path.join(F, "bahnschrift.ttf"), size)
    try:
        f.set_variation_by_name("SemiBold" if bold else "Regular")
    except Exception:
        pass
    return f


def wrap(d, text, f, width):
    lines, cur = [], ""
    for w in text.split(" "):
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def para(d, x, y, text, f, width, fill, step):
    for line in wrap(d, text, f, width):
        d.text((x, y), line, font=f, fill=fill)
        y += step
    return y


def card(d, x0, y0, x1, y1, num, label, lang):
    d.rectangle([x0, y0, x1, y1], fill=CARD, outline=LINE, width=1)
    d.rectangle([x0, y0, x0 + 46, y0 + 3], fill=GOLD)
    d.text((x0 + 14, y0 + 13), num, font=font("en", 20, bold=True), fill=CYAN)
    d.text((x0 + 40, y0 + 10), label, font=font(lang, 22, bold=True), fill=GOLD)


def icon(path, size):
    im = Image.open(path).convert("RGBA")
    return im.resize((size, size), Image.NEAREST if im.size[0] <= 32 else Image.LANCZOS)


def iconbox(img, d, x, y, path, size=88):
    d.rectangle([x, y, x + size + 14, y + size + 14], fill=INNER, outline=LINE)
    ic = icon(path, size)
    img.paste(ic, (x + 7, y + 7), ic)


def centered(d, cx, y, text, f, fill):
    d.text((cx - d.textlength(text, font=f) / 2, y), text, font=f, fill=fill)


def build(lang):
    t = TEXT[lang]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    ft = font(lang, 50, bold=True)
    d.text((24, 12), t["title"], font=ft, fill=GOLD)
    d.text((24 + d.textlength(t["title"], font=ft) + 18, 36), t["sub"], font=font(lang, 22), fill=WHITE)
    d.line([24, 80, W - 24, 80], fill=GOLD, width=2)
    body = font(lang, 20)

    # top row: 1 the zone, 2 the dose, 3 getting it out
    y0, y1 = 96, 356
    gap = 14
    xs = [(24, 400), (400 + gap, 860), (860 + gap, W - 24)]

    x0, x1 = xs[0]
    card(d, x0, y0, x1, y1, "1", t["zone"], lang)
    iconbox(img, d, x0 + 14, y0 + 50, os.path.join(MOD, "ui", "SH_Rad_Icon.png"))
    para(d, x0 + 130, y0 + 52, t["zonetxt"], body, x1 - x0 - 144, WHITE, 28)

    x0, x1 = xs[1]
    card(d, x0, y0, x1, y1, "2", t["dose"], lang)
    bx0, bx1, by = x0 + 24, x1 - 24, y0 + 84
    cols = [(60, 70, 74), (180, 170, 70), (220, 130, 50), (210, 60, 50)]
    stops = [0, 10, 40, 80, 100]
    for k in range(4):
        a = bx0 + (bx1 - bx0) * stops[k] / 100
        b = bx0 + (bx1 - bx0) * stops[k + 1] / 100
        d.rectangle([a, by, b, by + 26], fill=cols[k])
    for v in stops[1:-1]:
        x = bx0 + (bx1 - bx0) * v / 100
        d.line([x, by - 6, x, by + 32], fill=WHITE, width=1)
    for k, lab in enumerate(t["bands"]):
        a = bx0 + (bx1 - bx0) * stops[k + 1] / 100
        b = bx0 + (bx1 - bx0) * stops[k + 2] / 100
        centered(d, (a + b) / 2, by - 32, lab, font(lang, 17, bold=True), cols[k + 1])
    para(d, bx0, by + 46, t["dosetxt"], body, bx1 - bx0, WHITE, 28)

    x0, x1 = xs[2]
    card(d, x0, y0, x1, y1, "3", t["blue"], lang)
    iconbox(img, d, x0 + 14, y0 + 50, os.path.join(MOD, "textures", "Item_SH_PrussianBlue.png"))
    para(d, x0 + 130, y0 + 52, t["bluetxt"], body, x1 - x0 - 144, WHITE, 28)
    # where it turns up: the game's own map symbols
    fy = y0 + 172
    d.line([x0 + 14, fy - 8, x1 - 14, fy - 8], fill=LINE)
    d.text((x0 + 14, fy), t["found"], font=font(lang, 17, bold=True), fill=GREY)
    fx = x0 + 14
    fy += 30
    for sym, place in zip(("pill", "medcross", "star"), t["places"]):
        ic = Image.open(os.path.join(SYMBOLS, "map_" + sym + ".png")).convert("RGBA").resize((34, 34), Image.LANCZOS)
        tint = Image.new("RGBA", ic.size, CYAN + (255,))
        tint.putalpha(ic.getchannel("A"))
        img.paste(tint, (int(fx), fy), tint)
        d.text((fx + 40, fy + 5), place, font=font(lang, 19), fill=WHITE)
        fx += 40 + d.textlength(place, font=font(lang, 19)) + 16

    # bottom: 4 the gear
    y0, y1 = 372, H - 18
    card(d, 24, y0, W - 24, y1, "4", t["prot"], lang)
    fl = font(lang, 22, bold=True)
    d.text((64 + d.textlength(t["prot"], font=fl) + 14, y0 + 14), t["protsub"], font=font(lang, 19), fill=GREY)
    n = len(GEAR)
    cw = (W - 48 - 28 - 12 * (n - 1)) // n
    for i, (name, pct) in enumerate(GEAR):
        cx0 = 38 + i * (cw + 12)
        cx1 = cx0 + cw
        top = y0 + 52
        d.rectangle([cx0, top, cx1, top + 116], fill=INNER, outline=LINE)
        for gx in range(cx0, cx1, 20):
            d.line([gx, top, gx, top + 116], fill=(26, 33, 36))
        for gy in range(top, top + 116, 20):
            d.line([cx0, gy, cx1, gy], fill=(26, 33, 36))
        ic = icon(os.path.join(ICONS, name + ".png"), 96)
        img.paste(ic, ((cx0 + cx1) // 2 - 48, top + 10), ic)
        centered(d, (cx0 + cx1) // 2, top + 126, t["gear"][i], font(lang, 21, bold=True), WHITE)
        fp, fs = font("en", 50, bold=True), font("en", 22, bold=True)
        s = str(pct)
        wv = d.textlength(s, font=fp) + 4 + d.textlength("%", font=fs)
        x = (cx0 + cx1) / 2 - wv / 2
        d.text((x, top + 152), s, font=fp, fill=GOLD)
        d.text((x + d.textlength(s, font=fp) + 4, top + 178), "%", font=fs, fill=GOLD)
    d.text((38, y1 - 36), t["foot"], font=font(lang, 20), fill=GREY)

    out = os.path.join(HERE, f"fallout-card-{lang}.png")
    img.save(out)
    print("wrote", out, img.size)


SMALL = {
    "en": {"gear": ["HAZMAT", "GAS MASK", "NBC MASK", "IMPROVISED", "RESPIRATOR"],
           "zone": "Sign + radio warning", "blue": "Prussian Blue", "bluetxt": "clears it 3x faster",
           "foot": "Masks need a filter. Stacks up to 98%."},
    "ko": {"gear": ["방호복", "방독면", "NBC 마스크", "임시 방독면", "방진 마스크"],
           "zone": "경고 마크 + 무전", "blue": "프러시안 블루", "bluetxt": "피폭 3배 빨리 빠짐",
           "foot": "마스크는 필터 필수. 겹쳐 입으면 최대 98%."},
}


# The small card (420 px, like the description's other side features): the gear and the two
# things to know, drawn at twice the size and scaled down.
def build_small(lang):
    t, s2 = TEXT[lang], SMALL[lang]
    w, h = 840, 516
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    ft = font(lang, 52, bold=True)
    d.text((22, 10), t["title"], font=ft, fill=GOLD)
    d.line([22, 82, w - 22, 82], fill=GOLD, width=3)
    n = len(GEAR)
    cw = (w - 44 - 10 * (n - 1)) // n
    top = 98
    for i, (name, pct) in enumerate(GEAR):
        x0 = 22 + i * (cw + 10)
        x1 = x0 + cw
        d.rectangle([x0, top, x1, top + 230], fill=CARD, outline=LINE)
        ic = icon(os.path.join(ICONS, name + ".png"), 96)
        img.paste(ic, ((x0 + x1) // 2 - 48, top + 10), ic)
        centered(d, (x0 + x1) // 2, top + 112, s2["gear"][i], font(lang, 24 if lang == "en" else 25, bold=True), WHITE)
        fp, fs = font("en", 56, bold=True), font("en", 26, bold=True)
        v = str(pct)
        wv = d.textlength(v, font=fp) + 4 + d.textlength("%", font=fs)
        x = (x0 + x1) / 2 - wv / 2
        d.text((x, top + 146), v, font=fp, fill=GOLD)
        d.text((x + d.textlength(v, font=fp) + 4, top + 176), "%", font=fs, fill=GOLD)
    y = top + 246
    half = (w - 44 - 12) // 2
    for k, (path, head, body) in enumerate((
            (os.path.join(MOD, "ui", "SH_Rad_Icon.png"), s2["zone"], None),
            (os.path.join(MOD, "textures", "Item_SH_PrussianBlue.png"), s2["blue"], s2["bluetxt"]))):
        x0 = 22 + k * (half + 12)
        d.rectangle([x0, y, x0 + half, y + 104], fill=CARD, outline=LINE)
        ic = icon(path, 80)
        img.paste(ic, (x0 + 12, y + 12), ic)
        if body:
            d.text((x0 + 104, y + 18), head, font=font(lang, 28, bold=True), fill=GOLD)
            d.text((x0 + 104, y + 58), body, font=font(lang, 26), fill=WHITE)
        else:
            d.text((x0 + 104, y + 36), head, font=font(lang, 28, bold=True), fill=WHITE)
    d.text((22, h - 46), s2["foot"], font=font(lang, 26), fill=GREY)
    img = img.resize((420, 258), Image.LANCZOS)
    out = os.path.join(HERE, f"fallout-small-{lang}.png")
    img.save(out)
    print("wrote", out, img.size)


if __name__ == "__main__":
    for lang in ("en", "ko"):
        build(lang)
        build_small(lang)
