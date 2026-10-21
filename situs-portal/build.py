#!/usr/bin/env python3
"""Pembangun situs berita Brainwork.id (statis, tanpa dependensi selain Pillow untuk thumbnail).

Membaca data portal dari klon repo publik brainwork-cloud/brainwork-konten:
  portal/PT-*.json                      spec konten (judul, ringkas, caption, sumber, format, ...)
  queue/PT-*__facebook_portal.json      status tayang + tautan post (juga instagram_portal)
  aset/<ID>/                            kartu <ID>.jpg, slide <ID>_NN.jpg, video <ID>.mp4

Hanya konten yang SUDAH tayang (status "posted" di Facebook atau Instagram) yang masuk situs.
Keluaran (semua di folder --out, mis. brainwork-id/): index.html, berita/<slug>/, kategori/<slug>/, arsip/, tentang/,
kerja-sama/, feed.xml, sitemap.xml, media/<ID>/ (salinan kartu, slide, video, thumb). Keluaran deterministik: tanpa cap waktu build,
jadi bila data sama tidak ada perubahan berkas.

Pakai:  python3 situs-portal/build.py --konten /path/brainwork-konten --out brainwork-id
Pengaturan alamat (untuk domain sendiri nanti): --origin https://brainwork-cloud.github.io --base /brainwork-id/
"""
import argparse
import datetime as dt
import email.utils
import filecmp
import html
import json
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ekosistem"))
import blok as ekoblok  # blok 'proyek lain' bersama (ekosistem/blok.py; sumber: ekosistem.json)

try:
    from PIL import Image
except Exception:  # thumbnail opsional; tanpa Pillow dipakai kartu penuh
    Image = None

WIB = dt.timezone(dt.timedelta(hours=7))
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
BULAN_PENUH = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
               "November", "Desember"]
FB_URL = "https://www.facebook.com/brainwork.id"
IG_URL = "https://www.instagram.com/brainwork.id/"
NAMA = "Brainwork.id"
# Kerja sama / endorsement (permintaan Naufal 21 Okt 2026): ke profil Nopal Brainwork dan WhatsApp CS Nazwa (nomor sama dengan landing page publik)
NOPAL_URL = "https://brainwork-cloud.github.io/"
NOPAL_IG = "https://www.instagram.com/nopal.brainwork/"
WA_NOMOR = "6285158666066"
WA_TAMPIL = "+62 851-5866-6066"
WA_PESAN = "Halo Kak Nazwa, saya tertarik kerja sama/endorsement lewat Brainwork.id.\n\nNama brand:\nJenis kerja sama:\nTimeline:"
WA_URL = f"https://wa.me/{WA_NOMOR}?text=" + urllib.parse.quote(WA_PESAN, safe="")
# Sorotan "dibangun otomatis dengan AI, mau juga?" (permintaan Naufal 21 Okt 2026): masuk daftar tunggu mesin lewat CS Nazwa
WA_AI_PESAN = "Halo Kak Nazwa, saya mau masuk daftar tunggu mesin konten/situs otomatis seperti Brainwork.id.\n\nNama:\nBisnis atau niche:\nYang mau diotomasi:"
WA_AI_URL = f"https://wa.me/{WA_NOMOR}?text=" + urllib.parse.quote(WA_AI_PESAN, safe="")
SITUS_ID = "brainwork-id"   # id situs ini di ekosistem.json (proyek ini disembunyikan dari daftar "proyek lain")
SKALARIUM_MESIN = "https://brainwork-cloud.github.io/skalarium/#mesin"   # penjelasan alur agen AI (contoh mesin yang sama)
IKON_WA = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
           'stroke-linejoin="round" aria-hidden="true"><path d="M4 5h16v11H9l-5 4V5z"/><path d="M8 10h8M8 13h5"/></svg>')
IKON_PANAH = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
              'stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8"/></svg>')
TAGLINE = "Kabar marketing dan AI untuk advertiser dan pelaku usaha di Indonesia"

# nilai kategori di spec (termasuk nilai lama sebelum 21 Okt 2026) -> (label tampil, slug)
KATEGORI = {
    "ADS": ("Ads", "ads"), "IKLAN": ("Ads", "ads"),
    "SOCIAL MEDIA": ("Social media", "social-media"), "MEDIA SOSIAL": ("Social media", "social-media"),
    "AI": ("AI", "ai"), "E-COMMERCE": ("E-commerce", "e-commerce"),
    "PLATFORM": ("Platform", "platform"), "REGULASI": ("Regulasi", "regulasi"),
}
URUTAN_KAT = ["ads", "social-media", "ai", "e-commerce", "platform", "regulasi"]

JS_GALERI = """(function(){var f=document.currentScript.previousElementSibling;if(!f)return;var g=f.querySelector('.galeri'),t=f.querySelector('.tbl-slide'),c=f.querySelector('.ctr');if(!g||!t||!c)return;
t.hidden=false;var n=g.children.length;function idx(){var a=g.children[0],w=a.offsetWidth+10;return Math.min(n-1,Math.round(g.scrollLeft/w))}
function tampil(){c.textContent='Slide '+(idx()+1)+' dari '+n}tampil();g.addEventListener('scroll',tampil,{passive:true});
t.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;var w=g.children[0].offsetWidth+10;var r=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
g.scrollBy({left:w*Number(b.dataset.arah),behavior:r?'auto':'smooth'})})})();"""

MARK = ('<svg viewBox="0 0 64 64" aria-hidden="true" focusable="false"><rect width="64" height="64" rx="15" fill="#7B2FBE"/>'
        '<path d="M32 17 48 46H16Z" fill="#F5C107" stroke="#F5C107" stroke-width="4" stroke-linejoin="round"/></svg>')


# ---------------------------------------------------------------- util teks
def esc(s):
    return html.escape(str(s), quote=True)


def tgl(d):
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def jam(d):
    return f"{d.hour:02d}.{d.minute:02d} WIB"


def slugify(s, n=58):
    s = s.replace("**", "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > n:
        s = s[:n].rsplit("-", 1)[0]
    kata = s.split("-")
    while len(kata) > 3 and kata[-1] in {"dan", "di", "ke", "dari", "yang", "untuk", "lewat", "dengan", "atau", "pada", "sampai", "hingga", "tanpa", "the", "of"}:
        kata.pop()
    return "-".join(kata)


def judul_html(s, emas=True):
    """`**kata**` jadi sorotan emas (gaya kartu); emas=False membuang penandanya saja."""
    t = esc(s)
    if emas:
        return re.sub(r"\*\*(.+?)\*\*", r'<em class="emas">\1</em>', t)
    return t.replace("**", "")


def potong(s, n):
    s = " ".join(s.split())
    if len(s) <= n:
        return s
    return s[:n].rsplit(" ", 1)[0].rstrip(",;:") + "..."


def domain(u):
    m = re.match(r"https?://(?:www\.)?([^/]+)", u)
    return m.group(1) if m else ""


def huruf_awal(s):
    return s[:1].upper() + s[1:] if s else s


# ---------------------------------------------------------------- uraian caption
RE_ARTINYA = re.compile(r"^(Artinya (?:buat|bagi) [^:]{2,40}):\s*(.+)$", re.I)
RE_URL = re.compile(r"([^;—–]+?)\s+[—–-]\s+(https?://[^\s;]+)")


def urai_caption(cap):
    """Caption Facebook/IG -> bagian terstruktur. Toleran: baris yang tak dikenali tetap jadi paragraf."""
    r = {"lede": "", "poin": [], "artinya": None, "status": "", "sumber": [], "catatan": "", "foto": "", "lain": []}
    for raw in (cap or "").replace("\r", "").split("\n"):
        ln = raw.strip()
        if not ln:
            continue
        if ln[0] in "•*" or ln.startswith("- "):
            t = ln.lstrip("•*- ").strip()
            m = RE_ARTINYA.match(t)
            if m and not r["artinya"]:
                r["artinya"] = (m.group(1), m.group(2).strip())
            else:
                r["poin"].append(t)
        elif ln.lower().startswith("status:"):
            r["status"] = ln.split(":", 1)[1].strip()
        elif re.match(r"^Foto( ilustrasi)?\s*:", ln):
            r["foto"] = ln
        elif ln.lower().startswith("sumber:"):
            t = ln.split(":", 1)[1].strip()
            ujung = 0
            for m in RE_URL.finditer(t):
                nama = m.group(1).strip(" ;,.")
                url = m.group(2).rstrip(".,)")
                if nama and url not in [u for _, u in r["sumber"]]:
                    r["sumber"].append((nama, url))
                ujung = m.end()
            r["catatan"] = t[ujung:].lstrip(" .;") if ujung else (t if not r["sumber"] else "")
        elif re.match(r"^(Follow|Ikuti) Brainwork\.id", ln, re.I):
            continue
        elif all(w.startswith("#") for w in ln.split()):
            continue
        elif not r["lede"]:
            r["lede"] = ln
        else:
            r["lain"].append(ln)
    return r


def langkah_status(s):
    """0 = tidak diketahui (hanya teks), 1 = uji coba, 2 = bertahap, 3 = rilis untuk semua. Tidak pernah menebak."""
    t = (s or "").lower()
    if re.search(r"uji coba|\bbeta\b|pengujian", t):
        return 1
    if "bertahap" in t:
        return 2
    if re.search(r"sudah rilis|rilis untuk semua|tersedia untuk semua", t):
        return 3
    return 0


# ---------------------------------------------------------------- data
def muat_item(konten, out):
    konten = Path(konten)
    items = []
    for f in sorted((konten / "portal").glob("PT-*.json")):
        try:
            sp = json.loads(f.read_text("utf-8"))
        except Exception:
            continue
        pid = sp.get("id") or f.stem
        q = {}
        for plat in ("facebook_portal", "instagram_portal"):
            p = konten / "queue" / f"{pid}__{plat}.json"
            if p.exists():
                try:
                    q[plat] = json.loads(p.read_text("utf-8"))
                except Exception:
                    pass
        tayang = [v for v in q.values() if v.get("status") == "posted"]
        if not tayang:
            continue
        aset = konten / "aset" / pid
        cover = aset / f"{pid}.jpg"
        if not cover.exists():
            continue
        try:
            waktu = min(dt.datetime.fromisoformat(v["publish_at"]) for v in tayang).astimezone(WIB)
        except Exception:
            continue
        c = urai_caption(sp.get("caption", ""))
        label, kslug = KATEGORI.get(str(sp.get("kategori", "")).upper().strip(), ("Platform", "platform"))
        fmt = sp.get("format", "single")
        slides = sorted(p for p in aset.glob(f"{pid}_[0-9][0-9].jpg"))
        video = aset / f"{pid}.mp4"
        status = (sp.get("status") or c["status"] or "").strip()
        foto = c["foto"]
        ft = aset / ".foto.txt"
        if ft.exists() and ft.read_text("utf-8").lstrip().lower().startswith("diganti"):
            foto = ""  # render jatuh ke ilustrasi: kredit foto tidak ditampilkan
        judul = sp.get("judul", "").strip()
        items.append({
            "id": pid, "judul": judul, "plain": judul.replace("**", ""), "kat": label, "kslug": kslug, "format": fmt,
            "slug": f"{slugify(judul)}-{pid[3:].lower()}", "waktu": waktu, "lede": c["lede"] or " ".join(sp.get("ringkas", [])[:1]),
            "poin": c["poin"] or list(sp.get("ringkas", [])), "artinya": c["artinya"], "lain": c["lain"],
            "status": huruf_awal(status), "langkah": langkah_status(status),
            "sumber_nama": sp.get("sumber", ""), "tgl_rilis": sp.get("tanggal", ""),
            "sumber": c["sumber"], "catatan": c["catatan"], "foto": foto,
            "cover": cover, "slides": slides if fmt == "carousel" and len(slides) >= 2 else [],
            "video": video if fmt == "motion" and video.exists() else None,
            "slide_meta": sp.get("slides", []),
            "fb": (q.get("facebook_portal", {}).get("result") or {}).get("url") if q.get("facebook_portal", {}).get("status") == "posted" else "",
            "ig": (q.get("instagram_portal", {}).get("result") or {}).get("url") if q.get("instagram_portal", {}).get("status") == "posted" else "",
        })
    items.sort(key=lambda x: (x["waktu"], x["id"]), reverse=True)
    return items


def web_mp4(src, dst):
    """Video untuk situs: 720 px, ±1-2 MB (hemat ruang repo). Dibuat sekali; bila ffmpeg tidak ada, video asli disalin."""
    try:
        if shutil.which("ffmpeg"):
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", "scale=720:-2", "-c:v", "libx264",
                                "-crf", "29", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                                "-movflags", "+faststart", str(dst)], capture_output=True, timeout=240)
            if r.returncode == 0 and dst.exists() and dst.stat().st_size > 10000:
                return
            dst.unlink(missing_ok=True)
    except Exception:
        dst.unlink(missing_ok=True)
    shutil.copy2(src, dst)


def salin_media(items, out, aset_base=None):
    """Mode salin (aset_base kosong): kartu/slide/video disalin ke out/media/<ID>/ (hanya bila berubah).
    Mode tautan (aset_base mis. /brainwork-konten/aset/): kartu/slide/video dimuat langsung dari folder aset repo yang
    sama (tanpa salinan); hanya thumbnail dibuat di out/media/<ID>/thumb.jpg, sekali per berita."""
    for it in items:
        d = out / "media" / it["id"]
        d.mkdir(parents=True, exist_ok=True)
        berkas = [] if aset_base else [it["cover"]] + it["slides"]
        for s in berkas:
            t = d / s.name
            if not t.exists() or not filecmp.cmp(s, t, shallow=False):
                shutil.copy2(s, t)
        th = d / "thumb.jpg"
        if not th.exists() and Image is not None:
            try:
                im = Image.open(it["cover"]).convert("RGB")
                im.thumbnail((240, 300))
                im.save(th, "JPEG", quality=78, optimize=True)
            except Exception:
                pass
        if aset_base:
            ab = aset_base if aset_base.endswith("/") else aset_base + "/"
            it["foto_url"] = f"{ab}{it['id']}/{it['cover'].name}"
            it["slide_urls"] = [f"{ab}{it['id']}/{s.name}" for s in it["slides"]]
            it["video_url"] = f"{ab}{it['id']}/{it['video'].name}" if it["video"] else ""
            it["thumb"] = f"media/{it['id']}/thumb.jpg" if th.exists() else it["foto_url"]
            continue
        it["thumb"] = f"media/{it['id']}/thumb.jpg" if th.exists() else f"media/{it['id']}/{it['cover'].name}"
        it["foto_url"] = f"media/{it['id']}/{it['cover'].name}"
        it["slide_urls"] = [f"media/{it['id']}/{s.name}" for s in it["slides"]]
        it["video_url"] = ""
        if it["video"]:
            web = d / "video.mp4"
            if not web.exists():
                web_mp4(it["video"], web)
            it["video_url"] = f"media/{it['id']}/video.mp4" if web.exists() else ""


# ---------------------------------------------------------------- kerangka halaman
class Situs:
    def __init__(self, origin, base, items, eko=None):
        self.origin = origin.rstrip("/")
        self.base = base if base.endswith("/") else base + "/"
        self.items = items
        self.eko = eko or {"judul": {}, "proyek": []}
        self.kat_ada = [k for k in URUTAN_KAT if any(i["kslug"] == k for i in items)]
        self.kat_label = {s: l for l, s in KATEGORI.values()}

    def u(self, path=""):
        return path if path.startswith("/") else self.base + path

    def abs(self, path=""):
        return self.origin + (path if path.startswith("/") else self.base + path)

    def kepala_nav(self, aktif=None):
        cur0 = ' aria-current="page"' if aktif == "semua" else ""
        cur_k = ' aria-current="page"' if aktif == "kerja-sama" else ""
        li = [f'<li><a href="{self.u()}"{cur0}>Semua</a></li>']
        for k in self.kat_ada:
            cur = ' aria-current="page"' if aktif == k else ""
            li.append(f'<li><a href="{self.u(f"kategori/{k}/")}"{cur}>{esc(self.kat_label[k])}</a></li>')
        return ('<header class="kepala"><div class="wrap">'
                f'<a class="merek" href="{self.u()}" aria-label="{NAMA}, beranda">{MARK}<span>Brainwork<b>.id</b></span></a>'
                f'<nav class="ikuti" aria-label="Menu lain"><a class="kerja" href="{self.u("kerja-sama/")}"{cur_k}>Kerja sama</a>'
                f'<a class="sosial" href="{FB_URL}" rel="noopener">Facebook</a>'
                f'<a class="sosial" href="{IG_URL}" rel="noopener">Instagram</a></nav></div></header>'
                f'<nav class="rubrik" aria-label="Rubrik"><ul>{"".join(li)}</ul></nav>')

    def kaki(self):
        return ('<footer class="kaki"><div class="wrap">'
                f'<p>{NAMA}: kabar marketing dan AI untuk advertiser dan pelaku usaha di Indonesia. Satu berita per hari, dengan sumber yang bisa dibuka.</p>'
                f'<ul><li><a href="{self.u("tentang/")}">Tentang dan cara kami memeriksa</a></li>'
                f'<li><a href="{self.u("arsip/")}">Arsip</a></li><li><a href="{self.u("feed.xml")}">RSS</a></li>'
                f'<li><a href="{self.u("kerja-sama/")}">Kerja sama</a></li>'
                f'<li><a href="{WA_URL}" rel="noopener" target="_blank">Hubungi CS Nazwa</a></li>'
                f'<li><a href="{FB_URL}" rel="noopener">Facebook</a></li><li><a href="{IG_URL}" rel="noopener">Instagram</a></li></ul>'
                + self.kaki_proyek() +
                '</div></footer>')

    def kaki_proyek(self):
        ps = ekoblok.daftar(self.eko, SITUS_ID)
        if not ps:
            return ""
        li = "".join(f'<li><a href="{esc(p["url"])}" rel="noopener" target="_blank">{esc(p["nama"])}</a></li>' for p in ps)
        return f'<ul class="kaki-proyek" aria-label="Proyek lain dari Nopal Brainwork"><li class="lbl">Proyek lain:</li>{li}</ul>'

    def proyek_lain(self):
        """Blok kartu proyek lain (sama dengan di situs Nopal, NolKaryawan, dan Skalarium; sumber ekosistem.json)."""
        return ekoblok.html_blok(self.eko, SITUS_ID)

    def otomasi(self, ringkas=False):
        """Sorotan: situs ini dibangun dan dijalankan otomatis oleh AI, plus ajakan 'mau juga bangun seperti ini?'
        (permintaan Naufal 21 Okt 2026). Ajakan masuk daftar tunggu lewat CS Nazwa; alur kerja mesin dijelaskan di Skalarium."""
        if ringkas:
            teks = ('<h2 id="judul-otomasi">Dibangun dan dijalankan otomatis oleh AI</h2>'
                    '<p class="lede-o">Agen AI mengerjakan semuanya tiap hari. Manusia meninjau tiap pekan, bukan tiap posting.</p>')
        else:
            alur = ["Cari berita", "Periksa sumber", "Buat kartu dan video", "Posting ke Facebook dan Instagram", "Situs ini terisi sendiri"]
            teks = ('<h2 id="judul-otomasi">Dibangun dan dijalankan otomatis oleh AI</h2>'
                    f'<p class="lede-o">Dari cari berita sampai situs ini terisi, semuanya dikerjakan agen AI tiap hari. '
                    'Manusia meninjau tiap pekan, bukan tiap posting.</p>'
                    f'<ol class="alur" aria-label="Alur kerja otomatis">{"".join(f"<li>{esc(t)}</li>" for t in alur)}</ol>')
        ajak = ('<h3>Mau juga bangun mesin seperti ini?</h3>'
                '<p>Dibuat oleh Nopal Brainwork. Masuk daftar tunggu lewat CS Nazwa, atau lihat dulu cara kerja mesinnya di Skalarium.</p>'
                f'<div class="aksi"><a class="tombol wa" href="{WA_AI_URL}" rel="noopener" target="_blank">Masuk daftar tunggu{IKON_WA}</a>'
                f'<a class="tombol tipis" href="{SKALARIUM_MESIN}" rel="noopener" target="_blank">Lihat cara kerjanya</a></div>')
        return (f'<section class="otomasi{" ringkas" if ringkas else ""}" aria-labelledby="judul-otomasi">'
                f'<div class="otomasi-teks">{teks}</div><div class="otomasi-ajak">{ajak}</div></section>')

    def halaman(self, path, title, desc, isi, aktif=None, og_img=None, tipe="website", jsonld=None):
        canon = self.abs(path)
        og = self.abs(og_img or "aset/og.png")
        judul_penuh = NAMA if title == NAMA else f"{title} | {NAMA}"
        ld = ""
        if jsonld:
            ld = '<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/") + "</script>"
        return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(judul_penuh)}</title>
<meta name="description" content="{esc(potong(desc, 160))}">
<link rel="canonical" href="{esc(canon)}">
<link rel="icon" href="{self.u('aset/favicon.svg')}" type="image/svg+xml">
<link rel="icon" href="{self.u('aset/favicon.png')}" type="image/png" sizes="64x64">
<link rel="apple-touch-icon" href="{self.u('aset/apple-touch-icon.png')}">
<link rel="alternate" type="application/rss+xml" title="{NAMA}" href="{self.u('feed.xml')}">
<meta name="theme-color" content="#0A0A0F">
<meta property="og:site_name" content="{NAMA}">
<meta property="og:locale" content="id_ID">
<meta property="og:type" content="{tipe}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(potong(desc, 200))}">
<meta property="og:url" content="{esc(canon)}">
<meta property="og:image" content="{esc(og)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<link rel="stylesheet" href="{self.u('aset/situs.css')}">
{ld}
</head>
<body>
<a class="lompat" href="#isi">Lewati ke isi</a>
{self.kepala_nav(aktif)}
<main id="isi"><div class="wrap">
{isi}
</div></main>
{self.kaki()}
</body>
</html>
"""

    # ------------------------------------------------------------ komponen
    def kontak(self):
        return (f'<div class="kontak-daftar">'
                f'<a class="kontak wa" href="{WA_URL}" rel="noopener" target="_blank">'
                f'<span><b>Chat CS Nazwa</b><small>WhatsApp {WA_TAMPIL}</small></span>{IKON_WA}</a>'
                f'<a class="kontak" href="{NOPAL_URL}" rel="noopener" target="_blank">'
                f'<span><b>Kunjungi Nopal Brainwork</b><small>Profil, produk, dan kerja sama</small></span>{IKON_PANAH}</a>'
                f'<p class="catatan-k">Pesan pembuka WhatsApp sudah disiapkan. Tinggal isi nama brand, jenis kerja sama, dan timeline.</p>'
                f'</div>')

    def kerjasama(self, penuh=True):
        """Blok promosi kerja sama (gaya situs Skalarium): kunjungi Nopal Brainwork atau chat CS Nazwa. Dipakai di beranda,
        halaman berita (ringkas), dan halaman Kerja sama."""
        if penuh:
            teks = ('<h2 id="judul-kerjasama">Mau kolaborasi, endorsement, atau bikin konten bareng?</h2>'
                    f'<p class="lede-k">{NAMA} adalah bagian dari Nopal Brainwork. Kalau brand atau bisnismu ingin tampil bareng kami, '
                    'kunjungi Nopal untuk melihat profil dan produknya, atau chat langsung CS Nazwa di WhatsApp.</p>'
                    '<ul class="pilihan"><li>Endorsement dan paid promote</li><li>Kolaborasi konten</li><li>Event dan partnership</li></ul>')
        else:
            teks = ('<h2 id="judul-kerjasama">Mau bikin konten bareng atau endorsement?</h2>'
                    '<p class="lede-k">Kunjungi Nopal Brainwork atau chat CS Nazwa di WhatsApp.</p>')
        return (f'<section class="kerjasama{"" if penuh else " ringkas"}" aria-labelledby="judul-kerjasama">'
                f'<div class="kerjasama-teks">{teks}</div>{self.kontak()}</section>')

    def halaman_kerjasama(self):
        isi = (f'<div class="halaman-k"><h1>Kerja sama dan endorsement</h1>'
               f'<p class="lede-k">{NAMA} adalah bagian dari Nopal Brainwork, kreator konten digital marketing dan AI. '
               'Kalau kamu ingin brand atau bisnismu tampil bareng kami, mulai dari salah satu jalur di bawah.</p></div>'
               + f'<div class="halaman-k kontak-halaman">{self.kontak()}</div>' +
               '<div class="teks halaman-k">'
               '<h2>Yang bisa dikerjakan bareng</h2>'
               '<ul><li>Endorsement dan paid promote di akun Nopal Brainwork.</li>'
               '<li>Kolaborasi konten: konten edukasi atau tutorial bareng brand-mu.</li>'
               '<li>Event dan partnership.</li></ul>'
               '<h2>Cara mulai</h2>'
               '<ol><li>Klik <b>Chat CS Nazwa</b>. Pesan pembukanya sudah disiapkan.</li>'
               '<li>Isi nama brand, jenis kerja sama, dan timeline yang kamu mau.</li>'
               '<li>Kirim. CS Nazwa akan membalas lewat WhatsApp.</li></ol>'
               '<h2>Berita tetap berita</h2>'
               f'<p>Kerja sama tidak memengaruhi isi berita di {NAMA}. Konten kerja sama selalu diberi label dan dipisah dari berita.</p>'
               '<h2>Pernah berkolaborasi dengan</h2>'
               '<p>Chandra Asri, Bluebird, Aoklandz, ZenitLand, Purwadhika, Kemenag, FYP Management, Kelas.work, dan Slice.</p>'
               f'<p>Mau kenal Nopal lebih dulu? <a href="{NOPAL_URL}" rel="noopener" target="_blank">Buka profil Nopal Brainwork</a> '
               f'atau lihat akunnya di <a href="{NOPAL_IG}" rel="noopener" target="_blank">Instagram</a>.</p></div>'
               + self.proyek_lain())
        return self.halaman("kerja-sama/", "Kerja sama dan endorsement",
                            f"Mau kolaborasi, endorsement, atau bikin konten bareng {NAMA} dan Nopal Brainwork? Kunjungi Nopal atau chat CS Nazwa di WhatsApp.",
                            isi, aktif="kerja-sama")

    def jalur(self, it):
        if not it["status"]:
            return ""
        n = it["langkah"]
        teks = f'<p class="status-teks"><b>Status rilis:</b> {esc(it["status"])}</p>'
        if not n:
            return f'<div class="jalur-kotak">{teks}</div>'
        nama = ["Uji coba", "Bertahap", "Semua user"]
        li = []
        for i, t in enumerate(nama, 1):
            cls = "kini" if i == n else ("sudah" if i < n else "")
            li.append(f'<li class="{cls}">{t}</li>' if cls else f"<li>{t}</li>")
        return (f'<div class="jalur-kotak"><ol class="jalur" aria-label="Tahap rilis: {nama[n - 1]}">{"".join(li)}</ol>{teks}</div>')

    def baris(self, it, ringkas=True, thumb=True):
        img = (f'<img src="{self.u(it["thumb"])}" width="84" height="105" alt="" loading="lazy" decoding="async">' if thumb else "")
        rg = ""
        if ringkas and it["status"]:
            rg = f'<p class="ringkas"><b>Status:</b> {esc(potong(it["status"], 90))}</p>'
        return (f'<li class="baris">{img}<div><p class="meta"><span class="kat">{esc(it["kat"])}</span>'
                f'<time datetime="{it["waktu"].date().isoformat()}">{tgl(it["waktu"])}</time></p>'
                f'<h3><a href="{self.u("berita/" + it["slug"] + "/")}">{judul_html(it["judul"], emas=False)}</a></h3>{rg}</div></li>')

    # ------------------------------------------------------------ halaman
    def beranda(self):
        its = self.items
        if not its:
            isi = (f'<h1 class="sr">{NAMA}</h1><div class="kosong"><p>Berita pertama segera tayang. '
                   f'Sementara itu, ikuti kami di <a href="{FB_URL}">Facebook</a> dan <a href="{IG_URL}">Instagram</a>.</p></div>')
            return self.halaman("", NAMA, TAGLINE, isi, aktif="semua")
        a = its[0]
        sorot = (f'<h1 class="sr">{NAMA}: {TAGLINE}</h1><section class="sorot" aria-label="Berita utama"><div>'
                 f'<p class="meta"><a class="kat" href="{self.u("kategori/" + a["kslug"] + "/")}">{esc(a["kat"])}</a>'
                 f'<time datetime="{a["waktu"].date().isoformat()}">{tgl(a["waktu"])}</time></p>'
                 f'<h2 class="sorot-judul"><a href="{self.u("berita/" + a["slug"] + "/")}">{judul_html(a["judul"])}</a></h2>'
                 f'<p class="lede">{esc(a["lede"])}</p>{self.jalur(a)}</div>'
                 f'<a class="sorot-media" href="{self.u("berita/" + a["slug"] + "/")}" tabindex="-1" aria-hidden="true">'
                 f'<img src="{self.u(a["foto_url"])}" width="1080" height="1350" alt="" decoding="async" fetchpriority="high"></a></section>')
        sisa = its[1:11]
        daftar = ("".join(self.baris(i) for i in sisa) if sisa else
                  '<li class="kosong">Berita berikutnya tayang tiap hari.</li>')
        samping = (
            '<aside class="samping"><section><h2 class="bagian">Cara kami memeriksa</h2><ul>'
            '<li>Sumber dari pengumuman resmi platform atau media yang kredibel, dengan tautan yang bisa kamu buka.</li>'
            '<li>Setiap klaim diperiksa ulang ke halaman sumber sebelum tayang.</li>'
            '<li>Status rilis ditulis apa adanya: uji coba, bertahap, atau untuk semua user.</li>'
            f'</ul><p><a href="{self.u("tentang/")}">Selengkapnya</a></p></section>'
            f'<section><h2 class="bagian">Ikuti {NAMA}</h2><div class="aksi"><a class="tombol" href="{FB_URL}" rel="noopener">Facebook</a>'
            f'<a class="tombol tipis" href="{IG_URL}" rel="noopener">Instagram</a></div></section></aside>')
        isi = (f'{sorot}<div class="dua"><section aria-label="Berita terbaru"><h2 class="bagian">Terbaru</h2>'
               f'<ul class="daftar">{daftar}</ul>'
               + (f'<p><a href="{self.u("arsip/")}">Lihat semua berita</a></p>' if len(its) > 11 else "")
               + f'</section>{samping}</div>' + self.otomasi() + self.proyek_lain() + self.kerjasama(True))
        ld = {"@context": "https://schema.org", "@type": "WebSite", "name": NAMA, "url": self.abs(),
              "inLanguage": "id", "description": TAGLINE}
        return self.halaman("", NAMA, TAGLINE, isi, aktif="semua", og_img=a["foto_url"], jsonld=ld)

    def artikel(self, it):
        path = f"berita/{it['slug']}/"
        asal = ""
        if it["fb"] or it["ig"]:
            tb = []
            if it["fb"]:
                tb.append(f'<a class="tombol tipis" href="{esc(it["fb"])}" rel="noopener">Lihat di Facebook</a>')
            if it["ig"]:
                tb.append(f'<a class="tombol tipis" href="{esc(it["ig"])}" rel="noopener">Lihat di Instagram</a>')
            asal = f'<div class="asal"><div class="aksi">{"".join(tb)}</div></div>'
        # media
        if it["video_url"]:
            media = (f'<figure><video controls playsinline preload="metadata" poster="{self.u(it["foto_url"])}" '
                     f'aria-label="Video ringkas: {esc(it["plain"])}"><source src="{self.u(it["video_url"])}" type="video/mp4"></video>'
                     f'<figcaption>Video ringkas. Ilustrasi dibuat otomatis dan bukan tangkapan layar.</figcaption></figure>')
        elif it["slide_urls"]:
            ims = []
            for n, s in enumerate(it["slide_urls"], 1):
                meta = it["slide_meta"][n - 2] if 2 <= n <= len(it["slide_meta"]) + 1 else {}
                alt = it["plain"] if n == 1 else (f'{meta.get("judul", "Slide " + str(n))}: {meta.get("isi", "")}'.strip(": "))
                ims.append(f'<img src="{self.u(s)}" width="1080" height="1350" alt="{esc(alt)}" loading="{"eager" if n == 1 else "lazy"}" decoding="async">')
            media = (f'<figure class="gal"><div class="galeri" role="region" aria-label="Slide carousel, {len(ims)} slide" tabindex="0">{"".join(ims)}</div>'
                     f'<figcaption><span class="ctr">Geser untuk melihat {len(ims)} slide.</span>'
                     '<span class="tbl-slide" hidden><button type="button" data-arah="-1">Sebelumnya</button>'
                     '<button type="button" data-arah="1">Berikutnya</button></span></figcaption></figure>'
                     f'<script>{JS_GALERI}</script>')
        else:
            media = (f'<figure><img src="{self.u(it["foto_url"])}" width="1080" height="1350" alt="Kartu berita: {esc(it["plain"])}" decoding="async"></figure>')
        if it["foto"]:
            media = media.replace("</figure>", f'<figcaption>{esc(it["foto"])}</figcaption></figure>', 1)
        # isi
        poin = "".join(f"<li>{esc(p)}</li>" for p in it["poin"])
        lain = "".join(f'<p class="para">{esc(p)}</p>' for p in it["lain"])
        artinya = ""
        if it["artinya"]:
            artinya = f'<div class="artinya"><h2>{esc(it["artinya"][0])}</h2><p>{esc(huruf_awal(it["artinya"][1]))}</p></div>'
        if it["sumber"]:
            sl = "".join(f'<li><a href="{esc(u)}" rel="noopener nofollow" target="_blank">{esc(n)}</a> <span class="dom">{esc(domain(u))}</span></li>' for n, u in it["sumber"])
            cat = f'<p>{esc(it["catatan"])}</p>' if it["catatan"] else ""
        else:
            sl = f'<li>{esc(it["sumber_nama"])}</li>' if it["sumber_nama"] else ""
            cat = ""
        sumber = (f'<section class="sumber"><h2>Sumber</h2><ul>{sl}</ul>{cat}'
                  f'<p>Rilis sumber: {esc(it["tgl_rilis"])}. Ringkasan ini disusun ulang dari sumber di atas.</p></section>')
        laporan = f'<p class="laporan">Dilaporkan oleh <b>{esc(it["sumber_nama"])}</b>, rilis {esc(it["tgl_rilis"])}</p>' if it["sumber_nama"] else ""
        isi = (f'<article class="artikel"><div class="artikel-kepala">'
               f'<p class="meta"><a class="kat" href="{self.u("kategori/" + it["kslug"] + "/")}">{esc(it["kat"])}</a>'
               f'<time datetime="{it["waktu"].isoformat()}">Tayang {tgl(it["waktu"])}, {jam(it["waktu"])}</time></p>'
               f'<h1>{judul_html(it["judul"])}</h1>'
               f'<p class="lede">{esc(it["lede"])}</p>{self.jalur(it)}{laporan}</div>'
               f'<div class="artikel-media">{media}</div>'
               f'<div class="artikel-badan"><div class="isi"><h2>Poin utama</h2><ul class="poin">{poin}</ul>{lain}{artinya}</div>'
               f'{sumber}{asal}</div></article>')
        isi += self.kerjasama(False)
        # terkait
        lain_it = [i for i in self.items if i["id"] != it["id"]]
        serupa = [i for i in lain_it if i["kslug"] == it["kslug"]][:3]
        if len(serupa) < 3:
            serupa += [i for i in lain_it if i not in serupa][: 3 - len(serupa)]
        if serupa:
            isi += (f'<section class="terkait" aria-label="Berita lain"><h2 class="bagian">Berita lain</h2>'
                    f'<ul class="daftar">{"".join(self.baris(i, ringkas=False) for i in serupa)}</ul></section>')
        ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": it["plain"],
              "datePublished": it["waktu"].isoformat(), "dateModified": it["waktu"].isoformat(), "inLanguage": "id",
              "articleSection": it["kat"], "image": [self.abs(it["foto_url"])], "isAccessibleForFree": True,
              "mainEntityOfPage": self.abs(path), "description": potong(it["lede"], 200),
              "author": {"@type": "Organization", "name": NAMA},
              "publisher": {"@type": "Organization", "name": NAMA, "logo": {"@type": "ImageObject", "url": self.abs("aset/logo-512.png")}}}
        if it["sumber"]:
            ld["citation"] = [u for _, u in it["sumber"]]
        return self.halaman(path, it["plain"], it["lede"], isi, aktif=it["kslug"], og_img=it["foto_url"], tipe="article", jsonld=ld)

    def kategori(self, slug):
        label = self.kat_label[slug]
        its = [i for i in self.items if i["kslug"] == slug]
        isi = (f'<h1 class="bagian" style="font-size:28px;margin-bottom:20px">{esc(label)}</h1>'
               f'<ul class="daftar">{"".join(self.baris(i) for i in its)}</ul>')
        return self.halaman(f"kategori/{slug}/", label, f"Berita {label} terbaru dari {NAMA}.", isi, aktif=slug)

    def arsip(self):
        parts, bln = [], None
        for it in self.items:
            k = (it["waktu"].year, it["waktu"].month)
            if k != bln:
                if bln:
                    parts.append("</ul>")
                parts.append(f'<h2 class="bulan">{BULAN_PENUH[k[1] - 1]} {k[0]}</h2><ul class="daftar daftar-arsip">')
                bln = k
            parts.append(self.baris(it, ringkas=False, thumb=False))
        if bln:
            parts.append("</ul>")
        isi = '<h1 class="bagian" style="font-size:28px">Arsip</h1>' + ("".join(parts) or '<p class="kosong">Belum ada berita.</p>')
        return self.halaman("arsip/", "Arsip", f"Semua berita {NAMA}, urut dari yang terbaru.", isi)

    def tentang(self):
        isi = f"""<div class="teks">
<h1>Tentang {NAMA}</h1>
<p>{NAMA} adalah media kabar marketing dan AI untuk advertiser, marketer, dan pelaku usaha di Indonesia. Kami menulis satu berita per hari: apa yang berubah, bagaimana cara kerjanya, dan apa artinya untuk bisnismu.</p>
<h2>Yang kami liput</h2>
<ul><li>Digital marketing dan ads: fitur, aturan, dan perubahan di platform ads.</li><li>Social media dan platform: Facebook, Instagram, WhatsApp, YouTube, TikTok, dan sejenisnya.</li><li>AI untuk bisnis dan e-commerce.</li><li>Regulasi digital yang berdampak pada pelaku usaha di Indonesia.</li></ul>
<h2>Cara kami memeriksa</h2>
<ul><li>Sumber berasal dari pengumuman resmi platform, dokumentasi resmi, siaran pers regulator, atau media yang kredibel. Tautannya selalu kami cantumkan.</li><li>Sebelum tayang, setiap klaim di judul dan isi diperiksa ulang ke halaman sumber. Yang tidak terbukti dibuang.</li><li>Status rilis ditulis apa adanya: masih uji coba, bertahap, atau sudah untuk semua user. Ketersediaan di Indonesia hanya kami sebut bila sumber menyebutnya.</li><li>Kami tidak memuat bocoran, rumor, opini pribadi, atau ajakan investasi. Lebih baik tidak tayang daripada salah.</li></ul>
<h2>Cara kerja</h2>
<p>{NAMA} dikelola lewat alur otomatis berbantuan AI: mencari berita, menulis ringkasan, memeriksa fakta, lalu menerbitkannya di situs ini serta di Facebook dan Instagram. Redaksi meninjau hasilnya setiap pekan.</p>
<h2>Gambar</h2>
<p>Ilustrasi pada kartu dibuat otomatis dan ditandai "ILUSTRASI"; itu bukan tangkapan layar produk. Bila memakai foto, kreditnya kami cantumkan.</p>
<h2>Dibangun otomatis dengan AI</h2>
<p>Dari mencari berita sampai situs ini terisi, semuanya dikerjakan agen AI tiap hari. Manusia meninjau tiap pekan, bukan tiap posting. Mau juga membangun mesin seperti ini? Masuk daftar tunggu lewat <a href="{WA_AI_URL}" rel="noopener" target="_blank">CS Nazwa</a>, atau lihat cara kerjanya di <a href="{SKALARIUM_MESIN}" rel="noopener" target="_blank">Skalarium</a>.</p>
<h2>Kerja sama dan endorsement</h2>
<p>{NAMA} adalah bagian dari Nopal Brainwork. Untuk kolaborasi, endorsement, atau bikin konten bareng, lihat halaman <a href="{self.u("kerja-sama/")}">Kerja sama</a>. Kerja sama tidak memengaruhi isi berita, dan konten kerja sama selalu diberi label.</p>
<h2>Menemukan kesalahan?</h2>
<p>Kirim pesan lewat <a href="{FB_URL}" rel="noopener">Facebook</a> atau <a href="{IG_URL}" rel="noopener">Instagram</a> {NAMA}. Laporan koreksi ditinjau dalam review mingguan.</p>
</div>"""
        return self.halaman("tentang/", f"Tentang {NAMA}", f"Apa itu {NAMA}, apa yang kami liput, dan bagaimana kami memeriksa berita.", isi)

    def feed(self):
        its = self.items[:30]
        butir = []
        for it in its:
            butir.append(
                f"<item><title>{esc(it['plain'])}</title><link>{esc(self.abs('berita/' + it['slug'] + '/'))}</link>"
                f"<guid isPermaLink=\"true\">{esc(self.abs('berita/' + it['slug'] + '/'))}</guid>"
                f"<pubDate>{email.utils.format_datetime(it['waktu'])}</pubDate><category>{esc(it['kat'])}</category>"
                f"<description>{esc(it['lede'])}</description></item>")
        terbaru = email.utils.format_datetime(its[0]["waktu"]) if its else ""
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
                f"<title>{NAMA}</title><link>{esc(self.abs())}</link><description>{esc(TAGLINE)}</description><language>id</language>"
                + (f"<lastBuildDate>{terbaru}</lastBuildDate>" if terbaru else "") + "".join(butir) + "</channel></rss>\n")

    def sitemap(self):
        urls = [(self.abs(), self.items[0]["waktu"].date().isoformat() if self.items else None),
                (self.abs("tentang/"), None), (self.abs("kerja-sama/"), None), (self.abs("arsip/"), self.items[0]["waktu"].date().isoformat() if self.items else None)]
        for k in self.kat_ada:
            urls.append((self.abs(f"kategori/{k}/"), None))
        for it in self.items:
            urls.append((self.abs(f"berita/{it['slug']}/"), it["waktu"].date().isoformat()))
        body = "".join(f"<url><loc>{esc(u)}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>" for u, m in urls)
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'


# ---------------------------------------------------------------- tulis
def tulis(p, teks):
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.read_text("utf-8") == teks:
        return
    p.write_text(teks, "utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--konten", required=True, help="folder klon brainwork-konten")
    ap.add_argument("--out", default="brainwork-id")
    ap.add_argument("--origin", default="https://brainwork-cloud.github.io")
    ap.add_argument("--base", default="/brainwork-id/")
    ap.add_argument("--aset-base", default="", help="awalan URL folder aset repo (mode tautan), mis. /brainwork-konten/aset/")
    a = ap.parse_args()
    out = Path(a.out)
    here = Path(__file__).resolve().parent
    items = muat_item(a.konten, out)
    for d in ("berita", "kategori", "arsip", "tentang", "kerja-sama"):
        shutil.rmtree(out / d, ignore_errors=True)
    out.mkdir(parents=True, exist_ok=True)
    salin_media(items, out, a.aset_base or None)
    # media milik item yang tidak lagi tayang dibersihkan
    ada = {i["id"] for i in items}
    if (out / "media").exists():
        for d in (out / "media").iterdir():
            if d.is_dir() and d.name not in ada:
                shutil.rmtree(d, ignore_errors=True)
    eko = ekoblok.muat(Path(a.konten) / "ekosistem.json")
    s = Situs(a.origin, a.base, items, eko)
    tulis(out / "index.html", s.beranda())
    for it in items:
        tulis(out / "berita" / it["slug"] / "index.html", s.artikel(it))
    for k in s.kat_ada:
        tulis(out / "kategori" / k / "index.html", s.kategori(k))
    tulis(out / "arsip" / "index.html", s.arsip())
    tulis(out / "tentang" / "index.html", s.tentang())
    tulis(out / "kerja-sama" / "index.html", s.halaman_kerjasama())
    tulis(out / "feed.xml", s.feed())
    tulis(out / "sitemap.xml", s.sitemap())
    css = (here / "situs.css").read_text("utf-8")
    tulis(out / "aset" / "situs.css", css)
    for ik in sorted((here / "ikon").glob("*")):  # favicon, logo, gambar OG (dibuat sekali oleh buat_ikon.py)
        t = out / "aset" / ik.name
        if not t.exists() or not filecmp.cmp(ik, t, shallow=False):
            shutil.copy2(ik, t)
    print(f"situs: {len(items)} berita, kategori {','.join(s.kat_ada) or '-'}")


if __name__ == "__main__":
    main()
