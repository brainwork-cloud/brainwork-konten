#!/usr/bin/env python3
"""
Publisher Threads + YouTube Shorts @nopal.brainwork (dijalankan GitHub Actions tiap 30 menit).

Antrian: file queue/<ID>__<platform>.json, ditulis agen Penerbit HANYA untuk konten berstatus APPROVED.
{
  "id": "BW-261014-01",
  "platform": "threads" | "youtube",
  "publish_at": "2026-10-14T19:00:00+07:00",
  "status": "approved",                 # approved -> posted | failed
  # threads
  "posts": ["post 1", "post 2"],        # 1 item = single post, >1 = utas (balasan berantai)
  "image_url": null,                    # opsional, hanya untuk post pertama
  # youtube
  "video_path": "aset/BW-261014-01/BW-261014-01.mp4",
  "title": "...", "description": "...", "tags": ["..."]
}
Hasil ditulis kembali ke file yang sama: status, posted_at, result (id/url) atau error.
Secrets (GitHub Actions): THREADS_ACCESS_TOKEN, THREADS_USER_ID, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""
import os, sys, json, glob, time, datetime as dt
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
NOW = dt.datetime.now(dt.timezone.utc)
MAX_PER_RUN = 3
TH = "https://graph.threads.net/v1.0"


def threads_post(item):
    tok, uid = os.environ["THREADS_ACCESS_TOKEN"], os.environ["THREADS_USER_ID"]
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
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    media = MediaFileUpload(os.path.join(ROOT, item["video_path"]), mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return {"id": resp["id"], "url": f"https://youtube.com/shorts/{resp['id']}"}


def main():
    done = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "queue", "*.json"))):
        item = json.load(open(path, encoding="utf-8"))
        if item.get("status") != "approved":
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
            fn = {"threads": threads_post, "youtube": youtube_post}[item["platform"]]
            item["result"] = fn(item)
            item["status"] = "posted"
        except Exception as e:  # catat, jangan ulang terus
            item["status"] = "failed"
            item["error"] = f"{type(e).__name__}: {getattr(getattr(e, 'response', None), 'text', '') or e}"[:800]
        item["posted_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        json.dump(item, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(item["id"], item["platform"], item["status"], item.get("result") or item.get("error"))
        done += 1
    print(f"selesai: {done} item diproses")


if __name__ == "__main__":
    main()
