#!/usr/bin/env python3
"""
Scene "ui": tampilan aplikasi/dashboard yang realistis (ilustrasi buatan sendiri, BUKAN tangkapan layar dan tanpa logo merek)
untuk B-roll penuh @nopal.brainwork. Didaftarkan ke render_motion.SCENES, jadi dipakai di motion/*.json, make_broll
dan item "cover" di edits/*.json.

STANDAR SEMUA EDITING @nopal.brainwork (keputusan Naufal 19 Okt 2026): scene ini dipakai setiap kali tool, menu, pengaturan, dashboard,
atau angka performa dibahas. Enam layout: form, library, chat, table, chart, feed.

Isi: jendela aplikasi terang (bilah judul + alamat), kursor yang bergerak dan mengklik, toggle yang menyala, teks yang diketik,
angka yang menghitung naik, kerangka abu berkilau saat data "memuat" (shimmer), notifikasi toast "Perubahan disimpan" setelah toggle,
kamera yang zoom ke bagian penting lalu bergeser pelan (drift), label "Ilustrasi · data contoh". Semua data di dalamnya hanya contoh.

Umum:  {"type":"ui","layout":"form|library|chat|table|chart|feed","kicker":"Di Ads Manager","title":"Aktifkan **opsinya**","dur":6, ...}
  title  satu baris di atas jendela (maks ±34 karakter). kicker opsional. "tag" (opsional) = teks label emas di dekat target.
  Jendela berada di y 392-1132 supaya tidak menabrak subtitle talking head (y 1170-1360).

layout "form" (formulir pengaturan ads dengan opsi berpenggalan toggle + pratinjau di sisi kanan)
  {"layout":"form","url":"ads-manager.app","heading":"Buat ads","section":"Creative",
   "rows":[{"label":"Tingkatkan kualitas","sub":"keterangan kecil","on":true},
           {"label":"Ubah gambar jadi video","sub":"...","on":false,"toggle":true}],      # toggle:true = baris yang diklik kursor
   "preview":"follow"|"image"|"video", "tag":"Aktifkan ini"}
  "follow": pratinjau berupa video bila toggle menyala, gambar bila mati. Toggle yang awalnya "on":true lalu diklik = dimatikan.

layout "library" (halaman pencarian dengan filter, kolom ketik, dan kartu hasil)
  {"layout":"library","url":"ads-library.app","heading":"Ads Library",
   "phases":["country","query","results","highlight"],      # pilih tahapan yang ditampilkan (default semua)
   "country":"Indonesia","category":"Semua ads","query":"nama brand",
   "cards":[{"date":"3 Jun 2026","art":"a"},{"date":"2 Okt 2026","art":"b"}],"hl_card":0,"tag":"Sudah jalan lama"}

layout "chat" (asisten AI generik: lampiran + pesan pengguna, jawaban diketik per butir)
  {"layout":"chat","title_bar":"Asisten AI","file":"catatan-ads.txt","user":"Ringkas pola ads kompetitor ini.",
   "bullets":["Hook yang paling sering","Jenis penawaran","Celah yang belum dipakai"]}

layout "table" (dashboard: kartu angka + tabel ads)
  {"layout":"table","heading":"Ads","kpis":[{"label":"Hasil","value":128},{"label":"Biaya per hasil","value":"Rp12 rb"}],
   "rows":[{"name":"Ads A","on":true,"budget":"Rp150 rb","result":"54","cost":"Rp9 rb"}],"hl_row":0,"hl_col":"cost"}

layout "chart" (dashboard grafik garis: kartu angka di atas + kurva yang tergambar, titik penting ditandai)
  {"layout":"chart","url":"ads-manager.app/performa","heading":"Performa ads","range":"7 hari terakhir",
   "kpis":[{"label":"Hasil","value":128},{"label":"Biaya per hasil","value":"Rp12 rb"},{"label":"ROAS","value":"3,4x"}],   # maks 3
   "series":[18,22,20,31,44,52,61],"series2":[...opsional garis pembanding...],"labels":["Sen","Sel","Rab","Kam","Jum","Sab","Min"],
   "hl_idx":4,"unit":"hasil","fmt":"rb","legend":"Ads A","legend2":"Ads B","tag":"Mulai naik"}
  hl_idx = indeks titik yang disorot kamera. fmt "rb" = angka diringkas (12400 -> 12,4 rb).

layout "feed" (insight post di layar ponsel: kartu metrik berurutan, satu metrik disorot)
  {"layout":"feed","heading":"Insight post","hl":3,"tag":"Paling berharga",
   "metrics":[{"label":"Reach","value":12400,"fmt":"rb","icon":"chart"},{"label":"Disimpan","value":842,"icon":"bookmark"}]}
  Tanpa "metrics" dipakai bawaan (Reach, Disukai, Komentar, Disimpan, Dibagikan). icon: chart, heart, chat, bookmark, arrow.
  hl = indeks metrik yang disorot (angka 0 = pertama).

Catatan: layout form otomatis memunculkan toast "Perubahan disimpan" setelah toggle diklik ("toast":false mematikan, "toast_text" mengganti teks).
"""
import math, os, json, sys
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
K = 1.5                      # resolusi kerja jendela = 1.5x ukuran desain, lalu diperkecil (halus saat zoom)
DW, DH = 960, 740            # ukuran jendela (satuan desain = piksel video pada zoom 1)
VX, VY = 60, 392             # posisi jendela di bingkai 1080x1920
RAD = 26

C = dict(bg=(244, 245, 247), card=(255, 255, 255), line=(222, 225, 230), txt=(28, 30, 33), mute=(101, 104, 110),
         faint=(165, 170, 178), blue=(37, 99, 235), blue_l=(225, 235, 253), green=(34, 170, 84), red=(222, 62, 74),
         amber=(245, 166, 35), bar=(233, 236, 240), gold=(245, 193, 7), purple=(123, 47, 190), dark=(30, 32, 38))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def seg(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, p):
    return a + (b - a) * p


def mix(c1, c2, p):
    p = clamp(p)
    return tuple(int(c1[i] + (c2[i] - c1[i]) * p) for i in range(3))


@lru_cache(maxsize=256)
def F(px, wt=400):
    px = max(6, int(round(px)))
    p = os.path.join(FONT_DIR, "Inter-Var.ttf")
    if os.path.exists(p):
        try:
            f = ImageFont.truetype(p, px)
            f.set_variation_by_axes([14, wt])
            return f
        except Exception:
            pass
    name = "Poppins-Bold.ttf" if wt >= 700 else "Poppins-SemiBold.ttf" if wt >= 500 else "Poppins-Regular.ttf"
    q = os.path.join(FONT_DIR, name)
    return ImageFont.truetype(q, px) if os.path.exists(q) else ImageFont.truetype("DejaVuSans.ttf", px)


# --------------------------------------------------------------------------------------------- kanvas jendela
class U:
    """Kanvas dengan koordinat desain (960x740). Sub-kanvas (ox, oy) dipakai untuk kartu yang muncul pelan-pelan."""

    def __init__(self, w=DW, h=DH, ox=0, oy=0, bg=None):
        self.w, self.h, self.ox, self.oy = w, h, ox, oy
        self.im = Image.new("RGB", (max(1, round(w * K)), max(1, round(h * K))), bg or C["bg"])
        self.d = ImageDraw.Draw(self.im)
        self.R = {}

    def X(self, v):
        return (v - self.ox) * K

    def Y(self, v):
        return (v - self.oy) * K

    def reg(self, name, box):
        self.R[name] = tuple(box)

    def rect(self, x0, y0, x1, y1, r=0, fill=None, line=None, w=1):
        self.d.rounded_rectangle([self.X(x0), self.Y(y0), self.X(x1), self.Y(y1)], radius=r * K, fill=fill,
                                 outline=line, width=max(1, round(w * K)) if line else 0)

    def circle(self, cx, cy, r, fill=None, line=None, w=1):
        self.d.ellipse([self.X(cx - r), self.Y(cy - r), self.X(cx + r), self.Y(cy + r)], fill=fill, outline=line,
                       width=max(1, round(w * K)) if line else 0)

    def line(self, x0, y0, x1, y1, col, w=1):
        self.d.line([self.X(x0), self.Y(y0), self.X(x1), self.Y(y1)], fill=col, width=max(1, round(w * K)))

    def poly(self, pts, fill):
        self.d.polygon([(self.X(x), self.Y(y)) for x, y in pts], fill=fill)

    def text(self, x, y, s, px, wt=400, col=None, anchor="lm"):
        self.d.text((self.X(x), self.Y(y)), s, font=F(px * K, wt), fill=col or C["txt"], anchor=anchor)

    def width(self, s, px, wt=400):
        return F(px * K, wt).getlength(s) / K

    def sprite(self, im, cx, cy, al=1.0):
        if al < 1:
            im = im.copy()
            im.putalpha(im.split()[3].point(lambda v: int(v * al)))
        self.im.paste(im, (round(self.X(cx) - im.width / 2), round(self.Y(cy) - im.height / 2)), im)

    def blit(self, sub, al=1.0, dy=0.0):
        mask = Image.new("L", sub.im.size, int(255 * clamp(al)))
        self.im.paste(sub.im, (round(self.X(sub.ox)), round(self.Y(sub.oy) + dy * K)), mask)


def wrap(u, text, px, wt, maxw):
    out, cur = [], ""
    for w_ in text.split():
        t_ = (cur + " " + w_).strip()
        if cur and u.width(t_, px, wt) > maxw:
            out.append(cur); cur = w_
        else:
            cur = t_
    if cur:
        out.append(cur)
    return out


def ic(u, name, cx, cy, size, col, inner=(255, 255, 255)):
    from scenes_extra import icon
    u.sprite(icon(name, round(size * K), col, inner), cx, cy)


def pill(u, x, y, text, px, fill, col, wt=600, padx=12, h=None, line=None):
    h = h or px + 14
    w = u.width(text, px, wt) + padx * 2
    u.rect(x, y, x + w, y + h, h / 2, fill=fill, line=line)
    u.text(x + padx, y + h / 2, text, px, wt, col)
    return w


def toggle(u, x, cy, k, w=52, h=30):
    k = clamp(k)
    u.rect(x, cy - h / 2, x + w, cy + h / 2, h / 2, fill=mix((196, 200, 207), C["blue"], k))
    r = h / 2 - 3
    kx = x + h / 2 + (w - h) * k
    u.circle(kx, cy + 1.5, r, fill=(150, 156, 166))   # bayangan halus
    u.circle(kx, cy, r, fill=(255, 255, 255))


def chrome(u, url=None, title=None):
    u.rect(0, 0, DW, 54, 0, fill=C["card"])
    u.line(0, 54, DW, 54, C["line"], 1)
    for i, c in enumerate(((237, 106, 94), (245, 190, 79), (98, 197, 84))):
        u.circle(26 + i * 24, 27, 7, fill=c)
    if url:
        u.rect(120, 11, DW - 120, 43, 16, fill=C["bar"])
        u.rect(138, 22, 148, 31, 2, fill=C["mute"])
        u.d.arc([u.X(139), u.Y(15.5), u.X(147), u.Y(25)], 180, 360, fill=C["mute"], width=max(1, round(1.4 * K)))
        u.text(160, 27, url, 17, 500, C["mute"])
    if title:
        ic(u, "sparkle", DW / 2 - u.width(title, 19, 700) / 2 - 18, 27, 20, C["purple"], C["card"])
        u.text(DW / 2 + 4, 27, title, 19, 700, C["txt"], "mm")


def sidebar(u, active=1, items=("chart", "target", "doc", "chat")):
    u.rect(0, 54, 72, DH, 0, fill=C["card"])
    u.line(72, 54, 72, DH, C["line"], 1)
    for i, name in enumerate(items):
        cy = 108 + i * 68
        if i == active:
            u.rect(14, cy - 26, 58, cy + 26, 12, fill=C["blue_l"])
        ic(u, name, 36, cy, 26, C["blue"] if i == active else C["faint"], C["blue_l"] if i == active else C["card"])


# --------------------------------------------------------------------------------------------- gambar ilustrasi
@lru_cache(maxsize=64)
def art_tile(kind, w, h):
    """Foto/kreatif ilustrasi generik (tanpa merek). Ukuran piksel w x h."""
    S = 2
    W_, H_ = w * S, h * S
    pal = {"bottle": ((255, 232, 216), (255, 190, 205)), "a": ((196, 238, 233), (118, 196, 214)),
           "b": ((255, 233, 178), (255, 175, 120)), "c": ((206, 220, 255), (150, 160, 240)),
           "d": ((255, 214, 228), (214, 160, 235))}[kind if kind in ("bottle", "a", "b", "c", "d") else "a"]
    im = Image.new("RGB", (W_, H_))
    d = ImageDraw.Draw(im)
    for y in range(H_):
        d.line([(0, y), (W_, y)], fill=mix(pal[0], pal[1], y / H_))
    cx = W_ / 2
    if kind == "bottle":
        d.ellipse([cx - 0.46 * W_, 0.55 * H_, cx + 0.46 * W_, 0.96 * H_], fill=mix(pal[1], (255, 255, 255), 0.25))
        d.ellipse([cx - 0.22 * W_, 0.80 * H_, cx + 0.26 * W_, 0.90 * H_], fill=mix(pal[1], (120, 60, 90), 0.35))
        bw, top, bot = 0.30 * W_, 0.34 * H_, 0.86 * H_
        d.rounded_rectangle([cx - bw / 2, top, cx + bw / 2, bot], radius=0.05 * W_, fill=(122, 52, 190))
        d.rounded_rectangle([cx - bw / 2 + 0.03 * W_, top + 0.03 * H_, cx - bw / 2 + 0.07 * W_, bot - 0.04 * H_], radius=6, fill=(160, 96, 224))
        d.rounded_rectangle([cx - 0.17 * W_, 0.22 * H_, cx + 0.17 * W_, top + 6], radius=0.03 * W_, fill=(245, 193, 7))
        d.rounded_rectangle([cx - bw / 2 + 0.02 * W_, 0.48 * H_, cx + bw / 2 - 0.02 * W_, 0.74 * H_], radius=0.02 * W_, fill=(252, 250, 255))
        for i, ww in enumerate((0.62, 0.42, 0.52)):
            yy = 0.53 * H_ + i * 0.065 * H_
            d.rounded_rectangle([cx - bw * ww / 2 * 1.5, yy, cx + bw * ww / 2 * 1.5, yy + 0.022 * H_], radius=4, fill=(150, 90, 210) if i == 0 else (205, 190, 225))
    else:
        d.ellipse([0.08 * W_, 0.10 * H_, 0.52 * W_, 0.10 * H_ + 0.44 * W_], fill=mix(pal[1], (255, 255, 255), 0.45))
        d.rounded_rectangle([0.40 * W_, 0.34 * H_, 0.86 * W_, 0.86 * H_], radius=0.06 * W_, fill=mix(pal[1], (40, 40, 90), 0.42))
        d.rounded_rectangle([0.46 * W_, 0.42 * H_, 0.80 * W_, 0.50 * H_], radius=8, fill=(255, 255, 255))
        d.rounded_rectangle([0.46 * W_, 0.56 * H_, 0.68 * W_, 0.62 * H_], radius=8, fill=mix(pal[1], (255, 255, 255), 0.6))
        d.ellipse([0.14 * W_, 0.58 * H_, 0.34 * W_, 0.58 * H_ + 0.20 * W_], fill=mix(pal[0], (255, 255, 255), 0.35))
    return im.resize((w, h), Image.LANCZOS)


def art(u, box, kind, zoom=1.0, pan=(0.0, 0.0), r=0):
    """Tempel kreatif ke kotak (desain). zoom > 1 = gerakan kamera pelan (jadi terasa seperti video)."""
    x0, y0, x1, y1 = box
    w, h = round((x1 - x0) * K), round((y1 - y0) * K)
    big = art_tile(kind, int(w * 1.3), int(h * 1.3))
    cw, ch = big.width / zoom, big.height / zoom
    px = (big.width - cw) / 2 + pan[0] * (big.width - cw) / 2
    py = (big.height - ch) / 2 + pan[1] * (big.height - ch) / 2
    tile = big.resize((w, h), Image.LANCZOS, box=(px, py, px + cw, py + ch))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r * K, fill=255)
    u.im.paste(tile, (round(u.X(x0)), round(u.Y(y0))), mask)


# --------------------------------------------------------------------------------------------- rencana animasi
class Plan:
    def __init__(self):
        self.cur = []          # (t, x, y) posisi kursor (desain)
        self.cam = [(0.0, DW / 2, DH / 2, 1.0)]
        self.clicks = []
        self.ev = {}

    def cursor(self, t):
        if not self.cur or t < self.cur[0][0]:
            return None
        ks = self.cur
        if t >= ks[-1][0]:
            return ks[-1][1], ks[-1][2]
        for a, b in zip(ks, ks[1:]):
            if t <= b[0]:
                p = smooth((t - a[0]) / max(1e-6, b[0] - a[0]))
                x, y = lerp(a[1], b[1], p), lerp(a[2], b[2], p)
                dx, dy = b[1] - a[1], b[2] - a[2]
                dist = math.hypot(dx, dy)
                if dist > 1:
                    off = math.sin(math.pi * p) * 0.09 * dist
                    x += -dy / dist * off
                    y += dx / dist * off
                return x, y
        return ks[-1][1], ks[-1][2]

    def camera(self, t):
        ks = self.cam
        if t <= ks[0][0]:
            return ks[0][1:]
        for a, b in zip(ks, ks[1:]):
            if t <= b[0]:
                p = smooth((t - a[0]) / max(1e-6, b[0] - a[0]))
                return tuple(lerp(a[i], b[i], p) for i in (1, 2, 3))
        return ks[-1][1:]


def center(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def shimmer(u, box, t, r=8):
    """Kotak abu-abu berkilau (skeleton loading) sebelum gambar muncul."""
    x0, y0, x1, y1 = box
    w, h = max(1, round((x1 - x0) * K)), max(1, round((y1 - y0) * K))
    tile = Image.new("RGB", (w, h), C["bar"])
    d = ImageDraw.Draw(tile)
    band = ((t * 0.85) % 1.5) - 0.25
    for xx in range(w):
        a = max(0.0, 1 - abs(xx / w - band) / 0.2)
        if a > 0:
            d.line([(xx, 0), (xx, h)], fill=mix(C["bar"], (252, 252, 253), a * 0.9))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r * K, fill=255)
    u.im.paste(tile, (round(u.X(x0)), round(u.Y(y0))), mask)


def toast(u, text, p, x0=300, y_top=62):
    """Notifikasi kecil 'Perubahan disimpan' yang turun dari atas. p 0..1 = seberapa terlihat."""
    p = clamp(p)
    if p <= 0:
        return
    w = u.width(text, 17, 600) + 76
    y0 = y_top + (1 - p) * 26
    u.rect(x0, y0 + 3, x0 + w, y0 + 49, 23, fill=(190, 194, 202))
    u.rect(x0, y0, x0 + w, y0 + 46, 23, fill=C["dark"])
    u.circle(x0 + 26, y0 + 23, 12, fill=C["green"])
    u.line(x0 + 20, y0 + 23, x0 + 25, y0 + 28, (255, 255, 255), 2.4)
    u.line(x0 + 25, y0 + 28, x0 + 33, y0 + 18, (255, 255, 255), 2.4)
    u.text(x0 + 48, y0 + 23, text, 17, 600, (255, 255, 255))


def fmt_num(v, fmt=None, p=1.0):
    if isinstance(v, str):
        return v
    v = v * p
    if fmt == "rb":
        return f"{v / 1000:.1f}".replace(".", ",") + " rb"
    return f"{int(round(v)):,}".replace(",", ".")


def heart(u, cx, cy, r, fill=None, line=None):
    """Ikon hati: dua lingkaran + segitiga."""
    if fill:
        u.circle(cx - r * 0.5, cy - r * 0.28, r * 0.56, fill=fill)
        u.circle(cx + r * 0.5, cy - r * 0.28, r * 0.56, fill=fill)
        u.poly([(cx - r * 1.04, cy - r * 0.05), (cx + r * 1.04, cy - r * 0.05), (cx, cy + r * 1.0)], fill)
    else:
        u.circle(cx - r * 0.5, cy - r * 0.28, r * 0.56, line=line, w=2)
        u.circle(cx + r * 0.5, cy - r * 0.28, r * 0.56, line=line, w=2)
        u.line(cx - r * 1.02, cy + r * 0.08, cx, cy + r * 1.0, line, 2)
        u.line(cx + r * 1.02, cy + r * 0.08, cx, cy + r * 1.0, line, 2)
        u.circle(cx - r * 0.5, cy - r * 0.22, r * 0.4, fill=C["card"])
        u.circle(cx + r * 0.5, cy - r * 0.22, r * 0.4, fill=C["card"])
        u.poly([(cx - r * 0.9, cy - r * 0.1), (cx + r * 0.9, cy - r * 0.1), (cx, cy + r * 0.82)], C["card"])


def bookmark(u, cx, cy, r, col, fill=False):
    pts = [(cx - r * 0.7, cy - r), (cx + r * 0.7, cy - r), (cx + r * 0.7, cy + r), (cx, cy + r * 0.45), (cx - r * 0.7, cy + r)]
    if fill:
        u.poly(pts, col)
    else:
        for a, b in zip(pts, pts[1:] + pts[:1]):
            u.line(a[0], a[1], b[0], b[1], col, 2)


def bubble_icon(u, cx, cy, r, col):
    u.rect(cx - r, cy - r * 0.8, cx + r, cy + r * 0.6, r * 0.6, line=col, w=2)
    u.poly([(cx - r * 0.5, cy + r * 0.45), (cx - r * 0.7, cy + r * 1.0), (cx - r * 0.05, cy + r * 0.5)], col)


# --------------------------------------------------------------------------------------------- layout: form
def phone(u, x, y, w, h, vk, t, kind="bottle"):
    """HP kecil berisi pratinjau ads. vk 0 = gambar statis, 1 = video yang bergerak."""
    u.rect(x - 6, y - 6, x + w + 6, y + h + 6, 34, fill=C["dark"])
    u.rect(x, y, x + w, y + h, 28, fill=(255, 255, 255))
    u.circle(x + 26, y + 34, 14, fill=C["purple"])
    u.rect(x + 48, y + 26, x + 134, y + 34, 4, fill=C["bar"])
    u.text(x + 48, y + 46, "Bersponsor", 11, 500, C["faint"])
    u.rect(x + 14, y + 66, x + w - 36, y + 74, 4, fill=C["bar"])
    u.rect(x + 14, y + 82, x + w - 90, y + 90, 4, fill=C["bar"])
    ax0, ay0, ax1, ay1 = x + 6, y + 100, x + w - 6, y + 100 + 250
    loop = (t * 0.30) % 1.0
    z = 1.0 + vk * (0.05 + 0.10 * loop)
    if t < 0.9:
        shimmer(u, (ax0, ay0, ax1, ay1), t)
    else:
        art(u, (ax0, ay0, ax1, ay1), kind, zoom=z, pan=(vk * (loop - 0.5) * 0.8, 0))
    tag = "Video" if vk > 0.5 else "Gambar"
    pill(u, ax0 + 10, ay0 + 10, tag, 12, (255, 255, 255), C["txt"], 700, 9, 22)
    if vk > 0.5:
        u.rect(ax0 + 12, ay1 - 18, ax1 - 12, ay1 - 14, 2, fill=(255, 255, 255, 0) if False else (235, 232, 240))
        u.rect(ax0 + 12, ay1 - 18, ax0 + 12 + (ax1 - ax0 - 24) * loop, ay1 - 14, 2, fill=C["purple"])
    u.rect(x + 14, ay1 + 14, x + w - 108, ay1 + 22, 4, fill=C["bar"])
    u.rect(x + 14, ay1 + 30, x + w - 150, ay1 + 38, 4, fill=C["bar"])
    u.rect(x + w - 96, ay1 + 12, x + w - 14, ay1 + 42, 8, fill=C["blue_l"])
    u.text(x + w - 55, ay1 + 27, "Pelajari", 12, 700, C["blue"], "mm")
    u.reg("preview", (x - 6, y - 6, x + w + 6, y + h + 6))
    u.reg("art", (ax0, ay0, ax1, ay1))


def form_draw(u, s, t, P):
    chrome(u, s.get("url", "ads-manager.app/ads"))
    sidebar(u, 1)
    u.text(104, 86, s.get("heading", "Buat ads"), 26, 800)
    cx = 600
    for i, nm in enumerate(("Campaign", "Ad set", "Ads")):
        wdt = u.width(nm, 15, 600) + 22
        cx2 = cx + wdt
        u.rect(cx, 74, cx2, 98, 12, fill=C["blue_l"] if i == 2 else C["bar"])
        u.text(cx + 11, 86, nm, 15, 600, C["blue"] if i == 2 else C["mute"])
        cx = cx2 + 10
    u.rect(100, 126, 590, 708, 16, fill=C["card"], line=C["line"])
    u.text(124, 154, s.get("section", "Creative"), 22, 700)
    rows = s.get("rows", [])[:4]
    tc = P.ev.get("click", 1e9)
    k_t = 0.0
    tgt = None
    for i, r in enumerate(rows):
        y0 = 190 + i * 96
        if i:
            u.line(124, y0, 566, y0, C["line"], 1)
        u.text(124, y0 + 30, r["label"], 21, 600)
        for j, ln in enumerate(wrap(u, r.get("sub", ""), 16, 400, 360)[:2]):
            u.text(124, y0 + 56 + j * 21, ln, 16, 400, C["mute"])
        on = bool(r.get("on", False))
        if r.get("toggle"):
            p = smooth((t - tc) / 0.25)
            k = (1 - p) if on else p
            tgt = i
            k_t = k
        else:
            k = 1.0 if on else 0.0
        toggle(u, 506, y0 + 40, k)
        u.reg(f"row{i}", (112, y0 + 4, 578, y0 + 88))
        u.reg(f"tg{i}", (506, y0 + 25, 558, y0 + 55))
    yf = 190 + len(rows) * 96 + 6
    for i, (lab, val) in enumerate((("Teks utama", None), ("Tombol ajakan", "Belanja sekarang"))):
        y0 = yf + i * 104
        if y0 + 92 > 700:
            break
        u.line(124, y0 - 6, 566, y0 - 6, C["line"], 1)
        u.text(124, y0 + 18, lab, 18, 600)
        u.rect(124, y0 + 34, 566, y0 + 88, 10, fill=C["card"], line=C["line"])
        if val:
            u.text(142, y0 + 61, val, 18, 500)
            u.line(536, y0 + 57, 542, y0 + 65, C["mute"], 2); u.line(542, y0 + 65, 548, y0 + 57, C["mute"], 2)
        else:
            u.rect(142, y0 + 49, 480, y0 + 57, 4, fill=C["bar"])
            u.rect(142, y0 + 66, 400, y0 + 74, 4, fill=C["bar"])
    u.rect(612, 126, 930, 708, 16, fill=C["card"], line=C["line"])
    u.text(636, 154, "Pratinjau", 22, 700)
    for i, nm in enumerate(("Feed", "Reels")):
        wdt = u.width(nm, 14, 700) + 18
        px0 = 778 + i * 70
        u.rect(px0, 142, px0 + wdt, 166, 12, fill=C["blue_l"] if i == 0 else C["bar"])
        u.text(px0 + 9, 154, nm, 14, 700, C["blue"] if i == 0 else C["mute"])
    mode = s.get("preview", "follow")
    vk = k_t if (mode == "follow" and tgt is not None) else (1.0 if mode == "video" else 0.0)
    phone(u, 655, 190, 232, 500, vk, t, s.get("art", "bottle"))
    if tgt is not None:
        hp = smooth((t - P.ev.get("hl", 1e9)) / 0.3)
        if hp > 0:
            b = u.R[f"row{tgt}"]
            u.rect(b[0], b[1], b[2], b[3], 12, line=mix(C["card"], C["gold"], hp), w=3.5)
            if s.get("tag"):
                tw = u.width(s["tag"], 15, 800) + 24
                u.rect(b[2] - tw - 6, b[1] - 12, b[2] - 6, b[1] + 12, 12, fill=mix(C["card"], C["gold"], hp))
                u.text(b[2] - tw + 6, b[1], s["tag"], 15, 800, C["dark"])

    if tgt is not None and s.get("toast", True):
        pt = t - P.ev.get("click", 1e9) - 0.5
        if 0 < pt < 2.0:
            toast(u, s.get("toast_text", "Perubahan disimpan"), min(smooth(pt / 0.25), smooth((2.0 - pt) / 0.25)), x0=130, y_top=626)


def form_plan(u, s, dur):
    P = Plan()
    tg = next((i for i, r in enumerate(s.get("rows", [])) if r.get("toggle")), None)
    tc = max(1.5, dur * 0.42)
    P.ev["click"] = tc
    P.ev["hl"] = max(0.5, tc - 0.7)
    if tg is None:
        pv = center(u.R["art"])
        P.cur = [(0.3, 470, 640), (max(1.0, dur * 0.7), pv[0] + 40, pv[1] + 30)]
        P.cam = [(0, DW / 2, DH / 2, 1.0), (dur, 530, DH / 2, 1.12)]
        return P
    row = u.R[f"row{tg}"]
    tgp = center(u.R[f"tg{tg}"])
    pv = center(u.R["art"])
    P.cur = [(0.4, 820, 640), (tc - 0.12, tgp[0], tgp[1]), (tc + 0.3, tgp[0] + 4, tgp[1] + 4),
             (min(dur - 0.2, tc + 1.5), pv[0] + 60, pv[1] + 40)]
    P.clicks = [tc]
    rc = center(row)
    P.cam = [(0, DW / 2, DH / 2, 1.0), (0.6, DW / 2, DH / 2, 1.0), (tc - 0.5, 430, rc[1] + 20, 1.3),
             (tc + 0.5, 430, rc[1] + 20, 1.3), (min(dur - 0.1, tc + 1.5), 540, pv[1] - 10, 1.15)]
    return P


# --------------------------------------------------------------------------------------------- layout: library
CARD_W, CARD_H = 420, 232
STAGE = {"country": 0, "query": 1, "results": 2, "highlight": 3}
DEF_CARDS = [{"date": "3 Jun 2026", "art": "a"}, {"date": "2 Okt 2026", "art": "b"},
             {"date": "28 Sep 2026", "art": "c"}, {"date": "12 Okt 2026", "art": "d"}]


def dropdown(u, x, y, w, label, value, active=False):
    u.rect(x, y, x + w, y + 60, 12, fill=C["card"], line=C["blue"] if active else C["line"], w=2 if active else 1)
    u.text(x + 16, y + 17, label, 13, 500, C["mute"])
    u.text(x + 16, y + 39, value, 20, 600)
    cx, cy = x + w - 24, y + 31
    u.line(cx - 6, cy - 3, cx, cy + 3, C["mute"], 2)
    u.line(cx, cy + 3, cx + 6, cy - 3, C["mute"], 2)


def library_card(u, i, c, t, P, show_hl, loading=False):
    col, row = i % 2, i // 2
    x, y = 48 + col * (CARD_W + 24), 244 + row * (CARD_H + 16)
    sub = U(CARD_W + 4, CARD_H + 4, x - 2, y - 2, bg=C["bg"])
    sub.rect(x, y, x + CARD_W, y + CARD_H, 14, fill=C["card"], line=C["line"])
    sub.circle(x + 36, y + 34, 18, fill=[C["blue"], C["green"], C["amber"], C["purple"]][i % 4])
    sub.rect(x + 66, y + 20, x + 190, y + 32, 6, fill=C["bar"])
    sub.circle(x + 72, y + 48, 5, fill=C["green"])
    sub.text(x + 84, y + 48, "Aktif", 14, 700, C["green"])
    sub.text(x + 130, y + 48, "Mulai tayang " + c["date"], 14, 500, C["mute"])
    for j in range(2):
        sub.circle(x + CARD_W - 28 - j * 24, y + 34, 9, fill=C["bar"])
    if loading:
        shimmer(sub, (x + 14, y + 66, x + CARD_W - 14, y + 66 + 106), t, r=10)
    else:
        art(sub, (x + 14, y + 66, x + CARD_W - 14, y + 66 + 106), c.get("art", "a"), r=10)
    sub.rect(x + 14, y + 190, x + 190, y + 198, 4, fill=C["bar"])
    sub.rect(x + 14, y + 206, x + 120, y + 214, 4, fill=C["bar"])
    sub.rect(x + CARD_W - 130, y + 186, x + CARD_W - 14, y + 218, 9, fill=C["blue_l"])
    sub.text(x + CARD_W - 72, y + 202, "Lihat detail", 14, 700, C["blue"], "mm")
    return sub, (x, y)


def library_draw(u, s, t, P):
    ph = s.get("phases", ["country", "query", "results", "highlight"])
    chrome(u, s.get("url", "ads-library.app"))
    u.text(48, 88, s.get("heading", "Ads Library"), 28, 800)
    u.text(48, 116, "Telusuri ads yang sedang dan pernah tayang", 16, 400, C["mute"])
    ev = P.ev
    u.reg("pick", (54, 262, 282, 304))
    country = s.get("country", "Indonesia")
    first = min(STAGE[p_] for p_ in ph) if ph else 0
    picked = first > 0 or t >= ev.get("pick", 1e9)
    dd_open = ev.get("open", 1e9) <= t < ev.get("pick", 1e9)
    dropdown(u, 48, 142, 240, "Negara/wilayah", country if picked else "Semua", active=dd_open)
    dropdown(u, 304, 142, 240, "Kategori ads", s.get("category", "Semua ads"))
    u.reg("dd1", (48, 142, 288, 202))
    u.rect(560, 142, 912, 202, 12, fill=C["card"], line=C["blue"] if ev.get("q0", 1e9) <= t else C["line"],
           w=2 if ev.get("q0", 1e9) <= t else 1)
    ic(u, "search", 584, 172, 20, C["mute"], C["card"])
    q = s.get("query", "nama brand")
    if "query" in ph:
        n = int(max(0, (t - ev.get("q0", 1e9) - 0.15)) * ev.get("cps", 11))
    else:
        n = len(q) if first > 1 else 0
    typed = q[:n]
    if typed:
        u.text(610, 172, typed, 20, 500)
        if t < ev.get("q1", 1e9) + 0.6 and int(t * 2.4) % 2 == 0:
            xx = 610 + u.width(typed, 20, 500) + 2
            u.line(xx, 158, xx, 186, C["blue"], 2)
    else:
        u.text(610, 172, "Cari kata kunci atau advertiser", 17, 400, C["faint"])
    u.reg("search", (560, 142, 912, 202))
    cards = (s.get("cards") or DEF_CARDS)[:4]
    tres = ev.get("res", 1e9)
    if "results" in ph or "highlight" in ph:
        a = smooth((t - tres) / 0.3)
        if a > 0:
            u.text(48, 224, "± 24 ads ditemukan", 15, 600, C["mute"])
    for i, c in enumerate(cards):
        p = smooth((t - tres - i * 0.16) / 0.38)
        sub, (cx, cy) = library_card(u, i, c, t, P, False, loading=(t - tres - i * 0.16) < 0.8)
        u.reg(f"card{i}", (cx, cy, cx + CARD_W, cy + CARD_H))
        u.reg(f"meta{i}", (cx + 60, cy + 38, cx + 408, cy + 58))
        if p > 0:
            u.blit(sub, p, (1 - p) * 26)
    hl = s.get("hl_card", 0)
    hp = smooth((t - ev.get("hl", 1e9)) / 0.3)
    if hp > 0 and hl < len(cards):
        b = u.R[f"meta{hl}"]
        u.rect(b[0] - 6, b[1] - 3, b[2] - 14, b[3] + 3, 8, line=mix(C["card"], C["gold"], hp), w=3.5)
        if s.get("tag"):
            tw = u.width(s["tag"], 14, 800) + 22
            u.rect(b[2] - tw - 10, b[1] - 34, b[2] - 10, b[1] - 10, 12, fill=mix(C["card"], C["gold"], hp))
            u.text(b[2] - tw + 1, b[1] - 22, s["tag"], 14, 800, C["dark"])
    if dd_open or (picked and "country" in ph and t < ev.get("pick", 1e9) + 0.35):
        op = smooth((t - ev.get("open", 1e9)) / 0.18) * (1 - smooth((t - ev.get("pick", 1e9) - 0.12) / 0.2))
        if op > 0:
            items = ["Semua", country, "Malaysia", "Singapura"]
            mx, my = 48, 208
            u.rect(mx, my, mx + 240, my + 8 + 46 * len(items), 12, fill=C["card"], line=C["line"], w=1.5)
            for j, it in enumerate(items):
                iy = my + 8 + j * 46
                if j == 1:
                    u.rect(mx + 6, iy, mx + 234, iy + 42, 8, fill=C["blue_l"])
                u.text(mx + 20, iy + 21, it, 19, 600 if j == 1 else 400, C["blue"] if j == 1 else C["txt"])


def library_plan(u, s, dur):
    P = Plan()
    ph = s.get("phases", ["country", "query", "results", "highlight"])
    R = u.R
    q = s.get("query", "nama brand")
    cards = (s.get("cards") or DEF_CARDS)[:4]
    hl = min(s.get("hl_card", 0), len(cards) - 1)
    ev, cur, clicks = {}, [(0.3, 800, 620)], []
    cam = [(0.0, DW / 2, DH / 2, 1.0)]
    t = 0.5
    if "country" in ph:
        c = center(R["dd1"]); cur.append((t + 0.7, c[0] + 50, c[1] + 6)); cam.append((t + 0.7, 330, 240, 1.3)); t += 0.7
        ev["open"] = t + 0.1; clicks.append(t + 0.1); t += 0.55
        c = center(R["pick"]); cur.append((t + 0.45, c[0] + 30, c[1])); t += 0.45
        ev["pick"] = t + 0.1; clicks.append(t + 0.1); t += 0.5
    if "query" in ph:
        c = center(R["search"]); cur.append((t + 0.6, c[0] + 90, c[1] + 4)); cam.append((t + 0.6, 560, 250, 1.35)); t += 0.6
        ev["q0"] = t + 0.1; clicks.append(t + 0.1); t += 0.3
        t += len(q) / 11.0 + 0.2
        ev["q1"] = t; t += 0.3
    if "results" in ph or "highlight" in ph:
        ev["res"] = t
        cam.append((t, 560, 250, 1.3)); cam.append((t + 1.0, DW / 2, 380, 1.0)); t += 1.3
    if "highlight" in ph:
        c = center(R[f"meta{hl}"]); cur.append((t + 0.7, c[0] - 30, c[1] + 14)); cam.append((t + 0.8, c[0] + 60, c[1] + 70, 1.6)); t += 0.8
        ev["hl"] = t
        t += 0.9
    f = min(1.0, (dur - 0.2) / t)
    ev = {k: v * f for k, v in ev.items()}
    ev["cps"] = 11.0 / f
    P.ev = ev
    P.cur = [(a * f, x, y) for a, x, y in cur]
    P.cam = [(a * f, x, y, z) for a, x, y, z in cam]
    P.clicks = [c * f for c in clicks]
    return P


# --------------------------------------------------------------------------------------------- layout: chat
def chat_bullets(s):
    out = []
    for b in s.get("bullets", [])[:4]:
        out.append((b["text"], b.get("sub", "")) if isinstance(b, dict) else (b, ""))
    return out


def chat_draw(u, s, t, P):
    ev = P.ev
    chrome(u, None, s.get("title_bar", "Asisten AI"))
    u.rect(0, 54, DW, DH, 0, fill=C["card"])
    y = 92
    sub = U(DW, 230, 0, y - 6, bg=C["card"])
    yy = y
    if s.get("file"):
        fw = 270
        sub.rect(DW - 70 - fw, yy, DW - 70, yy + 56, 12, fill=C["bar"])
        ic(sub, "doc", DW - 70 - fw + 28, yy + 28, 26, C["blue"], C["bar"])
        sub.text(DW - 70 - fw + 54, yy + 28, s["file"], 17, 600)
        yy += 68
    lines = wrap(sub, s.get("user", ""), 21, 500, 520)
    bw = max([sub.width(l, 21, 500) for l in lines] or [60]) + 40
    bh = len(lines) * 30 + 26
    sub.rect(DW - 70 - bw, yy, DW - 70, yy + bh, 20, fill=C["blue"])
    for j, l in enumerate(lines):
        sub.text(DW - 70 - bw + 20, yy + 25 + j * 30, l, 21, 500, (255, 255, 255))
    pu = smooth((t - ev.get("user", 1e9)) / 0.35)
    if pu > 0:
        u.blit(sub, pu, (1 - pu) * 20)
    ya = max(yy + bh + 36, 270)
    u.reg("ans", (60, ya - 10, 900, ya + 330))
    pa = smooth((t - ev.get("ai", 1e9)) / 0.3)
    if pa > 0:
        u.circle(86, ya + 16, 20, fill=C["purple"])
        ic(u, "sparkle", 86, ya + 16, 22, (255, 255, 255), C["purple"])
        typing_end = ev.get("ans0", 1e9)
        if t < typing_end:
            for j in range(3):
                u.circle(142 + j * 22, ya + 18 - 5 * max(0, math.sin(t * 8 - j * 0.9)), 6, fill=C["faint"])
        else:
            shown = int((t - typing_end) * ev.get("cps", 40))
            yy2 = ya + 14
            if s.get("intro"):
                u.text(130, yy2 + 8, s["intro"][:max(0, shown)], 21, 500)
                shown -= len(s["intro"]); yy2 += 46
            bl = chat_bullets(s)
            sub_on = len(bl) <= 3
            for j, (txt, sb) in enumerate(bl):
                full = wrap(u, txt, 24, 600, 700)
                if shown > 0:
                    u.circle(142, yy2 + 20, 15, fill=C["blue_l"])
                    u.text(142, yy2 + 20, str(j + 1), 15, 800, C["blue"], "mm")
                    rem = shown
                    for k_, l in enumerate(full):
                        if rem <= 0:
                            break
                        u.text(172, yy2 + 20 + k_ * 32, l[:rem], 24, 600)
                        rem -= len(l) + 1
                    if sub_on and shown >= len(txt):
                        sp = smooth((shown - len(txt)) / 8.0)
                        ys = yy2 + 20 + len(full) * 32 - 8
                        if sb:
                            for k_, l in enumerate(wrap(u, sb, 17, 400, 700)[:2]):
                                u.text(172, ys + 8 + k_ * 24, l, 17, 400, mix(C["card"], C["mute"], sp))
                        else:
                            u.rect(172, ys, 172 + 520, ys + 8, 4, fill=mix(C["card"], C["bar"], sp))
                            u.rect(172, ys + 18, 172 + 380, ys + 26, 4, fill=mix(C["card"], C["bar"], sp))
                yy2 += max(len(full), 1) * 32 + (46 if sub_on else 0) + 20
                shown -= len(txt) + 12
    u.rect(60, 650, 900, 706, 28, fill=C["card"], line=C["blue"] if ev.get("type0", 1e9) <= t < ev.get("send", 1e9) else C["line"], w=1.5)
    t0, ts = ev.get("type0", 1e9), ev.get("send", 1e9)
    if t0 <= t < ts:
        typed = s.get("user", "")[:int((t - t0) * ev.get("cps_u", 24))]
        u.text(88, 678, typed, 19, 500)
        if int(t * 2.4) % 2 == 0:
            xx = 88 + u.width(typed, 19, 500) + 2
            u.line(xx, 663, xx, 693, C["blue"], 2)
    else:
        u.text(88, 678, "Tulis pesan…", 18, 400, C["faint"])
    u.circle(868, 678, 20, fill=C["blue"])
    ic(u, "arrow", 868, 678, 20, (255, 255, 255), C["blue"])
    u.reg("send", (848, 658, 888, 698))


def chat_plan(u, s, dur):
    P = Plan()
    user = s.get("user", "")
    bl = chat_bullets(s)
    phase = s.get("phase", "all")
    chars = sum(len(b[0]) for b in bl) + 12 * len(bl) + len(s.get("intro", ""))
    cps_u = 24.0
    t0 = 0.4
    t_type1 = t0 + len(user) / cps_u
    t_send = t_type1 + 0.5
    t_ai = t_send + 0.7
    t_ans = t_ai + 0.8
    need = chars / 18.0 + t_ans + 0.5
    if need > dur:                       # padatkan: ketik lebih cepat, jawaban lebih cepat
        cps_u = 40.0
        t_type1 = t0 + len(user) / cps_u
        t_send = t_type1 + 0.35
        t_ai = t_send + 0.5
        t_ans = t_ai + 0.6
    cps = max(18.0, chars / max(1.2, dur - t_ans - 0.4))
    a = center(u.R["ans"])
    if phase == "answer":                # pesan pengguna sudah terkirim di scene sebelumnya
        t_ans = 0.85
        cps = max(18.0, chars / max(1.2, dur - t_ans - 0.4))
        P.ev = {"type0": 1e9, "send": -1.0, "user": -1.0, "ai": 0.15, "ans0": t_ans, "cps": cps, "cps_u": cps_u}
        P.cam = [(0, DW / 2, DH / 2, 1.0), (t_ans + 0.4, DW / 2, a[1] - 20, 1.12)]
        return P
    P.ev = {"type0": t0, "send": t_send, "user": t_send + 0.1, "ai": t_ai, "ans0": t_ans, "cps": cps, "cps_u": cps_u}
    sd = center(u.R["send"])
    P.cur = [(max(0.1, t_type1 - 0.5), 720, 520), (t_send - 0.1, sd[0], sd[1])]
    P.clicks = [t_send]
    if phase == "ask":                   # hanya mengetik dan mengirim; jawaban di scene berikutnya
        P.ev["ans0"] = 1e9
        P.cam = [(0, DW / 2, DH / 2, 1.0), (0.5, DW / 2, 560, 1.15), (t_send + 0.2, DW / 2, 560, 1.15), (t_ai + 0.5, DW / 2, 330, 1.1)]
        return P
    P.cam = [(0, DW / 2, DH / 2, 1.0), (t_send, DW / 2, DH / 2, 1.0), (t_ans + 0.5, DW / 2, a[1] - 20, 1.12)]
    return P


# --------------------------------------------------------------------------------------------- layout: table
COLS = [("name", "Nama ads", 104), ("on", "Status", 392), ("budget", "Budget", 500), ("result", "Hasil", 650), ("cost", "Biaya per hasil", 760)]
DEF_ROWS = [{"name": "Ads A", "on": True, "budget": "Rp150 rb", "result": "54", "cost": "Rp9 rb", "art": "bottle"},
            {"name": "Ads B", "on": True, "budget": "Rp100 rb", "result": "31", "cost": "Rp14 rb", "art": "a"},
            {"name": "Ads C", "on": False, "budget": "Rp50 rb", "result": "9", "cost": "Rp27 rb", "art": "b"},
            {"name": "Ads D", "on": True, "budget": "Rp80 rb", "result": "22", "cost": "Rp16 rb", "art": "c"}]


def count_text(v, p):
    if isinstance(v, (int, float)):
        return f"{int(round(v * p)):,}".replace(",", ".")
    return v


def table_draw(u, s, t, P):
    chrome(u, s.get("url", "ads-manager.app/ads"))
    sidebar(u, 0)
    u.text(104, 88, s.get("heading", "Ads"), 26, 800)
    u.rect(760, 70, 928, 106, 18, fill=C["blue"])
    u.text(844, 88, "+ Buat ads", 16, 700, (255, 255, 255), "mm")
    kp = (s.get("kpis") or [{"label": "Hasil", "value": 116}, {"label": "Budget terpakai", "value": "Rp380 rb"}, {"label": "Biaya per hasil", "value": "Rp11 rb"}])[:3]
    kw = (DW - 104 - 32 - 2 * 16) / 3
    pk = smooth(t / 1.0)
    for i, k in enumerate(kp):
        x0 = 104 + i * (kw + 16)
        u.rect(x0, 124, x0 + kw, 214, 14, fill=C["card"], line=C["line"])
        u.text(x0 + 18, 148, k["label"], 15, 500, C["mute"])
        u.text(x0 + 18, 184, count_text(k["value"], pk), 32, 800)
        u.reg(f"kpi{i}", (x0, 124, x0 + kw, 214))
    u.rect(104, 236, DW - 32, 236 + 52 + 62 * 4 + 10, 14, fill=C["card"], line=C["line"])
    u.rect(105, 237, DW - 33, 288, 14, fill=C["bar"])
    for key, nm, x in COLS:
        u.text(x, 262, nm, 14, 700, C["mute"])
    rows = (s.get("rows") or DEF_ROWS)[:4]
    hr = s.get("hl_row", 0)
    hc = s.get("hl_col", "cost")
    tc = P.ev.get("row", 1e9)
    for i, r in enumerate(rows):
        y0 = 292 + i * 62
        hov = smooth((t - tc) / 0.2) if i == hr else 0
        if hov > 0:
            u.rect(106, y0, DW - 34, y0 + 60, 0, fill=mix(C["card"], C["blue_l"], hov))
        elif i:
            u.line(120, y0, DW - 48, y0, C["line"], 1)
        art(u, (120, y0 + 10, 160, y0 + 50), r.get("art", "a"), r=8)
        u.text(172, y0 + 30, r["name"], 18, 600)
        toggle(u, 392, y0 + 30, 1.0 if r.get("on") else 0.0, 44, 26)
        u.text(500, y0 + 30, r.get("budget", ""), 17, 500)
        u.text(650, y0 + 30, count_text(r.get("result", ""), pk), 17, 600)
        u.text(760, y0 + 30, r.get("cost", ""), 17, 600)
        xs = {k: x for k, _, x in COLS}
        u.reg(f"cell{i}", (xs[hc] - 12, y0 + 8, xs[hc] + 120, y0 + 52))
    hp = smooth((t - P.ev.get("hl", 1e9)) / 0.3)
    if hp > 0 and hr < len(rows):
        b = u.R[f"cell{hr}"]
        u.rect(b[0], b[1], b[2], b[3], 10, line=mix(C["card"], C["gold"], hp), w=3.5)
        if s.get("tag"):
            tw = u.width(s["tag"], 14, 800) + 22
            u.rect(b[2] - tw, b[3] + 4, b[2], b[3] + 26, 11, fill=mix(C["card"], C["gold"], hp))
            u.text(b[2] - tw + 11, b[3] + 15, s["tag"], 14, 800, C["dark"])


def table_plan(u, s, dur):
    P = Plan()
    hr = s.get("hl_row", 0)
    c = center(u.R[f"cell{hr}"])
    t_row = max(1.2, dur * 0.35)
    t_hl = t_row + 0.6
    P.ev = {"row": t_row, "hl": t_hl}
    P.cur = [(0.5, 840, 640), (t_row - 0.1, c[0] - 60, c[1] + 4)]
    P.clicks = []
    k0 = center(u.R.get("kpi1") or u.R["kpi0"])  # tabel dengan 1 KPI tidak punya kpi1
    P.cam = [(0, DW / 2, DH / 2, 1.0), (0.9, k0[0], k0[1] + 30, 1.1), (t_row, c[0] - 100, c[1], 1.1), (t_hl + 0.4, c[0], c[1], 1.45)]
    return P


# --------------------------------------------------------------------------------------------- layout: chart
PX0, PX1, PY0, PY1 = 176, 896, 316, 628


def spline(pts, n=12):
    """Kurva halus (Catmull-Rom) melewati titik-titik data."""
    if len(pts) < 3:
        return list(pts)
    P_ = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]
        for k in range(n):
            t_ = k / n
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t_ + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t_ ** 2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t_ ** 3) for j in (0, 1)))
    out.append(tuple(pts[-1]))
    return out


def chart_pts(vals, vmax):
    n = len(vals)
    return [(PX0 + (PX1 - PX0) * i / max(1, n - 1), PY1 - (PY1 - PY0) * v / vmax) for i, v in enumerate(vals)]


def chart_draw(u, s, t, P):
    ev = P.ev
    chrome(u, s.get("url", "ads-manager.app/performa"))
    sidebar(u, 0)
    u.text(104, 88, s.get("heading", "Performa ads"), 26, 800)
    u.rect(722, 70, 928, 106, 18, fill=C["card"], line=C["line"])
    u.text(742, 88, s.get("range", "7 hari terakhir"), 16, 600)
    u.line(900, 85, 906, 91, C["mute"], 2); u.line(906, 91, 912, 85, C["mute"], 2)
    kp = (s.get("kpis") or [{"label": "Hasil", "value": 128}, {"label": "Biaya per hasil", "value": "Rp12 rb"},
                            {"label": "ROAS", "value": "3,4x"}])[:3]
    kw = (DW - 104 - 32 - 2 * 16) / 3
    pk = smooth((t - 0.2) / 1.0)
    for i, k in enumerate(kp):
        x0 = 104 + i * (kw + 16)
        u.rect(x0, 124, x0 + kw, 214, 14, fill=C["card"], line=C["line"])
        u.text(x0 + 18, 148, k["label"], 15, 500, C["mute"])
        u.text(x0 + 18, 184, fmt_num(k["value"], k.get("fmt"), pk), 32, 800)
    vals = s.get("series", [18, 22, 20, 31, 44, 52, 61])
    n = len(vals)
    labels = s.get("labels") or ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"][:n]
    labels = (labels + [""] * n)[:n]
    v2 = s.get("series2")
    top = max(vals + (v2 or [])) * 1.12
    step = 10 ** max(0, len(str(int(top))) - 1)
    vmax = math.ceil(top / (step / 2)) * (step / 2) or 1
    u.rect(104, 236, DW - 32, 706, 14, fill=C["card"], line=C["line"])
    u.text(128, 266, s.get("chart_title", "Hasil per hari"), 19, 700)
    lx = 690 if v2 else 780
    u.circle(lx, 266, 6, fill=C["blue"]); u.text(lx + 12, 266, s.get("legend", "Pekan ini"), 14, 500, C["mute"])
    if v2:
        u.circle(lx + 104, 266, 6, fill=C["faint"]); u.text(lx + 116, 266, s.get("legend2", "Pekan lalu"), 14, 500, C["mute"])
    for g in range(5):
        yy = PY1 - (PY1 - PY0) * g / 4
        u.line(PX0, yy, PX1, yy, C["line"], 1)
        u.text(PX0 - 14, yy, str(int(round(vmax * g / 4))), 14, 500, C["faint"], "rm")
    pts = chart_pts(vals, vmax)
    for i, (x, _) in enumerate(pts):
        u.text(x, PY1 + 24, labels[i], 14, 500, C["mute"], "mm")
    if v2:
        d2 = spline(chart_pts(v2, vmax))
        for a, b in list(zip(d2, d2[1:]))[::2]:
            u.line(a[0], a[1], b[0], b[1], C["faint"], 2)
    dense = spline(pts)
    pdraw = smooth((t - ev.get("draw", 1e9)) / 1.7)
    xcut = PX0 + (PX1 - PX0) * pdraw
    vis = [q for q in dense if q[0] <= xcut]
    if pdraw >= 1:
        vis = dense
    elif vis:
        a = vis[-1]
        nxt = next((q for q in dense if q[0] > xcut), None)
        if nxt and nxt[0] > a[0]:
            f = (xcut - a[0]) / (nxt[0] - a[0])
            vis.append((xcut, lerp(a[1], nxt[1], f)))
    if len(vis) > 1:
        u.poly(vis + [(vis[-1][0], PY1), (vis[0][0], PY1)], mix(C["card"], C["blue_l"], 0.75))
        for a, b in zip(vis, vis[1:]):
            u.line(a[0], a[1], b[0], b[1], C["blue"], 3.4)
    for (x, y) in pts:
        if x <= xcut + 0.5:
            u.circle(x, y, 6.5, fill=C["card"], line=C["blue"], w=2.6)
    hi = min(s.get("hl_idx", n - 2), n - 1)
    hx, hy = pts[hi]
    u.reg("pt", (hx - 10, hy - 10, hx + 10, hy + 10))
    u.reg("plot", (PX0, PY0, PX1, PY1))
    hp = smooth((t - ev.get("hl", 1e9)) / 0.3)
    if hp > 0:
        u.circle(hx, hy, 14, line=mix(C["card"], C["gold"], hp), w=3.6)
        u.circle(hx, hy, 6.5, fill=C["gold"])
        txt1, txt2 = labels[hi], fmt_num(vals[hi], s.get("fmt"), 1.0) + (" " + s["unit"] if s.get("unit") else "")
        bw = max(u.width(txt1, 14, 500), u.width(txt2, 22, 800)) + 32
        by = hy - 92 if hy - 92 > PY0 - 20 else hy + 24
        bx = min(max(hx - bw / 2, PX0 - 10), PX1 - bw + 20)
        u.rect(bx + 2, by + 3, bx + bw + 2, by + 67, 12, fill=(214, 218, 226))
        u.rect(bx, by, bx + bw, by + 64, 12, fill=C["dark"])
        u.text(bx + 16, by + 20, txt1, 14, 500, (200, 204, 212))
        u.text(bx + 16, by + 45, txt2, 22, 800, (255, 255, 255))
        if s.get("tag"):
            tw = u.width(s["tag"], 14, 800) + 22
            ty = by - 30 if by - 30 > 244 else by + 70
            u.rect(bx, ty, bx + tw, ty + 24, 12, fill=mix(C["card"], C["gold"], hp))
            u.text(bx + 11, ty + 12, s["tag"], 14, 800, C["dark"])


def chart_plan(u, s, dur):
    P = Plan()
    R = u.R
    ev, cur = {}, [(0.3, 860, 690)]
    cam = [(0.0, DW / 2, DH / 2, 1.0)]
    t = 0.6
    ev["draw"] = t
    cam.append((t + 0.2, 560, 430, 1.1))
    t += 1.9
    pt = center(R["pt"])
    cur.append((t + 0.8, pt[0] + 6, pt[1] + 8)); cam.append((t + 0.8, pt[0] - 30, max(pt[1] - 10, 236 + (DH / 1.5) / 2 + 6), 1.5)); t += 0.8
    ev["hl"] = t
    t += 1.2
    f = min(1.0, (dur - 0.2) / t)
    P.ev = {k: v * f for k, v in ev.items()}
    P.cur = [(a * f, x, y) for a, x, y in cur]
    P.cam = [(a * f, x, y, z) for a, x, y, z in cam]
    return P


# --------------------------------------------------------------------------------------------- layout: feed
FEED_DEF = [{"label": "Reach", "value": 12400, "fmt": "rb", "icon": "chart"}, {"label": "Disukai", "value": 1248, "icon": "heart"},
            {"label": "Komentar", "value": 86, "icon": "chat"}, {"label": "Disimpan", "value": 842, "icon": "bookmark"},
            {"label": "Dibagikan", "value": 210, "icon": "arrow"}]
FPX, FPY, FPW, FPH = 70, 84, 300, 640


def metric_icon(u, name, cx, cy):
    if name == "heart":
        heart(u, cx, cy - 1, 11, fill=C["red"])
    elif name == "bookmark":
        bookmark(u, cx, cy, 11, C["blue"], fill=True)
    else:
        ic(u, name, cx, cy, 24, C["blue"], C["blue_l"])


def feed_draw(u, s, t, P):
    ev = P.ev
    chrome(u, s.get("url", "insight-sosmed.app"))
    u.rect(0, 54, DW, DH, 0, fill=C["bg"])
    metrics = (s.get("metrics") or FEED_DEF)[:5]
    pc = smooth((t - ev.get("count", 1e9)) / 1.5)
    px, py, pw, ph = FPX, FPY, FPW, FPH
    u.rect(px - 7, py - 7, px + pw + 7, py + ph + 7, 40, fill=C["dark"])
    u.rect(px, py, px + pw, py + ph, 33, fill=C["card"])
    u.rect(px + pw / 2 - 44, py + 9, px + pw / 2 + 44, py + 29, 10, fill=C["dark"])
    u.text(px + 28, py + 20, "09.41", 13, 700)
    u.rect(px + pw - 52, py + 14, px + pw - 26, py + 25, 4, line=C["txt"], w=1.5)
    u.circle(px + 28, py + 62, 17, fill=C["purple"])
    u.rect(px + 54, py + 52, px + 150, py + 60, 4, fill=C["bar"])
    u.rect(px + 54, py + 66, px + 112, py + 72, 3, fill=C["bar"])
    u.text(px + pw - 44, py + 62, "Ikuti", 14, 700, C["blue"], "mm")
    ay0, ay1 = py + 92, py + 92 + pw
    if t < 0.9:
        shimmer(u, (px, ay0, px + pw, ay1), t, r=0)
    else:
        art(u, (px, ay0, px + pw, ay1), s.get("art", "bottle"), zoom=1.0 + 0.05 * smooth(t / 6))
    yact = ay1 + 28
    lk = ev.get("like", 1e9)
    lp = clamp((t - lk) / 0.35)
    liked = t >= lk
    sc = 1.0 + 0.4 * math.sin(math.pi * lp) if liked and lp < 1 else 1.0
    if liked:
        heart(u, px + 28, yact, 12 * sc, fill=C["red"])
    else:
        heart(u, px + 28, yact, 12, line=C["txt"])
    u.reg("heart", (px + 10, yact - 18, px + 46, yact + 18))
    bubble_icon(u, px + 72, yact - 1, 12, C["txt"])
    u.poly([(px + 108, yact - 11), (px + 132, yact), (px + 108, yact + 11), (px + 112, yact)], C["txt"])
    bookmark(u, px + pw - 30, yact, 12, C["txt"], fill=(t >= ev.get("save", 1e9)))
    likes = [m for m in metrics if m.get("icon") == "heart"]
    lv = likes[0]["value"] if likes else 1248
    u.text(px + 18, yact + 38, "Disukai " + fmt_num(lv, None, pc), 15, 800)
    u.rect(px + 18, yact + 58, px + pw - 40, yact + 66, 4, fill=C["bar"])
    u.rect(px + 18, yact + 74, px + pw - 110, yact + 82, 4, fill=C["bar"])
    for i in range(4):
        u.circle(px + 40 + i * ((pw - 80) / 3), py + ph - 24, 7, fill=C["bar"])
    u.text(410, 100, s.get("heading", "Insight post"), 24, 800)
    u.text(410, 128, s.get("sub", "7 hari pertama setelah tayang"), 15, 400, C["mute"])
    hl = s.get("hl", 3)
    mx = max(1.0, max(m["value"] if not isinstance(m["value"], str) else 0 for m in metrics))
    for i, m in enumerate(metrics):
        y0 = 150 + i * 100
        u.rect(410, y0, 930, y0 + 88, 14, fill=C["card"], line=C["line"])
        u.circle(446, y0 + 44, 22, fill=C["blue_l"] if m.get("icon") not in ("heart",) else (253, 232, 234))
        metric_icon(u, m.get("icon", "chart"), 446, y0 + 44)
        u.text(488, y0 + 30, m["label"], 16, 500, C["mute"])
        u.text(488, y0 + 62, fmt_num(m["value"], m.get("fmt"), pc), 30, 800)
        frac = 0.0 if isinstance(m["value"], str) else (m["value"] / mx) ** 0.5
        u.rect(720, y0 + 40, 900, y0 + 48, 4, fill=C["bar"])
        u.rect(720, y0 + 40, 720 + 180 * frac * pc, y0 + 48, 4, fill=C["blue"])
        u.reg(f"m{i}", (410, y0, 930, y0 + 88))
    hp = smooth((t - ev.get("hl", 1e9)) / 0.3)
    if hp > 0 and hl < len(metrics):
        b = u.R[f"m{hl}"]
        u.rect(b[0], b[1], b[2], b[3], 14, line=mix(C["card"], C["gold"], hp), w=3.6)
        if s.get("tag"):
            tw = u.width(s["tag"], 14, 800) + 22
            u.rect(b[2] - tw - 10, b[1] - 12, b[2] - 10, b[1] + 12, 12, fill=mix(C["card"], C["gold"], hp))
            u.text(b[2] - tw + 1, b[1], s["tag"], 14, 800, C["dark"])


def feed_plan(u, s, dur):
    P = Plan()
    R = u.R
    hl = min(s.get("hl", 3), len(s.get("metrics") or FEED_DEF) - 1)
    ev, cur, clicks = {"count": 0.5}, [(0.3, 700, 690)], []
    cam = [(0.0, DW / 2, DH / 2, 1.0)]
    t = 0.7
    hc = center(R["heart"])
    cur.append((t + 0.8, hc[0] + 4, hc[1] + 6)); cam.append((t + 0.8, 240, 470, 1.35)); t += 0.8
    ev["like"] = t + 0.05; clicks.append(t + 0.05); t += 0.9
    mc = center(R[f"m{hl}"])
    cur.append((t + 0.8, mc[0] - 60, mc[1] + 6)); cam.append((t + 0.9, 640, mc[1], 1.25)); t += 0.9
    ev["hl"] = t
    t += 1.0
    f = min(1.0, (dur - 0.2) / t)
    P.ev = {k: v * f for k, v in ev.items()}
    P.cur = [(a * f, x, y) for a, x, y in cur]
    P.cam = [(a * f, x, y, z) for a, x, y, z in cam]
    P.clicks = [c * f for c in clicks]
    return P


# --------------------------------------------------------------------------------------------- scene
LAYOUTS = {"form": (form_draw, form_plan), "library": (library_draw, library_plan), "chat": (chat_draw, chat_plan),
           "table": (table_draw, table_plan), "chart": (chart_draw, chart_plan), "feed": (feed_draw, feed_plan)}
_PLANS = {}
_SHADOW = {}
_CURSOR = {}


def get_plan(s, dur):
    key = json.dumps(s, sort_keys=True) + f"|{dur:.3f}"
    if key not in _PLANS:
        lay = s.get("layout", "form")
        draw, plan = LAYOUTS[lay]
        P0 = Plan()
        P0.ev = {}
        u = U()
        draw(u, s, 0.0, P0)               # lewat kering: mendaftarkan posisi elemen
        P = plan(u, s, dur)
        P.R = u.R
        _PLANS.clear() if len(_PLANS) > 8 else None
        _PLANS[key] = P
    return _PLANS[key]


def cursor_sprite(scale=1.0):
    k = round(46 * scale)
    if k not in _CURSOR:
        S = 4
        im = Image.new("RGBA", (k * S, k * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        pts = [(2, 1), (2, 28), (9, 22), (14, 34), (19, 32), (14, 20.5), (24, 20.5)]
        pts = [(x * k * S / 46, y * k * S / 46) for x, y in pts]
        sh = [(x + 3 * S, y + 4 * S) for x, y in pts]
        d.polygon(sh, fill=(0, 0, 0, 90))
        d.polygon(pts, fill=(255, 255, 255, 255), outline=(20, 20, 24, 255))
        d.line(pts + [pts[0]], fill=(20, 20, 24, 255), width=int(2.6 * S), joint="curve")
        _CURSOR[k] = im.resize((k, k), Image.LANCZOS)
    return _CURSOR[k]


def window_mask():
    if "m" not in _SHADOW:
        m = Image.new("L", (DW, DH), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, DW - 1, DH - 1], radius=RAD, fill=255)
        sh = Image.new("L", (DW + 160, DH + 160), 0)
        ImageDraw.Draw(sh).rounded_rectangle([80, 96, 80 + DW, 96 + DH], radius=RAD, fill=150)
        _SHADOW["m"], _SHADOW["s"] = m, sh.filter(ImageFilter.GaussianBlur(26))
    return _SHADOW["m"], _SHADOW["s"]


def register(rm):
    W, H = rm.W, rm.H
    GOLD, INK, MUTE, BG, XW, X0 = rm.GOLD, rm.INK, rm.MUTE, rm.BG, rm.XW, rm.X0
    font, eo = rm.font, rm.eo

    def sc_ui(fr, s, t, dur):
        lay = s.get("layout", "form")
        if lay not in LAYOUTS:
            raise ValueError(f"layout ui tidak dikenal: {lay}")
        P = get_plan(s, dur)
        u = U()
        LAYOUTS[lay][0](u, s, t, P)
        cx, cy, z = P.camera(t)
        z *= 1.0 + 0.025 * clamp(t / max(dur, 0.1))
        vw, vh = DW / z, DH / z
        x0 = clamp(cx - vw / 2, 0, DW - vw)
        y0 = clamp(cy - vh / 2, 0, DH - vh)
        view = u.im.resize((DW, DH), Image.LANCZOS, box=(x0 * K, y0 * K, (x0 + vw) * K, (y0 + vh) * K))
        mask, shadow = window_mask()
        k_in = eo(seg(t, 0, 0.45))
        dy = (1 - k_in) * 36
        sh = shadow.point(lambda v: int(v * k_in))
        dark = Image.new("RGB", sh.size, (0, 0, 0))
        fr.img.paste(dark, (VX - 80, int(VY - 80 + dy)), sh)
        m2 = mask.point(lambda v: int(v * k_in))
        fr.img.paste(view, (VX, int(VY + dy)), m2)
        # kursor + riak klik (ruang layar)
        cp = P.cursor(t)
        if cp and k_in > 0.5:
            sx, sy = VX + (cp[0] - x0) * z, VY + dy + (cp[1] - y0) * z
            if VX < sx < VX + DW and VY < sy < VY + DH:
                for tc in P.clicks:
                    q = seg(t, tc, tc + 0.5)
                    if 0 < q < 1:
                        rr = 14 + 46 * q
                        col = tuple(int(BG[i] + (c_[i] - BG[i]) * (1 - q)) for i, c_ in enumerate([(70, 120, 255)] * 3)) if False else (60, 110, 255)
                        fr.d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], outline=col, width=max(1, int(5 * (1 - q))))
                press = any(0 < t - tc < 0.14 for tc in P.clicks)
                spr = cursor_sprite(0.88 if press else 1.0)
                al = seg(t, P.cur[0][0], P.cur[0][0] + 0.25)
                if al < 1:
                    spr = spr.copy(); spr.putalpha(spr.split()[3].point(lambda v: int(v * al)))
                fr.img.paste(spr, (int(sx - 3), int(sy - 3)), spr)
        # keterangan di atas jendela
        if s.get("kicker"):
            fr.fade_text(X0, 262, s["kicker"].upper(), font("s", 26), t, 0, GOLD)
        if s.get("title"):
            f = rm.fit(fr.d, s["title"], "x", [50, 44, 38, 34], XW, 1)
            fr.text_anim(X0, 298, s["title"], f, XW, t, 0.1)
        # label ilustrasi
        lab = s.get("label", "Ilustrasi · data contoh")
        lf = font("s", 20)
        a = eo(seg(t, 0.4, 0.9))
        c = tuple(int(BG[i] + (MUTE[i] - BG[i]) * a) for i in range(3))
        fr.d.text((VX + DW, VY + DH + 8), lab, font=lf, fill=c, anchor="ra")

    rm.SCENES["ui"] = sc_ui
