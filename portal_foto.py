#!/usr/bin/env python3
"""
Foto latar konten portal Brainwork.id (gaya referensi: foto berita redup + gradasi gelap + judul di atas foto).
Keputusan Naufal 19 Okt 2026: foto diambil dari artikel sumber (gambar utama/og:image), dengan kredit "Foto: <nama>" di
gambar dan caption. Risiko hak cipta ditanggung keputusan itu; foto yang buruk atau tak bisa diunduh otomatis diganti
ilustrasi (portal_art.py), jadi render tidak pernah gagal karena foto.

spec["foto"] = {"url": "https://.../gambar.jpg", "kredit": "TechCrunch"}      # diunduh saat render (Actions punya internet)
               {"url": "https://images.unsplash.com/photo-...", "kredit": "Nama Fotografer / Unsplash", "jenis": "stok"}
                                                                               # foto stok berlisensi bebas; tercetak "Foto ilustrasi: ..." supaya tidak dikira foto kejadian aslinya
               {"file": "preview/contoh.jpg", "kredit": "..."}                 # berkas lokal (uji)
STANDAR FOTO WAJIB (keputusan Naufal 22 Okt 2026, "apa pun alasannya konten harus berfoto"): foto yang tidak lolos di atas TIDAK lagi membuat
konten polos/ilustrasi. Renderer otomatis memakai foto cadangan dari foto_cadangan.json (kolam foto stok Unsplash yang sudah dipilih manual),
dipilih menurut kata kunci topik konten (cadangan() di bawah), dan baris kredit konten otomatis mengikuti foto yang benar-benar tampil.
Di GitHub Actions render GAGAL (bukan polos) bila tidak ada satu foto pun yang bisa tampil; render lokal (sandbox tanpa internet ke Unsplash) tetap
jalan polos supaya QA tata letak bisa dilakukan, set FOTO_LONGGAR=1 untuk melonggarkan juga di Actions.
Syarat lolos: kredit terisi, bisa dibuka sebagai gambar, sisi terpendek >= 560 px, sisi terpanjang >= 900 px,
bukan gambar hampir polos (logo/latar rata) atau tangkapan layar/grafik antarmuka (>30% piksel hampir putih), dan pembesaran ke area kartu <= 2,1x (kalau lebih, hasilnya terlalu buram).
"""
import io, json, os, re, time, zlib
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

UA = "Mozilla/5.0 (compatible; BrainworkBot/1.0; +https://brainwork.id)"
BG = (10, 8, 20)
MAX_BYTES = 15_000_000
KOLAM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "foto_cadangan.json")
_KOLAM = None


def wajib():
    """True bila foto WAJIB tampil (render di GitHub Actions): tanpa foto = render gagal, bukan polos."""
    return os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("FOTO_LONGGAR") != "1"


def kolam():
    """Daftar foto cadangan (foto_cadangan.json). Kosong bila berkas hilang/rusak (jangan gagalkan render)."""
    global _KOLAM
    if _KOLAM is None:
        try:
            _KOLAM = [d for d in json.load(open(KOLAM, encoding="utf-8")).get("foto", [])
                      if isinstance(d, dict) and d.get("url") and (d.get("kredit") or "").strip()]
        except Exception as e:
            print(f"peringatan: kolam foto cadangan gagal dibaca: {type(e).__name__}: {e}", file=__import__("sys").stderr)
            _KOLAM = []
    return _KOLAM


def teks_spec(obj, _skip=("foto", "url", "kredit", "file")):
    """Gabungkan semua nilai teks di spec (judul, poin, slide, scene, caption) jadi satu string huruf kecil untuk mencocokkan topik."""
    out = []
    def walk(o):
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in _skip:
                    walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
    walk(obj)
    return " ".join(out).lower()


def cadangan(teks="", seed="", hindari=()):
    """Foto cadangan terurut dari yang paling cocok dengan topik `teks` (jumlah kata kunci 'tema' yang muncul, per kata utuh);
    seri skor sama diurutkan stabil menurut `seed` (ID konten), jadi hasilnya sama tiap render tetapi bergilir antar konten.
    `hindari` = URL/kunci foto yang tak boleh dipilih (sudah dipakai atau sudah gagal). Mengembalikan salinan dict siap pakai."""
    teks = (teks or "").lower()
    hasil = []
    for d in kolam():
        if d["url"] in hindari:
            continue
        skor = sum(1 for k in d.get("tema", []) if re.search(r"(?<![a-z0-9])" + re.escape(k.lower()) + r"(?![a-z0-9])", teks))
        hasil.append((-skor, zlib.crc32((str(seed) + d.get("id", d["url"])).encode()), d))
    hasil.sort(key=lambda x: (x[0], x[1]))
    return [{k: v for k, v in d.items() if k in ("url", "kredit", "jenis", "fokus")} for _, _, d in hasil]


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
            r = None
            for coba in range(3):    # gangguan jaringan sesaat atau 5xx: ulangi (404/403 tidak diulang)
                try:
                    r = requests.get(f["url"], headers={"User-Agent": UA, "Accept": "image/avif,image/webp,image/*;q=0.8"},
                                     timeout=30, stream=True)
                    if r.status_code < 500 and r.status_code != 429:
                        break
                except (requests.ConnectionError, requests.Timeout):
                    if coba == 2:
                        raise
                time.sleep(2 * (coba + 1))
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
        im = ImageOps.exif_transpose(im)
        if im.mode in ("P", "LA", "RGBA", "PA"):       # transparansi: letakkan di atas latar gelap, bukan hitam/putih acak
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, BG + (255,))
            im = Image.alpha_composite(bg, im)
        im = im.convert("RGB")
    except Exception as e:  # unduhan gagal, bukan gambar, format tak didukung, dsb.
        return None, f"gagal memuat: {type(e).__name__}: {str(e)[:120]}"
    w, h = im.size
    if min(w, h) < 560 or max(w, h) < 900:
        return None, f"terlalu kecil ({w}x{h})"
    small = np.asarray(im.convert("L").resize((64, 64)), dtype=float)
    if small.std() < 12:
        return None, "hampir polos (kemungkinan logo atau latar rata)"
    g = np.asarray(im.convert("L").resize((96, 96)), dtype=float)
    if (g > 235).mean() > 0.30:
        return None, "tampak tangkapan layar/grafik antarmuka (banyak area putih), bukan foto berita"
    up = max(tw / w, th / h)
    if up > 2.1:
        return None, f"pembesaran {up:.1f}x terlalu besar untuk {w}x{h}"
    return im, f"ok {w}x{h}, pembesaran {up:.2f}x"


def latar(im, w, h, focus=(0.5, 0.4), zoom=1.0, sat=0.35, gelap=0.0, blur=0.0):
    """Potong gaya 'cover' ke w x h, kurangi warna, gelapkan (campur dengan warna latar) dan kaburkan bila perlu."""
    iw, ih = im.size
    sc = max(w / iw, h / ih) * max(1.0, zoom)          # zoom < 1 membuat kotak potong melebihi foto -> galat PIL; batasi
    vw, vh = min(w / sc, iw), min(h / sc, ih)
    x0 = min(max(focus[0] * iw - vw / 2, 0.0), iw - vw)
    y0 = min(max(focus[1] * ih - vh / 2, 0.0), ih - vh)
    out = im.resize((int(w), int(h)), Image.LANCZOS, box=(x0, y0, x0 + vw, y0 + vh))
    if blur:
        out = out.filter(ImageFilter.GaussianBlur(blur))
    out = ImageEnhance.Color(out).enhance(sat)
    out = ImageEnhance.Contrast(out).enhance(1.06)
    if gelap:
        out = Image.blend(out, Image.new("RGB", out.size, BG), gelap)
    return out


def terang(im):
    """Kecerahan rata-rata foto (0-255), dipakai menggelapkan foto yang terlalu terang supaya teks putih tetap terbaca."""
    return float(np.asarray(im.convert("L").resize((48, 48)), dtype=float).mean())


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
