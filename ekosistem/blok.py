#!/usr/bin/env python3
"""Blok 'proyek lain dari Nopal Brainwork' yang sama untuk semua situs (sumber: ekosistem.json di akar repo).

Dipakai dua cara:
  1. situs-portal/build.py (Brainwork.id) memanggil html_blok() saat membangun situs.
  2. Perintah di bawah mencetak markup cadangan untuk situs lain (Nopal, NolKaryawan, Skalarium). Markup itu ditempel SEKALI
     di halaman; sesudahnya ekosistem/ekosistem.js menggantinya dengan data terbaru dari ekosistem.json.

  python3 ekosistem/blok.py nopal            # markup untuk link bio Nopal Brainwork
  python3 ekosistem/blok.py skalarium        # dst.: nolkaryawan, brainwork-id

Markup di sini HARUS sama dengan yang dibuat ekosistem.js (kelas eko-*), supaya tidak ada lompatan tampilan.
"""
import html
import json
import sys
from pathlib import Path

CSS_URL = "https://brainwork-cloud.github.io/brainwork-konten/ekosistem/ekosistem.css"
JUDUL_BAWAAN = "Proyek lain dari Nopal Brainwork"
SITUS = ("nopal", "nolkaryawan", "skalarium", "brainwork-id")


def muat(path):
    """Baca dan saring ekosistem.json. Berkas hilang atau rusak = daftar kosong (situs tetap terbit)."""
    try:
        d = json.loads(Path(path).read_text("utf-8"))
    except Exception as e:
        print(f"peringatan: ekosistem.json tidak terbaca ({type(e).__name__}); bagian proyek lain dilewati", file=sys.stderr)
        return {"judul": {}, "proyek": []}
    ok = []
    for p in d.get("proyek", []):
        if not isinstance(p, dict):
            continue
        if not all(isinstance(p.get(k), str) and p[k].strip() for k in ("id", "nama", "deskripsi", "url", "tombol")):
            continue
        if not p["url"].startswith("https://"):
            continue
        a2 = p.get("aksi2")
        if not (isinstance(a2, dict) and str(a2.get("url", "")).startswith("https://") and str(a2.get("teks", "")).strip()):
            p = {k: v for k, v in p.items() if k != "aksi2"}
        ok.append(p)
    j = d.get("judul") if isinstance(d.get("judul"), dict) else {}
    return {"judul": j, "proyek": ok}


def daftar(eko, situs):
    return [p for p in eko["proyek"] if p["id"] != situs]


def judul(eko, situs):
    j = eko["judul"]
    return str(j.get(situs) or j.get("bawaan") or JUDUL_BAWAAN)


def tombol(p, situs):
    """-> [(url, teks, tipis, label)]: tombol utama (emas) dulu. Bila ada aksi tambahan untuk situs ini, aksi itu yang utama.
    label = nilai data-label (untuk hitung klik); aksi2 boleh membawa "label" sendiri."""
    base = "eko-" + p["id"]
    a2 = p.get("aksi2")
    if a2 and (not isinstance(a2.get("hanya_di"), list) or situs in a2["hanya_di"]):
        return [(a2["url"], a2["teks"], False, str(a2.get("label") or base + "-2")), (p["url"], p["tombol"], True, base)]
    return [(p["url"], p["tombol"], False, base)]


def html_blok(eko, situs, link_css=True):
    """Markup <section class="eko"> lengkap (sama dengan hasil ekosistem.js). Kosong bila tidak ada proyek untuk ditampilkan."""
    ps = daftar(eko, situs)
    if not ps:
        return ""
    e = html.escape
    kartu = []
    for p in ps:
        bag = []
        if p.get("jenis"):
            bag.append(f'<p class="eko-jenis">{e(p["jenis"])}</p>')
        bag.append(f'<h3>{e(p["nama"])}</h3><p class="eko-isi">{e(p["deskripsi"])}</p>')
        cat = p.get("catatan")
        if isinstance(cat, dict) and cat.get(situs):
            bag.append(f'<p class="eko-isi eko-catatan">{e(str(cat[situs]))}</p>')
        tb = "".join(
            f'<a class="eko-tombol{" tipis" if tipis else ""}" href="{e(u, quote=True)}" data-label="{e(lb, quote=True)}">{e(t)}</a>'
            for u, t, tipis, lb in tombol(p, situs))
        bag.append(f'<div class="eko-aksi">{tb}</div>')
        kartu.append(f'<li class="eko-kartu">{"".join(bag)}</li>')
    css = f'<link rel="stylesheet" href="{CSS_URL}">' if link_css else ""
    return (f'<section class="eko" data-ekosistem="{e(situs)}" aria-labelledby="eko-judul-{e(situs)}">{css}'
            f'<h2 class="eko-judul" id="eko-judul-{e(situs)}">{e(judul(eko, situs))}</h2>'
            f'<ul class="eko-daftar">{"".join(kartu)}</ul></section>')


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SITUS:
        sys.exit("pakai: python3 ekosistem/blok.py <" + "|".join(SITUS) + ">")
    akar = Path(__file__).resolve().parent.parent
    print(html_blok(muat(akar / "ekosistem.json"), sys.argv[1]))
