#!/usr/bin/env python3
"""
Ilustrasi realistis untuk konten portal Brainwork.id (tanpa foto berhak cipta, tanpa logo merek).
Setiap "jenis" menggambar satu panggung 1200x700 (HP / jendela browser / kartu melayang dengan tampilan produk
yang terbaca), lalu dipotong ke ukuran yang diminta (kartu single, sampul/slide carousel, scene video).

Pemakaian dari renderer:
    import portal_art
    im = portal_art.hero("hp-feed", 960, 520, teks=[...], focus=(0.5, 0.5), zoom=1.0)   # -> RGBA (sudut membulat, label ILUSTRASI)

Jenis tersedia (kolom "gambar.jenis" di portal/<ID>.json): lihat KINDS. Jenis tak dikenal -> "grafik".
Teks label dalam gambar (gambar.teks, 0-5 string) harus berasal dari fakta yang sama dengan konten; tidak boleh menambah fakta baru.
"""
import os, math, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import render_carousel as rc

SW, SH, S = 1200, 700, 2   # panggung (satuan desain), supersampling
INK = (24, 26, 33)
GREY = (233, 235, 240)
GREY2 = (200, 204, 213)
MUTE = (118, 124, 138)
WHITE = (255, 255, 255)
BLUE = (24, 119, 242)
GREEN = (37, 211, 102)
GREEN_D = (7, 94, 84)
RED = (236, 72, 85)
GOLD = rc.GOLD
PURPLE = rc.PURPLE
PURPLE_L = rc.PURPLE_L
PURPLE_D = rc.PURPLE_D


def F(wt, px):
    return rc.font(wt, max(8, int(round(px * S))))


# ------------------------------------------------------------------ kanvas
class Cv:
    """Kanvas RGBA berukuran (w, h) satuan desain, digambar S kali lebih besar."""

    def __init__(self, w, h, bg=(0, 0, 0, 0)):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (int(w * S), int(h * S)), bg)
        self.d = ImageDraw.Draw(self.im, "RGBA")

    def _b(self, box):
        return [v * S for v in box]

    def rr(self, box, r=0, fill=None, line=None, w=1):
        self.d.rounded_rectangle(self._b(box), radius=r * S, fill=fill, outline=line,
                                 width=max(1, int(w * S)) if line else 0)

    def ell(self, cx, cy, rx, ry=None, fill=None, line=None, w=1):
        ry = rx if ry is None else ry
        self.d.ellipse(self._b((cx - rx, cy - ry, cx + rx, cy + ry)), fill=fill, outline=line,
                       width=max(1, int(w * S)) if line else 0)

    def poly(self, pts, fill):
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)

    def line(self, pts, fill, w=2):
        self.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=max(1, int(w * S)), joint="curve")

    def text(self, x, y, s, wt, px, fill=INK, anchor="lm"):
        self.d.text((x * S, y * S), s, font=F(wt, px), fill=fill, anchor=anchor)

    def tw(self, s, wt, px):
        return self.d.textlength(s, font=F(wt, px)) / S

    def paste(self, sub, x, y, r=0, alpha=1.0):
        im = sub.im if isinstance(sub, Cv) else sub
        mask = im.split()[3] if im.mode == "RGBA" else Image.new("L", im.size, 255)
        if r:
            m2 = Image.new("L", im.size, 0)
            ImageDraw.Draw(m2).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=r * S, fill=255)
            mask = ImageChops_multiply(mask, m2)
        if alpha < 1:
            mask = mask.point(lambda v: int(v * alpha))
        self.im.paste(im.convert("RGB") if im.mode != "RGBA" else im, (int(x * S), int(y * S)), mask)
        self.d = ImageDraw.Draw(self.im, "RGBA")

    def shadow(self, box, r=20, blur=18, dy=14, alpha=110, col=(0, 0, 0), spread=0):
        x0, y0, x1, y1 = box
        pad = blur * 3 + abs(dy) + spread
        rx0, ry0 = max(0, int((x0 - pad) * S)), max(0, int((y0 - pad) * S))
        rx1, ry1 = min(self.im.width, int((x1 + pad) * S)), min(self.im.height, int((y1 + pad) * S))
        lay = Image.new("L", (rx1 - rx0, ry1 - ry0), 0)
        ImageDraw.Draw(lay).rounded_rectangle(
            [(x0 - spread) * S - rx0, (y0 - spread + dy) * S - ry0, (x1 + spread) * S - rx0, (y1 + spread + dy) * S - ry0],
            radius=(r + spread) * S, fill=alpha)
        lay = lay.filter(ImageFilter.GaussianBlur(blur * S))
        self.im.paste(Image.new("RGBA", lay.size, col + (255,)), (rx0, ry0), lay)
        self.d = ImageDraw.Draw(self.im, "RGBA")

    def glow(self, cx, cy, r, col, a=0.5):
        x0, y0 = max(0, int((cx - r) * S)), max(0, int((cy - r) * S))
        x1, y1 = min(self.im.width, int((cx + r) * S)), min(self.im.height, int((cy + r) * S))
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1]
        dist = np.sqrt((xx - cx * S) ** 2 + (yy - cy * S) ** 2) / (r * S)
        m = np.clip(1 - dist, 0, 1) ** 2 * a * 255
        lay = Image.fromarray(m.astype("uint8"), "L")
        self.im.paste(Image.new("RGBA", lay.size, col + (255,)), (x0, y0), lay)
        self.d = ImageDraw.Draw(self.im, "RGBA")


def ImageChops_multiply(a, b):
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


def vgrad(w, h, c1, c2):
    t = np.linspace(0, 1, int(h * S))[:, None, None]
    a = np.array(c1, float)[None, None, :]
    b = np.array(c2, float)[None, None, :]
    arr = (a + (b - a) * t) * np.ones((1, int(w * S), 1))
    return Image.fromarray(arr.astype("uint8"), "RGB").convert("RGBA")


def mixc(c1, c2, p):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * p) for i in range(3))


# ------------------------------------------------------------------ ikon
def heart(cv, cx, cy, r, fill):
    cv.ell(cx - r * 0.5, cy - r * 0.25, r * 0.55, fill=fill)
    cv.ell(cx + r * 0.5, cy - r * 0.25, r * 0.55, fill=fill)
    cv.poly([(cx - r * 1.02, cy - r * 0.05), (cx + r * 1.02, cy - r * 0.05), (cx, cy + r * 1.05)], fill)


def bubble(cv, cx, cy, r, col):
    cv.rr((cx - r, cy - r * 0.8, cx + r, cy + r * 0.55), r * 0.45, line=col, w=1.8)
    cv.poly([(cx - r * 0.35, cy + r * 0.5), (cx - r * 0.6, cy + r * 0.95), (cx - r * 0.0, cy + r * 0.5)], col)


def share(cv, cx, cy, r, col):
    cv.line([(cx - r, cy + r * 0.2), (cx + r * 0.15, cy - r * 0.55), (cx + r * 0.15, cy + r * 0.85)], col, 1.8)
    cv.poly([(cx + r * 0.1, cy - r * 0.9), (cx + r, cy - r * 0.05), (cx + r * 0.1, cy + r * 0.8)], col)


def sparkle(cv, cx, cy, r, fill):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr_ = r if i % 2 == 0 else r * 0.28
        pts.append((cx + math.cos(a) * rr_, cy + math.sin(a) * rr_))
    cv.poly(pts, fill)


def check(cv, cx, cy, r, fill, mark=WHITE):
    cv.ell(cx, cy, r, fill=fill)
    cv.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.32)], mark, max(1.6, r * 0.2))


def cross(cv, cx, cy, r, fill, mark=WHITE):
    cv.ell(cx, cy, r, fill=fill)
    cv.line([(cx - r * 0.4, cy - r * 0.4), (cx + r * 0.4, cy + r * 0.4)], mark, max(1.6, r * 0.2))
    cv.line([(cx - r * 0.4, cy + r * 0.4), (cx + r * 0.4, cy - r * 0.4)], mark, max(1.6, r * 0.2))


def arrow(cv, cx, cy, r, up, fill):
    if up:
        cv.poly([(cx, cy - r), (cx + r, cy + r * 0.7), (cx - r, cy + r * 0.7)], fill)
    else:
        cv.poly([(cx, cy + r), (cx + r, cy - r * 0.7), (cx - r, cy - r * 0.7)], fill)


def lock(cv, cx, cy, r, col):
    cv.d.arc([(cx - r * 0.6) * S, (cy - r * 1.15) * S, (cx + r * 0.6) * S, (cy + r * 0.3) * S], 180, 360, fill=col,
             width=max(1, int(r * 0.28 * S)))
    cv.rr((cx - r * 0.85, cy - r * 0.15, cx + r * 0.85, cy + r * 0.95), r * 0.2, fill=col)


def linkicon(cv, cx, cy, r, col):
    cv.rr((cx - r * 1.15, cy - r * 0.5, cx + r * 0.2, cy + r * 0.5), r * 0.5, line=col, w=max(1.8, r * 0.26))
    cv.rr((cx - r * 0.2, cy - r * 0.5, cx + r * 1.15, cy + r * 0.5), r * 0.5, line=col, w=max(1.8, r * 0.26))


def mic(cv, cx, cy, r, col):
    cv.rr((cx - r * 0.35, cy - r * 0.85, cx + r * 0.35, cy + r * 0.2), r * 0.35, fill=col)
    cv.d.arc([(cx - r * 0.65) * S, (cy - r * 0.45) * S, (cx + r * 0.65) * S, (cy + r * 0.6) * S], 0, 180, fill=col,
             width=max(1, int(r * 0.16 * S)))
    cv.line([(cx, cy + r * 0.6), (cx, cy + r * 0.95)], col, max(1.5, r * 0.16))


def cam(cv, cx, cy, r, col):
    cv.rr((cx - r * 0.95, cy - r * 0.55, cx + r * 0.3, cy + r * 0.55), r * 0.18, fill=col)
    cv.poly([(cx + r * 0.38, cy - r * 0.15), (cx + r * 0.98, cy - r * 0.5), (cx + r * 0.98, cy + r * 0.5), (cx + r * 0.38, cy + r * 0.15)], col)


def endcall(cv, cx, cy, r):
    cv.ell(cx, cy, r, fill=RED)
    cv.rr((cx - r * 0.5, cy - r * 0.14, cx + r * 0.5, cy + r * 0.14), r * 0.14, fill=WHITE)


def search(cv, cx, cy, r, col):
    cv.ell(cx - r * 0.12, cy - r * 0.12, r * 0.55, line=col, w=max(1.6, r * 0.2))
    cv.line([(cx + r * 0.28, cy + r * 0.28), (cx + r * 0.78, cy + r * 0.78)], col, max(1.6, r * 0.22))


def bars(cv, x, y, widths, h=7, gap=11, col=GREY2, r=3.5):
    for i, w in enumerate(widths):
        cv.rr((x, y + i * (h + gap), x + w, y + i * (h + gap) + h), r, fill=col)


def clip(cv, text, wt, px, maxw):
    """Potong teks dengan '…' bila lebih lebar dari maxw (satuan desain)."""
    if cv.tw(text, wt, px) <= maxw:
        return text
    while text and cv.tw(text + "…", wt, px) > maxw:
        text = text[:-1]
    return text.rstrip() + "…"


def pill(cv, x, y, text, wt="semi", px=14, fill=GREY, fg=INK, padx=12, h=None, lead=0):
    h = h or px * 1.9
    w = cv.tw(text, wt, px) + padx * 2 + lead
    cv.rr((x, y, x + w, y + h), h / 2, fill=fill)
    cv.text(x + padx + lead, y + h / 2, text, wt, px, fg)
    return w


def pending(cv, cx, cy, r):
    cv.ell(cx, cy, r, fill=GOLD)
    for i in (-1, 0, 1):
        cv.ell(cx + i * r * 0.5, cy, r * 0.14, fill=(60, 40, 0))


# ------------------------------------------------------------------ latar, HP, jendela
_ACC = [None]
_MODE = [False]
SCALE = 0.86   # isi gambar diperkecil di dalam panggung supaya perangkat tampil utuh saat dipotong lebar


def backdrop(accent):
    if _MODE[0]:           # mode isi: kanvas transparan, latar digambar belakangan oleh _stage
        _ACC[0] = accent
        return Cv(SW, SH)
    cv = Cv(SW, SH)
    cv.im.paste(vgrad(SW, SH, (22, 12, 46), (10, 8, 22)), (0, 0))
    cv.d = ImageDraw.Draw(cv.im, "RGBA")
    cv.glow(260, 140, 520, PURPLE, 0.55)
    cv.glow(980, 560, 560, accent, 0.40)
    cv.glow(620, 360, 380, mixc(PURPLE, accent, 0.5), 0.25)
    lay = Image.new("RGBA", cv.im.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    for gx in range(0, SW, 60):
        ld.line([(gx * S, 0), (gx * S, SH * S)], fill=(255, 255, 255, 10), width=S)
    for gy in range(0, SH, 60):
        ld.line([(0, gy * S), (SW * S, gy * S)], fill=(255, 255, 255, 10), width=S)
    cv.im.alpha_composite(lay)
    cv.d = ImageDraw.Draw(cv.im, "RGBA")
    return cv


def phone(cv, x, y, w, h, draw_screen, bg=WHITE, r=46, dark=False):
    cv.shadow((x, y, x + w, y + h), r, blur=26, dy=26, alpha=170)
    cv.rr((x, y, x + w, y + h), r, fill=(40, 41, 50), line=(104, 106, 122), w=2)
    cv.rr((x + 3, y + 3, x + w - 3, y + h - 3), r - 3, fill=(14, 14, 18))
    bz = 11
    sw, sh = w - 2 * bz, h - 2 * bz
    sub = Cv(sw, sh, bg + (255,))
    draw_screen(sub, sw, sh)
    sub.rr((sw / 2 - 40, 9, sw / 2 + 40, 31), 11, fill=(10, 10, 12))          # dynamic island
    sub.rr((sw / 2 - 52, sh - 14, sw / 2 + 52, sh - 9), 3, fill=(255, 255, 255, 235) if dark else (30, 30, 36, 220))  # indikator home
    cv.paste(sub, x + bz, y + bz, r=r - bz)
    # tombol samping
    cv.rr((x - 3, y + 120, x, y + 168), 1.5, fill=(88, 90, 104))
    cv.rr((x - 3, y + 186, x, y + 250), 1.5, fill=(88, 90, 104))
    cv.rr((x + w, y + 170, x + w + 3, y + 250), 1.5, fill=(88, 90, 104))
    # kilap kaca
    gl = Cv(sw, sh)
    gl.poly([(sw * 0.55, 0), (sw, 0), (sw, sh * 0.18), (sw * 0.2, sh * 0.62), (0, sh * 0.62), (0, sh * 0.5)], (255, 255, 255, 14))
    cv.paste(gl, x + bz, y + bz, r=r - bz)


def window(cv, x, y, w, h, title, draw_body, accent=BLUE):
    cv.shadow((x, y, x + w, y + h), 18, blur=30, dy=26, alpha=170)
    cv.rr((x, y, x + w, y + h), 18, fill=(250, 250, 252), line=(120, 124, 146), w=1.5)
    sub = Cv(w, h, (250, 250, 252, 255))
    sub.rr((0, 0, w, 46), 0, fill=(238, 240, 246))
    sub.line([(0, 46), (w, 46)], (214, 218, 228), 1)
    for i, c in enumerate(((237, 106, 94), (245, 190, 79), (98, 197, 84))):
        sub.ell(24 + i * 22, 23, 6.5, fill=c)
    tw_ = sub.tw(title, "semi", 14) + 40
    sub.rr((110, 9, 110 + tw_, 46), 10, fill=(250, 250, 252))
    sub.text(130, 28, title, "semi", 14, INK)
    draw_body(sub, w, h)
    cv.paste(sub, x, y, r=18)


def tag_pill(cv, x, y, text, fill, fg, px=13):
    return pill(cv, x, y, text, "bold", px, fill, fg, 10, px * 1.8)


# ------------------------------------------------------------------ jenis: hp-feed
def kind_hp_feed(t):
    cv = backdrop(BLUE)
    px0, py0, pw, ph = 245, 36, 300, 628

    def screen(s, sw, sh):
        s.text(18, 20, "9:41", "bold", 12, INK)
        s.rr((sw - 54, 14, sw - 20, 26), 4, line=INK, w=1.4)
        s.rr((sw - 51, 17, sw - 33, 23), 2, fill=INK)
        s.text(18, 62, "Beranda", "black", 22, BLUE)
        for i in range(2):
            s.ell(sw - 54 + i * 40, 62, 16, fill=GREY)
        search(s, sw - 54, 62, 8, INK)
        bubble(s, sw - 14, 62, 7, INK)
        for i in range(5):
            cx = 30 + i * (sw - 60) / 4
            s.rr((cx - 10, 108, cx + 10, 124), 4, fill=BLUE if i == 0 else GREY2)
        s.line([(10, 138), (sw - 10, 138)], (226, 229, 236), 1)
        s.rr((10, 138, 70, 141), 1.5, fill=BLUE)
        # kartu post 1
        s.rr((0, 146, sw, 150), 0, fill=(236, 238, 243))
        s.ell(32, 184, 17, fill=(255, 170, 140))
        s.ell(32, 180, 7, fill=(255, 226, 205))
        s.rr((22, 188, 42, 200), 6, fill=(255, 226, 205))
        s.rr((58, 172, 140, 181), 4, fill=(60, 64, 78))
        s.rr((58, 188, 112, 195), 3.5, fill=GREY2)
        for i in range(3):
            s.ell(sw - 54 + i * 12, 184, 2.4, fill=MUTE)
        s.rr((16, 212, sw - 40, 219), 3.5, fill=GREY2)
        s.rr((16, 228, sw - 90, 235), 3.5, fill=GREY2)
        # gambar post
        g = vgrad(sw - 20, 178, (255, 214, 168), (244, 143, 177)).convert("RGBA")
        gd = Cv(sw - 20, 178)
        gd.im.paste(g, (0, 0))
        gd.d = ImageDraw.Draw(gd.im, "RGBA")
        gd.ell(190, 52, 30, fill=(255, 244, 200))
        gd.poly([(0, 178), (0, 118), (60, 84), (120, 120), (170, 92), (250, 140), (260, 178)], (126, 87, 194))
        gd.poly([(70, 178), (130, 118), (200, 112), (270, 150), (270, 178)], (86, 54, 150))
        s.paste(gd, 10, 246, r=10)
        # reaksi
        heart(s, 36, 446, 9, RED)
        bubble(s, 92, 446, 10, MUTE)
        share(s, 148, 446, 10, MUTE)
        s.rr((0, 468, sw, 472), 0, fill=(236, 238, 243))
        # kartu post 2
        s.ell(32, 504, 17, fill=(142, 202, 230))
        s.rr((58, 492, 150, 501), 4, fill=(60, 64, 78))
        s.rr((58, 508, 118, 515), 3.5, fill=GREY2)
        s.rr((16, 532, sw - 60, 539), 3.5, fill=GREY2)
        s.rr((10, 552, sw - 10, 620), 10, fill=mixc((190, 222, 240), WHITE, 0.2))

    phone(cv, px0, py0, pw, ph, screen)
    # lingkaran sorot pada menu tiga titik
    dx, dy = px0 + 11 + 300 - 22 - 50 + 33 + 12, py0 + 11 + 184
    dx = px0 + 11 + (pw - 22) - 54 + 12
    cv.glow(dx, dy, 56, GOLD, 0.45)
    cv.ell(dx, dy, 22, line=GOLD, w=3.4)

    # panel kontrol melayang
    qx, qy, qw, qh = 590, 120, 380, 440
    cv.shadow((qx, qy, qx + qw, qy + qh), 24, blur=30, dy=24, alpha=170)
    cv.rr((qx, qy, qx + qw, qy + qh), 24, fill=WHITE, line=(210, 214, 224), w=1.5)
    sparkle(cv, qx + 34, qy + 40, 14, GOLD)
    cv.text(qx + 60, qy + 40, t[0], "bold", 22, INK)
    cv.text(qx + 28, qy + 82, "Jelaskan dengan bahasa sehari-hari", "reg", 14.5, MUTE)
    cv.rr((qx + 24, qy + 108, qx + qw - 24, qy + 184), 16, fill=(246, 247, 250), line=(214, 218, 228), w=1.5)
    cv.text(qx + 44, qy + 146, clip(cv, t[1], "reg", 15, qw - 44 - 24 - 70), "reg", 15, MUTE)
    cv.ell(qx + qw - 58, qy + 146, 20, fill=BLUE)
    cv.poly([(qx + qw - 66, qy + 154), (qx + qw - 66, qy + 138), (qx + qw - 48, qy + 146)], WHITE)
    cv.text(qx + 28, qy + 222, "Atur topik", "bold", 15, MUTE)
    w1 = pill(cv, qx + 24, qy + 242, t[2], "bold", 16, (225, 246, 233), (16, 120, 66), 14, 38, lead=20)
    arrow(cv, qx + 24 + 24, qy + 242 + 19, 6.5, True, (16, 150, 80))
    w2 = pill(cv, qx + 24 + w1 + 14, qy + 242, t[3], "bold", 16, (252, 228, 231), (176, 30, 50), 14, 38, lead=20)
    arrow(cv, qx + 24 + w1 + 14 + 24, qy + 242 + 19, 6.5, False, (214, 50, 70))
    cv.line([(qx + 24, qy + 312), (qx + qw - 24, qy + 312)], (226, 229, 236), 1.5)
    check(cv, qx + 40, qy + 360, 15, GREEN)
    cv.text(qx + 66, qy + 352, t[4], "bold", 17, INK)
    cv.text(qx + 66, qy + 378, "Feed dan Reels langsung menyesuaikan", "reg", 14, MUTE)
    # penghubung dari titik tiga ke panel
    pts = []
    for i in range(21):
        u = i / 20
        x = (1 - u) ** 3 * (dx + 28) + 3 * (1 - u) ** 2 * u * (dx + 70) + 3 * (1 - u) * u ** 2 * (qx - 50) + u ** 3 * qx
        y = (1 - u) ** 3 * dy + 3 * (1 - u) ** 2 * u * dy + 3 * (1 - u) * u ** 2 * (qy + 40) + u ** 3 * (qy + 40)
        pts.append((x, y))
    cv.line(pts, GOLD, 3.4)
    cv.ell(qx, qy + 40, 6, fill=GOLD)
    return cv


# ------------------------------------------------------------------ jenis: dashboard-iklan
def kind_dashboard_iklan(t):
    cv = backdrop(PURPLE_L)
    x, y, w, h = 170, 52, 860, 596

    def body(s, bw, bh):
        s.rr((0, 47, 64, bh), 0, fill=(244, 245, 249))
        s.line([(64, 47), (64, bh)], (222, 225, 233), 1)
        for i in range(5):
            cy = 90 + i * 58
            if i == 1:
                s.rr((10, cy - 22, 54, cy + 22), 12, fill=(228, 237, 255))
            s.rr((24, cy - 9, 40, cy + 9), 4, fill=BLUE if i == 1 else GREY2)
        s.text(92, 80, "Kampanye  ›  Ad set  ›", "reg", 13.5, MUTE)
        s.text(92 + s.tw("Kampanye  ›  Ad set  ›", "reg", 13.5) + 8, 80, "Placements", "bold", 13.5, INK)
        s.text(92, 120, t[0], "black", 26, INK)
        # kartu 1: otomatis
        c1 = (92, 150, 540, 276)
        s.shadow(c1, 14, blur=10, dy=6, alpha=40)
        s.rr(c1, 14, fill=WHITE, line=BLUE, w=2.2)
        s.ell(124, 188, 11, fill=WHITE, line=BLUE, w=2.6)
        s.ell(124, 188, 5.5, fill=BLUE)
        s.text(150, 188, t[1], "bold", 18, INK)
        tag_pill(s, 150, 207, "Otomatis", (225, 236, 255), (20, 90, 200))
        for i, o in enumerate(("Sales", "Leads", "Engagement", "App")):
            pass
        px = 150
        for o in ("Sales", "Leads", "Engagement", "App"):
            px += pill(s, px, 242, o, "semi", 12.5, GREY, MUTE, 10, 24) + 8
        # kartu 2: manual dicoret
        c2 = (92, 296, 540, 420)
        s.rr(c2, 14, fill=(247, 248, 251), line=(214, 218, 228), w=1.6)
        s.ell(124, 334, 11, fill=WHITE, line=GREY2, w=2.2)
        s.text(150, 334, t[2], "bold", 18, MUTE)
        wtxt = s.tw(t[2], "bold", 18)
        s.line([(148, 335), (152 + wtxt, 335)], (170, 174, 188), 2)
        tag_pill(s, 150, 353, "Dihapus bertahap", (252, 228, 231), (176, 30, 50))
        lock(s, 512, 334, 9, (160, 165, 180))
        px = 150
        for o in ("Feed", "Stories", "Reels"):
            px += pill(s, px, 386, "✕ " + o if False else o, "semi", 12.5, (236, 238, 243), (160, 165, 180), 10, 24) + 8
        # catatan: masih bisa manual
        s.rr((92, 440, 540, 512), 14, fill=(236, 248, 241))
        check(s, 122, 476, 13, (30, 160, 90))
        s.text(148, 462, t[3], "bold", 15.5, (16, 100, 60))
        s.text(148, 488, "Placement manual masih tersedia", "reg", 13.5, (46, 110, 78))
        # panel pengganti
        qx0, qy0, qx1, qy1 = 566, 150, 828, 548
        s.shadow((qx0, qy0, qx1, qy1), 14, blur=10, dy=6, alpha=40)
        s.rr((qx0, qy0, qx1, qy1), 14, fill=WHITE, line=(222, 225, 233), w=1.5)
        sparkle(s, qx0 + 28, qy0 + 32, 11, PURPLE)
        s.text(qx0 + 48, qy0 + 32, t[4], "bold", 17, INK)
        rows = (("Kustomisasi media", "per placement"), ("Placement", "value rules"), ("Pengecualian placement", "di level akun"))
        for i, r_ in enumerate(rows):
            ry = qy0 + 66 + i * 108
            s.rr((qx0 + 14, ry, qx1 - 14, ry + 98), 12, fill=(246, 247, 251))
            s.rr((qx0 + 26, ry + 16, qx0 + 60, ry + 50), 9, fill=(236, 228, 250))
            s.ell(qx0 + 43, ry + 33, 6, fill=PURPLE)
            s.text(qx0 + 72, ry + 26, r_[0], "semi", 13.5, INK)
            s.text(qx0 + 72, ry + 46, r_[1], "semi", 13.5, INK)
            s.rr((qx0 + 26, ry + 70, qx0 + 26 + 90 + i * 16, ry + 77), 3.5, fill=GREY2)
            s.rr((qx1 - 66, ry + 62, qx1 - 26, ry + 80), 9, fill=PURPLE)
            s.ell(qx1 - 35, ry + 71, 6.5, fill=WHITE)

    window(cv, x, y, w, h, "Ads Manager", body)
    return cv


# ------------------------------------------------------------------ jenis: panggilan
def _siluet(w, h, c1, c2, skin, shirt, hair=None, shift=0.0):
    s = Cv(w, h)
    s.im.paste(vgrad(w, h, c1, c2), (0, 0))
    s.d = ImageDraw.Draw(s.im, "RGBA")
    cx = w / 2 + shift * w
    s.ell(cx, h * 1.05, w * 0.42, h * 0.46, fill=shirt)
    s.rr((cx - w * 0.07, h * 0.46, cx + w * 0.07, h * 0.66), 6, fill=mixc(skin, (0, 0, 0), 0.08))
    s.ell(cx, h * 0.38, w * 0.17, h * 0.21, fill=skin)
    if hair:
        s.d.pieslice([(cx - w * 0.19) * S, (h * 0.15) * S, (cx + w * 0.19) * S, (h * 0.52) * S], 180, 360, fill=hair)
    return s


def kind_panggilan(t):
    cv = backdrop(GREEN)
    px0, py0, pw, ph = 215, 36, 300, 628

    def screen(s, sw, sh):
        s.rr((0, 0, sw, sh), 0, fill=(15, 22, 26))
        s.text(18, 20, "9:41", "bold", 12, WHITE)
        s.text(sw / 2, 60, "Panggilan grup", "bold", 16, WHITE, "mm")
        s.text(sw / 2, 80, "00:12", "reg", 12.5, (160, 190, 180), "mm")
        tiles = [((255, 183, 120), (240, 110, 120), (255, 214, 184), (60, 90, 190), (60, 40, 30)),
                 ((120, 200, 230), (60, 120, 200), (240, 196, 160), (236, 120, 70), (40, 30, 30)),
                 ((200, 170, 240), (130, 90, 210), (210, 160, 130), (40, 150, 120), (30, 20, 30)),
                 ((255, 226, 140), (240, 170, 90), (255, 210, 175), (120, 80, 170), (90, 50, 30))]
        gw, gh, gx0, gy0 = (sw - 36) / 2, 190, 12, 104
        for i, tl in enumerate(tiles):
            gx, gy = gx0 + (i % 2) * (gw + 12), gy0 + (i // 2) * (gh + 12)
            if i == 3:  # tamu: tanpa akun, bingkai putus-putus hijau
                tile = _siluet(gw, gh, (52, 62, 72), (30, 38, 46), (180, 170, 160), (80, 90, 100), shift=0.04)
                s.paste(tile, gx, gy, r=14)
                s.rr((gx, gy, gx + gw, gy + gh), 14, line=GREEN, w=2.2)
                pill(s, gx + 8, gy + gh - 32, "Tamu", "bold", 12, (22, 28, 32), WHITE, 9, 22)
            else:
                tile = _siluet(gw, gh, tl[0], tl[1], tl[2], tl[3], tl[4], shift=(i - 1.5) * 0.02)
                s.paste(tile, gx, gy, r=14)
        by = sh - 96
        s.rr((22, by, sw - 22, by + 56), 28, fill=(32, 44, 50))
        for i in range(4):
            cx = 22 + (sw - 44) * (i + 0.5) / 4
            if i == 2:
                endcall(s, cx, by + 28, 21)
                continue
            s.ell(cx, by + 28, 21, fill=(54, 70, 78))
            if i == 0:
                mic(s, cx, by + 28, 10, WHITE)
            elif i == 1:
                cam(s, cx, by + 28, 10, WHITE)
            else:
                for k in (-1, 0, 1):
                    s.ell(cx + k * 8, by + 28, 2.4, fill=WHITE)

    phone(cv, px0, py0, pw, ph, screen, bg=(15, 22, 26), dark=True)

    # kartu tautan
    qx, qy, qw, qh = 560, 70, 420, 220
    cv.shadow((qx, qy, qx + qw, qy + qh), 22, blur=26, dy=22, alpha=170)
    cv.rr((qx, qy, qx + qw, qy + qh), 22, fill=WHITE, line=(210, 214, 224), w=1.5)
    cv.ell(qx + 46, qy + 52, 24, fill=GREEN)
    linkicon(cv, qx + 46, qy + 52, 10, WHITE)
    cv.text(qx + 86, qy + 44, t[0], "bold", 21, INK)
    cv.text(qx + 86, qy + 72, t[1], "reg", 14.5, MUTE)
    cv.rr((qx + 26, qy + 108, qx + qw - 26, qy + 154), 14, fill=(244, 246, 249), line=(214, 218, 228), w=1.5)
    cv.rr((qx + 46, qy + 126, qx + 46 + 190, qy + 136), 5, fill=GREY2)
    pill(cv, qx + qw - 26 - 116, qy + 113, "Salin", "bold", 14.5, GREEN_D, WHITE, 18, 36)
    cv.rr((qx + 26, qy + 168, qx + qw - 26, qy + 204), 12, fill=(236, 248, 241))
    pending(cv, qx + 50, qy + 186, 11)
    cv.text(qx + 72, qy + 186, t[2], "semi", 14.5, (16, 100, 60))

    # jendela browser tamu
    wx, wy, ww, wh = 600, 330, 410, 310

    def gbody(s, bw, bh):
        s.text(bw / 2, 96, "Gabung panggilan", "black", 21, INK, "mm")
        s.text(bw / 2, 124, "Tidak perlu akun", "reg", 14, MUTE, "mm")
        s.rr((34, 150, bw - 34, 198), 12, fill=(246, 247, 250), line=(206, 210, 220), w=1.6)
        s.text(54, 174, t[3], "reg", 15.5, INK)
        s.rr((34, 214, bw - 34, 262), 24, fill=GREEN_D)
        s.text(bw / 2, 238, "Minta bergabung", "bold", 16, WHITE, "mm")
        s.text(bw / 2, 288, t[4], "reg", 13, MUTE, "mm")

    window(cv, wx, wy, ww, wh, "Gabung panggilan", gbody)
    return cv


# ------------------------------------------------------------------ jenis generik
def kind_chat_ai(t):
    cv = backdrop(PURPLE_L)
    x, y, w, h = 190, 56, 820, 588

    def body(s, bw, bh):
        s.rr((0, 47, 210, bh), 0, fill=(244, 245, 249))
        s.line([(210, 47), (210, bh)], (222, 225, 233), 1)
        s.text(24, 84, "Percakapan", "bold", 14.5, MUTE)
        for i in range(5):
            s.rr((14, 108 + i * 52, 196, 148 + i * 52), 10, fill=(232, 224, 250) if i == 0 else None)
            s.rr((30, 124 + i * 52, 30 + 100 - i * 8, 132 + i * 52), 4, fill=(160, 140, 210) if i == 0 else GREY2)
        s.text(240, 90, t[0], "black", 22, INK)
        s.rr((240, 124, bw - 40, 190), 16, fill=(240, 242, 247))
        s.text(262, 157, t[1], "reg", 16.5, INK)
        sparkle(s, 262, 232, 13, PURPLE)
        s.rr((240, 214, bw - 120, 380), 16, fill=(246, 241, 255), line=(222, 208, 248), w=1.5)
        s.text(290, 232, t[2], "bold", 16.5, PURPLE_D)
        bars(s, 262, 262, (bw - 400, bw - 360, bw - 440, bw - 420), 8, 14, (206, 192, 238), 4)
        s.rr((240, bh - 96, bw - 40, bh - 36), 30, fill=WHITE, line=(206, 210, 220), w=1.6)
        s.text(268, bh - 66, t[3], "reg", 15.5, MUTE)
        s.ell(bw - 76, bh - 66, 20, fill=PURPLE)
        arrow(s, bw - 76, bh - 66, 8, True, WHITE)

    window(cv, x, y, w, h, "Asisten AI", body)
    return cv


def kind_toko_online(t):
    cv = backdrop(GOLD)
    px0, py0, pw, ph = 250, 36, 300, 628

    def screen(s, sw, sh):
        s.text(18, 20, "9:41", "bold", 12, INK)
        s.rr((16, 48, sw - 70, 84), 18, fill=(242, 244, 248))
        search(s, 36, 66, 7, MUTE)
        s.text(52, 66, t[0], "reg", 13.5, MUTE)
        s.ell(sw - 36, 66, 18, fill=(255, 238, 200))
        s.rr((sw - 44, 62, sw - 28, 74), 3, fill=(210, 140, 20))
        s.ell(sw - 24, 54, 8, fill=RED)
        s.rr((12, 100, sw - 12, 190), 16, fill=(255, 226, 150))
        s.text(28, 130, t[1], "black", 22, (120, 60, 0))
        pill(s, 28, 150, t[2], "bold", 12.5, (120, 60, 0), WHITE, 12, 26)
        cols = [((255, 214, 168), (244, 143, 177)), ((196, 238, 233), (118, 196, 214)), ((206, 220, 255), (150, 160, 240)),
                ((255, 233, 178), (255, 175, 120))]
        for i, (c1, c2) in enumerate(cols):
            gx, gy = 12 + (i % 2) * ((sw - 36) / 2 + 12), 206 + (i // 2) * 188
            gw = (sw - 36) / 2
            im = Cv(gw, 118)
            im.im.paste(vgrad(gw, 118, c1, c2), (0, 0))
            im.d = ImageDraw.Draw(im.im, "RGBA")
            im.rr((gw * 0.3, 26, gw * 0.7, 98), 10, fill=mixc(c2, (40, 30, 90), 0.4))
            im.ell(gw * 0.5, 34, 22, fill=mixc(c1, WHITE, 0.5))
            s.paste(im, gx, gy, r=12)
            s.rr((gx + 4, gy + 128, gx + gw - 30, gy + 135), 3.5, fill=(60, 64, 78))
            s.rr((gx + 4, gy + 146, gx + 60, gy + 153), 3.5, fill=GREY2)
            s.text(gx + 4, gy + 172, "Rp •••", "bold", 12.5, RED, "lm")

    phone(cv, px0, py0, pw, ph, screen)
    qx, qy, qw, qh = 600, 150, 360, 330
    cv.shadow((qx, qy, qx + qw, qy + qh), 22, blur=26, dy=22, alpha=170)
    cv.rr((qx, qy, qx + qw, qy + qh), 22, fill=WHITE, line=(210, 214, 224), w=1.5)
    cv.text(qx + 28, qy + 44, t[3], "bold", 21, INK)
    for i in range(3):
        ry = qy + 78 + i * 70
        cv.rr((qx + 24, ry, qx + qw - 24, ry + 58), 12, fill=(246, 247, 250))
        check(cv, qx + 50, ry + 29, 12, (30, 160, 90) if i < 2 else GOLD)
        cv.rr((qx + 76, ry + 16, qx + 76 + 150 - i * 20, ry + 24), 4, fill=(60, 64, 78))
        cv.rr((qx + 76, ry + 34, qx + 76 + 100, ry + 41), 3.5, fill=GREY2)
    return cv


def kind_dokumen(t):
    cv = backdrop(PURPLE_L)
    for i, (dx, dyy, rot) in enumerate(((-26, 14, 0), (-10, 6, 0), (6, 0, 0))):
        x, y, w, h = 330 + dx, 44 + dyy, 540, 620
        cv.shadow((x, y, x + w, y + h), 14, blur=26, dy=22, alpha=150)
        cv.rr((x, y, x + w, y + h), 14, fill=(252, 252, 254) if i == 2 else (236, 238, 245), line=(206, 210, 222), w=1.4)
    x, y, w, h = 336, 44, 540, 620
    cv.text(x + 44, y + 62, t[0], "black", 24, INK)
    cv.rr((x + 44, y + 86, x + 120, y + 92), 3, fill=GOLD)
    cv.text(x + 44, y + 128, t[1], "semi", 15.5, MUTE)
    bars(cv, x + 44, y + 164, (440, 420, 450, 380, 440, 300), 8, 14, GREY2, 4)
    cv.rr((x + 44, y + 322, x + w - 44, y + 420), 14, fill=(246, 241, 255), line=(222, 208, 248), w=1.5)
    sparkle(cv, x + 78, y + 371, 15, PURPLE)
    cv.text(x + 108, y + 355, t[2], "bold", 17, PURPLE_D)
    cv.text(x + 108, y + 384, t[3], "reg", 14.5, MUTE)
    bars(cv, x + 44, y + 452, (400, 440, 360), 8, 14, GREY2, 4)
    cv.ell(x + w - 110, y + h - 104, 54, line=(190, 60, 80), w=3)
    cv.ell(x + w - 110, y + h - 104, 44, line=(190, 60, 80), w=1.6)
    cv.text(x + w - 110, y + h - 104, t[4], "black", 15, (190, 60, 80), "mm")
    return cv


def kind_grafik(t):
    cv = backdrop(GOLD)
    x, y, w, h = 170, 52, 860, 596

    def body(s, bw, bh):
        s.rr((0, 47, 64, bh), 0, fill=(244, 245, 249))
        s.line([(64, 47), (64, bh)], (222, 225, 233), 1)
        for i in range(5):
            cy = 90 + i * 58
            if i == 0:
                s.rr((10, cy - 22, 54, cy + 22), 12, fill=(228, 237, 255))
            s.rr((24, cy - 9, 40, cy + 9), 4, fill=BLUE if i == 0 else GREY2)
        s.text(92, 86, t[0], "black", 26, INK)
        for i in range(3):
            cx0 = 92 + i * 232
            s.shadow((cx0, 116, cx0 + 216, 206), 12, blur=8, dy=5, alpha=34)
            s.rr((cx0, 116, cx0 + 216, 206), 12, fill=WHITE, line=(222, 225, 233), w=1.4)
            s.text(cx0 + 18, 140, (t[1], t[2], t[3])[i], "semi", 14, MUTE)
            s.text(cx0 + 18, 176, ("•••", "•••", "•••")[i], "black", 26, INK)
        s.shadow((92, 226, bw - 40, bh - 40), 14, blur=8, dy=5, alpha=34)
        s.rr((92, 226, bw - 40, bh - 40), 14, fill=WHITE, line=(222, 225, 233), w=1.4)
        for i in range(5):
            gy = 270 + i * 54
            s.line([(116, gy), (bw - 64, gy)], (234, 236, 242), 1)
        pts = [(130 + i * (bw - 250) / 7, 480 - v) for i, v in enumerate((40, 70, 55, 120, 150, 140, 210, 250))]
        poly = [(pts[0][0], 500)] + pts + [(pts[-1][0], 500)]
        s.poly(poly, (123, 47, 190, 38))
        s.line(pts, PURPLE, 4)
        for p in pts[-3:]:
            s.ell(p[0], p[1], 6, fill=WHITE, line=PURPLE, w=3)

    window(cv, x, y, w, h, "Dasbor", body)
    return cv


KINDS = {
    "hp-feed": (kind_hp_feed, ["Atur rekomendasi", "Ketik topik yang ingin lebih sering atau jarang…", "Lebih sering", "Lebih jarang", "Rekomendasi diperbarui"]),
    "dashboard-iklan": (kind_dashboard_iklan, ["Placements", "Advantage+ placements", "Manual placements", "Awareness dan Traffic: masih manual", "Pengganti"]),
    "panggilan": (kind_panggilan, ["Tautan panggilan", "Undang siapa pun, tanpa akun", "Tamu menunggu persetujuan host", "Masukkan nama Anda", "Panggilan 1:1 atau grup hingga 32 orang"]),
    "chat-ai": (kind_chat_ai, ["Asisten AI", "Tulis pertanyaan Anda", "Jawaban AI", "Ketik pesan…", ""]),
    "toko-online": (kind_toko_online, ["Cari produk", "Promo", "Lihat", "Pesanan", ""]),
    "dokumen": (kind_dokumen, ["Aturan baru", "Ringkasan isi", "Poin utama", "Berlaku bertahap", "RESMI"]),
    "grafik": (kind_grafik, ["Ringkasan", "Tayangan", "Klik", "Konversi", ""]),
}


# Detail yang disorot per fakta (carousel slide isi, scene fakta video): (x, y, zoom), x dan y 0-1 pada panggung
FOCI = {
    "hp-feed": [(0.65, 0.39, 1.5), (0.40, 0.29, 1.5), (0.65, 0.67, 1.5)],
    "dashboard-iklan": [(0.42, 0.52, 1.3), (0.41, 0.75, 1.5), (0.72, 0.57, 1.3)],
    "panggilan": [(0.64, 0.26, 1.5), (0.67, 0.69, 1.4), (0.30, 0.43, 1.2)],
}
FOCI_DEFAULT = [(0.35, 0.50, 1.4), (0.72, 0.45, 1.4), (0.50, 0.72, 1.3)]


def focus_for(kind, i, override=None):
    """Titik fokus ke-i: override dari spec (daftar [x, y, zoom]) lebih dulu, lalu bawaan per jenis."""
    lst = override if override else FOCI.get(kind, FOCI_DEFAULT)
    f = lst[i % len(lst)]
    z = float(f[2]) if len(f) > 2 else 1.4
    # koordinat fokus ditulis terhadap isi gambar (sebelum diperkecil SCALE); ubah ke koordinat panggung
    return (0.5 + (float(f[0]) - 0.5) * SCALE, 0.5 + (float(f[1]) - 0.5) * SCALE), z / SCALE


@functools.lru_cache(maxsize=16)
def _stage(kind, teks):
    fn, default = KINDS.get(kind, KINDS["grafik"])
    t = list(default)
    for i, v in enumerate(teks or ()):
        if i < len(t) and v:
            t[i] = v
    _MODE[0] = True
    try:
        content = fn(t)
    finally:
        _MODE[0] = False
    bg = backdrop(_ACC[0] or PURPLE_L)
    small = content.im.resize((int(SW * S * SCALE), int(SH * S * SCALE)), Image.LANCZOS)
    bg.im.alpha_composite(small, ((bg.im.width - small.width) // 2, (bg.im.height - small.height) // 2))
    return bg.im.convert("RGB")


def hero(kind, w, h, teks=None, focus=(0.5, 0.5), zoom=1.0, radius=28, tag=True):
    """Ilustrasi dipotong ke w x h px (RGBA, sudut membulat). focus (0-1) dan zoom>1 = detail di bagian gambar."""
    st = _stage(kind, tuple(teks or ()))
    sc = max(w / SW, h / SH) * zoom                    # px keluaran per satuan desain
    vw, vh = w / sc, h / sc                            # bagian panggung yang tampak (satuan desain)
    cx = min(max(focus[0] * SW, vw / 2), SW - vw / 2)
    cy = min(max(focus[1] * SH, vh / 2), SH - vh / 2)
    box = ((cx - vw / 2) * S, (cy - vh / 2) * S, (cx + vw / 2) * S, (cy + vh / 2) * S)
    im = st.resize((int(w), int(h)), Image.LANCZOS, box=box)          # RGB
    d = ImageDraw.Draw(im, "RGBA")                                      # RGBA di atas RGB = campur transparan
    if tag:
        f = rc.font("bold", max(16, int(h * 0.034)))
        tw_ = d.textlength("ILUSTRASI", font=f)
        pad = int(f.size * 0.6)
        x1, y1 = int(w - 18), int(h - 18)
        d.rounded_rectangle([x1 - tw_ - 2 * pad, y1 - f.size - pad, x1, y1], radius=int((f.size + pad) / 2), fill=(10, 8, 20, 190))
        d.text((x1 - pad, y1 - (f.size + pad) / 2), "ILUSTRASI", font=f, fill=(215, 205, 235), anchor="rm")
    im = im.convert("RGBA")
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=radius, fill=255)
    im.putalpha(m)
    return im


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for k in KINDS:
        hero(k, 1200, 700, radius=0).convert("RGB").save(os.path.join(out, f"stage_{k}.png"))
