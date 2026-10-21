#!/usr/bin/env python3
"""Buat ikon dan gambar OG Brainwork.id (sekali jalan; hasilnya disimpan di brainwork-id/aset/). Butuh Pillow dan font Poppins."""
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path(sys.argv[1] if len(sys.argv) > 1 else "situs-portal/ikon")
out.mkdir(parents=True, exist_ok=True)
UNGU, EMAS, MALAM, PUTIH, REDUP = (123, 47, 190), (245, 193, 7), (10, 10, 15), (246, 243, 251), (185, 175, 204)


def font(w, n):
    for d in (os.environ.get("FONTS", "fonts"), "/usr/share/fonts/truetype/google-fonts"):
        p = Path(d) / f"Poppins-{w}.ttf"
        if p.exists():
            return ImageFont.truetype(str(p), n)
    raise SystemExit("font Poppins tidak ditemukan")


def mark(size):
    S = 4
    im = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size * S - 1, size * S - 1), radius=int(size * S * 15 / 64), fill=UNGU)
    k = size * S / 64
    tri = [(32 * k, 17 * k), (48 * k, 46 * k), (16 * k, 46 * k)]
    d.polygon(tri, fill=EMAS)
    d.line(tri + [tri[0]], fill=EMAS, width=int(4 * k), joint="curve")
    for x, y in tri:
        d.ellipse((x - 2 * k, y - 2 * k, x + 2 * k, y + 2 * k), fill=EMAS)
    return im.resize((size, size), Image.LANCZOS)


for n, sz in (("favicon.png", 64), ("apple-touch-icon.png", 180), ("logo-512.png", 512)):
    mark(sz).save(out / n)
(out / "favicon.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="15" fill="#7B2FBE"/>'
    '<path d="M32 17 48 46H16Z" fill="#F5C107" stroke="#F5C107" stroke-width="4" stroke-linejoin="round"/></svg>\n', "utf-8")

# OG 1200x630
W, H = 1200, 630
im = Image.new("RGB", (W, H), MALAM)
d = ImageDraw.Draw(im)
for x in range(0, W, 90):
    d.line((x, 0, x, H), fill=(22, 18, 36))
for y in range(0, H, 90):
    d.line((0, y, W, y), fill=(22, 18, 36))
im.paste(mark(120), (90, 150), mark(120))
f1, f2 = font("ExtraBold", 92), font("SemiBold", 40)
d.text((240, 150), "Brainwork", font=f1, fill=PUTIH)
w = d.textlength("Brainwork", font=f1)
d.text((240 + w, 150), ".id", font=f1, fill=EMAS)
d.text((90, 330), "Kabar marketing dan AI untuk", font=f2, fill=PUTIH)
d.text((90, 385), "advertiser dan pelaku usaha di Indonesia", font=f2, fill=PUTIH)
d.rectangle((0, H - 14, W, H), fill=UNGU)
im.save(out / "og.png", optimize=True)
print("ikon dibuat di", out)
