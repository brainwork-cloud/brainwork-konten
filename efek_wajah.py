#!/usr/bin/env python3
"""
Efek wajah untuk Reels Talking Head @nopal.brainwork (dipanggil edit_reel.py).

Hanya bekerja di bagian video yang wajahnya tampil (di luar cover/sisipan). Subtitle dan teks hook dibakar SESUDAH
efek ini, jadi tidak ikut membesar.
  1. Zoom pelan: kamera maju pelan di pembuka, mundur pelan di penutup.
  2. Snap zoom: zoom cepat pada kata penting, ditahan sebentar, lalu kembali.
  3. Gelembung chat pop-up: pesan singkat muncul di pojok kanan atas lalu hilang.

Spec edits/<ID>.json (opsional; tanpa "efek_wajah" video dirender seperti biasa):
  "efek_wajah": {
    "zoom": true,                          # zoom pelan (default true)
    "snap": ["gratis", "Simpan"],          # kata pemicu snap zoom: "kata", "dua kata", atau "kata#2" (kemunculan ke-2).
                                           #   Default: kata highlight_words pertama yang diucapkan di pembuka. [] = tanpa snap.
    "chat": [{"from_word": "gratis", "teks": "Serius gratis?", "dari": "kamu", "dur": 2.4}],   # atau "at": detik (waktu video akhir)
    "fokus": [0.5, 0.4]                    # titik tengah zoom (relatif lebar, tinggi layar); default wajah selfie
  }
Aturan gelembung chat: pengirim hanya "kamu" (pertanyaan/reaksi penonton yang dibayangkan), "AI", atau "Nopal".
Bukan nama atau akun orang sungguhan dan bukan testimoni. Teks maks ±8 kata, tanpa emoji (font tidak memuat emoji).
"""
import math
import os
import re
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
UNGU, EMAS, HITAM = (123, 47, 190), (245, 193, 7), (10, 10, 15)

DORONG = 0.08        # zoom pelan pembuka: 1,00 -> 1,08
TARIK = 0.08         # zoom pelan penutup: 1,08 -> 1,00
SNAP = 0.14          # snap zoom menambah 14%
HOOK_SAMPAI = 3.0    # teks hook (banner atas) tampil 0-3 dtk; gelembung tidak boleh bertabrakan dengannya
PENGIRIM = {"kamu": "kamu", "ai": "AI", "nopal": "Nopal"}


def _font(nama, ukuran):
    for f in (nama, "Poppins-Bold.ttf"):
        p = os.path.join(FONTS, f)
        if os.path.exists(p):
            return ImageFont.truetype(p, ukuran)
    return ImageFont.load_default()


def _halus(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _keluar(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def _pantul(x, k=1.7):
    x = min(1.0, max(0.0, x)) - 1
    return 1 + (k + 1) * x ** 3 + k * x ** 2


def tanpa_emoji(s):
    return re.sub("[\U0001F000-\U0001FAFF☀-➿️‍⬀-⯿]", "", s or "").strip()


def jendela_wajah(main_len, cuts):
    """Rentang waktu (video akhir sebelum penutup) yang wajahnya tampil = di luar cover/sisipan."""
    tutup = sorted((float(c[0]), float(c[0]) + float(c[1])) for c in cuts)
    out, t = [], 0.0
    for a, b in tutup:
        if a > t + 0.05:
            out.append((t, min(a, main_len)))
        t = max(t, b)
    if main_len > t + 0.05:
        out.append((t, main_len))
    return [(a, b) for a, b in out if b - a >= 0.3]


def _rentang_kata(words, akhir):
    for w in words:
        if abs(w["e"] - akhir) < 1e-6:
            return w["s"], w["e"]
    return akhir - 0.25, akhir


def _di_jendela(t, jendela, sisa=0.0):
    return next(((a, b) for a, b in jendela if a <= t <= b - sisa), None)


def rencana(spec, words, main_len, cuts, cari_akhir):
    """-> (rencana efek, peringatan). cari_akhir = edit_reel.find_word_end."""
    ew = spec.get("efek_wajah")
    if not ew:
        return None, []
    ew = ew if isinstance(ew, dict) else {}
    warns = []
    jendela = jendela_wajah(main_len, cuts)
    if not jendela:
        return None, ["efek_wajah: wajah tidak pernah tampil (seluruh video tertutup cover), efek dilewati"]
    fx, fy = (ew.get("fokus") or [0.5, 0.4])[:2]
    plan = {"jendela": jendela, "fokus": (min(0.9, max(0.1, float(fx))), min(0.9, max(0.1, float(fy)))),
            "kunci": [], "snap": [], "chat": [], "catatan": []}

    # 1. zoom pelan: titik kunci (waktu, faktor), diinterpolasi halus; di bagian tertutup cover perubahan tidak terlihat
    if ew.get("zoom", True):
        a0, b0 = jendela[0]
        if len(jendela) == 1:
            L = b0 - a0
            k = [(a0, 1.0), (a0 + min(6.0, L / 3), 1 + DORONG)]
            if L >= 10:
                k += [(b0 - min(4.0, L / 4), 1 + DORONG), (b0, 1.0)]
        else:
            k = [(a0, 1.0), (a0 + min(6.0, b0 - a0), 1 + DORONG)]
            c0, c1 = jendela[-1]
            mulai = max(k[-1][0] + 0.01, c0 - 0.25)   # mulai sedikit sebelum cover terakhir selesai memudar
            k += [(mulai, 1 + TARIK), (c1, 1.0)]
        plan["kunci"] = k
        plan["catatan"].append("zoom pelan: " + ", ".join(f"{a:.1f}-{b:.1f} dtk" for a, b in jendela))

    # 2. snap zoom
    if "snap" in ew:
        pemicu = [str(x) for x in (ew.get("snap") or [])]
    else:   # default: kata highlight pertama yang diucapkan di bagian wajah pembuka
        hl = [h.lower() for h in spec.get("highlight_words") or []]
        a0, b0 = jendela[0]
        pertama = next((w for w in words if a0 <= w["s"] <= b0 - 0.6 and re.sub(r"[^\w]", "", w["w"].lower()) in hl), None)
        pemicu = [pertama["w"].strip(".,?!")] if pertama else []
    for p in pemicu[:4]:
        akhir = cari_akhir(words, p)
        if akhir is None:
            warns.append(f"efek_wajah: kata snap '{p}' tidak ketemu di transkrip, dilewati")
            continue
        s, e = _rentang_kata(words, akhir)
        j = _di_jendela(s, jendela, 0.5)
        if not j:
            warns.append(f"efek_wajah: kata snap '{p}' ({s:.1f} dtk) jatuh di bagian yang tertutup cover, dilewati")
            continue
        tahan = max(s + 0.1, min(max(s + 0.45, e + 0.15), j[1] - 0.32))
        plan["snap"].append((s, tahan))
        plan["catatan"].append(f"snap zoom '{p}' {s:.1f} dtk")

    # 3. gelembung chat
    hook_tampil = bool(spec.get("hook")) and not spec.get("_hook_di_kartu")
    for c in (ew.get("chat") or [])[:3]:
        teks = tanpa_emoji(str(c.get("teks") or ""))
        if not teks:
            continue
        dari = PENGIRIM.get(str(c.get("dari") or "kamu").strip().lower(), "kamu")
        t0 = c.get("at")
        if t0 is None and c.get("from_word"):
            akhir = cari_akhir(words, c["from_word"])
            if akhir is None:
                warns.append(f"efek_wajah: kata pemicu chat '{c['from_word']}' tidak ketemu, dilewati")
                continue
            t0 = akhir + 0.1
        if t0 is None:
            warns.append("efek_wajah: item chat tanpa 'from_word' atau 'at', dilewati")
            continue
        t0 = float(t0)
        if hook_tampil and t0 < HOOK_SAMPAI + 0.05:
            warns.append(f"efek_wajah: chat '{teks[:24]}' digeser dari {t0:.1f} ke {HOOK_SAMPAI + 0.05:.1f} dtk (bertabrakan dengan teks hook)")
            t0 = HOOK_SAMPAI + 0.05
        dur = min(4.0, max(1.2, float(c.get("dur", 2.4))))
        j = _di_jendela(t0, jendela)
        if not j or j[1] - t0 < 1.0:
            warns.append(f"efek_wajah: chat '{teks[:24]}' ({t0:.1f} dtk) tidak muat di bagian wajah, dilewati")
            continue
        t1 = min(t0 + dur, j[1] - 0.05)
        plan["chat"].append((t0, t1, dari, teks))
        plan["catatan"].append(f"chat {t0:.1f}-{t1:.1f} dtk dari {dari}: {teks}")
    return plan, warns


def faktor_zoom(plan, t):
    z = 1.0
    k = plan["kunci"]
    if k:
        if t <= k[0][0]:
            z = k[0][1]
        elif t >= k[-1][0]:
            z = k[-1][1]
        else:
            for (ta, za), (tb, zb) in zip(k, k[1:]):
                if ta <= t <= tb:
                    z = za + (zb - za) * _halus((t - ta) / max(1e-6, tb - ta))
                    break
    for s, tahan in plan["snap"]:
        if s - 0.09 <= t < s:
            z += SNAP * _keluar((t - (s - 0.09)) / 0.09)
        elif s <= t < tahan:
            z += SNAP
        elif tahan <= t < tahan + 0.3:
            z += SNAP * (1 - _halus((t - tahan) / 0.3))
    return z


def gambar_gelembung(dari, teks):
    """Gelembung chat (RGBA, digambar 2x lalu diperkecil supaya tepi halus) + titik jangkar ekor (kiri bawah)."""
    S = 2
    fn, fm, fa = _font("Poppins-SemiBold.ttf", 32 * S), _font("Poppins-Bold.ttf", 52 * S), _font("Poppins-Bold.ttf", 21 * S)
    tmp = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    maks = 600 * S
    kata, baris, cur = teks.split(), [], ""
    for k in kata:
        uji = (cur + " " + k).strip()
        if tmp.textlength(uji, font=fm) > maks and cur:
            baris.append(cur)
            cur = k
        else:
            cur = uji
    if cur:
        baris.append(cur)
    if len(baris) > 2:
        baris = baris[:2]
        while tmp.textlength(baris[1] + "...", font=fm) > maks and len(baris[1]) > 1:
            baris[1] = baris[1][:-1]
        baris[1] = baris[1].rstrip() + "..."
    px, pt, pb, lh = 32 * S, 20 * S, 24 * S, 64 * S
    av = 36 * S
    lebar_isi = max([tmp.textlength(b, font=fm) for b in baris] + [av + 12 * S + tmp.textlength(dari, font=fn)])
    bw = int(lebar_isi + 2 * px)
    bh = int(pt + 40 * S + 4 * S + lh * len(baris) + pb)
    m = 40 * S                 # ruang untuk bayangan dan ekor
    im = Image.new("RGBA", (bw + 2 * m, bh + 2 * m), (0, 0, 0, 0))
    x0, y0 = m, m
    ekor = [(x0 + 30 * S, y0 + bh - 6 * S), (x0 + 6 * S, y0 + bh + 26 * S), (x0 + 74 * S, y0 + bh - 6 * S)]
    bayang = Image.new("L", im.size, 0)
    db = ImageDraw.Draw(bayang)
    db.rounded_rectangle([x0, y0 + 10 * S, x0 + bw, y0 + bh + 10 * S], radius=34 * S, fill=120)
    db.polygon([(x, y + 10 * S) for x, y in ekor], fill=120)
    bayang = bayang.filter(ImageFilter.GaussianBlur(14 * S))
    im.paste((0, 0, 0, 255), (0, 0), bayang)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=34 * S, fill=UNGU + (250,))
    d.polygon(ekor, fill=UNGU + (250,))
    # baris pengirim: lingkaran emas berisi huruf awal + nama
    cy = y0 + pt + 20 * S
    d.ellipse([x0 + px, cy - av / 2, x0 + px + av, cy + av / 2], fill=EMAS + (255,))
    d.text((x0 + px + av / 2, cy), dari[:1].upper(), font=fa, fill=HITAM + (255,), anchor="mm")
    d.text((x0 + px + av + 12 * S, cy), dari, font=fn, fill=EMAS + (255,), anchor="lm")
    y = y0 + pt + 44 * S
    for b in baris:
        d.text((x0 + px, y), b, font=fm, fill=(255, 255, 255, 255))
        y += lh
    im = im.resize((im.width // S, im.height // S), Image.LANCZOS)
    jangkar = (int((x0 + 6 * S) / S), int((y0 + bh + 26 * S) / S))   # ujung ekor
    return im, jangkar


def _tempel_gelembung(fr, g, t, t0, t1):
    img, (ax, ay) = g
    u = t - t0
    sisa = t1 - t
    skala = 0.3 + 0.7 * _pantul(u / 0.30)
    alfa = min(1.0, u / 0.12)
    if sisa < 0.22:
        k = max(0.0, sisa / 0.22)
        alfa *= k
        skala *= 0.92 + 0.08 * k
    if alfa <= 0.01 or skala <= 0.05:
        return
    melayang = -4 * math.sin(2 * math.pi * 0.6 * u)
    w2, h2 = max(1, int(img.width * skala)), max(1, int(img.height * skala))
    g2 = img.resize((w2, h2), Image.BILINEAR)
    if alfa < 0.999:
        a = g2.getchannel("A").point(lambda v: int(v * alfa))
        g2.putalpha(a)
    # posisi: kanan atas (di bawah area UI aplikasi), jangkar ekor tetap di tempat selama animasi pop
    x_kanan, y_atas = W - 44, 236
    tx = x_kanan - img.width + ax          # titik ekor saat skala 1
    ty = y_atas + ay
    fr.alpha_composite(g2, (int(tx - ax * skala), int(ty - ay * skala + melayang)))


def terapkan(plan, src, dst):
    """Baca src (main.mp4: wajah + audio), terapkan zoom dan gelembung frame demi frame, tulis dst (audio disalin)."""
    fx, fy = plan["fokus"]
    gel = [(t0, t1, gambar_gelembung(dari, teks)) for t0, t1, dari, teks in plan["chat"]]
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264",
                            "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", dst],
                           stdin=subprocess.PIPE)
    n, ukuran, diubah = 0, W * H * 3, 0
    try:
        while True:
            buf = dec.stdout.read(ukuran)
            if len(buf) < ukuran:
                break
            t = n / FPS
            z = faktor_zoom(plan, t)
            aktif = [g for g in gel if g[0] <= t <= g[1]]
            wajah = any(a - 0.3 <= t <= b + 0.3 for a, b in plan["jendela"])   # di bawah cover tidak perlu diubah
            if (z > 1.0005 and wajah) or aktif:
                fr = Image.frombuffer("RGB", (W, H), buf, "raw", "RGB", 0, 1)
                if z > 1.0005 and wajah:
                    x0, y0 = fx * W * (1 - 1 / z), fy * H * (1 - 1 / z)
                    fr = fr.transform((W, H), Image.AFFINE, (1 / z, 0, x0, 0, 1 / z, y0), resample=Image.BICUBIC)
                if aktif:
                    fr = fr.convert("RGBA")
                    for t0, t1, g in aktif:
                        _tempel_gelembung(fr, g, t, t0, t1)
                    fr = fr.convert("RGB")
                buf = fr.tobytes()
                diubah += 1
            enc.stdin.write(buf)
            n += 1
    finally:
        enc.stdin.close()
        dec.stdout.close()
        dec.wait()
        enc.wait()
    if enc.returncode != 0 or n == 0:
        raise RuntimeError(f"efek_wajah: encode gagal (kode {enc.returncode}, {n} frame)")
    return n, diubah
