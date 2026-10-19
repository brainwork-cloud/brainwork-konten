#!/usr/bin/env python3
"""
Publisher Threads + Facebook Page + YouTube Shorts @nopal.brainwork + Facebook dan Instagram portal Brainwork.id
(dijalankan GitHub Actions tiap 30 menit).

Antrian: file queue/<ID>__<platform>.json, ditulis agen HANYA untuk konten berstatus APPROVED/POSTED di Sheet.
{
  "id": "BW-261014-01",
  "platform": "threads" | "facebook" | "youtube" | "facebook_portal" | "instagram_portal",
  "publish_at": "2026-10-14T19:00:00+07:00",
  "status": "approved",                 # approved -> posted | failed ; cancelled = dilewati
  # threads
  "posts": ["post 1", "post 2"],        # 1 item = single post, >1 = utas (balasan berantai)
  "image_url": null,                    # opsional, hanya untuk post pertama
  # facebook (mirror dari IG): salah satu dari
  "message": "caption",
  "image_urls": ["https://raw.githubusercontent.com/.../_01.jpg", ...],   # carousel -> post multi-foto
  "video_url": "https://raw.githubusercontent.com/.../<ID>.mp4",          # reels -> Facebook Reels
  # facebook_portal (portal berita Brainwork.id, produksi sendiri, BUKAN mirror; halaman Facebook terpisah).
  # Tiga format bergilir; pilih SATU jenis media per file antrian:
  "message": "caption (wajib memuat kata 'Sumber' dan tautan http)",
  "image_url": "https://raw.githubusercontent.com/.../aset/<ID>/<ID>.jpg"          # single post (kartu berita 1 gambar)
  "image_urls": ["https://.../aset/<ID>/<ID>_01.jpg", ... "_NN.jpg"]               # carousel (2-10 gambar) -> post multi-foto
  "video_url": "https://raw.githubusercontent.com/.../aset/<ID>/<ID>.mp4"          # Reels Motion -> Facebook Reels
  # instagram_portal (mirror konten portal yang sama ke @brainwork.id lewat Graph API; akun IG dicari dari halaman portal)
  "message": "caption (wajib memuat 'Sumber' dan tautan http, maks 2200 karakter)", dan media yang SAMA persis dengan Facebook:
  "image_url" (1 gambar) | "image_urls" (carousel 2-10 gambar: container anak lalu container induk CAROUSEL) | "video_url" (REELS, share_to_feed)
  # youtube
  "video_path": "aset/BW-261014-01/BW-261014-01.mp4",
  "title": "...", "description": "...", "tags": ["..."]
}
Hasil ditulis kembali ke file yang sama: status, posted_at, result (id/url) atau error.
Secrets (GitHub Actions): THREADS_ACCESS_TOKEN, THREADS_USER_ID, FB_PAGE_TOKEN, FB_PAGE_ID,
                          PORTAL_FB_PAGE_TOKEN, PORTAL_FB_PAGE_ID,
                          YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Pengaman (dua halaman Facebook tidak boleh tertukar):
- "facebook" (mirror @nopal.brainwork): nama halaman FB_PAGE_ID harus mengandung "brainwork" DAN halamannya bukan brainwork.id.
- "facebook_portal": username halaman PORTAL_FB_PAGE_ID harus "brainwork.id", id-nya beda dari FB_PAGE_ID, caption wajib memuat
  "Sumber" + tautan, tepat satu jenis media (gambar / carousel / video). Media belum ada (404) = ditunda, tetap approved,
  dicoba lagi 30 menit kemudian.
- "instagram_portal": lolos pengaman halaman portal di atas, lalu akun IG yang tertaut ke halaman itu harus berusername "brainwork.id".
  Token yang sama (PORTAL_FB_PAGE_TOKEN), tanpa secret baru. Kegagalan IG tidak memengaruhi posting Facebook (file antrian terpisah).
"""
import os, sys, json, glob, time, datetime as dt
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
NOW = dt.datetime.now(dt.timezone.utc)
MAX_PER_RUN = 4
PORTAL_USERNAME = "brainwork.id"


class Tunda(Exception):
    """Belum bisa diposting sekarang (mis. gambar belum dirender); status tetap approved."""
TH = "https://graph.threads.net/v1.0"
FB = "https://graph.facebook.com/v23.0"


def threads_post(item):
    tok = os.environ["THREADS_ACCESS_TOKEN"]
    uid = os.environ.get("THREADS_USER_ID") or requests.get(f"{TH}/me", params={"fields": "id", "access_token": tok}, timeout=30).json()["id"]
    reply_to, ids = None, []
    for i, text in enumerate(item["posts"]):
        if len(text) > 500:
            raise ValueError(f"post {i+1} lebih dari 500 karakter")
        params = {"access_token": tok, "text": text, "media_type": "TEXT"}
        if i == 0 and item.get("image_url"):
            params.update(media_type="IMAGE", image_url=item["image_url"])
        if reply_to:
            params["reply_to_id"] = reply_to
        r = requests.post(f"{TH}/{uid}/threads", data=params, timeout=60)
        r.raise_for_status()
        cid = r.json()["id"]
        time.sleep(5 if params["media_type"] == "TEXT" else 30)
        p = requests.post(f"{TH}/{uid}/threads_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
        p.raise_for_status()
        reply_to = p.json()["id"]
        ids.append(reply_to)
        time.sleep(3)
    link = requests.get(f"{TH}/{ids[0]}", params={"fields": "permalink", "access_token": tok}, timeout=30).json()
    return {"ids": ids, "url": link.get("permalink")}


def fb_page(portal=False):
    """Kembalikan (page_id, token) setelah memastikan halamannya benar. Ada DUA halaman Facebook yang tidak boleh tertukar:
    - Mirror @nopal.brainwork: FB_PAGE_ID/FB_PAGE_TOKEN. Nama harus mengandung "brainwork" dan BUKAN halaman portal.
    - Portal Brainwork.id: PORTAL_FB_PAGE_ID/PORTAL_FB_PAGE_TOKEN. Username halaman harus "brainwork.id".
    Id kedua halaman juga harus berbeda. Tidak pernah posting ke halaman lain."""
    pre = "PORTAL_" if portal else ""
    tok, pid = os.environ[pre + "FB_PAGE_TOKEN"], os.environ[pre + "FB_PAGE_ID"]
    r = requests.get(f"{FB}/{pid}", params={"fields": "id,name,username,link", "access_token": tok}, timeout=30)
    r.raise_for_status()
    d = r.json()
    name, user = d.get("name", ""), (d.get("username") or "").lower()
    link = (d.get("link") or "").lower().rstrip("/")
    is_portal = user == PORTAL_USERNAME or link.endswith("/" + PORTAL_USERNAME)
    lain = os.environ.get("FB_PAGE_ID" if portal else "PORTAL_FB_PAGE_ID", "")
    if lain and lain in (pid, d.get("id")):
        raise RuntimeError("FB_PAGE_ID dan PORTAL_FB_PAGE_ID menunjuk halaman yang sama; posting dibatalkan")
    if portal and not is_portal:
        raise RuntimeError(f"PORTAL_FB_PAGE_ID bukan halaman brainwork.id (nama: {name!r}, username: {user!r}); posting dibatalkan")
    if not portal and ("brainwork" not in name.lower() or is_portal):
        raise RuntimeError(f"FB_PAGE_ID bukan halaman mirror Nopal (nama: {name!r}, username: {user!r}); posting dibatalkan")
    return pid, tok


def _fb_wait(vid, tok, phase, tries=90):
    for _ in range(tries):
        st = requests.get(f"{FB}/{vid}", params={"fields": "status", "access_token": tok}, timeout=30).json().get("status", {})
        s = (st.get(phase) or {}).get("status")
        if s == "complete":
            return
        if s == "error":
            raise RuntimeError(f"{phase} gagal: {json.dumps(st)[:500]}")
        time.sleep(10)
    raise TimeoutError(f"{phase} belum selesai setelah {tries * 10} detik")


def facebook_post(item, portal=False):
    pid, tok = fb_page(portal)
    text = item.get("message", "") or ""
    if item.get("video_url"):  # Facebook Reels dari file publik (raw.githubusercontent)
        s = requests.post(f"{FB}/{pid}/video_reels", data={"upload_phase": "start", "access_token": tok}, timeout=60)
        s.raise_for_status()
        vid = s.json()["video_id"]
        up_url = s.json().get("upload_url") or f"https://rupload.facebook.com/video-upload/v23.0/{vid}"
        u = requests.post(up_url, headers={"Authorization": f"OAuth {tok}", "file_url": item["video_url"]}, timeout=300)
        u.raise_for_status()
        _fb_wait(vid, tok, "uploading_phase")
        f = requests.post(f"{FB}/{pid}/video_reels", data={"upload_phase": "finish", "video_id": vid,
                          "video_state": "PUBLISHED", "description": text, "access_token": tok}, timeout=60)
        f.raise_for_status()
        _fb_wait(vid, tok, "publishing_phase")
        perma = requests.get(f"{FB}/{vid}", params={"fields": "permalink_url", "access_token": tok}, timeout=30).json().get("permalink_url", "")
        url = ("https://www.facebook.com" + perma) if perma.startswith("/") else (perma or f"https://www.facebook.com/reel/{vid}")
        return {"id": vid, "url": url}
    if item.get("image_url") and not item.get("image_urls"):  # satu foto (kartu berita portal)
        r = requests.post(f"{FB}/{pid}/photos", data={"url": item["image_url"], "message": text, "access_token": tok}, timeout=120)
        r.raise_for_status()
        j = r.json()
        post_id = j.get("post_id") or j["id"]
        return {"id": post_id, "url": f"https://www.facebook.com/{post_id}"}
    if item.get("image_urls"):  # carousel IG -> post multi-foto
        ids = []
        for url in item["image_urls"][:10]:
            p = requests.post(f"{FB}/{pid}/photos", data={"url": url, "published": "false", "access_token": tok}, timeout=120)
            p.raise_for_status()
            ids.append(p.json()["id"])
        data = {"message": text, "access_token": tok}
        for i, mid in enumerate(ids):
            data[f"attached_media[{i}]"] = json.dumps({"media_fbid": mid})
        r = requests.post(f"{FB}/{pid}/feed", data=data, timeout=120)
        r.raise_for_status()
        post_id = r.json()["id"]
        return {"id": post_id, "url": f"https://www.facebook.com/{post_id}"}
    if not text:
        raise ValueError("facebook: butuh message, image_urls, atau video_url")
    r = requests.post(f"{FB}/{pid}/feed", data={"message": text, "access_token": tok}, timeout=60)
    r.raise_for_status()
    post_id = r.json()["id"]
    return {"id": post_id, "url": f"https://www.facebook.com/{post_id}"}


def _cek_url(u):
    """Media harus sudah bisa dibuka publik (hasil render sudah ter-push). Belum bisa = Tunda (tetap approved)."""
    try:
        ok = requests.head(u, allow_redirects=True, timeout=30).status_code == 200
    except requests.RequestException:
        ok = False
    if not ok:
        raise Tunda(f"media belum tersedia: {u}")


def _portal_media(item, label):
    """Validasi media portal: tepat satu jenis. Mengembalikan ("video", url) atau ("images", [url, ...])."""
    video = item.get("video_url")
    urls = item.get("image_urls") or ([item["image_url"]] if item.get("image_url") else [])
    if video and urls:
        raise ValueError(f"{label}: pilih salah satu, gambar (image_url/image_urls) atau video_url, bukan keduanya")
    if not video and not urls:
        raise ValueError(f"{label}: butuh image_url (single), image_urls (carousel) atau video_url (Reels Motion)")
    if len(urls) > 10:
        raise ValueError(f"{label}: maksimal 10 gambar per carousel")
    for u in ([video] if video else urls):
        _cek_url(u)
    return ("video", video) if video else ("images", urls)


def _cek_caption(text, label):
    if "sumber" not in text.lower() or "http" not in text.lower():
        raise ValueError(f"{label}: caption wajib memuat 'Sumber' dan tautan sumber (http...)")


def facebook_portal(item):
    """Portal Brainwork.id: berita bersumber ke halaman portal saja. Format: 1 gambar, carousel (multi-foto) atau Reels."""
    text = item.get("message") or ""
    _cek_caption(text, "portal")
    kind, media = _portal_media(item, "portal")
    if kind == "video":
        it = dict(item, image_url=None, image_urls=None)
    elif len(media) == 1:  # satu gambar = post foto biasa
        it = dict(item, image_url=media[0], image_urls=None, video_url=None)
    else:  # carousel = post multi-foto
        it = dict(item, image_url=None, image_urls=media, video_url=None)
    return facebook_post(it, portal=True)


def ig_portal_account():
    """Akun Instagram portal: dicari dari halaman Facebook portal (tertaut), username WAJIB brainwork.id.
    Memakai token halaman portal yang sama; tidak ada secret baru. Mengembalikan (ig_user_id, token)."""
    pid, tok = fb_page(portal=True)  # pengaman halaman Facebook portal (username brainwork.id, bukan halaman mirror Nopal)
    r = requests.get(f"{FB}/{pid}", params={"fields": "instagram_business_account{id,username}", "access_token": tok}, timeout=30)
    r.raise_for_status()
    ig = r.json().get("instagram_business_account") or {}
    if not ig.get("id") or (ig.get("username") or "").lower() != PORTAL_USERNAME:
        raise RuntimeError(f"akun Instagram yang tertaut ke halaman portal bukan @brainwork.id (ditemukan: {ig.get('username')!r}); posting dibatalkan")
    return ig["id"], tok


def _ig_wait(cid, tok, tries, jeda):
    """Tunggu container Instagram FINISHED (gambar cepat, video lebih lama)."""
    for _ in range(tries):
        j = requests.get(f"{FB}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
        st = j.get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container Instagram {st}: {str(j.get('status'))[:300]}")
        time.sleep(jeda)
    raise TimeoutError(f"container Instagram belum FINISHED setelah {tries * jeda} detik")


def instagram_portal(item):
    """Portal Brainwork.id di Instagram (@brainwork.id saja, Graph API), media sama dengan Facebook:
    1 gambar (IMAGE), 2-10 gambar (CAROUSEL: container anak lalu induk), atau video (REELS, tampil juga di feed)."""
    text = item.get("message") or ""
    _cek_caption(text, "portal IG")
    if len(text) > 2200:
        raise ValueError(f"portal IG: caption {len(text)} karakter, batas Instagram 2200")
    kind, media = _portal_media(item, "portal IG")
    ig, tok = ig_portal_account()

    def buat(data):
        c = requests.post(f"{FB}/{ig}/media", data={**data, "access_token": tok}, timeout=120)
        c.raise_for_status()
        return c.json()["id"]

    if kind == "video":
        cid = buat({"media_type": "REELS", "video_url": media, "caption": text, "share_to_feed": "true"})
        _ig_wait(cid, tok, 60, 10)  # video: sampai 10 menit
    elif len(media) == 1:
        cid = buat({"image_url": media[0], "caption": text})
        _ig_wait(cid, tok, 30, 5)
    else:
        anak = [buat({"image_url": u, "is_carousel_item": "true"}) for u in media]
        for k in anak:
            _ig_wait(k, tok, 30, 5)
        cid = buat({"media_type": "CAROUSEL", "children": ",".join(anak), "caption": text})
        _ig_wait(cid, tok, 30, 5)
    p = requests.post(f"{FB}/{ig}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=120)
    p.raise_for_status()
    mid = p.json()["id"]
    perma = requests.get(f"{FB}/{mid}", params={"fields": "permalink", "access_token": tok}, timeout=30).json().get("permalink")
    return {"id": mid, "url": perma or f"https://www.instagram.com/{PORTAL_USERNAME}/"}


def youtube_post(item):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    yt = build("youtube", "v3", credentials=creds)
    title = item["title"][:100]
    desc = item.get("description", "")
    if "#shorts" not in (title + desc).lower():
        desc += "\n#shorts"
    body = {"snippet": {"title": title, "description": desc, "tags": item.get("tags", []), "categoryId": "27",
                        "defaultLanguage": "id"},
            "status": {"privacyStatus": item.get("privacy", "public"), "selfDeclaredMadeForKids": False}}
    path = os.path.join(ROOT, item["video_path"])
    if not os.path.exists(path) and item.get("video_url"):  # fallback: unduh dari URL publik
        with requests.get(item["video_url"], stream=True, timeout=300) as r:
            r.raise_for_status()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
    media = MediaFileUpload(path, mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return {"id": resp["id"], "url": f"https://youtube.com/shorts/{resp['id']}"}


HANDLERS = {"threads": threads_post, "facebook": facebook_post, "youtube": youtube_post, "facebook_portal": facebook_portal,
            "instagram_portal": instagram_portal}
NEEDS = {"threads": ["THREADS_ACCESS_TOKEN"], "facebook": ["FB_PAGE_TOKEN", "FB_PAGE_ID"],
         "facebook_portal": ["PORTAL_FB_PAGE_TOKEN", "PORTAL_FB_PAGE_ID"],
         "instagram_portal": ["PORTAL_FB_PAGE_TOKEN", "PORTAL_FB_PAGE_ID"],
         "youtube": ["YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]}


def main():
    done = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "queue", "*.json"))):
        item = json.load(open(path, encoding="utf-8"))
        if item.get("status") != "approved":
            continue
        plat = item.get("platform")
        missing = [k for k in NEEDS.get(plat, []) if not os.environ.get(k)]
        if missing:  # secret belum diisi: biarkan tetap approved, coba lagi nanti (tidak dihitung terlewat)
            print(item["id"], plat, "menunggu secret:", ", ".join(missing))
            continue
        when = dt.datetime.fromisoformat(item["publish_at"])
        if when > NOW or NOW - when > dt.timedelta(hours=12):
            if NOW - when > dt.timedelta(hours=12):
                item.update(status="failed", error="terlewat > 12 jam, tidak diposting")
                json.dump(item, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            continue
        if done >= MAX_PER_RUN:
            break
        try:
            item["result"] = HANDLERS[plat](item)
            item["status"] = "posted"
        except Tunda as e:  # belum siap: biarkan approved, coba lagi di run berikutnya
            print(item["id"], plat, "ditunda:", e)
            continue
        except Exception as e:  # catat, jangan ulang terus
            item["status"] = "failed"
            item["error"] = f"{type(e).__name__}: {getattr(getattr(e, 'response', None), 'text', '') or e}"[:800]
        item["posted_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        json.dump(item, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(item["id"], plat, item["status"], item.get("result") or item.get("error"))
        done += 1
    print(f"selesai: {done} item diproses")


if __name__ == "__main__":
    main()
