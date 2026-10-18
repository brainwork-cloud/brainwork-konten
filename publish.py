#!/usr/bin/env python3
"""
Publisher Threads + Facebook Page + YouTube Shorts @nopal.brainwork (dijalankan GitHub Actions tiap 30 menit).

Antrian: file queue/<ID>__<platform>.json, ditulis agen HANYA untuk konten berstatus APPROVED/POSTED di Sheet.
{
  "id": "BW-261014-01",
  "platform": "threads" | "facebook" | "youtube",
  "publish_at": "2026-10-14T19:00:00+07:00",
  "status": "approved",                 # approved -> posted | failed ; cancelled = dilewati
  # threads
  "posts": ["post 1", "post 2"],        # 1 item = single post, >1 = utas (balasan berantai)
  "image_url": null,                    # opsional, hanya untuk post pertama
  # facebook (mirror dari IG): salah satu dari
  "message": "caption",
  "image_urls": ["https://raw.githubusercontent.com/.../_01.jpg", ...],   # carousel -> post multi-foto
  "video_url": "https://raw.githubusercontent.com/.../<ID>.mp4",          # reels -> Facebook Reels
  # youtube
  "video_path": "aset/BW-261014-01/BW-261014-01.mp4",
  "title": "...", "description": "...", "tags": ["..."]
}
Hasil ditulis kembali ke file yang sama: status, posted_at, result (id/url) atau error.
Secrets (GitHub Actions): THREADS_ACCESS_TOKEN, THREADS_USER_ID, FB_PAGE_TOKEN, FB_PAGE_ID,
                          YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Pengaman: Facebook hanya diposting kalau nama halaman FB_PAGE_ID mengandung "brainwork" (tidak pernah ke halaman lain).
"""
import os, sys, json, glob, time, datetime as dt
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
NOW = dt.datetime.now(dt.timezone.utc)
MAX_PER_RUN = 4
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


def fb_page():
    """Kembalikan (page_id, token) setelah memastikan halamannya Brainwork. Tidak pernah posting ke halaman lain."""
    tok, pid = os.environ["FB_PAGE_TOKEN"], os.environ["FB_PAGE_ID"]
    r = requests.get(f"{FB}/{pid}", params={"fields": "id,name", "access_token": tok}, timeout=30)
    r.raise_for_status()
    name = r.json().get("name", "")
    if "brainwork" not in name.lower():
        raise RuntimeError(f"FB_PAGE_ID bukan halaman Brainwork (nama: {name!r}); posting dibatalkan")
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


def facebook_post(item):
    pid, tok = fb_page()
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


HANDLERS = {"threads": threads_post, "facebook": facebook_post, "youtube": youtube_post}
NEEDS = {"threads": ["THREADS_ACCESS_TOKEN"], "facebook": ["FB_PAGE_TOKEN", "FB_PAGE_ID"],
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
