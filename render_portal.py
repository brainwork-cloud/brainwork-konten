#!/usr/bin/env python3
"""
Renderer kartu berita Brainwork.id (portal media, produksi sendiri, terpisah dari @nopal.brainwork)
Pemakaian:  python3 render_portal.py portal/<ID>.json [folder_output]
Hasil:      <folder_output>/<ID>.jpg  (1080x1350, 4:5) + cetak JSON {"file": ...}

Format portal/<ID>.json:
{
  "id": "PT-261020-01",
  "kategori": "IKLAN",                       # label kecil (IKLAN, MEDIA SOSIAL, AI, E-COMMERCE, PLATFORM, REGULASI)
  "judul": "Meta uji **iklan video** otomatis dari foto produk",   # judul berita, **kata penting** berwarna emas, maks ~16 kata
  "ringkas": ["Fitur tersedia umum di Ads Manager.", "Pengiklan bisa mengubah gambar jadi video."],   # 1-3 poin, tiap poin satu kalimat
  "sumber": "Meta for Business",             # nama sumber utama
  "tanggal": "20 Okt 2026",                  # tanggal berita
  "caption": "teks postingan Facebook"       # dipakai agen redaktur untuk antrian, tidak digambar
}
Gaya media netral: tanpa aku/kamu, tanpa wajah, tanpa nama pribadi.
"""
import sys, os, json
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_carousel import (font, wrap_rich, draw_rich, fit, pill, W, H, M, BG, BG2, PURPLE, PURPLE_D,
                             PURPLE_L, GRID, GOLD, WHITE, MUTE)

FOOT = 190  # tinggi footer


def base():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for yy in range(0, 620):
        a = 1 - yy / 620
        d.line([(0, yy), (W, yy)], fill=tuple(int(BG[i] + (BG2[i] - BG[i]) * a) for i in range(3)))
    for gx in range(0, W, 90):
        d.line([(gx, 0), (gx, H - FOOT)], fill=GRID, width=1)
    for gy in range(0, H - FOOT, 90):
        d.line([(0, gy), (W, gy)], fill=GRID, width=1)
    d.rectangle([0, H - FOOT, W, H], fill=(8, 6, 16))
    d.rectangle([0, H - FOOT, W, H - FOOT + 4], fill=PURPLE)
    return img, d


def wordmark(d, x, y):
    d.rounded_rectangle([x, y, x + 52, y + 52], radius=12, fill=PURPLE)
    d.polygon([(x + 14, y + 36), (x + 26, y + 12), (x + 38, y + 36)], fill=GOLD)
    f1, f2 = font("black", 38), font("black", 38)
    tx = x + 70
    d.text((tx, y + 26), "BRAINWORK", font=f1, fill=WHITE, anchor="lm")
    d.text((tx + d.textlength("BRAINWORK", font=f1), y + 26), ".ID", font=f2, fill=GOLD, anchor="lm")


def render(spec, out_path):
    img, d = base()
    wordmark(d, M, 64)
    d.text((W - M, 90), spec.get("tanggal", ""), font=font("semi", 30), fill=MUTE, anchor="rm")
    y = 200
    y = pill(d, M, y, spec.get("kategori", "BERITA").upper(), font("bold", 30)) + 46
    tf = fit(d, spec["judul"], "black", [84, 76, 70, 64, 58, 52], W - 2 * M, 4)
    y = draw_rich(d, M, y, spec["judul"], tf, W - 2 * M, lh=1.13) + 34
    d.rounded_rectangle([M, y, M + 170, y + 12], radius=6, fill=GOLD)
    y += 62
    bf = font("reg", 42)
    limit = H - FOOT - 50
    for b in spec.get("ringkas", [])[:3]:
        lines = wrap_rich(d, b, bf, W - 2 * M - 52)
        need = len(lines) * int(42 * 1.32) + 28
        if y + need > limit:
            break
        d.regular_polygon((M + 12, y + 30, 12), 4, fill=GOLD)
        y = draw_rich(d, M + 52, y, b, bf, W - 2 * M - 52, color=(226, 220, 240), lh=1.32) + 28
    fy = H - FOOT + 46
    d.text((M, fy), "SUMBER", font=font("bold", 24), fill=PURPLE_L)
    sf = fit(d, spec.get("sumber", ""), "bold", [40, 36, 32, 28], W - 2 * M - 300, 1)
    d.text((M, fy + 40), spec.get("sumber", ""), font=sf, fill=WHITE)
    d.text((W - M, fy + 64), "brainwork.id", font=font("semi", 30), fill=PURPLE_L, anchor="rm")
    img.save(out_path, "JPEG", quality=90, optimize=True)


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", spec["id"])
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, f"{spec['id']}.jpg")
    render(spec, p)
    print(json.dumps({"file": p}))


if __name__ == "__main__":
    main()
