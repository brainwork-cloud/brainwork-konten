#!/usr/bin/env python3
"""Pengambil data performa untuk dashboard "Pantauan Performa Nopal Brainwork" (claude.ai, tipe Dashboard).

Jalan di GitHub Actions (workflow performa.yml), 2x sehari. Gratis: repo ini publik dan semua sumbernya API resmi
atau feed publik. Memakai token yang SUDAH ada di secret repo ini; nilai token tidak pernah dicetak atau disimpan.
- FB_PAGE_TOKEN / FB_PAGE_ID: Page Nopal Brainwork (±44 rb) + Instagram yang tertaut ke Page itu (@nopal.brainwork)
- PORTAL_FB_PAGE_TOKEN / PORTAL_FB_PAGE_ID: Page Brainwork.id + Instagram @brainwork.id
- THREADS_ACCESS_TOKEN (+ THREADS_USER_ID opsional): Threads @nopal.brainwork
- Feed publik YouTube (tanpa token): views dan likes video terbaru Brainwork, Skalarium, skalarium english
- Instagram @skalarium dan @skalarium.en: angka publik lewat business discovery (token Skalarium ada di repo privat)

Hasil di folder performa/ (dibaca dashboard lewat konektor GitHub):
  konten.json    satu baris per posting: views, reach, likes, komentar, save, share (null = tidak tersedia)
  akun.json      satu baris per akun yang dikelola: followers, jumlah posting, status data
  harian.json    views, reach, followers baru per hari untuk akun Instagram yang punya insight (riwayat)
  followers.json snapshot followers per akun per hari (riwayat)
  log.txt        log run terakhir (tanpa token)
Gagal di satu sumber tidak menghentikan sumber lain; angka lama dipertahankan bila sumbernya gagal.
"""
import datetime as dt
import glob
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import requests

FB = "https://graph.facebook.com/v23.0"
TH = "https://graph.threads.net/v1.0"
WIB = dt.timezone(dt.timedelta(hours=7))
PT = ZoneInfo("America/Los_Angeles")  # hari insight Meta mengikuti waktu Pasifik
OUT = os.environ.get("PERFORMA_OUT", "performa")
HARI_KONTEN = 365   # posting yang disimpan (hari ke belakang)
HARI_SEGAR = 120    # insight posting yang lebih muda dari ini disegarkan tiap run; yang lebih tua tiap Senin
HARI_HARIAN = 56    # riwayat views/reach harian akun yang diisi
RIWAYAT_MAKS = 400  # hari riwayat harian/followers yang disimpan
UA = {"User-Agent": "Mozilla/5.0 (compatible; brainwork-performa/1.0)", "Accept-Language": "en-US,en;q=0.8"}

# kode, brand, platform, akun (tampilan), cara posting, sumber plan
AKUN = [
    ("nopal-ig", "Nopal Brainwork", "Instagram", "@nopal.brainwork", "Otomatis (Penerbit IG)", "Tab Antrian"),
    ("nopal-threads", "Nopal Brainwork", "Threads", "@nopal.brainwork", "Otomatis", "Tab Antrian"),
    ("nopal-yt", "Nopal Brainwork", "YouTube", "Brainwork (Shorts)", "Otomatis (mirror Shorts)", "Tab Antrian"),
    ("nopal-tiktok", "Nopal Brainwork", "TikTok", "@nopal.brainwork", "Manual (Nazwa)", "Tab Antrian"),
    ("nopal-fb", "Nopal Brainwork", "Facebook", "Page Nopal Brainwork", "Mirror dihentikan, menunggu keputusan", "Tab Antrian"),
    ("portal-fb", "Brainwork.id", "Facebook", "Page Brainwork.id", "Otomatis (Redaktur Portal)", "Tab Portal"),
    ("portal-ig", "Brainwork.id", "Instagram", "@brainwork.id", "Otomatis (mirror portal)", "Tab Portal"),
    ("sk-id-ig", "Skalarium ID", "Instagram", "@skalarium", "Otomatis (mesin konten)", "Mesin Skalarium"),
    ("sk-id-fb", "Skalarium ID", "Facebook", "Page Skalarium", "Otomatis (mesin konten)", "Mesin Skalarium"),
    ("sk-id-yt", "Skalarium ID", "YouTube", "@skalarium", "Otomatis (mesin konten)", "Mesin Skalarium"),
    ("sk-id-tiktok", "Skalarium ID", "TikTok", "@skalarium.id", "Manual", "Mesin Skalarium"),
    ("sk-en-ig", "Skalarium EN", "Instagram", "@skalarium.en", "Otomatis (mesin konten)", "Mesin Skalarium"),
    ("sk-en-fb", "Skalarium EN", "Facebook", "Page Skalarium.en", "Otomatis (mesin konten)", "Mesin Skalarium"),
    ("sk-en-yt", "Skalarium EN", "YouTube", "@skalariumenglish", "Otomatis (mesin konten)", "Mesin Skalarium"),
    ("sk-en-tiktok", "Skalarium EN", "TikTok", "@skalarium.en", "Manual", "Mesin Skalarium"),
]
INFO = {a[0]: a for a in AKUN}
BELUM_BISA = {
    "nopal-tiktok": "TikTok belum menyediakan API gratis tanpa app yang lolos review",
    "sk-id-tiktok": "TikTok belum menyediakan API gratis tanpa app yang lolos review",
    "sk-en-tiktok": "TikTok belum menyediakan API gratis tanpa app yang lolos review",
    "sk-id-fb": "token Page Skalarium tersimpan di repo privat mesin-konten",
    "sk-en-fb": "token Page Skalarium.en tersimpan di repo privat mesin-konten",
}
YOUTUBE = [  # kode, handle (None = cari dari video contoh), video contoh
    ("nopal-yt", None, "H6V6qpEy4YQ"),
    ("sk-id-yt", "@skalarium", None),
    ("sk-en-yt", "@skalariumenglish", None),
]
IG_PUBLIK = [("sk-id-ig", "skalarium"), ("sk-en-ig", "skalarium.en")]

SES = requests.Session()
NOW = dt.datetime.now(dt.timezone.utc)
HARI_INI = NOW.astimezone(WIB).date()
SENIN = HARI_INI.weekday() == 0
LOG = []
ST = {}          # kode -> status akun run ini
KONTEN = {}      # kunci -> baris konten
LAMA_KONTEN = {}
LAMA_AKUN = {}
HARIAN = {}      # (kode, tanggal) -> baris
FOLLOWERS = {}   # (kode, tanggal) -> baris
PENANYA = []     # (ig_id, token) akun IG bertoken untuk business discovery


# ---------- bantuan ----------
def _token_rahasia():
    return [v for k, v in os.environ.items() if k.endswith("TOKEN") and v and len(v) > 8]


def bersih(s):
    """Buang nilai token dari teks apa pun sebelum dicetak atau disimpan (repo ini publik)."""
    s = str(s)
    for t in _token_rahasia():
        s = s.replace(t, "***")
    return re.sub(r"(access_token=)[^&\s'\"]+", r"\1***", s)


def log(*a):
    s = bersih(" ".join(str(x) for x in a))
    LOG.append(s)
    print(s, flush=True)


class ApiError(Exception):
    def __init__(self, code, msg):
        super().__init__(f"[{code}] {msg}")
        self.code = code
        self.msg = msg


def get(url, params=None, tries=3):
    params = dict(params or {})
    for i in range(tries):
        try:
            r = SES.get(url, params=params, timeout=45)
        except requests.RequestException as e:
            if i == tries - 1:
                raise ApiError("jaringan", bersih(type(e).__name__))
            time.sleep(3 * (i + 1))
            continue
        try:
            j = r.json()
        except ValueError:
            j = {}
        if r.status_code == 200 and isinstance(j, dict) and "error" not in j:
            return j
        err = (j.get("error") if isinstance(j, dict) else None) or {}
        code = err.get("code", r.status_code)
        msg = bersih(err.get("message") or r.text[:200])[:300]
        if code in (1, 2, 4, 17, 32, 613, 429, 500, 502, 503) and i < tries - 1:
            time.sleep(8 * (i + 1))
            continue
        raise ApiError(code, msg)
    raise ApiError("ulang", "gagal setelah beberapa kali coba")


def waktu(s):
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def batas_konten():
    return NOW - dt.timedelta(days=HARI_KONTEN)


def semua(url, params, batas=None, kunci="timestamp", maks_halaman=20):
    """Ambil data berhalaman (terbaru dulu); berhenti bila item terakhir lebih tua dari batas."""
    out, j, n = [], get(url, params), 0
    while True:
        data = j.get("data") or []
        out.extend(data)
        n += 1
        if batas and data:
            t = waktu(data[-1].get(kunci))
            if t and t < batas:
                break
        nxt = (j.get("paging") or {}).get("next")
        if not nxt or n >= maks_halaman:
            break
        j = get(nxt)
    return out


def potong(s, n=140):
    s = (s or "").strip().split("\n")[0].strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def angka(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, dict):
        vals = [x for x in v.values() if isinstance(x, (int, float))]
        return sum(vals) if vals else None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v) if "." in str(v) else int(v)
    except (TypeError, ValueError):
        return None


def nilai_insight(d):
    """Nilai satu metrik insight Meta/Threads: values[0].value atau total_value.value."""
    v = None
    if d.get("values"):
        v = d["values"][0].get("value")
    if v is None and isinstance(d.get("total_value"), dict):
        v = d["total_value"].get("value")
    return angka(v)


def status(kode, **kw):
    ST.setdefault(kode, {}).update(kw)


def catat_followers(kode, n):
    n = angka(n)
    if n is None:
        return
    tgl = HARI_INI.isoformat()
    FOLLOWERS[(kode, tgl)] = {"kode": kode, "akun": INFO[kode][3], "tanggal": tgl, "followers": n}


def baris(kode, kid, t, jenis, judul, link, **m):
    w = t.astimezone(WIB) if t else None
    return {
        "kunci": f"{INFO[kode][2].lower()}:{kid}",
        "kode": kode,
        "platform": INFO[kode][2],
        "brand": INFO[kode][1],
        "akun": INFO[kode][3],
        "id": str(kid),
        "tanggal": w.strftime("%Y-%m-%d") if w else "",
        "waktu": w.strftime("%Y-%m-%dT%H:%M") if w else "",
        "umur_hari": None,
        "jenis": jenis,
        "judul": potong(judul) or "(tanpa teks)",
        "link": link or "",
        "views": angka(m.get("views")),
        "reach": angka(m.get("reach")),
        "likes": angka(m.get("likes")),
        "komentar": angka(m.get("komentar")),
        "save": angka(m.get("save")),
        "share": angka(m.get("share")),
        "sumber": m.get("sumber", ""),
    }


def simpan(rows):
    for r in rows:
        KONTEN[r["kunci"]] = r


def warisi(kode, rows_baru, sumber_lama):
    """Untuk sumber berjendela terbatas (feed YouTube, angka publik IG): pertahankan posting lama yang tidak lagi
    muncul di sumber, dengan angka terakhir yang diketahui."""
    ada = {r["kunci"] for r in rows_baru}
    for k, r in LAMA_KONTEN.items():
        if r.get("kode") == kode and k not in ada and k not in KONTEN:
            KONTEN[k] = dict(r, sumber=sumber_lama)


def pakai_lama(kode):
    """Sumber gagal total: pakai baris konten lama akun ini apa adanya."""
    for k, r in LAMA_KONTEN.items():
        if r.get("kode") == kode and k not in KONTEN:
            KONTEN[k] = r


# ---------- Instagram (punya token) ----------
def ig_insight_media(mid, tok):
    """views, reach, save, share satu posting IG. None bila insight tidak tersedia sama sekali."""
    nama = {"views": "views", "reach": "reach", "saved": "save", "shares": "share"}
    try:
        j = get(f"{FB}/{mid}/insights", {"metric": "views,reach,saved,shares", "access_token": tok}, tries=2)
        return {nama[d["name"]]: nilai_insight(d) for d in j.get("data", []) if d.get("name") in nama}
    except ApiError:
        pass
    out = {}
    for m in nama:  # satu per satu: posting lama/jenis tertentu kadang tidak mendukung semua metrik
        try:
            j = get(f"{FB}/{mid}/insights", {"metric": m, "access_token": tok}, tries=1)
            for d in j.get("data", []):
                out[nama[m]] = nilai_insight(d)
        except ApiError:
            continue
    return out or None


def ig_jenis(m):
    if m.get("media_product_type") == "REELS":
        return "Reels"
    if m.get("media_type") == "CAROUSEL_ALBUM":
        return "Carousel"
    if m.get("media_type") == "VIDEO":
        return "Video"
    return "Foto"


def tanggal_meta(end_time):
    """end_time insight harian Meta = awal hari berikutnya (waktu Pasifik)."""
    t = waktu(end_time)
    return (t.astimezone(PT) - dt.timedelta(seconds=1)).date().isoformat() if t else None


def ig_harian(kode, ig_id, tok):
    catatan = []
    # reach dan followers baru: deret harian, maks 30 hari per permintaan
    for metrik, kolom, rentang in (("reach", "reach", [(HARI_HARIAN, 29), (29, 0)]), ("follower_count", "followers_baru", [(29, 0)])):
        for a, b in rentang:
            mulai = NOW - dt.timedelta(days=a)
            akhir = NOW - dt.timedelta(days=b)
            try:
                j = get(f"{FB}/{ig_id}/insights", {"metric": metrik, "period": "day", "since": int(mulai.timestamp()),
                                                   "until": int(akhir.timestamp()), "access_token": tok}, tries=2)
            except ApiError as e:
                catatan.append(f"{metrik} harian: {e.msg[:80]}")
                break
            for d in j.get("data", []):
                for v in d.get("values", []):
                    tgl = tanggal_meta(v.get("end_time"))
                    if tgl:
                        HARIAN.setdefault((kode, tgl), {"kode": kode, "akun": INFO[kode][3], "tanggal": tgl})[kolom] = angka(v.get("value"))
    # views: total per hari (metric_type=total_value), satu permintaan per hari yang belum ada
    hari_pt = NOW.astimezone(PT).date()
    for i in range(1, HARI_HARIAN + 1):
        tgl = hari_pt - dt.timedelta(days=i)
        r = HARIAN.get((kode, tgl.isoformat()))
        if r and r.get("views") is not None and i > 3:
            continue  # angka hari lama sudah tetap
        mulai = dt.datetime.combine(tgl, dt.time(0), PT)
        try:
            # Meta mengambil hari yang end_time-nya ada di [since, until]: +1 detik supaya hari sebelumnya tidak ikut
            j = get(f"{FB}/{ig_id}/insights", {"metric": "views", "period": "day", "metric_type": "total_value",
                                               "since": int(mulai.timestamp()) + 1, "until": int((mulai + dt.timedelta(days=1)).timestamp()),
                                               "access_token": tok}, tries=2)
        except ApiError as e:
            catatan.append(f"views harian: {e.msg[:80]}")
            break
        v = None
        for d in j.get("data", []):
            v = nilai_insight(d)
        baris_h = HARIAN.setdefault((kode, tgl.isoformat()), {"kode": kode, "akun": INFO[kode][3], "tanggal": tgl.isoformat()})
        baris_h["views"] = v
        baris_h["vv"] = 2
    return catatan


def ig_akun(kode, ig_id, tok):
    info = get(f"{FB}/{ig_id}", {"fields": "username,followers_count,media_count", "access_token": tok})
    status(kode, followers=angka(info.get("followers_count")), posting_total=angka(info.get("media_count")))
    catat_followers(kode, info.get("followers_count"))
    media = semua(f"{FB}/{ig_id}/media", {"fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count",
                                          "limit": 50, "access_token": tok}, batas_konten())
    rows, tanpa_insight = [], 0
    for m in media:
        t = waktu(m.get("timestamp"))
        if not t or t < batas_konten():
            continue
        kunci = f"instagram:{m['id']}"
        met = {"likes": m.get("like_count"), "komentar": m.get("comments_count"), "sumber": "API Instagram"}
        lama = LAMA_KONTEN.get(kunci) or {}
        if (NOW - t).days <= HARI_SEGAR or SENIN or not lama:
            ins = ig_insight_media(m["id"], tok)
            if ins is None:
                tanpa_insight += 1
                ins = {k: lama.get(k) for k in ("views", "reach", "save", "share")}
            met.update(ins)
        else:
            met.update({k: lama.get(k) for k in ("views", "reach", "save", "share")})
        rows.append(baris(kode, m["id"], t, ig_jenis(m), m.get("caption"), m.get("permalink"), **met))
    simpan(rows)
    catatan = ig_harian(kode, ig_id, tok)
    if tanpa_insight:
        catatan.insert(0, f"insight {tanpa_insight} posting tidak tersedia (biasanya posting lama)")
    status(kode, status="SEBAGIAN" if catatan else "OK", catatan="; ".join(catatan) or "lengkap: views, reach, likes, komentar, save, share",
           posting_diambil=len(rows))
    log(f"{kode}: {len(rows)} posting, followers {ST[kode].get('followers')}", "|", "; ".join(catatan))


def ig_tertaut(kode, pid, tok, harap):
    j = get(f"{FB}/{pid}", {"fields": "instagram_business_account{id,username}", "access_token": tok})
    ig = j.get("instagram_business_account") or {}
    if not ig.get("id"):
        status(kode, status="TIDAK TERSEDIA", catatan=f"Instagram @{harap} tidak tertaut ke Page yang tokennya tersimpan")
        pakai_lama(kode)
        log(f"{kode}: tidak ada Instagram tertaut")
        return
    if (ig.get("username") or "").lower() != harap:
        status(kode, status="TIDAK TERSEDIA", catatan=f"Page itu tertaut ke @{ig.get('username')}, bukan @{harap}")
        pakai_lama(kode)
        log(f"{kode}: IG tertaut lain (@{ig.get('username')})")
        return
    PENANYA.append((ig["id"], tok))
    ig_akun(kode, ig["id"], tok)


# ---------- Facebook Page ----------
SALAH_METRIK = set()  # (jenis objek, metrik) yang ditolak API, supaya tidak dicoba berulang


def fb_insight(obj_id, tok, jenis, kebutuhan):
    out = {}
    for kolom, calon in kebutuhan:
        for m in calon:
            if (jenis, m) in SALAH_METRIK:
                continue
            try:
                j = get(f"{FB}/{obj_id}/insights", {"metric": m, "access_token": tok}, tries=1)
            except ApiError as e:
                if e.code in (100, "100"):
                    SALAH_METRIK.add((jenis, m))
                continue
            v = None
            for d in j.get("data", []):
                v = nilai_insight(d)
            if v is not None:
                out[kolom] = v
                break
    return out


def norm_link(u):
    return (u or "").split("?")[0].rstrip("/").lower()


FB_POST_FIELDS = ("id,created_time,message,permalink_url,status_type,shares,"
                  "reactions.limit(0).summary(total_count),comments.limit(0).summary(total_count)")


def fb_dari_antrian(platform_antrian):
    """Posting Facebook yang pernah diterbitkan mesin ini (folder queue/), untuk dibaca satu per satu lewat ID-nya."""
    out = []
    for p in sorted(glob.glob(os.path.join("queue", f"*__{platform_antrian}.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        res = d.get("result") or {}
        if d.get("status") == "posted" and res.get("id"):
            out.append({"id": str(res["id"]), "url": res.get("url") or "", "waktu": d.get("posted_at") or d.get("publish_at"),
                        "teks": d.get("message") or ""})
    return out


def fb_baris_reel(kode, v, tok, reel_link):
    t = waktu(v.get("created_time"))
    if not t or t < batas_konten():
        return None
    link = v.get("permalink_url") or ""
    if link.startswith("/"):
        link = "https://www.facebook.com" + link
    reel_link.add(norm_link(link))
    reel_link.add(str(v["id"]))
    met = {"sumber": "API Facebook"}
    met.update(fb_insight(v["id"], tok, "reel", [("views", ["blue_reels_play_count", "post_video_views"]),
                                                  ("reach", ["post_impressions_unique"])]))
    return baris(kode, v["id"], t, "Reels", v.get("description"), link, **met)


def fb_halaman(kode, pid, tok, platform_antrian):
    info = get(f"{FB}/{pid}", {"fields": "id,name,username,followers_count,fan_count", "access_token": tok})
    status(kode, followers=angka(info.get("followers_count") or info.get("fan_count")))
    catat_followers(kode, info.get("followers_count") or info.get("fan_count"))
    rows, catatan, reel_link = [], [], set()
    try:
        reels = semua(f"{FB}/{pid}/video_reels", {"fields": "id,description,created_time,permalink_url", "limit": 50, "access_token": tok},
                      batas_konten(), "created_time")
    except ApiError as e:
        reels = []
        log(f"{kode}: daftar Reels tidak terbaca ({e.msg[:80]})")
    for v in reels:
        r = fb_baris_reel(kode, v, tok, reel_link)
        if r:
            rows.append(r)
    posts = None
    for edge in ("posts", "published_posts"):
        try:
            posts = semua(f"{FB}/{pid}/{edge}", {"fields": FB_POST_FIELDS, "limit": 50, "access_token": tok}, batas_konten(), "created_time")
            break
        except ApiError as e:
            log(f"{kode}: /{edge} tidak terbaca ({e.msg[:80]})")
    if posts is None:
        # token tidak boleh membaca daftar posting Page: baca posting yang diterbitkan mesin ini satu per satu
        catatan.append("hanya posting yang diterbitkan mesin konten (daftar posting Page butuh izin pages_read_user_content)")
        posts = []
        for q in fb_dari_antrian(platform_antrian):
            if norm_link(q["url"]) in reel_link or q["id"] in reel_link:
                continue
            if "/reel/" in q["url"] or "/videos/" in q["url"]:
                try:
                    v = get(f"{FB}/{q['id']}", {"fields": "id,description,created_time,permalink_url", "access_token": tok}, tries=2)
                except ApiError:
                    v = {"id": q["id"], "description": q["teks"], "created_time": q["waktu"], "permalink_url": q["url"]}
                r = fb_baris_reel(kode, v, tok, reel_link)
                if r:
                    rows.append(r)
                continue
            try:
                posts.append(get(f"{FB}/{q['id']}", {"fields": FB_POST_FIELDS, "access_token": tok}, tries=2))
            except ApiError:
                posts.append({"id": q["id"], "created_time": q["waktu"], "message": q["teks"], "permalink_url": q["url"]})
    for p in posts:
        t = waktu(p.get("created_time"))
        if not t or t < batas_konten():
            continue
        link = p.get("permalink_url") or ""
        if norm_link(link) in reel_link or any(x in link for x in reel_link if x.isdigit()):
            continue  # Reels yang sama sudah diambil di atas
        met = {"likes": ((p.get("reactions") or {}).get("summary") or {}).get("total_count"),
               "komentar": ((p.get("comments") or {}).get("summary") or {}).get("total_count"),
               "share": (p.get("shares") or {}).get("count", 0), "sumber": "API Facebook"}
        met.update(fb_insight(p["id"], tok, "post", [("views", ["post_media_view", "post_impressions"]),
                                                      ("reach", ["post_total_media_view_unique", "post_impressions_unique"])]))
        jenis = "Video" if p.get("status_type") == "added_video" else "Posting"
        rows.append(baris(kode, p["id"], t, jenis, p.get("message"), link, **met))
    simpan(rows)
    tanpa_views = sum(1 for r in rows if r["views"] is None)
    if tanpa_views:
        catatan.append(f"views {tanpa_views} posting tidak tersedia")
    status(kode, status="SEBAGIAN" if catatan else "OK", catatan="; ".join(catatan) or "views, reach, reaksi, komentar, share",
           posting_diambil=len(rows))
    log(f"{kode}: {len(rows)} posting (Reels {len(reels)}), followers {ST[kode].get('followers')}", "|", "; ".join(catatan))


# ---------- Threads ----------
def threads_akun(kode):
    tok = os.environ.get("THREADS_ACCESS_TOKEN")
    if not tok:
        status(kode, status="GAGAL", catatan="secret THREADS_ACCESS_TOKEN belum ada")
        pakai_lama(kode)
        return
    uid = os.environ.get("THREADS_USER_ID") or get(f"{TH}/me", {"fields": "id", "access_token": tok})["id"]
    catatan, izin = [], True
    try:
        f = get(f"{TH}/{uid}/threads_insights", {"metric": "followers_count", "access_token": tok}, tries=2)
        n = None
        for d in f.get("data", []):
            n = nilai_insight(d)
        status(kode, followers=n)
        catat_followers(kode, n)
    except ApiError as e:
        izin = False
        catatan.append(f"insight Threads belum diizinkan token ({e.msg[:60]})")
    posts = semua(f"{TH}/{uid}/threads", {"fields": "id,text,timestamp,permalink,media_type", "limit": 50, "access_token": tok},
                  batas_konten())
    rows = []
    for p in posts:
        t = waktu(p.get("timestamp"))
        if not t or t < batas_konten() or p.get("media_type") == "REPOST_FACADE":
            continue
        met = {"sumber": "API Threads"}
        if izin:
            for metrik in ("views,likes,replies,reposts,quotes,shares", "views,likes,replies,reposts,quotes"):
                try:
                    j = get(f"{TH}/{p['id']}/insights", {"metric": metrik, "access_token": tok}, tries=2)
                except ApiError:
                    continue
                v = {d.get("name"): nilai_insight(d) for d in j.get("data", [])}
                share = [v.get(k) for k in ("reposts", "quotes", "shares") if v.get(k) is not None]
                met.update(views=v.get("views"), likes=v.get("likes"), komentar=v.get("replies"), share=sum(share) if share else None)
                break
        rows.append(baris(kode, p["id"], t, "Threads", p.get("text"), p.get("permalink"), **met))
    simpan(rows)
    if izin and rows and all(r["views"] is None for r in rows):
        catatan.append("insight posting Threads tidak tersedia")
    status(kode, status="SEBAGIAN" if catatan else "OK", catatan="; ".join(catatan) or "views, likes, balasan, repost", posting_diambil=len(rows))
    log(f"{kode}: {len(rows)} posting", "|", "; ".join(catatan))


# ---------- YouTube (feed publik) ----------
def yt_id_kanal(handle, contoh):
    url = f"https://www.youtube.com/{handle}" if handle else None
    if not url:
        o = SES.get("https://www.youtube.com/oembed", params={"url": f"https://www.youtube.com/watch?v={contoh}", "format": "json"},
                    headers=UA, timeout=30)
        o.raise_for_status()
        url = o.json().get("author_url")
    h = SES.get(url, headers=UA, timeout=30)
    h.raise_for_status()
    m = (re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', h.text)
         or re.search(r'"(?:externalId|channelId|browseId)":"(UC[\w-]{22})"', h.text))
    if not m:
        raise ApiError("youtube", f"ID kanal tidak ditemukan di {url}")
    return m.group(1)


def youtube_kanal(kode, handle, contoh):
    cid = (LAMA_AKUN.get(kode) or {}).get("id_kanal") or yt_id_kanal(handle, contoh)
    r = SES.get("https://www.youtube.com/feeds/videos.xml", params={"channel_id": cid}, headers=UA, timeout=30)
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "m": "http://search.yahoo.com/mrss/"}
    root = ET.fromstring(r.content)
    rows = []
    for e in root.findall("a:entry", ns):
        vid = e.findtext("yt:videoId", namespaces=ns)
        if not vid:
            continue
        el = e.find("a:link[@rel='alternate']", ns)
        link = el.get("href") if el is not None else f"https://www.youtube.com/watch?v={vid}"
        st = e.find("m:group/m:community/m:statistics", ns)
        rt = e.find("m:group/m:community/m:starRating", ns)
        rows.append(baris(kode, vid, waktu(e.findtext("a:published", namespaces=ns)), "Shorts" if "/shorts/" in link else "Video",
                          e.findtext("a:title", default="", namespaces=ns), link,
                          views=st.get("views") if st is not None else None,
                          likes=rt.get("count") if rt is not None else None,
                          sumber="feed publik YouTube"))
    simpan(rows)
    warisi(kode, rows, "feed publik YouTube (angka terakhir)")
    status(kode, status="SEBAGIAN", id_kanal=cid, nama=root.findtext("a:title", default="", namespaces=ns),
           catatan="views dan likes 15 video terbaru dari feed publik; subscriber dan reach butuh izin baca YouTube",
           posting_diambil=len(rows))
    log(f"{kode}: {len(rows)} video dari feed ({ST[kode].get('nama')})")


# ---------- Instagram angka publik (business discovery) ----------
def ig_publik(kode, username):
    if not PENANYA:
        raise ApiError("izin", "butuh akun Instagram bertoken (nopal atau portal) untuk membaca angka publik")
    ig_id, tok = PENANYA[0]
    f = ("business_discovery.username(%s){username,followers_count,media_count,"
         "media.limit(50){id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count}}") % username
    bd = get(f"{FB}/{ig_id}", {"fields": f, "access_token": tok}).get("business_discovery") or {}
    status(kode, followers=angka(bd.get("followers_count")), posting_total=angka(bd.get("media_count")))
    catat_followers(kode, bd.get("followers_count"))
    rows = []
    for m in (bd.get("media") or {}).get("data", []):
        t = waktu(m.get("timestamp"))
        if not t or t < batas_konten():
            continue
        rows.append(baris(kode, m["id"], t, ig_jenis(m), m.get("caption"), m.get("permalink"),
                          likes=m.get("like_count"), komentar=m.get("comments_count"), sumber="angka publik Instagram"))
    simpan(rows)
    warisi(kode, rows, "angka publik Instagram (angka terakhir)")
    status(kode, status="SEBAGIAN", catatan="angka publik (followers, likes, komentar) 50 posting terbaru; views, reach, save butuh token Skalarium",
           posting_diambil=len(rows))
    log(f"{kode}: {len(rows)} posting publik, followers {ST[kode].get('followers')}")


# ---------- simpan ----------
def baca(nama):
    try:
        with open(os.path.join(OUT, nama), encoding="utf-8") as f:
            d = json.load(f)
        return d.get("rows", []) if isinstance(d, dict) else []
    except (OSError, ValueError):
        return []


def tulis(nama, rows):
    data = {"diperbarui": NOW.astimezone(WIB).strftime("%Y-%m-%d %H:%M WIB"), "rows": rows}
    with open(os.path.join(OUT, nama), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
        f.write("\n")


def jalan(kode_list, fungsi, *args):
    try:
        fungsi(*args)
    except Exception as e:  # satu sumber gagal tidak menghentikan yang lain
        pesan = bersih(e)[:200]
        log(f"GAGAL {', '.join(kode_list)}: {type(e).__name__}: {pesan}")
        for k in kode_list:
            if ST.get(k, {}).get("status") not in ("OK", "SEBAGIAN"):
                status(k, status="GAGAL", catatan=pesan)
            pakai_lama(k)


def main():
    os.makedirs(OUT, exist_ok=True)
    LAMA_KONTEN.update({r["kunci"]: r for r in baca("konten.json") if r.get("kunci")})
    LAMA_AKUN.update({r["kode"]: r for r in baca("akun.json") if r.get("kode")})
    for r in baca("harian.json"):
        if r.get("kode") and r.get("tanggal"):
            if r.get("vv") != 2:
                r.pop("views", None)  # views versi awal terhitung 2 hari; ambil ulang
            HARIAN[(r["kode"], r["tanggal"])] = r
    FOLLOWERS.update({(r["kode"], r["tanggal"]): r for r in baca("followers.json") if r.get("kode") and r.get("tanggal")})
    log(f"Mulai {NOW.astimezone(WIB):%Y-%m-%d %H:%M} WIB (Senin = segarkan semua insight: {SENIN})")

    for awalan, kode_fb, kode_ig, harap, antrian in (("", "nopal-fb", "nopal-ig", "nopal.brainwork", "facebook"),
                                                     ("PORTAL_", "portal-fb", "portal-ig", "brainwork.id", "facebook_portal")):
        tok, pid = os.environ.get(awalan + "FB_PAGE_TOKEN"), os.environ.get(awalan + "FB_PAGE_ID")
        if not tok or not pid:
            for k in (kode_fb, kode_ig):
                status(k, status="GAGAL", catatan=f"secret {awalan}FB_PAGE_TOKEN/{awalan}FB_PAGE_ID belum ada")
                pakai_lama(k)
            continue
        jalan([kode_ig], ig_tertaut, kode_ig, pid, tok, harap)
        jalan([kode_fb], fb_halaman, kode_fb, pid, tok, antrian)
    jalan(["nopal-threads"], threads_akun, "nopal-threads")
    for kode, handle, contoh in YOUTUBE:
        jalan([kode], youtube_kanal, kode, handle, contoh)
    for kode, username in IG_PUBLIK:
        jalan([kode], ig_publik, kode, username)
    for kode, alasan in BELUM_BISA.items():
        status(kode, status="TIDAK TERSEDIA", catatan=alasan)

    # konten: umur dihitung ulang, buang yang lewat batas
    rows = []
    for r in KONTEN.values():
        try:
            umur = (HARI_INI - dt.date.fromisoformat(r["tanggal"])).days
        except (KeyError, ValueError):
            continue
        if umur <= HARI_KONTEN:
            rows.append(dict(r, umur_hari=umur))
    rows.sort(key=lambda r: r.get("waktu", ""), reverse=True)
    tulis("konten.json", rows)

    akun = []
    for kode, brand, platform, nama, posting, plan in AKUN:
        s, lama = ST.get(kode, {}), LAMA_AKUN.get(kode, {})
        gagal = s.get("status") == "GAGAL"
        akun.append({
            "kode": kode, "brand": brand, "platform": platform, "akun": nama, "posting": posting, "plan": plan,
            "followers": s.get("followers") if s.get("followers") is not None else (lama.get("followers") if gagal else None),
            "posting_total": s.get("posting_total") if s.get("posting_total") is not None else (lama.get("posting_total") if gagal else None),
            "konten_tercatat": sum(1 for r in rows if r["kode"] == kode),
            "status": s.get("status", "TIDAK TERSEDIA"),
            "catatan": s.get("catatan", ""),
            "id_kanal": s.get("id_kanal") or lama.get("id_kanal") or "",
        })
    tulis("akun.json", akun)

    batas_riwayat = (HARI_INI - dt.timedelta(days=RIWAYAT_MAKS)).isoformat()
    tulis("harian.json", sorted((r for r in HARIAN.values() if r["tanggal"] >= batas_riwayat), key=lambda r: (r["kode"], r["tanggal"])))
    tulis("followers.json", sorted((r for r in FOLLOWERS.values() if r["tanggal"] >= batas_riwayat), key=lambda r: (r["kode"], r["tanggal"])))

    ringkas = ", ".join(f"{a['kode']}={a['status']}" for a in akun)
    log(f"Selesai: {len(rows)} konten. {ringkas}")
    with open(os.path.join(OUT, "log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
