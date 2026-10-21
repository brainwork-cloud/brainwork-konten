#!/usr/bin/env python3
"""
Foto latar untuk konten @nopal.brainwork: carousel, Reels Motion, dan cover Talking Head.
Standar foto (keputusan Naufal 21 Okt 2026, sama dengan portal Brainwork.id): foto relevan berkredit sebagai latar redup,
teks di atasnya, dan render tidak pernah gagal karena foto (foto yang buruk atau gagal diunduh = tampilan polos seperti biasa).

Field `foto` boleh ada di slide carousel (cover, point, list, statement, cta) dan di scene video (hook, stat, points,
statement, icon, flow, steps, vs; bukan ui, mock, end). Bentuknya sama dengan portal (portal_foto.py):
  {"url": "https://images.unsplash.com/photo-...?fm=jpg&q=80&w=1800", "kredit": "Nama Fotografer / Unsplash", "jenis": "stok"}
      -> foto stok berlisensi bebas; tercetak "Foto ilustrasi: <kredit>" supaya tidak dikira foto kejadian aslinya
  {"url": "https://situs.com/gambar-utama.jpg", "kredit": "TechCrunch"}
      -> foto dari artikel sumber (pilar NEWS); tercetak "Foto: <kredit>"
  {"file": "contoh/foto.jpg", "kredit": "..."}                   -> berkas lokal (uji)
  opsional "fokus": [x, y] (0-1, bagian foto yang dipertahankan saat dipotong; bawaan [0.5, 0.42])
Foto yang sama boleh dipakai di beberapa slide/scene; unduhan dan kreditnya dihitung sekali.

Hasil tiap render dicatat di <folder aset>/.foto.txt:
  baris 1: "dipakai" (minimal satu foto tampil) atau "diganti ilustrasi" (tidak ada yang tampil)
  baris 2: ringkasan per foto (dipakai atau alasan gagal)
  baris 3: "kredit: <baris kredit sesuai foto yang benar-benar tampil>" (hanya bila ada yang dipakai)
Publisher (publish.py) dan agen memakainya untuk menyesuaikan baris kredit di caption.
"""
import os
import sys

LOG = []        # satu entri per foto unik: {"kunci", "kredit", "stok", "label", "dipakai", "ket"}
_IM = {}        # (kunci, tw, th) -> (PIL.Image atau None, pesan)
_BG = {}        # (kunci, tw, th, fokus, gelap) -> latar siap pakai
_GAMBAR_OK = ("hook", "stat", "points", "statement", "icon", "flow", "steps", "vs")   # jenis scene video yang boleh berlatar foto
CREDIT_Y = 1522  # baris kredit di video (di bawah subtitle talking head y 1170-1360, di atas zona UI Reels y > 1580)


def kunci(f):
    return str(f.get("url") or f.get("file") or "")


def adalah_stok(f):
    return (f.get("jenis") or "").strip().lower() == "stok"


def label(f):
    return ("Foto ilustrasi: " if adalah_stok(f) else "Foto: ") + (f.get("kredit") or "").strip()


def muat(f, tw, th):
    """-> PIL.Image atau None. Unduh dan periksa lewat portal_foto.ambil; hasil di-cache dan dicatat di LOG."""
    if not isinstance(f, dict):
        return None
    k = (kunci(f), tw, th)
    if k not in _IM:
        try:
            import portal_foto
            im, ket = portal_foto.ambil(f, tw, th)
        except Exception as e:   # numpy/requests tak ada, dsb.: jangan gagalkan render
            im, ket = None, f"modul foto gagal: {type(e).__name__}: {str(e)[:100]}"
        _IM[k] = (im, ket)
        print(f"foto: {ket}", file=sys.stderr)
        if not any(e["kunci"] == kunci(f) for e in LOG):
            LOG.append({"kunci": kunci(f), "kredit": (f.get("kredit") or "").strip(), "stok": adalah_stok(f),
                        "label": label(f), "dipakai": im is not None, "ket": ket})
        else:
            for e in LOG:
                if e["kunci"] == kunci(f):
                    e["dipakai"], e["ket"] = im is not None, ket
    return _IM[k][0]


def _gelap_ekstra(im):
    import portal_foto
    t = portal_foto.terang(im)
    return max(0.0, min(1.0, (t - 105.0) / 140.0)) * 0.45


def _fokus(f):
    fk = f.get("fokus")
    if isinstance(fk, (list, tuple)) and len(fk) >= 2:
        try:
            return (min(1.0, max(0.0, float(fk[0]))), min(1.0, max(0.0, float(fk[1]))))
        except (TypeError, ValueError):
            pass
    return (0.5, 0.42)


def _gelap(im, dasar):
    return min(0.80, dasar + _gelap_ekstra(im) * 0.5)


def latar_video(img, f, t, dur, tipe=None):
    """Tempel latar foto ke frame video 1080x1920 (img = fr.img), zoom pelan selama scene, plus baris kredit.
    Mengembalikan True bila foto terpasang; False = biarkan frame apa adanya (tampilan polos)."""
    if tipe is not None and tipe not in _GAMBAR_OK:
        return False
    from PIL import Image, ImageDraw
    import portal_foto
    W, H = img.size
    im = muat(f, W, H)
    if im is None:
        return False
    fok = _fokus(f)
    kk = (kunci(f), W, H, fok)
    if kk not in _BG:
        base = portal_foto.latar(im, W, H, fok, 1.0, 0.35, _gelap(im, 0.60))
        portal_foto.gradasi(base, 0, 380, 0.55, 0.0)        # atas lebih gelap (kicker dan judul)
        portal_foto.gradasi(base, 820, 1760, 0.0, 0.55)     # bawah lebih gelap (subtitle, kredit)
        _BG[kk] = base
    base = _BG[kk]
    p = max(0.0, min(1.0, t / max(0.5, dur)))
    z = 1.0 + 0.07 * (1 - (1 - p) ** 3)
    if z > 1.0005:
        cw, ch = W / z, H / z
        x0, y0 = (W - cw) / 2, (H - ch) / 2
        base = base.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    img.paste(base, (0, 0))
    # kredit foto (muncul pelan, kecil, di bawah area subtitle)
    a = max(0.0, min(1.0, (t - 0.3) / 0.4))
    if a > 0:
        try:
            import render_motion as rm
            sz = 24
            txt = label(f)
            while sz > 17 and ImageDraw.Draw(img).textlength(txt, font=rm.font("r", sz)) > rm.XW:
                sz -= 1
            c = tuple(int(rm.BG[i] + (rm.MUTE[i] - rm.BG[i]) * a) for i in range(3))
            ImageDraw.Draw(img).text((rm.X0, CREDIT_Y), txt, font=rm.font("r", sz), fill=c)
        except Exception:
            pass
    return True


def latar_slide(img, f, area_h):
    """Latar foto statis untuk slide carousel (area atas footer setinggi area_h). Mengembalikan teks kredit, atau None bila foto
    tak dipakai (slide memakai latar grid biasa)."""
    import portal_foto
    W = img.size[0]
    im = muat(f, W, area_h)
    if im is None:
        return None
    base = portal_foto.latar(im, W, area_h, _fokus(f), 1.0, 0.35, _gelap(im, 0.62))
    portal_foto.gradasi(base, 0, 300, 0.5, 0.0)
    portal_foto.gradasi(base, int(area_h * 0.55), area_h, 0.0, 0.55)
    img.paste(base, (0, 0))
    return label(f)


def kredit_baris(dipakai=None):
    """Baris kredit gabungan dari foto yang benar-benar tampil, tanpa duplikat."""
    dipakai = [e for e in LOG if e["dipakai"]] if dipakai is None else dipakai
    art, stok = [], []
    for e in dipakai:
        tujuan = stok if e["stok"] else art
        if e["kredit"] and e["kredit"] not in tujuan:
            tujuan.append(e["kredit"])
    bagian = []
    if art:
        bagian.append("Foto: " + ", ".join(art))
    if stok:
        bagian.append("Foto ilustrasi: " + ", ".join(stok))
    return ". ".join(bagian)


def tulis_log(path):
    """Tulis .foto.txt (format di docstring). Tanpa foto di spec = tidak menulis apa pun."""
    if not LOG:
        return
    ok = [e for e in LOG if e["dipakai"]]
    ringkas = "; ".join(("dipakai: " if e["dipakai"] else "gagal: ") + (e["kredit"] or "?") + " (" + e["ket"] + ")" for e in LOG)
    baris = ["dipakai" if ok else "diganti ilustrasi", f"{len(ok)} dari {len(LOG)} foto tampil. {ringkas}"[:900]]
    if ok:
        baris.append("kredit: " + kredit_baris(ok))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(baris) + "\n")
