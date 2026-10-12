#!/usr/bin/env python3
"""
Renderer carousel @nopal.brainwork
Pemakaian:  python3 render_carousel.py spec.json [folder_output]
Hasil:      JPEG 1080x1350 (4:5) per slide + cetak JSON {"files":[...]}

Format spec.json:
{
  "id": "BW-2026-10-001",
  "kicker": "TOOLS AI",                     # label kecil di atas (opsional)
  "slides": [
    {"type": "cover", "title": "5 Setting **Meta Ads** yang Aku Matiin", "subtitle": "...", "badge": "SAVE DULU"},
    {"type": "point", "num": "01", "title": "...", "body": ["poin 1", "poin 2"], "tip": "..."},
    {"type": "statement", "text": "Kalimat besar dengan **kata emas**", "note": "teks kecil"},
    {"type": "list", "title": "...", "items": ["...", "..."]},
    {"type": "cta", "title": "Simpan & coba minggu ini", "body": "...", "action": "Komen 'MAU' ..."}
  ]
}
Teks di antara **...** dicetak warna emas.
"""
import sys, os, json, re
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
W, H = 1080, 1350
M = 84  # margin

# Palet brand (Brand Guidelines v2)
BG = (10, 8, 20)
BG2 = (22, 12, 44)
PURPLE = (123, 47, 190)
PURPLE_D = (74, 24, 128)
PURPLE_L = (155, 79, 212)
GRID = (40, 22, 74)
GOLD = (245, 193, 7)
WHITE = (255, 255, 255)
MUTE = (186, 176, 210)
HANDLE = "@nopal.brainwork"


def font(weight, size):
    name = {"black": "Poppins-Black.ttf", "xbold": "Poppins-ExtraBold.ttf", "bold": "Poppins-Bold.ttf",
            "semi": "Poppins-SemiBold.ttf", "reg": "Poppins-Regular.ttf"}[weight]
    p = os.path.join(FONT_DIR, name)
    if os.path.exists(p):
        return ImageFont.truetype(p, size)
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if weight != "reg" else "DejaVuSans.ttf", size)


def tokens(text):
    """Pecah teks jadi [(kata, emas?)] berdasar **...**"""
    out = []
    for i, part in enumerate(re.split(r"\*\*", text or "")):
        for w in part.split():
            out.append((w, i % 2 == 1))
    return out


def wrap_rich(d, text, f, maxw):
    lines, cur, curw = [], [], 0
    sp = d.textlength(" ", font=f)
    for w, g in tokens(text):
        ww = d.textlength(w, font=f)
        if cur and curw + sp + ww > maxw:
            lines.append(cur); cur, curw = [], 0
        curw = curw + (sp if cur else 0) + ww
        cur.append((w, g))
    if cur:
        lines.append(cur)
    return lines


def draw_rich(d, x, y, text, f, maxw, color=WHITE, lh=1.18, align="left"):
    lines = wrap_rich(d, text, f, maxw)
    sp = d.textlength(" ", font=f)
    size = f.size
    for ln in lines:
        lw = sum(d.textlength(w, font=f) for w, _ in ln) + sp * (len(ln) - 1)
        cx = x if align == "left" else x + (maxw - lw) / 2
        for w, g in ln:
            d.text((cx, y), w, font=f, fill=GOLD if g else color)
            cx += d.textlength(w, font=f) + sp
        y += int(size * lh)
    return y


def fit(d, text, weight, sizes, maxw, max_lines):
    for s in sizes:
        f = font(weight, s)
        if len(wrap_rich(d, text, f, maxw)) <= max_lines:
            return f
    return font(weight, sizes[-1])


def base(idx, total):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # gradien halus atas
    for yy in range(0, 700):
        a = 1 - yy / 700
        c = tuple(int(BG[i] + (BG2[i] - BG[i]) * a) for i in range(3))
        d.line([(0, yy), (W, yy)], fill=c)
    # grid
    for gx in range(0, W, 90):
        d.line([(gx, 0), (gx, H - 130)], fill=GRID, width=1)
    for gy in range(0, H - 130, 90):
        d.line([(0, gy), (W, gy)], fill=GRID, width=1)
    # footer
    d.rectangle([0, H - 130, W, H], fill=(8, 6, 16))
    d.text((M, H - 88), HANDLE, font=font("semi", 30), fill=PURPLE_L)
    d.text((W - M, H - 88), f"{idx}/{total}", font=font("semi", 30), fill=(90, 80, 120), anchor="ra")
    # dots
    dx = W / 2 - (total - 1) * 11
    for i in range(total):
        r = 9 if i + 1 == idx else 5
        cx = dx + i * 22
        d.ellipse([cx - r, H - 72 - r, cx + r, H - 72 + r], fill=GOLD if i + 1 == idx else (60, 52, 84))
    return img, d


def pill(d, x, y, text, f, fg=GOLD, bg=PURPLE_D, center=False):
    tw = d.textlength(text, font=f)
    pw, ph = tw + 48, f.size + 26
    if center:
        x = (W - pw) / 2
    d.rounded_rectangle([x, y, x + pw, y + ph], radius=ph / 2, fill=bg)
    d.text((x + 24, y + ph / 2), text, font=f, fill=fg, anchor="lm")
    return y + ph


def slide_cover(s, kicker, idx, total):
    img, d = base(idx, total)
    y = 190
    if kicker:
        y = pill(d, 0, y, kicker.upper(), font("bold", 30), center=True) + 70
    tf = fit(d, s["title"], "black", [104, 96, 88, 80, 72, 64], W - 2 * M, 5)
    y = draw_rich(d, M, y, s["title"], tf, W - 2 * M, lh=1.12, align="center") + 30
    d.rounded_rectangle([W / 2 - 110, y, W / 2 + 110, y + 12], radius=6, fill=GOLD)
    y += 60
    if s.get("subtitle"):
        y = draw_rich(d, M, y, s["subtitle"], font("reg", 40), W - 2 * M, color=MUTE, lh=1.3, align="center") + 30
    if s.get("badge"):
        pill(d, 0, max(y + 20, 1000), s["badge"].upper(), font("bold", 32), fg=BG, bg=GOLD, center=True)
    return img


def _point(d, s):
    y0 = y = 0
    if s.get("num"):
        d.text((M, y - 30), s["num"], font=font("black", 150), fill=PURPLE)
        y += 160
        d.rounded_rectangle([M, y, M + 300, y + 22], radius=11, fill=PURPLE)
        y += 60
    tf = fit(d, s["title"], "xbold", [80, 72, 64, 56], W - 2 * M, 3)
    y = draw_rich(d, M, y, s["title"], tf, W - 2 * M, lh=1.15) + 24
    d.line([(M, y), (W - M, y)], fill=(60, 52, 84), width=3)
    y += 48
    bf = font("reg", 44)
    for b in s.get("body", []):
        d.regular_polygon((M + 12, y + 31, 12), 4, fill=GOLD)
        y = draw_rich(d, M + 48, y, b, bf, W - 2 * M - 48, lh=1.32) + 26
    if s.get("tip"):
        tipf = font("reg", 38)
        lines = wrap_rich(d, s["tip"], tipf, W - 2 * M - 80)
        bh = 110 + len(lines) * int(38 * 1.35)
        top = y + 40
        d.rounded_rectangle([M, top, W - M, top + bh], radius=26, fill=PURPLE_D)
        d.rectangle([M, top + 14, M + 10, top + bh - 14], fill=GOLD)
        d.text((M + 44, top + 30), "PRO TIP", font=font("bold", 32), fill=GOLD)
        draw_rich(d, M + 44, top + 82, s["tip"], tipf, W - 2 * M - 80, color=MUTE, lh=1.35)
        y = top + bh
    return y0, y


def _list(d, s):
    y0 = y = 0
    tf = fit(d, s["title"], "xbold", [76, 68, 60], W - 2 * M, 3)
    y = draw_rich(d, M, y, s["title"], tf, W - 2 * M, lh=1.15) + 56
    nf, bf = font("black", 46), font("semi", 44)
    for i, it in enumerate(s.get("items", []), 1):
        d.rounded_rectangle([M, y, M + 84, y + 84], radius=20, fill=PURPLE)
        d.text((M + 42, y + 42), str(i), font=nf, fill=GOLD, anchor="mm")
        ny = draw_rich(d, M + 120, y + 12, it, bf, W - 2 * M - 120, lh=1.28)
        y = max(ny, y + 84) + 36
    return y0, y - 36


def slide_statement(s, kicker, idx, total):
    img, d = base(idx, total)
    tf = fit(d, s["text"], "black", [92, 84, 76, 68, 60], W - 2 * M, 6)
    lines = wrap_rich(d, s["text"], tf, W - 2 * M)
    th = len(lines) * int(tf.size * 1.15)
    y = (H - 130 - th) / 2 - 40
    d.text((M - 6, y - 150), "“", font=font("black", 220), fill=PURPLE)
    y = draw_rich(d, M, y, s["text"], tf, W - 2 * M, lh=1.15) + 40
    if s.get("note"):
        draw_rich(d, M, y, s["note"], font("reg", 38), W - 2 * M, color=MUTE, lh=1.3)
    return img


def slide_cta(s, kicker, idx, total):
    img, d = base(idx, total)
    y = 260
    tf = fit(d, s["title"], "black", [92, 84, 76, 68], W - 2 * M, 4)
    y = draw_rich(d, M, y, s["title"], tf, W - 2 * M, lh=1.12, align="center") + 50
    if s.get("body"):
        y = draw_rich(d, M, y, s["body"], font("reg", 40), W - 2 * M, color=MUTE, lh=1.32, align="center") + 60
    if s.get("action"):
        af = font("bold", 36)
        lines = wrap_rich(d, s["action"], af, W - 2 * M - 120)
        bh = 60 + len(lines) * int(36 * 1.3)
        d.rounded_rectangle([M + 20, y, W - M - 20, y + bh], radius=30, fill=GOLD)
        yy = y + 30
        for ln in lines:
            t = " ".join(w for w, _ in ln)
            d.text((W / 2, yy), t, font=af, fill=BG, anchor="ma")
            yy += int(36 * 1.3)
    return img


def centered(fn):
    """Gambar konten di layer transparan lalu taruh di tengah vertikal area konten."""
    def wrap(s, kicker, idx, total):
        img, _ = base(idx, total)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        top, bottom = fn(d, s)
        area = H - 130
        off = int((area - (bottom - top)) / 2 - top)
        off = max(min(off, area - bottom - 60), 90 - top)
        img.paste(layer, (0, off), layer)
        return img
    return wrap


RENDER = {"cover": slide_cover, "point": centered(_point), "list": centered(_list),
          "statement": slide_statement, "cta": slide_cta}


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "output", spec["id"])
    os.makedirs(out, exist_ok=True)
    slides = spec["slides"]
    if not 2 <= len(slides) <= 10:
        sys.exit("Carousel IG wajib 2-10 slide")
    files = []
    for i, s in enumerate(slides, 1):
        img = RENDER[s["type"]](s, spec.get("kicker"), i, len(slides))
        p = os.path.join(out, f"{spec['id']}_{i:02d}.jpg")
        img.save(p, "JPEG", quality=90, optimize=True)
        files.append(p)
    print(json.dumps({"files": files}))


if __name__ == "__main__":
    main()
