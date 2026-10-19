#!/usr/bin/env python3
"""
Foto latar konten portal Brainwork.id (gaya referensi: foto berita redup + gradasi gelap + judul di atas foto).
Keputusan Naufal 19 Okt 2026: foto diambil dari artikel sumber (gambar utama/og:image), dengan kredit "Foto: <nama>" di
gambar dan caption. Risiko hak cipta ditanggung keputusan itu; foto yang buruk atau tak bisa diunduh otomatis diganti
ilustrasi (portal_art.py), jadi render tidak pernah gagal karena foto.

spec["foto"] = {"url": "https://.../gambar.jpg", "kredit": "TechCrunch"}      # diunduh saat render (Actions punya internet)
               {"file": "preview/contoh.jpg", "kredit": "..."}                 # berkas lokal (uji)
Syarat lolos: kredit terisi, bisa dibuka sebagai gambar, sisi terpendek >= 560 px, sisi terpanjang >= 900 px,
bukan gambar hampir polos (logo/latar rata), dan pembesaran ke area kartu <= 2,1x (kalau lebih, hasilnya terlalu buram).
"""
import io, os
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

UA = "Mozilla/5.0 (compatible; BrainworkBot/1.0; +https://brainwork.id)"
BG = (10, 8, 20)
MAX_BYTES = 15_000_000


def ambil(f, tw, th):
    """f = spec['foto'] (dict). -> (PIL.Image RGB atau None, pesan)."""
    if not isinstance(f, dict):
        return None, "spec foto bukan objek"
    if not (f.get("kredit") or "").strip():
        return None, "kredit foto kosong (wajib)"
    try:
        if f.get("file"):
            data = open(f["file"], "rb").read()
        elif f.get("url"):
            import requests
            r = requests.get(f["url"], headers={"User-Agent": UA, "Accept": "image/avif,image/webp,image/*;q=0.8"},
                             timeout=30, stream=True)
            r.raise_for_status()
            ct = (r.headers.get("content-type") or "").lower()
            if ct and not ct.startswith("image/"):
                return None, f"bukan gambar ({ct[:40]})"
            data = r.raw.read(MAX_BYTES + 1, decode_content=True)
            if len(data) > MAX_BYTES:
                return None, "berkas lebih dari 15 MB"
        else:
            return None, "tidak ada url atau file"
        im = Image.open(io.BytesIO(data))
        im.load()
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception as e:  # unduhan gagal, bukan gambar, format tak didukung, dsb.
        return None, f"gagal memuat: {type(e).__name__}: {str(e)[:120]}"
    w, h = im.size
    if min(w, h) < 560 or max(w, h) < 900:
        return None, f"terlalu kecil ({w}x{h})"
    small = np.asarray(im.convert("L").resize((64, 64)), dtype=float)
    if small.std() < 12:
        return None, "hampir polos (kemungkinan logo atau latar rata)"
    up = max(tw / w, th / h)
    if up > 2.1:
        return None, f"pembesaran {up:.1f}x terlalu besar untuk {w}x{h}"
    return im, f"ok {w}x{h}, pembesaran {up:.2f}x"


def latar(im, w, h, focus=(0.5, 0.4), zoom=1.0, sat=0.35, gelap=0.0, blur=0.0):
    """Potong gaya 'cover' ke w x h, kurangi warna, gelapkan (campur dengan warna latar) dan kaburkan bila perlu."""
    iw, ih = im.size
    sc = max(w / iw, h / ih) * zoom
    vw, vh = w / sc, h / sc
    cx = min(max(focus[0] * iw, vw / 2), iw - vw / 2)
    cy = min(max(focus[1] * ih, vh / 2), ih - vh / 2)
    out = im.resize((int(w), int(h)), Image.LANCZOS, box=(cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2))
    if blur:
        out = out.filter(ImageFilter.GaussianBlur(blur))
    out = ImageEnhance.Color(out).enhance(sat)
    out = ImageEnhance.Contrast(out).enhance(1.06)
    if gelap:
        out = Image.blend(out, Image.new("RGB", out.size, BG), gelap)
    return out


def mask(w, h, y0, y1, a0, a1):
    """Mask L (0-255): alpha a0 di y0 menuju a1 di y1 (halus), konstan di luar rentang."""
    ys = np.clip((np.arange(h) - y0) / max(1.0, (y1 - y0)), 0, 1)
    ys = ys * ys * (3 - 2 * ys)
    col = (a0 + (a1 - a0) * ys) * 255
    return Image.fromarray(np.repeat(col[:, None], w, axis=1).astype("uint8"), "L")


def gradasi(img, y0, y1, a0, a1, box=None):
    """Tempel warna latar gelap dengan alpha bergradasi pada seluruh lebar (box=(x0,y0,x1,y1) opsional)."""
    x0, ya, x1, yb = box or (0, 0, img.width, img.height)
    m = mask(x1 - x0, yb - ya, y0 - ya, y1 - ya, a0, a1)
    img.paste(Image.new("RGB", m.size, BG), (x0, ya), m)
