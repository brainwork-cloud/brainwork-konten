#!/usr/bin/env python3
"""
Scene gaya EDITORIAL untuk Talking Head @nopal.brainwork (27 Nov 2026).
Acuan Naufal: video TembusinCPNS 4/5 (banner avatar, chip bernomor, kartu realistis) + reel B-roll editorial
(judul dua warna: huruf tegak tebal + miring serif emas, foto berbingkai berlabel, perbandingan, kartu angka, ajakan komentar).
Didaftarkan ke render_motion.SCENES, jadi bisa dipakai sebagai "cover" di edits/*.json (wajah di pembuka & penutup, tengah penuh scene ini).

Semua scene ed_* memakai latar gelap bergaris + bintang dan banner tetap di atas (avatar + nama + titik progres), jadi pergantian
scene terlihat seperti satu "acara". Kolom umum (semua opsional kecuali yang disebut):
  "no": 1, "total": 4          nomor bagian (chip "01") dan jumlah titik progres; tanpa "no" chip tidak tampil
  "label": "TEMUAN"            teks chip di samping nomor
  "kicker": "yang pertama"     tulisan miring emas di atas judul
  "judul": "META AD LIBRARY"   huruf tegak tebal (otomatis kapital); **kata** = emas
  "aksen": "gratis & legal"    baris miring serif emas di bawah judul

Jenis:
  ed_judul   pembuka bagian / pernyataan. + "foto" opsional (foto berbingkai di bawah judul), "tag" (label di bingkai)
  ed_foto    foto berbingkai besar, zoom pelan. "foto": {...} (format standar foto), "tag": "FOTO ILUSTRASI"
  ed_banding dua bingkai berdampingan. "kiri": {"foto":{...}|null, "ikon":"cross", "tag":"SEBELUM", "teks":"opsional"}, "kanan": {...}
             (tanpa foto = ikon besar di bingkai; ikon dari scenes_extra: check, cross, clock, chart, doc, chat, ...)
  ed_situs   tangkapan layar situs di jendela browser yang menggulir pelan. "situs": "https://contoh.com" (ditangkap Playwright
             saat render; gagal = kerangka halaman), atau "gambar": {"file": "contoh/x.png"}; "url_tampil" opsional
  ed_daftar  2-4 kartu putih bernomor muncul satu per satu. "items": ["Kalimat pembuka", "Penawaran", "Format"]
  ed_angka   angka besar menghitung naik. "angka": "2.684.092", "satuan": "pelamar" (+ judul/aksen opsional)
  ed_cta     ajakan komentar: kolom komentar dengan kata kunci yang diketik. "kata": "LIBRARY", "judul": "TULIS", "aksen": "di kolom komentar"
Area aman: konten y 130-1140 (subtitle Talking Head y 1170-1360, kredit foto y 1522).
Foto: standar foto berlaku (foto_umum.pilih: gagal/kosong = foto cadangan, kredit tercetak di bingkai dan masuk .foto.txt).
"""
import hashlib
import math
import os
import random
import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TIPE = ("ed_judul", "ed_foto", "ed_banding", "ed_situs", "ed_daftar", "ed_angka", "ed_cta")
FOTO_TIPE = ("ed_judul", "ed_foto", "ed_banding")   # scene yang memasang foto berbingkai (dihitung standar foto)

UNGU = (123, 47, 190)
EMAS = (245, 193, 7)
PUTIH = (245, 242, 250)
REDUP = (160, 154, 178)
GELAP = (12, 10, 20)


def register(rm):
    W, H = rm.W, rm.H
    eo, eob, seg, clamp = rm.eo, rm.eob, rm.seg, rm.clamp
    X0 = 70
    XW = W - 2 * X0

    # ---------- font ----------
    @lru_cache(maxsize=64)
    def F(nama, size):
        for n in (nama, "Poppins-Bold.ttf"):
            p = os.path.join(rm.FONT_DIR, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, int(size))
        return ImageFont.truetype("DejaVuSans-Bold.ttf", int(size))

    tegak = lambda s: F("Anton-Regular.ttf", s)
    miring = lambda s: F("InstrumentSerif-Italic.ttf", s)
    pop = lambda w, s: F({"r": "Poppins-Regular.ttf", "s": "Poppins-SemiBold.ttf", "b": "Poppins-Bold.ttf",
                          "x": "Poppins-ExtraBold.ttf"}[w], s)
    UK = ImageDraw.Draw(Image.new("RGB", (8, 8)))

    # ---------- tempel RGBA dengan alfa ----------
    def tempel(fr, im, x, y, al=1.0, skala=1.0, cx=None, cy=None):
        al = clamp(al)
        if al <= 0.004 or im is None:
            return
        if abs(skala - 1) > 0.003:
            w2, h2 = max(1, int(im.width * skala)), max(1, int(im.height * skala))
            ox = (cx if cx is not None else im.width / 2)
            oy = (cy if cy is not None else im.height / 2)
            x, y = x + ox - ox * skala, y + oy - oy * skala
            im = im.resize((w2, h2), Image.BILINEAR)
        if al < 0.999:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * al)))
        fr.img.paste(im, (int(round(x)), int(round(y))), im)

    @lru_cache(maxsize=256)
    def teks_img(teks, nama, size, warna, spasi=0):
        f = F(nama, size)
        if spasi:
            w = sum(UK.textlength(c, font=f) for c in teks) + spasi * max(0, len(teks) - 1)
        else:
            w = UK.textlength(teks, font=f)
        asc, desc = f.getmetrics()
        im = Image.new("RGBA", (int(w) + 8, asc + desc + 8), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if spasi:
            x = 2
            for c in teks:
                d.text((x, 2), c, font=f, fill=warna + (255,))
                x += UK.textlength(c, font=f) + spasi
        else:
            d.text((2, 2), teks, font=f, fill=warna + (255,))
        return im

    # ---------- latar ----------
    @lru_cache(maxsize=1)
    def dasar():
        im = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(im)
        a, b, c = (22, 13, 42), (11, 9, 22), (6, 6, 11)
        for y in range(H):
            p = y / H
            col = [int(a[k] + (b[k] - a[k]) * p / 0.5) for k in range(3)] if p < 0.5 else \
                  [int(b[k] + (c[k] - b[k]) * (p - 0.5) / 0.5) for k in range(3)]
            d.line([(0, y), (W, y)], fill=tuple(col))
        glow = Image.new("L", (W, H), 0)
        ImageDraw.Draw(glow).ellipse([W - 620, -380, W + 380, 520], fill=120)
        ImageDraw.Draw(glow).ellipse([-500, 900, 420, 1700], fill=60)
        glow = glow.filter(ImageFilter.GaussianBlur(160))
        im.paste(Image.new("RGB", (W, H), (88, 34, 150)), (0, 0), glow)
        return im

    rnd = random.Random(7)
    BINTANG = [(rnd.randrange(W), rnd.randrange(120, 1180), rnd.choice((1, 1, 2, 2, 3)), rnd.random() * 6.3) for _ in range(70)]

    def latar(fr, t):
        fr.img.paste(dasar(), (0, 0))
        d = fr.d
        off = (t * 7) % 96
        g = (30, 22, 50)
        for x in range(-96 + int(off), W, 96):
            d.line([(x, 0), (x, H)], fill=g)
        for y in range(-96 + int(off), H, 96):
            d.line([(0, y), (W, y)], fill=g)
        for x, y, r, ph in BINTANG:
            k = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(t * 1.7 + ph))
            c = tuple(int(40 + (230 - 40) * k * (0.5 + r / 6)) for _ in range(3))
            if r >= 3 and k > 0.8:
                d.line([(x - 7, y), (x + 7, y)], fill=c)
                d.line([(x, y - 7), (x, y + 7)], fill=c)
            d.ellipse([x - r / 2, y - r / 2, x + r / 2, y + r / 2], fill=c)

    # ---------- banner tetap (avatar + nama) ----------
    @lru_cache(maxsize=1)
    def avatar(sz=84):
        p = os.path.join(rm.HERE, "aset", "nopal_avatar.jpg")
        S = 3
        im = Image.new("RGBA", (sz * S, sz * S), (0, 0, 0, 0))
        mask = Image.new("L", (sz * S, sz * S), 0)
        ImageDraw.Draw(mask).ellipse([6 * S, 6 * S, (sz - 6) * S, (sz - 6) * S], fill=255)
        try:
            foto = Image.open(p).convert("RGB").resize((sz * S, sz * S), Image.LANCZOS)
            im.paste(foto, (0, 0), mask)
        except Exception:
            ImageDraw.Draw(im).ellipse([6 * S, 6 * S, (sz - 6) * S, (sz - 6) * S], fill=UNGU + (255,))
            ImageDraw.Draw(im).text((sz * S / 2, sz * S / 2), "N", font=pop("x", 40 * S), fill=PUTIH + (255,), anchor="mm")
        ImageDraw.Draw(im).ellipse([2 * S, 2 * S, (sz - 2) * S, (sz - 2) * S], outline=EMAS + (255,), width=4 * S)
        return im.resize((sz, sz), Image.LANCZOS)

    BANNER_Y, BANNER_H = 150, 108

    @lru_cache(maxsize=1)
    def banner():
        bw = W - 2 * X0
        S = 2
        im = Image.new("RGBA", (bw * S, BANNER_H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, bw * S - 1, BANNER_H * S - 1], radius=BANNER_H * S // 2, fill=(255, 255, 255, 22),
                            outline=(255, 255, 255, 52), width=2 * S)
        im = im.resize((bw, BANNER_H), Image.LANCZOS)
        av = avatar()
        im.paste(av, (12, (BANNER_H - av.height) // 2), av)
        d = ImageDraw.Draw(im)
        d.text((112, 20), "Nopal Brainwork", font=pop("b", 33), fill=PUTIH + (255,))
        d.text((112, 60), rm.HANDLE, font=pop("r", 24), fill=REDUP + (255,))
        return im

    def kepala(fr, s, t):
        tempel(fr, banner(), X0, BANNER_Y)
        n = int(s.get("total") or 0)
        k = int(s.get("no") or 0)
        if n > 1:
            xr = W - X0 - 40
            xs = []
            for i in range(n - 1, -1, -1):
                ww = 40 if i + 1 == k else 13
                xs.append((xr - ww, ww, i))
                xr -= ww + 12
            cy = BANNER_Y + BANNER_H // 2
            for x, ww, i in xs:
                aktif = i + 1 == k
                if aktif:
                    p = eo(seg(t, 0.1, 0.5))
                    fr.d.rounded_rectangle([x, cy - 6, x + ww, cy + 6], radius=6, fill=tuple(int(70 + (EMAS[j] - 70) * p) for j in range(3)))
                else:
                    c = (120, 112, 140) if i + 1 < k else (64, 58, 84)
                    fr.d.ellipse([x, cy - 6, x + 12, cy + 6], fill=c)

    # ---------- chip nomor + label ----------
    @lru_cache(maxsize=64)
    def chip_img(no, label):
        S = 2
        f_no, f_lb = tegak(46 * S), pop("b", 28 * S)
        hh = 76 * S
        lw = int(UK.textlength(label, font=f_lb) + 2 * 30 * S) if label else 0
        im = Image.new("RGBA", (hh + (lw + 10 * S if label else 0), hh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, hh - 1, hh - 1], radius=20 * S, fill=EMAS + (255,))
        d.text((hh / 2, hh / 2 + 2 * S), f"{no:02d}", font=f_no, fill=GELAP + (255,), anchor="mm")
        if label:
            x0 = hh + 10 * S
            d.rounded_rectangle([x0, 0, x0 + lw, hh - 1], radius=hh // 2, fill=UNGU + (255,))
            d.text((x0 + lw / 2, hh / 2), label, font=f_lb, fill=PUTIH + (255,), anchor="mm")
        return im.resize((im.width // S, im.height // S), Image.LANCZOS)

    def chip(fr, s, t, y):
        if not s.get("no"):
            return y
        im = chip_img(int(s["no"]), (s.get("label") or "").upper()[:22])
        p = eo(seg(t, 0.0, 0.4))
        tempel(fr, im, X0 - 40 * (1 - p), y, p)
        return y + im.height + 22

    # ---------- judul dua warna ----------
    def bungkus(teks, f, maks):
        kata = [(w, g) for w, g in rm.words(teks)]
        baris, cur, cw = [], [], 0
        sp = UK.textlength(" ", font=f)
        for w, g in kata:
            ww = UK.textlength(w, font=f)
            if cur and cw + sp + ww > maks:
                baris.append(cur); cur, cw = [], 0
            cur.append((w, g)); cw += (sp if len(cur) > 1 else 0) + ww
        if cur:
            baris.append(cur)
        return baris

    def pas(teks, mk, sizes, maks, maxbaris):
        for sz in sizes:
            if len(bungkus(teks, mk(sz), maks)) <= maxbaris:
                return sz
        return sizes[-1]

    @lru_cache(maxsize=128)
    def baris_img(baris_t, nama, size, warna_biasa):
        f = F(nama, size)
        sp = UK.textlength(" ", font=f)
        w = sum(UK.textlength(x, font=f) for x, _ in baris_t) + sp * (len(baris_t) - 1)
        asc, desc = f.getmetrics()
        im = Image.new("RGBA", (int(w) + 10, asc + desc + 6), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x = 3
        for kata, g in baris_t:
            d.text((x, 2), kata, font=f, fill=(EMAS if g else warna_biasa) + (255,))
            x += UK.textlength(kata, font=f) + sp
        return im

    def judul_blok(fr, s, t, y, t0=0.12, besar=(132, 118, 104, 92, 84), aksen_sz=(104, 92, 82, 72), maxb=2, tengah=False, aksen_maxb=2):
        """Kicker miring + judul tegak kapital + aksen miring emas. -> y bawah."""
        if s.get("kicker"):
            im = teks_img(s["kicker"], "InstrumentSerif-Italic.ttf", 66, EMAS)
            p = eo(seg(t, t0 - 0.06, t0 + 0.34))
            x = (W - im.width) / 2 if tengah else X0
            tempel(fr, im, x, y + 18 * (1 - p), p)
            y += im.height - 4
        if s.get("judul"):
            teks = s["judul"].upper()
            sz = pas(teks, tegak, list(besar), XW, maxb)
            for i, b in enumerate(bungkus(teks, tegak(sz), XW)):
                im = baris_img(tuple(b), "Anton-Regular.ttf", sz, PUTIH)
                p = eo(seg(t, t0 + 0.08 * i, t0 + 0.08 * i + 0.42))
                x = (W - im.width) / 2 if tengah else X0
                tempel(fr, im, x, y + 36 * (1 - p), p)
                y += int(sz * 1.08)
        if s.get("aksen"):
            sz = pas(s["aksen"], miring, list(aksen_sz), XW, aksen_maxb)
            for i, b in enumerate(bungkus(s["aksen"], miring(sz), XW)[:aksen_maxb]):
                im = baris_img(tuple((w, True) for w, _ in b), "InstrumentSerif-Italic.ttf", sz, EMAS)
                p = eo(seg(t, t0 + 0.3 + 0.08 * i, t0 + 0.72 + 0.08 * i))
                x = (W - im.width) / 2 if tengah else X0
                tempel(fr, im, x - 14 * (1 - p), y + 8, p)
                y += int(sz * 0.98)
            y += 18
        return y

    # ---------- foto berbingkai ----------
    def _cover_crop(im, w, h, fok=(0.5, 0.42)):
        r = max(w / im.width, h / im.height)
        im2 = im.resize((max(w, int(im.width * r + 0.5)), max(h, int(im.height * r + 0.5))), Image.LANCZOS)
        x = int((im2.width - w) * fok[0]); y = int((im2.height - h) * fok[1])
        return im2.crop((x, y, x + w, y + h))

    _FOTO = {}

    def ambil_foto(f, w, h):
        """-> (PIL.Image RGB ukuran (w*1.1, h*1.1) atau None, label kredit atau '')."""
        key = (str(f), w, h)
        if key in _FOTO:
            return _FOTO[key]
        im, lab = None, ""
        fe = f
        if isinstance(f, dict) and f.get("file") and os.path.exists(os.path.join(rm.HERE, f["file"])) and not f.get("url"):
            try:
                im = Image.open(os.path.join(rm.HERE, f["file"])).convert("RGB")
                lab = ("Foto: " + f["kredit"]) if f.get("kredit") else ""
            except Exception:
                im = None
        if im is None and rm.foto_umum is not None:
            try:
                im, fe = rm.foto_umum.pilih(f if isinstance(f, dict) else None, w, h)
                if im is not None:
                    rm.foto_umum.tandai_tampil(fe)
                    lab = rm.foto_umum.label(fe)
            except Exception:
                im = None
        if im is not None:
            fok = tuple((fe or {}).get("fokus") or (0.5, 0.42)) if isinstance(fe, dict) else (0.5, 0.42)
            im = _cover_crop(im.convert("RGB"), int(w * 1.1), int(h * 1.1), fok)
        _FOTO[key] = (im, lab)
        return _FOTO[key]

    @lru_cache(maxsize=16)
    def pengganti(w, h, ikon):
        im = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(im)
        for y in range(h):
            p = y / h
            d.line([(0, y), (w, y)], fill=(int(70 - 40 * p), int(30 - 15 * p), int(120 - 60 * p)))
        try:
            import scenes_extra
            ic = scenes_extra.icon(ikon, min(w, h) // 3, (255, 255, 255, 200), (60, 25, 100))
            im.paste(ic, ((w - ic.width) // 2, (h - ic.height) // 2), ic)
        except Exception:
            pass
        return im

    @lru_cache(maxsize=32)
    def bayangan(w, h, r):
        m = 50
        sh = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([m, m + 18, m + w, m + h + 18], radius=r, fill=(0, 0, 0, 170))
        return sh.filter(ImageFilter.GaussianBlur(22))

    @lru_cache(maxsize=32)
    def tag_img(teks, gaya="gelap"):
        S = 2
        f = pop("b", 25 * S)
        tw = UK.textlength(teks, font=f)
        hh = 54 * S
        w = int(tw + 2 * 24 * S + 22 * S)
        im = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if gaya == "emas":
            d.rounded_rectangle([0, 0, w - 1, hh - 1], radius=hh // 2, fill=EMAS + (255,))
            d.ellipse([20 * S, hh / 2 - 7 * S, 34 * S, hh / 2 + 7 * S], fill=GELAP + (255,))
            d.text((44 * S, hh / 2), teks, font=f, fill=GELAP + (255,), anchor="lm")
        else:
            d.rounded_rectangle([0, 0, w - 1, hh - 1], radius=hh // 2, fill=(14, 11, 24, 235), outline=(255, 255, 255, 60), width=2 * S)
            d.ellipse([20 * S, hh / 2 - 7 * S, 34 * S, hh / 2 + 7 * S], fill=EMAS + (255,))
            d.text((44 * S, hh / 2), teks, font=f, fill=PUTIH + (255,), anchor="lm")
        return im.resize((w // S, hh // S), Image.LANCZOS)

    def bingkai(fr, f, x, y, w, h, t, dur, tag=None, t0=0.15, rot=0.0, ikon="image", gaya_tag="gelap", zoom_arah=1):
        """Foto (atau pengganti) dalam bingkai putih bersudut bulat, zoom pelan, label di pojok kiri atas, kredit kiri bawah."""
        r, bd = 28, 9
        iw, ih = w - 2 * bd, h - 2 * bd
        foto, lab = ambil_foto(f, iw, ih) if f not in (None, False) else (None, "")
        p = clamp(t / max(0.6, dur))
        z = 1.0 + 0.08 * (p if zoom_arah > 0 else 1 - p)
        if foto is not None:
            bw_, bh_ = foto.width / (1.1 * z) * 1.0, foto.height / (1.1 * z)
            cx, cy = foto.width / 2 + (foto.width - bw_) * 0.15 * (p - 0.5), foto.height / 2
            isi = foto.resize((iw, ih), Image.BILINEAR, box=(cx - bw_ / 2, cy - bh_ / 2, cx + bw_ / 2, cy + bh_ / 2))
        else:
            isi = pengganti(iw, ih, ikon)
        kart = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        mk = Image.new("L", (w * 2, h * 2), 0)
        ImageDraw.Draw(mk).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], radius=r * 2, fill=255)
        mk = mk.resize((w, h), Image.LANCZOS)
        kart.paste((250, 248, 252, 255), (0, 0), mk)
        mi = Image.new("L", (iw * 2, ih * 2), 0)
        ImageDraw.Draw(mi).rounded_rectangle([0, 0, iw * 2 - 1, ih * 2 - 1], radius=(r - 6) * 2, fill=255)
        mi = mi.resize((iw, ih), Image.LANCZOS)
        kart.paste(isi, (bd, bd), mi)
        if lab:
            d = ImageDraw.Draw(kart)
            gr = Image.new("L", (iw, 90), 0)
            for yy in range(90):
                ImageDraw.Draw(gr).line([(0, yy), (iw, yy)], fill=int(170 * yy / 90))
            kart.paste((0, 0, 0, 255), (bd, h - bd - 90), Image.composite(gr, Image.new("L", gr.size, 0), mi.crop((0, ih - 90, iw, ih))))
            d.text((bd + 22, h - bd - 22), lab[:70], font=pop("s", 21), fill=(235, 232, 240, 255), anchor="ls")
        a = eo(seg(t, t0, t0 + 0.45))
        sk = 0.9 + 0.1 * eob(seg(t, t0, t0 + 0.6))
        if rot:
            kart = kart.rotate(rot, resample=Image.BICUBIC, expand=True)
        sh = bayangan(kart.width, kart.height, r)
        ox, oy = x - (kart.width - w) / 2, y - (kart.height - h) / 2
        tempel(fr, sh, ox - 50, oy - 50, a * 0.9, sk, cx=kart.width / 2 + 50, cy=kart.height / 2 + 50)
        tempel(fr, kart, ox, oy, a, sk)
        if tag:
            ti = tag_img(tag.upper()[:28], gaya_tag)
            pt = eob(seg(t, t0 + 0.35, t0 + 0.75))
            tempel(fr, ti, x + 26, y - ti.height / 2, seg(t, t0 + 0.35, t0 + 0.55), 0.6 + 0.4 * pt, cx=0, cy=ti.height / 2)

    # ================= scene =================
    def sc_judul(fr, s, t, dur):
        latar(fr, t); kepala(fr, s, t)
        y = chip(fr, s, t, 310)
        ada_foto = "foto" in s
        if ada_foto:
            y = judul_blok(fr, s, t, y, besar=(118, 104, 92, 84), aksen_sz=(88, 78, 70, 62, 56), maxb=2, aksen_maxb=1)
        else:
            y = judul_blok(fr, s, t, y + 80, besar=(140, 124, 110, 96, 86), maxb=3)
        if ada_foto:
            top = y + 34
            hh = 1140 - top
            if hh >= 220:
                bingkai(fr, s.get("foto") or {}, X0, top, XW, hh, t, dur, s.get("tag"), t0=0.35, ikon=s.get("ikon", "image"))
        elif s.get("catatan"):
            im = teks_img(s["catatan"][:60], "Poppins-Regular.ttf", 36, REDUP)
            tempel(fr, im, X0, y + 30, seg(t, 0.8, 1.2))

    def sc_foto(fr, s, t, dur):
        latar(fr, t); kepala(fr, s, t)
        y = chip(fr, s, t, 300)
        y = judul_blok(fr, s, t, y, besar=(96, 88, 80, 72), aksen_sz=(80, 72, 64), maxb=2, aksen_maxb=1)
        top = max(y + 36, 520)
        bingkai(fr, s.get("foto") or {}, X0, top, XW, 1135 - top, t, dur, s.get("tag") or "FOTO ILUSTRASI", t0=0.25,
                ikon=s.get("ikon", "image"))

    def sc_banding(fr, s, t, dur):
        latar(fr, t); kepala(fr, s, t)
        y = chip(fr, s, t, 300)
        y = judul_blok(fr, s, t, y, besar=(96, 88, 80, 72), aksen_sz=(80, 72, 64), maxb=2, aksen_maxb=1)
        top = max(y + 50, 560)
        gap = 34
        w = (XW - gap) // 2
        hh = 1120 - top
        for j, (sisi, rot, x) in enumerate(((s.get("kiri") or {}, -2.2, X0), (s.get("kanan") or {}, 2.2, X0 + w + gap))):
            t0 = 0.3 + 0.35 * j
            if True:
                bingkai(fr, sisi.get("foto"), x, top, w, hh - (90 if sisi.get("teks") else 0), t, dur, sisi.get("tag"), t0=t0, rot=rot,
                        ikon=sisi.get("ikon", "image"), gaya_tag="emas" if j == 1 else "gelap", zoom_arah=1 - 2 * j)
            if sisi.get("teks"):
                im = teks_img(sisi["teks"][:26], "Poppins-Bold.ttf", 34, PUTIH if j == 0 else EMAS)
                tempel(fr, im, x + (w - im.width) / 2, top + hh - 64, eo(seg(t, t0 + 0.5, t0 + 0.9)))
        # lencana VS
        p = eob(seg(t, 0.75, 1.15))
        if p > 0:
            S = 2
            vs = Image.new("RGBA", (120 * S, 120 * S), (0, 0, 0, 0))
            dv = ImageDraw.Draw(vs)
            dv.ellipse([0, 0, 120 * S - 1, 120 * S - 1], fill=EMAS + (255,), outline=GELAP + (255,), width=8 * S)
            dv.text((60 * S, 62 * S), "VS", font=tegak(54 * S), fill=GELAP + (255,), anchor="mm")
            vs = vs.resize((120, 120), Image.LANCZOS)
            tempel(fr, vs, W / 2 - 60, top + (hh - 90) / 2 - 60, seg(t, 0.75, 0.9), max(0.05, p))

    _SITUS = {}

    def tangkap(url):
        """Tangkapan layar ponsel satu halaman situs (Playwright). Gagal / tanpa jaringan = None."""
        if url in _SITUS:
            return _SITUS[url]
        im = None
        d = os.path.join(os.environ.get("RUNNER_TEMP") or "/tmp", "ed_situs")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, hashlib.md5(url.encode()).hexdigest() + ".png")
        if not os.path.exists(p):
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as pw:
                    b = pw.chromium.launch()
                    pg = b.new_page(viewport={"width": 412, "height": 900}, device_scale_factor=2.4, is_mobile=True,
                                    locale="id-ID", user_agent="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36")
                    pg.goto(url, wait_until="networkidle", timeout=30000)
                    pg.wait_for_timeout(1500)
                    pg.screenshot(path=p, full_page=True, clip=None, timeout=30000)
                    b.close()
            except Exception as e:
                print(f"ed_situs: gagal menangkap {url}: {type(e).__name__}: {str(e)[:120]}")
        if os.path.exists(p):
            try:
                im = Image.open(p).convert("RGB")
                if im.height > im.width * 4:
                    im = im.crop((0, 0, im.width, im.width * 4))
            except Exception:
                im = None
        _SITUS[url] = im
        return im

    @lru_cache(maxsize=8)
    def kerangka(w, h):
        im = Image.new("RGB", (w, h), (246, 245, 250))
        d = ImageDraw.Draw(im)
        y = 30
        d.rounded_rectangle([30, y, w - 30, y + 60], radius=14, fill=(226, 223, 236)); y += 100
        d.rounded_rectangle([30, y, w - 30, y + 360], radius=22, fill=(214, 208, 230)); y += 400
        for i in range(8):
            d.rounded_rectangle([30, y, w * (0.9 if i % 2 else 0.7), y + 34], radius=10, fill=(226, 223, 236)); y += 58
        d.rounded_rectangle([30, y + 20, w - 30, y + 320], radius=22, fill=(214, 208, 230))
        return im

    def sc_situs(fr, s, t, dur):
        latar(fr, t); kepala(fr, s, t)
        y = chip(fr, s, t, 300)
        y = judul_blok(fr, s, t, y, besar=(92, 84, 76, 70), aksen_sz=(76, 68, 60), maxb=2, aksen_maxb=1)
        top = max(y + 34, 520)
        x, w, h = X0 + 20, XW - 40, 1135 - top
        bar = 74
        a = eo(seg(t, 0.2, 0.6))
        sk = 0.92 + 0.08 * eob(seg(t, 0.2, 0.75))
        win = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        mk = Image.new("L", (w * 2, h * 2), 0)
        ImageDraw.Draw(mk).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], radius=56, fill=255)
        mk = mk.resize((w, h), Image.LANCZOS)
        isi = Image.new("RGB", (w, h), (32, 29, 44))
        d = ImageDraw.Draw(isi)
        for i, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
            d.ellipse([26 + i * 30, bar / 2 - 9, 44 + i * 30, bar / 2 + 9], fill=c)
        url = s.get("url_tampil") or re.sub(r"^https?://(www\.)?", "", s.get("situs") or "situs.com").rstrip("/")
        d.rounded_rectangle([130, 14, w - 24, bar - 14], radius=22, fill=(52, 48, 68))
        d.text((160, bar / 2), "\U0001F512" if False else "", font=pop("s", 24), fill=REDUP)
        # gembok sederhana
        d.rounded_rectangle([150, bar / 2 - 4, 168, bar / 2 + 12], radius=3, fill=(170, 165, 190))
        d.arc([152, bar / 2 - 16, 166, bar / 2 + 2], 180, 360, fill=(170, 165, 190), width=3)
        d.text((182, bar / 2), url[:38], font=pop("s", 26), fill=(230, 228, 238), anchor="lm")
        vw, vh = w, h - bar
        shot = None
        if s.get("gambar"):
            g = s["gambar"]
            try:
                shot = Image.open(os.path.join(rm.HERE, g["file"])).convert("RGB") if isinstance(g, dict) and g.get("file") else None
            except Exception:
                shot = None
        if shot is None and s.get("situs"):
            shot = tangkap(s["situs"])
        if shot is None:
            shot = kerangka(vw, int(vh * 1.6))
        k = vw / shot.width
        sh_h = int(shot.height * k)
        gul = max(0, sh_h - vh)
        p = eo(seg(t, 0.9, max(1.6, dur - 0.3)))
        y_off = min(gul, int(gul * 0.55 * p)) if gul else 0
        y0s = y_off / k
        view = shot.resize((vw, vh), Image.BILINEAR, box=(0, y0s, shot.width, y0s + vh / k))
        isi.paste(view, (0, bar))
        win.paste(isi, (0, 0), mk)
        ImageDraw.Draw(win).rounded_rectangle([0, 0, w - 1, h - 1], radius=28, outline=(255, 255, 255, 70), width=2)
        sh = bayangan(w, h, 28)
        tempel(fr, sh, x - 50, top - 50, a * 0.9, sk, cx=w / 2 + 50, cy=h / 2 + 50)
        tempel(fr, win, x, top, a, sk)
        if s.get("tag"):
            ti = tag_img(s["tag"].upper()[:28], "emas")
            tempel(fr, ti, x + 30, top + h - ti.height / 2, seg(t, 0.6, 0.8), 0.6 + 0.4 * eob(seg(t, 0.6, 1.0)), cx=0, cy=ti.height / 2)

    def _format_angka(target_str, p):
        digits = re.sub(r"[^\d]", "", target_str)
        if not digits:
            return target_str
        v = int(round(int(digits) * p))
        s_ = f"{v:,}".replace(",", ".")
        pre = re.match(r"^[^\d]*", target_str).group(0)
        suf = re.search(r"[^\d.,]*$", target_str).group(0)
        if "," in target_str and "." not in target_str:   # angka desimal pendek seperti 4,8 jt: tampilkan apa adanya di akhir
            return target_str if p >= 1 else s_
        return pre + s_ + suf

    @lru_cache(maxsize=4)
    def cahaya(r):
        im = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse([r * 0.3, r * 0.3, r * 1.7, r * 1.7], fill=EMAS + (70,))
        return im.filter(ImageFilter.GaussianBlur(r * 0.28))

    def sc_angka(fr, s, t, dur):
        latar(fr, t); kepala(fr, s, t)
        y = chip(fr, s, t, 310)
        if s.get("kicker"):
            im = teks_img(s["kicker"], "InstrumentSerif-Italic.ttf", 70, EMAS)
            tempel(fr, im, (W - im.width) / 2, y + 30, eo(seg(t, 0.05, 0.4)))
        cy = 700
        gl = cahaya(320)
        tempel(fr, gl, W / 2 - 320, cy - 320, seg(t, 0.1, 0.6) * (0.85 + 0.15 * math.sin(t * 2.2)))
        p = eo(seg(t, 0.15, min(dur * 0.6, 1.6)))
        teks = _format_angka(str(s.get("angka", "0")), p)
        sz = 260
        while sz > 120 and UK.textlength(teks, font=tegak(sz)) > XW:
            sz -= 10
        im = teks_img(teks, "Anton-Regular.ttf", sz, EMAS)
        tempel(fr, im, (W - im.width) / 2, cy - im.height / 2 - 20, seg(t, 0.1, 0.3), 0.85 + 0.15 * eob(seg(t, 0.1, 0.6)))
        y = cy + sz // 2 + 30
        if s.get("satuan"):
            im = teks_img(s["satuan"].upper()[:30], "Poppins-Bold.ttf", 46, PUTIH, 4)
            tempel(fr, im, (W - im.width) / 2, y, eo(seg(t, 0.5, 0.9)))
            y += im.height + 20
        s2 = {k: v for k, v in s.items() if k in ("judul", "aksen")}
        if s2:
            judul_blok(fr, s2, t, y + 10, t0=0.7, besar=(76, 68, 60), aksen_sz=(72, 64, 58), maxb=2, tengah=True)

    def sc_cta(fr, s, t, dur):
        latar(fr, t); kepala(fr, s, t)
        s2 = dict(s)
        s2.setdefault("judul", "TULIS")
        s2.setdefault("aksen", "di kolom komentar")
        y = judul_blok(fr, s2, t, 330, besar=(150, 132, 116), aksen_sz=(110, 96, 84), maxb=1, tengah=True)
        top = max(y + 40, 640)
        w, h = XW - 40, 1130 - top
        x = X0 + 20
        a = eo(seg(t, 0.3, 0.7))
        card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dc = ImageDraw.Draw(card)
        dc.rounded_rectangle([0, 0, w - 1, h - 1], radius=36, fill=(250, 249, 252, 255))
        dc.rounded_rectangle([w / 2 - 40, 14, w / 2 + 40, 22], radius=4, fill=(210, 206, 220, 255))
        dc.text((w / 2, 56), "Komentar", font=pop("b", 30), fill=(20, 18, 30, 255), anchor="mm")
        kata = (s.get("kata") or "MAU").upper()[:16]
        rows = [("budi.ads", 0.62), ("sari.umkm", 0.48)]
        yy = 100
        for nm, ww in rows:
            dc.ellipse([30, yy, 82, yy + 52], fill=(222, 218, 232, 255))
            dc.text((100, yy + 4), nm, font=pop("s", 24), fill=(120, 116, 135, 255))
            dc.rounded_rectangle([100, yy + 36, 100 + (w - 140) * ww, yy + 52], radius=8, fill=(232, 229, 240, 255))
            yy += 84
        # komentar baru dari "kamu"
        tk = seg(t, 1.0, 1.0 + 0.09 * len(kata))
        n = int(round(len(kata) * tk))
        kirim = t > 1.25 + 0.09 * len(kata)
        if kirim:
            pp = eob(seg(t, 1.25 + 0.09 * len(kata), 1.65 + 0.09 * len(kata)))
            yk = yy + 10 * (1 - pp)
            dc.ellipse([30, yk, 82, yk + 52], fill=UNGU + (255,))
            dc.text((56, yk + 26), "K", font=pop("b", 26), fill=(255, 255, 255, 255), anchor="mm")
            dc.text((100, yk + 2), "kamu", font=pop("b", 24), fill=(20, 18, 30, 255))
            dc.text((100, yk + 30), kata, font=pop("x", 34), fill=UNGU + (255,))
        # kolom ketik di bawah
        by = h - 96
        dc.rounded_rectangle([24, by, w - 24, by + 72], radius=36, fill=(240, 238, 246, 255), outline=(220, 216, 230, 255), width=2)
        teks = kata[:n] if not kirim else ""
        if teks:
            dc.text((58, by + 36), teks, font=pop("b", 32), fill=(20, 18, 30, 255), anchor="lm")
            cx = 58 + UK.textlength(teks, font=pop("b", 32)) + 4
        else:
            dc.text((58, by + 36), "Tambahkan komentar...", font=pop("r", 28), fill=(150, 146, 162, 255), anchor="lm")
            cx = 56
        if (t * 2) % 1 < 0.6 and not kirim:
            dc.line([(cx, by + 18), (cx, by + 54)], fill=UNGU + (255,), width=3)
        dc.ellipse([w - 24 - 64, by + 4, w - 24 - 4, by + 68], fill=(UNGU if teks else (200, 196, 212)) + (255,))
        dc.polygon([(w - 70, by + 22), (w - 70, by + 50), (w - 44, by + 36)], fill=(255, 255, 255, 255))
        sh = bayangan(w, h, 36)
        tempel(fr, sh, x - 50, top - 50, a * 0.9)
        tempel(fr, card, x, top + 40 * (1 - a), a)
        # chip kata kunci melayang
        ti = tag_img(f"KETIK: {kata}", "emas")
        pt = eob(seg(t, 0.6, 1.0))
        tempel(fr, ti, W - X0 - ti.width - 10, top - ti.height / 2 + 6 * math.sin(t * 2.5), seg(t, 0.6, 0.8), 0.5 + 0.5 * pt)

    def sc_daftar(fr, s, t, dur):
        latar(fr, t); kepala(fr, s, t)
        y = chip(fr, s, t, 300)
        y = judul_blok(fr, s, t, y, besar=(104, 94, 84, 76), aksen_sz=(84, 74, 66), maxb=2, aksen_maxb=1)
        items = [str(x) for x in (s.get("items") or [])][:4]
        if not items:
            return
        top = max(y + 30, 560)
        gap = 22
        hh = min(150, int((1130 - top - gap * (len(items) - 1)) / len(items)))
        jarak = min(0.9, max(0.35, (dur - 1.2) / max(1, len(items))))
        for i, it in enumerate(items):
            t0 = 0.45 + i * jarak
            p = eo(seg(t, t0, t0 + 0.4))
            if p <= 0:
                continue
            S = 2
            w = XW
            card = Image.new("RGBA", (w * S, hh * S), (0, 0, 0, 0))
            dc = ImageDraw.Draw(card)
            dc.rounded_rectangle([0, 0, w * S - 1, hh * S - 1], radius=30 * S, fill=(250, 249, 252, 255))
            b = hh - 40
            dc.rounded_rectangle([20 * S, 20 * S, (20 + b) * S, (20 + b) * S], radius=22 * S, fill=EMAS + (255,))
            dc.text(((20 + b / 2) * S, (20 + b / 2 + 2) * S), f"{i + 1:02d}", font=tegak(int(b * 0.5) * S), fill=GELAP + (255,), anchor="mm")
            fsz = 46
            while fsz > 30 and UK.textlength(it, font=pop("b", fsz)) > w - b - 90:
                fsz -= 2
            dc.text(((40 + b + 10) * S, hh / 2 * S), it, font=pop("b", fsz * S), fill=(20, 18, 30, 255), anchor="lm")
            card = card.resize((w, hh), Image.LANCZOS)
            yy = top + i * (hh + gap)
            sh = bayangan(w, hh, 30)
            tempel(fr, sh, X0 - 50 + 60 * (1 - p), yy - 50, p * 0.7)
            tempel(fr, card, X0 + 60 * (1 - p), yy, p)

    for nama, fn in (("ed_judul", sc_judul), ("ed_foto", sc_foto), ("ed_banding", sc_banding), ("ed_situs", sc_situs), ("ed_daftar", sc_daftar),
                     ("ed_angka", sc_angka), ("ed_cta", sc_cta)):
        rm.SCENES[nama] = fn
