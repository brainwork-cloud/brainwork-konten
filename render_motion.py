#!/usr/bin/env python3
"""
Renderer Reels Motion (motion graphic tanpa rekaman) @nopal.brainwork
Pemakaian:  python3 render_motion.py motion/<ID>.json [folder_output] [--frames 1.0,4.5]
Hasil:      <ID>.mp4 (1080x1920, 30 fps, musik latar), <ID>_tiktok.mp4 (720x1280), <ID>_cover.jpg
            --frames: hanya simpan PNG di detik tertentu (untuk QA cepat, tanpa video)

Format motion/<ID>.json:
{
  "id": "BW-261024-01",
  "music": true,
  "scenes": [
    {"type": "hook", "kicker": "DIGITAL MARKETING", "text": "Calon pembelimu nggak cuma nyari di **Google** lagi", "dur": 3},
    {"type": "stat", "kicker": "RISET SEBELUM BELI", "big": "3 dari 5", "text": "orang Indonesia pakai media sosial buat riset online", "source": "Sumber: ...", "dur": 5},
    {"type": "points", "kicker": "ARTINYA", "title": "Kontenmu = halaman pencarianmu", "items": ["...", "...", "..."], "dur": 4.5},
    {"type": "statement", "kicker": "INGAT", "text": "Kalimat besar dengan **kata emas**", "note": "teks kecil", "dur": 3},
    {"type": "end", "kicker": "SIMPAN DULU", "text": "Cek kontenmu minggu ini", "dur": 3.5}
  ]
}
Aturan: 3-6 scene, total 15-30 detik, scene terakhir "end" (>= 3 dtk). Teks di antara **...** berwarna emas.
Foto latar (standar foto 21 Okt 2026, lihat foto_umum.py): scene hook/stat/points/statement/icon/flow/steps/vs boleh punya
  "foto": {"url": "https://images.unsplash.com/photo-...?fm=jpg&q=80&w=1800", "kredit": "Nama / Unsplash", "jenis": "stok"}
  Foto dimuat saat render (butuh internet; di sandbox tanpa akses hasilnya tampilan polos), diredupkan, zoom pelan, kredit tercetak.
  Hasil dicatat di <folder output>/.foto.txt. Foto gagal/tidak lolos = scene tampil polos seperti biasa.
Area aman Reels/TikTok: teks berada di x 90-960, y 250-1500.
"""
import sys, os, json, re, math, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
try:   # foto latar opsional; tanpa numpy/requests render tetap jalan tanpa foto
    import foto_umum
except Exception:
    foto_umum = None
FONT_DIR = os.path.join(HERE, "fonts")
W, H, FPS = 1080, 1920, 30
X0, XW = 90, 880
BG = (10, 10, 15)
PURPLE = (123, 47, 190)
PANEL = (110, 42, 170)
GOLD = (245, 193, 7)
INK = (245, 242, 250)
MUTE = (150, 146, 162)
CARD = (28, 27, 36)
HANDLE = "@nopal.brainwork"


def font(w, s):
    n = {"x": "Poppins-ExtraBold.ttf", "b": "Poppins-Bold.ttf", "s": "Poppins-SemiBold.ttf", "r": "Poppins-Regular.ttf"}[w]
    p = os.path.join(FONT_DIR, n)
    return ImageFont.truetype(p, s) if os.path.exists(p) else ImageFont.truetype("DejaVuSans-Bold.ttf", s)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def seg(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def eo(x):
    return 1 - (1 - x) ** 3


def eob(x, k=1.7):
    x -= 1
    return 1 + (k + 1) * x ** 3 + k * x ** 2


def words(text):
    out = []
    for i, part in enumerate(re.split(r"\*\*", text or "")):
        for w in part.split():
            out.append((w, i % 2 == 1))
    return out


def layout(d, text, f, maxw, lh=1.1):
    """-> [(word, gold, x, y)] relatif terhadap (0,0), tinggi total"""
    sp = d.textlength(" ", font=f)
    lines, cur, cw = [], [], 0
    for w, g in words(text):
        ww = d.textlength(w, font=f)
        if cur and cw + sp + ww > maxw:
            lines.append(cur); cur, cw = [], 0
        cur.append((w, g, ww)); cw += (sp if len(cur) > 1 else 0) + ww
    if cur:
        lines.append(cur)
    out, y = [], 0
    for ln in lines:
        x = 0
        for w, g, ww in ln:
            out.append((w, g, x, y)); x += ww + sp
        y += int(f.size * lh)
    return out, y


def _baris_sumber(fr, s, t, t0):
    """Baris sumber di scene penutup: "source" (y=1440) dan opsional "source2" (y=1482, mis. kredit foto); font mengecil bila terlalu panjang."""
    for key, y in (("source", 1440), ("source2", 1482)):
        txt = s.get(key)
        if not txt:
            continue
        sz = 26
        while sz > 18 and fr.d.textlength(txt, font=font("r", sz)) > XW:
            sz -= 1
        fr.fade_text(X0, y, txt, font("r", sz), t, t0, MUTE)


def fit(d, text, w, sizes, maxw, maxlines):
    for s in sizes:
        f = font(w, s)
        items, h = layout(d, text, f, maxw)
        if h <= maxlines * int(s * 1.1) + 1:
            return f
    return font(w, sizes[-1])


class Frame:
    def __init__(self, t):
        self.img = Image.new("RGB", (W, H), BG)
        self.d = ImageDraw.Draw(self.img)
        # grid halus yang bergeser pelan
        off = int(t * 6) % 90
        g = (20, 19, 28)
        for x in range(-90 + off, W, 90):
            self.d.line([(x, 0), (x, H)], fill=g)
        for y in range(-90 + off, H, 90):
            self.d.line([(0, y), (W, y)], fill=g)

    def text_anim(self, x, y, text, f, maxw, t, t0, color=INK, stagger=0.07, dur=0.45, dy=30, lh=1.1, alpha=1.0):
        items, h = layout(self.d, text, f, maxw, lh)
        for i, (w, g, wx, wy) in enumerate(items):
            p = eo(seg(t, t0 + i * stagger, t0 + i * stagger + dur)) * alpha
            if p <= 0:
                continue
            c = GOLD if g else color
            c = tuple(int(BG[k] + (c[k] - BG[k]) * p) for k in range(3))
            self.d.text((x + wx, y + wy + (1 - p) * dy), w, font=f, fill=c)
        return y + h

    def fade_text(self, x, y, s, f, t, t0, color, dur=0.4):
        p = eo(seg(t, t0, t0 + dur))
        if p > 0:
            c = tuple(int(BG[k] + (color[k] - BG[k]) * p) for k in range(3))
            self.d.text((x, y + (1 - p) * 16), s, font=f, fill=c)


def sc_hook(fr, s, t, dur):
    y = 300
    fr.fade_text(X0, y, s.get("kicker", "").upper(), font("s", 32), t, 0, GOLD)
    f = fit(fr.d, s["text"], "x", [104, 96, 88, 80], XW, 5)
    y = fr.text_anim(X0, y + 70, s["text"], f, XW, t, 0.1)
    # garis emas tumbuh di bawah judul
    p = eo(seg(t, 0.9, 1.5))
    if p > 0:
        fr.d.rounded_rectangle([X0, y + 40, X0 + int(260 * p), y + 54], radius=7, fill=GOLD)
    if s.get("sub"):
        fr.text_anim(X0, y + 100, s["sub"], font("r", 44), XW, t, 1.2, color=MUTE, stagger=0.04)


def sc_stat(fr, s, t, dur):
    y = 290
    fr.fade_text(X0, y, s.get("kicker", "").upper(), font("s", 32), t, 0, GOLD)
    big = s["big"]
    bf = fit(fr.d, big, "x", [230, 200, 170, 140], XW, 1)
    p = eob(seg(t, 0.25, 0.85))
    if t >= 0.25:
        tw = int(fr.d.textlength(big, font=bf)); th = int(bf.size * 1.15)
        layer = Image.new("RGBA", (tw + 20, th), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((0, 0), big, font=bf, fill=GOLD)
        sc = max(0.05, 0.8 + 0.2 * p)
        lw, lh_ = max(1, int(layer.width * sc)), max(1, int(layer.height * sc))
        layer = layer.resize((lw, lh_))
        a = layer.split()[3].point(lambda v: int(v * clamp(seg(t, 0.25, 0.45))))
        layer.putalpha(a)
        fr.img.paste(layer, (X0, int(y + 60 + (1 - p) * 30)), layer)
    y2 = y + 60 + int(bf.size * 1.15) + 10
    y3 = fr.text_anim(X0, y2, s.get("text", ""), font("r", 48), XW, t, 0.9, stagger=0.05, lh=1.3)
    # titik penanda kecil berirama
    n = int(s.get("dots", 0))
    if n:
        on = int(s.get("dots_on", 0))
        for i in range(n):
            pa = eob(seg(t, 1.6 + i * 0.12, 2.1 + i * 0.12))
            if pa <= 0:
                continue
            cx = X0 + 70 + i * 165; cy = y3 + 170
            lit = i < on and t > 2.7 + i * 0.25
            col = GOLD if lit else (60, 58, 72)
            r = int(40 * pa)
            fr.d.ellipse([cx - r, cy - 70 - r, cx + r, cy - 70 + r], fill=col)
            fr.d.pieslice([cx - int(66 * pa), cy, cx + int(66 * pa), cy + int(130 * pa)], 180, 360, fill=col)
    _baris_sumber(fr, s, t, 1.4)


def sc_points(fr, s, t, dur):
    y = 290
    fr.fade_text(X0, y, s.get("kicker", "").upper(), font("s", 32), t, 0, GOLD)
    f = fit(fr.d, s["title"], "x", [92, 84, 76, 68], XW, 4)
    y = fr.text_anim(X0, y + 70, s["title"], f, XW, t, 0.1) + 60
    itf = font("s", 42)
    for i, it in enumerate(s.get("items", [])[:4]):
        a = eo(seg(t, 1.2 + i * 0.35, 1.7 + i * 0.35))
        items, h = layout(fr.d, it, itf, XW - 170, 1.25)
        bh = max(130, h + 70)
        if a > 0:
            x = X0 + int((1 - a) * 50)
            card = tuple(int(BG[k] + (CARD[k] - BG[k]) * a) for k in range(3))
            fr.d.rounded_rectangle([x, y, x + XW, y + bh], radius=26, fill=card)
            for (w, g, wx, wy) in items:
                c = GOLD if g else INK
                c = tuple(int(BG[k] + (c[k] - BG[k]) * a) for k in range(3))
                fr.d.text((x + 130 + wx, y + (bh - h) / 2 + wy), w, font=itf, fill=c)
            k = eo(seg(t, 1.6 + i * 0.35, 1.95 + i * 0.35))
            if k > 0:
                pts = [(x + 46, y + bh / 2 + 2), (x + 66, y + bh / 2 + 22), (x + 100, y + bh / 2 - 20)]
                l1 = min(1, k * 2); l2 = max(0, k * 2 - 1)
                fr.d.line([pts[0], (pts[0][0] + (pts[1][0] - pts[0][0]) * l1, pts[0][1] + (pts[1][1] - pts[0][1]) * l1)], fill=GOLD, width=12)
                if l2 > 0:
                    fr.d.line([pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * l2, pts[1][1] + (pts[2][1] - pts[1][1]) * l2)], fill=GOLD, width=12)
        y += bh + 28


def sc_statement(fr, s, t, dur):
    y = 420
    fr.fade_text(X0, y - 90, s.get("kicker", "").upper(), font("s", 32), t, 0, GOLD)
    p = eo(seg(t, 0, 0.5))
    fr.d.text((X0 - 10, y - 60 - (1 - p) * 20), "“", font=font("x", 220), fill=tuple(int(BG[k] + (PURPLE[k] - BG[k]) * p) for k in range(3)))
    f = fit(fr.d, s["text"], "x", [96, 88, 80, 72], XW, 6)
    y = fr.text_anim(X0, y + 120, s["text"], f, XW, t, 0.2)
    if s.get("note"):
        fr.text_anim(X0, y + 40, s["note"], font("r", 40), XW, t, 1.2, color=MUTE, stagger=0.04)


def sc_end(fr, s, t, dur):
    p = eob(seg(t, 0, 0.55), 1.4)
    if p > 0:
        cx, cy, w, h = W / 2, 250 + 560, 960, 1120
        sw, sh = w * p, h * p
        fr.d.rounded_rectangle([cx - sw / 2, cy - sh / 2, cx + sw / 2, cy + sh / 2], radius=40, fill=PANEL)
    fr.fade_text(140, 380, s.get("kicker", "SIMPAN DULU").upper(), font("s", 32), t, 0.4, GOLD)
    f = fit(fr.d, s["text"], "x", [96, 88, 80, 72], 800, 6)
    y = fr.text_anim(140, 450, s["text"], f, 800, t, 0.5)
    b = eo(seg(t, 1.5, 2.0))
    if b > 0:
        hf = font("x", 58)
        c = tuple(int(PANEL[k] + (INK[k] - PANEL[k]) * b) for k in range(3))
        fr.d.text((140, 1180 + (1 - b) * 20), HANDLE, font=hf, fill=c)
        bw = int(fr.d.textlength(HANDLE, font=hf) * eo(seg(t, 1.9, 2.4)))
        if bw > 0:
            fr.d.rounded_rectangle([140, 1272, 140 + bw, 1286], radius=7, fill=GOLD)
    _baris_sumber(fr, s, t, 1.8)


def sc_mock(fr, s, t, dur):
    """Layar aplikasi ilustrasi (generik, tanpa logo) dengan animasi ketukan pada baris "hl".
    {"type":"mock","kicker":"...","title":"...","path":["Profil","Menu","Pengaturan"],
     "screen":"Kualitas media","rows":[{"label":"...","on":true,"hl":true,"note":"..."}],"dur":4}"""
    y = 280
    if s.get("kicker"):
        fr.fade_text(X0, y, s["kicker"].upper(), font("s", 32), t, 0, GOLD); y += 60
    if s.get("title"):
        f = fit(fr.d, s["title"], "x", [72, 64, 56], XW, 2)
        y = fr.text_anim(X0, y, s["title"], f, XW, t, 0.05) + 24
    if s.get("path"):
        cf = font("s", 30); x = X0
        for i, step in enumerate(s["path"]):
            a = eo(seg(t, 0.3 + i * 0.15, 0.6 + i * 0.15))
            tw = fr.d.textlength(step, font=cf); pw = tw + 40
            if x + pw > X0 + XW:
                x, y = X0, y + 74
            last = i == len(s["path"]) - 1
            if a > 0:
                bg = GOLD if last else (60, 30, 100)
                bg = tuple(int(BG[k] + (bg[k] - BG[k]) * a) for k in range(3))
                fr.d.rounded_rectangle([x, y, x + pw, y + 58], radius=29, fill=bg)
                fr.d.text((x + 20, y + 29), step, font=cf, fill=BG if last else INK, anchor="lm")
            x += pw + (46 if not last else 0)
            if not last and a > 0:
                fr.d.text((x - 23, y + 27), ">", font=font("b", 34), fill=GOLD, anchor="mm")
        y += 100
    # HP
    p = eo(seg(t, 0.2, 0.7))
    pw, ph = 720, min(1500 - y, 1100)
    x0 = (W - pw) / 2; y0 = y + (1 - p) * 60
    fr.d.rounded_rectangle([x0 - 16, y0 - 16, x0 + pw + 16, y0 + ph + 16], radius=64, fill=(44, 36, 64))
    fr.d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=50, fill=(24, 18, 40))
    yy = y0 + 70
    fr.d.text((x0 + 40, yy), "<", font=font("b", 44), fill=MUTE)
    fr.d.text((x0 + 96, yy + 2), s.get("screen", ""), font=font("b", 42), fill=INK)
    yy += 96
    fr.d.line([(x0, yy), (x0 + pw, yy)], fill=(52, 42, 76), width=2)
    lf, nf = font("s", 40), font("r", 32)
    tap = 1.3
    for r in s.get("rows", []):
        items, h = layout(fr.d, r["label"], lf, pw - 230, 1.3)
        rh = 60 + h + (44 if r.get("note") else 0); ry = yy
        for (w, g, wx, wy) in items:
            fr.d.text((x0 + 40 + wx, ry + 30 + wy), w, font=lf, fill=GOLD if g else INK)
        if r.get("note"):
            fr.d.text((x0 + 40, ry + 30 + h + 4), r["note"], font=nf, fill=MUTE)
        if "on" in r:
            on = r["on"]
            if r.get("hl") and on:
                on = t > tap + 0.15
            tx, ty = x0 + pw - 160, ry + rh / 2 - 32
            k = eo(seg(t, tap + 0.1, tap + 0.35)) if (r.get("hl") and r["on"]) else (1 if on else 0)
            col = tuple(int((78, 70, 100)[c] + (PURPLE[c] - (78, 70, 100)[c]) * k) for c in range(3))
            fr.d.rounded_rectangle([tx, ty, tx + 120, ty + 64], radius=32, fill=col)
            kx = tx + 32 + 56 * k
            fr.d.ellipse([kx - 26, ty + 6, kx + 26, ty + 58], fill=INK)
        else:
            fr.d.text((x0 + pw - 60, ry + rh / 2), ">", font=font("b", 40), fill=MUTE, anchor="mm")
        yy = ry + rh
        if r.get("hl"):
            hp = eo(seg(t, 0.9, 1.2))
            if hp > 0:
                fr.d.rounded_rectangle([x0 + 12, ry + 6, x0 + pw - 12, yy - 6], radius=22, outline=GOLD, width=max(1, int(7 * hp)))
            # lingkaran ketukan
            rp = seg(t, tap, tap + 0.6)
            if 0 < rp < 1:
                cx, cy, rr = x0 + pw - 100, (ry + yy) / 2, 30 + 50 * rp
                fr.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=GOLD, width=max(1, int(8 * (1 - rp))))
        fr.d.line([(x0 + 24, yy), (x0 + pw - 24, yy)], fill=(52, 42, 76), width=2)


SCENES = {"hook": sc_hook, "stat": sc_stat, "points": sc_points, "statement": sc_statement, "end": sc_end, "mock": sc_mock}

# scene tambahan (icon, flow, steps, vs) untuk B-roll penuh
import scenes_extra
scenes_extra.register(sys.modules[__name__])
import scenes_ui
scenes_ui.register(sys.modules[__name__])


def render_clip(scenes, path):
    """B-roll tanpa suara dari daftar scene (dipakai make_broll.py)."""
    spec = {"scenes": scenes}
    total = sum(s["dur"] for s in scenes)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(round(total * FPS))):
        pr.stdin.write(render_frame(spec, i / FPS).tobytes())
    pr.stdin.close(); pr.wait()


def render_frame(spec, T):
    t0 = 0.0
    for s in spec["scenes"]:
        if T < t0 + s["dur"] or s is spec["scenes"][-1]:
            fr = Frame(T)
            if s.get("foto") and foto_umum is not None:
                foto_umum.latar_video(fr.img, s["foto"], T - t0, s["dur"], s["type"])   # gagal = tetap tampilan polos
            SCENES[s["type"]](fr, s, T - t0, s["dur"])
            return fr.img
        t0 += s["dur"]


def score(spec, path):
    sr = 44100
    starts, t = [], 0.0
    for s in spec["scenes"]:
        starts.append((t, s)); t += s["dur"]
    dur = t; n = int(sr * dur); out = np.zeros(n)
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)

    def note(f, t, d, v, kind="pad"):
        i = int(t * sr); m = min(int(d * sr), n - i)
        if m <= 0 or i < 0:
            return
        tt = np.arange(m) / sr
        if kind == "pad":
            w = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.minimum(1, tt / 0.4) * np.minimum(1, (d - tt) / 0.6)
        elif kind == "pluck":
            w = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 6)
        elif kind == "bass":
            w = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 2.5)
        elif kind == "kick":
            w = np.sin(2 * np.pi * (55 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 9)
        else:
            w = np.random.default_rng(int(t * 1000)).standard_normal(m) * np.exp(-tt * 80)
        out[i:i + m] += v * w

    chords = [(45, [57, 61, 64]), (42, [54, 57, 61]), (38, [50, 54, 57]), (40, [52, 56, 59])]
    first = starts[0][1]["dur"]; end_t = starts[-1][0]
    note(hz(57), 0, first, 0.10); note(hz(76), 0, 1, 0.12, "pluck")
    b, tb = 0, first
    while tb < end_t - 0.05:
        root, ch = chords[b % 4]; L = min(2.0, end_t - tb)
        note(hz(root), tb, 0.75, 0.35, "bass"); note(hz(root), tb + 1, 0.5, 0.25, "bass")
        for m in ch:
            note(hz(m), tb, L, 0.06)
        for k in range(4):
            if tb + k * 0.5 < end_t:
                note(0, tb + k * 0.5, 0.3, 0.45, "kick") if k % 2 == 0 else note(0, tb + k * 0.5, 0.05, 0.04, "tick")
        for k, mm in enumerate([76, 73, 69, 73]):
            if tb + k * 0.5 + 0.25 < end_t:
                note(hz(mm), tb + k * 0.5 + 0.25, 0.4, 0.10, "pluck")
        b += 1; tb += 2.0
    for st, s in starts:
        if s["type"] == "points":
            for i in range(len(s.get("items", [])[:4])):
                note(hz(84), st + 1.75 + i * 0.35, 0.5, 0.10, "pluck")
        if s["type"] == "stat":
            note(hz(81), st + 0.3, 0.5, 0.12, "pluck")
    for k, m in enumerate([69, 73, 76, 81]):
        note(hz(m), end_t - 0.4 + k * 0.1, 0.5, 0.12, "pluck")
    note(hz(45), end_t, dur - end_t, 0.4, "bass"); note(0, end_t, 0.4, 0.6, "kick")
    for m in [57, 61, 64, 69]:
        note(hz(m), end_t, dur - end_t, 0.08)
    fl = int(1.2 * sr); out[-fl:] *= np.linspace(1, 0, fl)
    out = out / (np.max(np.abs(out)) or 1) * 0.8
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((out * 32767).astype(np.int16).tobytes()); w.close()
    return dur


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    spec = json.load(open(args[0], encoding="utf-8"))
    sid = spec["id"]
    out = args[1] if len(args) > 1 else os.path.join(HERE, "aset", sid)
    os.makedirs(out, exist_ok=True)
    sc = spec["scenes"]
    total = sum(s["dur"] for s in sc)
    if not (3 <= len(sc) <= 6) or not (12 <= total <= 32) or sc[-1]["type"] != "end":
        sys.exit("spec tidak valid: 3-6 scene, 12-32 detik, scene terakhir 'end'")
    if "--frames" in sys.argv:
        ts = sys.argv[sys.argv.index("--frames") + 1].split(",")
        for tt in ts:
            p = os.path.join(out, f"{sid}_t{float(tt):05.2f}.png"); render_frame(spec, float(tt)).save(p); print(p)
        return
    wav = os.path.join(out, "_score.wav")
    score(spec, wav) if spec.get("music", True) else None
    mp4 = os.path.join(out, f"{sid}.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if spec.get("music", True):
        cmd += ["-i", wav, "-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(round(total * FPS))):
        pr.stdin.write(render_frame(spec, i / FPS).tobytes())
    pr.stdin.close(); pr.wait()
    if os.path.exists(wav):
        os.remove(wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "26",
                    "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", os.path.join(out, f"{sid}_tiktok.mp4")], check=True)
    cover_t = min(sc[0]["dur"] - 0.2, 2.6)
    render_frame(spec, cover_t).save(os.path.join(out, f"{sid}_cover.jpg"), quality=90)
    if foto_umum is not None:
        foto_umum.tulis_log(os.path.join(out, ".foto.txt"))
    print(json.dumps({"files": [mp4, f"{sid}_tiktok.mp4", f"{sid}_cover.jpg"], "duration": total}))


if __name__ == "__main__":
    main()
