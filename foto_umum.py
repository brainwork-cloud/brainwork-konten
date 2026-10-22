#!/usr/bin/env python3
"""
Foto latar untuk konten @nopal.brainwork: carousel, Reels Motion, dan cover Talking Head.
STANDAR FOTO WAJIB (keputusan Naufal 21 Okt 2026, diperketat 22 Okt 2026: "apa pun alasannya konten harus berfoto"): foto relevan
berkredit sebagai latar redup, teks di atasnya. Foto TIDAK PERNAH dilewati:
  - spec tanpa foto -> renderer memasang foto cadangan (foto_cadangan.json, dipilih menurut topik) di sampul/hook dan satu slide/scene lain;
  - foto di spec gagal diunduh atau tidak lolos pemeriksaan -> diganti foto cadangan (kreditnya ikut berganti);
  - di GitHub Actions render GAGAL bila ada tempat berfoto tetapi tak satu foto pun bisa dimuat (bukan keluar polos);
  - render lokal tanpa internet ke Unsplash tetap jalan polos supaya QA tata letak bisa dilakukan.
Pengecualian satu-satunya adalah yang tertulis di standar: scene `ui`, `mock`, `end`, slide `visual`, Reels Faceless, Reels Aktivitas, Threads.

Field `foto` boleh ada di slide carousel (cover, point, list, statement, cta) dan di scene video (hook, stat, points,
statement, icon, flow, steps, vs; bukan ui, mock, end). Bentuknya sama dengan portal (portal_foto.py):
  {"url": "https://images.unsplash.com/photo-...?fm=jpg&q=80&w=1800", "kredit": "Nama Fotografer / Unsplash", "jenis": "stok"}
      -> foto stok berlisensi bebas; tercetak "Foto ilustrasi: <kredit>" supaya tidak dikira foto kejadian aslinya
  {"url": "https://situs.com/gambar-utama.jpg", "kredit": "TechCrunch"}
      -> foto dari artikel sumber (pilar NEWS); tercetak "Foto: <kredit>"
  {"file": "contoh/foto.jpg", "kredit": "..."}                   -> berkas lokal (uji)
  opsional "fokus": [x, y] (0-1, bagian foto yang dipertahankan saat dipotong; bawaan [0.5, 0.42])
Foto yang sama boleh dipakai di beberapa slide/scene; unduhan dan kreditnya dihitung sekali.

Hasil tiap render dicatat di <folder aset>/.foto.txt (SELALU ditulis untuk konten yang tunduk standar foto):
  baris 1: "dipakai" (minimal satu foto tampil) atau "tanpa foto: <alasan>" (tidak ada yang tampil; portal: "diganti ilustrasi")
  baris 2: ringkasan per foto (dipakai, diganti cadangan, atau alasan gagal)
  baris 3: "kredit: <baris kredit sesuai foto yang benar-benar tampil>" (hanya bila ada yang tampil)
Publisher (publish.py) dan agen memakainya untuk menyesuaikan baris kredit di caption, termasuk MENAMBAHKANNYA bila caption belum memuat
baris kredit (mis. karena foto dipasang otomatis oleh renderer).
"""
import os
import sys

LOG = []        # satu entri per foto unik: {"kunci", "kredit", "stok", "label", "dipakai" (berhasil dimuat), "tampil" (benar-benar terpasang), "cadangan", "ket"}
_IM = {}        # (kunci, tw, th) -> (PIL.Image atau None, pesan)
_BG = {}        # (kunci, tw, th, fokus, gelap) -> latar siap pakai
_GANTI = {}     # kunci foto asli yang gagal/tak ada -> foto cadangan yang dipilih (konsisten untuk semua ukuran)
AKTIF = False   # konten ini tunduk standar foto (carousel, Reels Motion, cover Talking Head, portal)
ADA_TEMPAT = True   # ada slide/scene yang boleh berfoto (False = semua `ui`/`visual`, tidak wajib gagal)
SEED = ""       # ID konten (urutan foto cadangan stabil per konten)
TEKS = ""       # teks topik konten (untuk mencocokkan foto cadangan)
_MATI = False   # True bila unduhan gagal terus (jaringan ke host foto tertutup): berhenti mencoba foto cadangan satu per satu
_GAMBAR_OK = ("hook", "stat", "points", "statement", "icon", "flow", "steps", "vs")   # jenis scene video yang boleh berlatar foto
CREDIT_Y = 1522  # baris kredit di video (di bawah subtitle talking head y 1170-1360, di atas zona UI Reels y > 1580)


def atur(spec, aktif=True):
    """Dipanggil renderer sekali di awal: ID dan teks topik spec dipakai memilih foto cadangan; hapus keadaan render sebelumnya."""
    global AKTIF, ADA_TEMPAT, SEED, TEKS, _MATI
    LOG.clear(); _IM.clear(); _BG.clear(); _GANTI.clear()
    _MATI = False
    AKTIF, ADA_TEMPAT = bool(aktif), True
    SEED = str(spec.get("id") or "")
    try:
        import portal_foto
        TEKS = portal_foto.teks_spec(spec)
    except Exception:
        TEKS = ""


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
                        "label": label(f), "dipakai": im is not None, "tampil": False, "cadangan": bool(f.get("cadangan")), "ket": ket})
        else:
            for e in LOG:
                if e["kunci"] == kunci(f):
                    e["dipakai"], e["ket"] = im is not None, ket
    return _IM[k][0]


def _kunci_dipakai_lain(k0):
    pakai = {kunci(g) for k, g in _GANTI.items() if k != k0}
    pakai |= {e["kunci"] for e in LOG if e["dipakai"] and e["kunci"] != k0}
    return pakai


def pilih(f, tw, th):
    """-> (PIL.Image atau None, f efektif). Foto `f` dicoba dulu; gagal, tak lolos, atau tak ada = foto cadangan pertama yang lolos
    (urutan menurut topik konten, tanpa mengulang foto yang sudah dipakai bagian lain). Pilihan konsisten untuk semua ukuran."""
    f0 = f if isinstance(f, dict) else {}
    k0 = kunci(f0)
    if f0:
        im = muat(f0, tw, th)
        if im is not None:
            return im, f0
        g = _GANTI.get(k0)
        if g is not None:
            im = muat(g, tw, th)
            if im is not None:
                return im, g
    try:
        import portal_foto
        kandidat = portal_foto.cadangan(TEKS, SEED, hindari=_kunci_dipakai_lain(k0) | {k0})
    except Exception:
        kandidat = []
    global _MATI
    if _MATI:
        return None, f0
    gagal = 0
    for g in kandidat:
        g = dict(g, cadangan=True)
        im = muat(g, tw, th)
        if im is not None:
            _GANTI[k0] = g
            print(f"foto: {k0 or '(tanpa foto di spec)'} diganti cadangan {g['kredit']}", file=sys.stderr)
            return im, g
        if _IM[(kunci(g), tw, th)][1].startswith("gagal memuat"):    # unduhan gagal (bukan sekadar foto tak lolos periksa)
            gagal += 1
            if gagal >= 3 and not any(e["dipakai"] for e in LOG):
                _MATI = True       # host foto tak terjangkau: jangan buang waktu mencoba sisanya
                break
    return None, f0


def tandai_tampil(f):
    """Catat bahwa foto f benar-benar terpasang di hasil (dasar baris kredit)."""
    for e in LOG:
        if e["kunci"] == kunci(f):
            e["tampil"] = True


def siapkan(f, tw, th):
    """Muat (dan ganti bila perlu) foto lebih awal supaya kegagalan ketahuan sebelum render panjang dimulai."""
    return pilih(f, tw, th)[0] is not None


def _punya(f):
    return isinstance(f, dict) and bool(f.get("url") or f.get("file"))


def _cad(n, hindari=()):
    try:
        import portal_foto
        return [dict(g, cadangan=True) for g in portal_foto.cadangan(TEKS, SEED, hindari=set(hindari))[:n]]
    except Exception:
        return []


def _dipakai_semua():
    return {kunci(g) for g in _GANTI.values()} | {e["kunci"] for e in LOG if e["dipakai"]}


def _muat_awal(daftar_f, tw, th):
    """Muat foto yang sudah ada di spec lebih dulu (yang gagal langsung diganti cadangan), lalu kembalikan kunci semua foto yang sudah
    terpakai supaya foto tambahan dari renderer tidak sama dengan yang sudah ada."""
    for f in daftar_f:
        pilih(f, tw, th)
    return _dipakai_semua() | {kunci(f) for f in daftar_f}


def lengkapi_carousel(slides, tw, th):
    """Spec tanpa foto di sampul = pasang foto cadangan di sampul; bila total foto < 2 dan ada slide point/list tanpa foto, satu lagi."""
    global ADA_TEMPAT
    elig = [i for i, s in enumerate(slides) if s.get("type") != "visual"]
    if not elig:
        ADA_TEMPAT = False
        return
    ada = [slides[i]["foto"] for i in elig if _punya(slides[i].get("foto"))]
    cad = _cad(2, _muat_awal(ada, tw, th))
    pakai = len(ada)
    if not _punya(slides[elig[0]].get("foto")) and cad:
        slides[elig[0]]["foto"] = cad.pop(0)
        pakai += 1
    if pakai < 2 and cad:
        for i in elig[1:]:
            if slides[i].get("type") in ("point", "list") and not _punya(slides[i].get("foto")):
                slides[i]["foto"] = cad.pop(0)
                break


def _lengkapi_scene(scenes, utama, kedua, tw, th):
    global ADA_TEMPAT
    elig = [s for s in scenes if s.get("type") in _GAMBAR_OK]
    if not elig:
        ADA_TEMPAT = False
        return
    ada = [s["foto"] for s in elig if _punya(s.get("foto"))]
    cad = _cad(2, _muat_awal(ada, tw, th))
    pakai = len(ada)
    if not pakai and cad:
        s0 = next((s for s in elig if s.get("type") in utama), None)
        if s0 is not None:
            s0["foto"] = cad.pop(0)
            pakai += 1
    if pakai < 2 and cad:
        for s in elig:
            if s.get("type") in kedua and not _punya(s.get("foto")):
                s["foto"] = cad.pop(0)
                break


def lengkapi_motion(scenes, tw, th):
    """Reels Motion: hook berfoto; bila total foto < 2, satu scene points/icon/flow/steps/vs juga (stat dan statement tidak otomatis, supaya
    foto suasana tidak jadi 'bukti' angka atau klaim)."""
    _lengkapi_scene(scenes, ("hook",), ("points", "icon", "flow", "steps", "vs"), tw, th)


def lengkapi_talking_head(spec, tw, th):
    """Talking Head: minimal dua item cover non-ui berfoto (icon/flow/steps/vs/points; `statement` hanya bila tak ada jenis lain)."""
    global ADA_TEMPAT
    sc = [c["scene"] for c in spec.get("cover", []) if isinstance(c.get("scene"), dict)]
    inti = ("icon", "flow", "steps", "vs", "points")
    elig = [s for s in sc if s.get("type") in inti] or [s for s in sc if s.get("type") == "statement"]
    if not elig:
        ADA_TEMPAT = False
        return
    ada = [s for s in sc if s.get("type") in _GAMBAR_OK and _punya(s.get("foto"))]
    cad = _cad(2, _muat_awal([s["foto"] for s in ada], tw, th))
    for s in elig:
        if len(ada) >= 2 or not cad:
            break
        if not _punya(s.get("foto")):
            s["foto"] = cad.pop(0)
            ada.append(s)


def pastikan(path):
    """Panggil setelah foto dimuat (siapkan) dan sebelum render panjang: di Actions, bila ada tempat berfoto tetapi tak satu foto pun
    berhasil dimuat (jaringan putus, Unsplash turun), tulis .foto.txt lalu hentikan render dengan galat jelas. Konten tidak boleh
    terbit polos."""
    import portal_foto
    if AKTIF and ADA_TEMPAT and portal_foto.wajib() and not any(e["dipakai"] for e in LOG):
        tulis_log(path, kosong="tanpa foto")
        sys.exit("FOTO WAJIB GAGAL: tidak ada foto yang bisa dimuat (termasuk foto cadangan). " +
                 "; ".join(f"{e['kredit'] or e['kunci'][:60]}: {e['ket']}" for e in LOG)[:600])


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
    im, f = pilih(f, W, H)
    if im is None:
        return False
    tandai_tampil(f)
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
    im, f = pilih(f, W, area_h)
    if im is None:
        return None
    tandai_tampil(f)
    base = portal_foto.latar(im, W, area_h, _fokus(f), 1.0, 0.35, _gelap(im, 0.62))
    portal_foto.gradasi(base, 0, 300, 0.5, 0.0)
    portal_foto.gradasi(base, int(area_h * 0.55), area_h, 0.0, 0.55)
    img.paste(base, (0, 0))
    return label(f)


def kredit_baris(dipakai=None):
    """Baris kredit gabungan dari foto yang benar-benar tampil, tanpa duplikat."""
    dipakai = [e for e in LOG if e["tampil"]] if dipakai is None else dipakai
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


def tulis_log(path, kosong="tanpa foto"):
    """Tulis .foto.txt (format di docstring). Konten yang tunduk standar foto SELALU ditulis; selain itu (Faceless, Aktivitas) tidak menulis apa pun."""
    if not LOG and not AKTIF:
        return
    ok = [e for e in LOG if e["tampil"]]
    ringkas = "; ".join(("dipakai" + (" (cadangan)" if e["cadangan"] else "") if e["tampil"] else "tidak tampil") + ": " + (e["kredit"] or "?") + " (" + e["ket"] + ")"
                        for e in LOG) or "tidak ada foto di spec dan tidak ada tempat yang boleh berfoto"
    if ok:
        baris = ["dipakai"]
    elif not ADA_TEMPAT:
        baris = [kosong + ": semua slide/scene bertipe visual/ui (tidak boleh berfoto)"]
    else:
        baris = [kosong + ": " + (ringkas[:200] if LOG else "tidak ada foto yang dipasang")]
    baris.append(f"{len(ok)} dari {len(LOG)} foto tampil. {ringkas}"[:900])
    if ok:
        baris.append("kredit: " + kredit_baris(ok))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(baris) + "\n")
