#!/usr/bin/env python3
"""Cek token Threads, Facebook Page (mirror Nopal), Facebook Page portal Brainwork.id & YouTube (dijalankan GitHub Actions).
Tidak memposting apa pun; hanya cetak nama akun."""
import os, requests

ok = True
if os.environ.get("THREADS_ACCESS_TOKEN"):
    r = requests.get("https://graph.threads.net/v1.0/me", params={
        "fields": "id,username", "access_token": os.environ["THREADS_ACCESS_TOKEN"]}, timeout=30)
    if r.ok:
        d = r.json()
        uid = os.environ.get("THREADS_USER_ID")
        same = (not uid) or d.get("id") == uid
        print(f"THREADS: OK @{d.get('username')} | id {d.get('id')} | cocok dengan THREADS_USER_ID: {same if uid else 'secret kosong, dipakai otomatis'}")
        if d.get("username") != "nopal.brainwork":
            print("THREADS: PERINGATAN token ini bukan milik @nopal.brainwork")
        ok &= same and d.get("username") == "nopal.brainwork"
    else:
        print("THREADS: GAGAL", r.status_code, r.text[:300]); ok = False
else:
    print("THREADS: secret belum diisi")

if os.environ.get("FB_PAGE_TOKEN") and os.environ.get("FB_PAGE_ID"):
    r = requests.get(f"https://graph.facebook.com/v23.0/{os.environ['FB_PAGE_ID']}", params={
        "fields": "id,name,username,link", "access_token": os.environ["FB_PAGE_TOKEN"]}, timeout=30)
    if r.ok:
        d = r.json()
        print(f"FACEBOOK: OK halaman '{d.get('name')}' | id {d.get('id')} | {d.get('link')}")
        if "brainwork" not in (d.get("name") or "").lower():
            print("FACEBOOK: PERINGATAN ini BUKAN halaman Brainwork; publish.py akan menolak posting"); ok = False
        if (d.get("username") or "").lower() == "brainwork.id":
            print("FACEBOOK: PERINGATAN FB_PAGE_ID menunjuk halaman PORTAL brainwork.id; publish.py akan menolak mirror Nopal"); ok = False
        dbg = requests.get("https://graph.facebook.com/v23.0/debug_token", params={
            "input_token": os.environ["FB_PAGE_TOKEN"], "access_token": os.environ["FB_PAGE_TOKEN"]}, timeout=30)
        if dbg.ok:
            data = dbg.json().get("data", {})
            exp = data.get("expires_at", 0)
            print("FACEBOOK: token", "tidak kedaluwarsa" if not exp else f"kedaluwarsa (epoch {exp}), buat ulang token long-lived!",
                  "| izin:", ", ".join(data.get("scopes", [])))
            if exp:
                ok = False
    else:
        print("FACEBOOK: GAGAL", r.status_code, r.text[:300]); ok = False
else:
    print("FACEBOOK: secret belum diisi (FB_PAGE_TOKEN, FB_PAGE_ID)")

if os.environ.get("PORTAL_FB_PAGE_TOKEN") and os.environ.get("PORTAL_FB_PAGE_ID"):
    r = requests.get(f"https://graph.facebook.com/v23.0/{os.environ['PORTAL_FB_PAGE_ID']}", params={
        "fields": "id,name,username,link,fan_count", "access_token": os.environ["PORTAL_FB_PAGE_TOKEN"]}, timeout=30)
    if r.ok:
        d = r.json()
        print(f"PORTAL: OK halaman '{d.get('name')}' | id {d.get('id')} | @{d.get('username')} | pengikut {d.get('fan_count', 'tidak terbaca')}")
        if (d.get("username") or "").lower() != "brainwork.id":
            print("PORTAL: PERINGATAN ini BUKAN halaman brainwork.id; publish.py akan menolak posting"); ok = False
        if d.get("id") == os.environ.get("FB_PAGE_ID"):
            print("PORTAL: PERINGATAN id sama dengan FB_PAGE_ID (halaman mirror Nopal)"); ok = False
        dbg = requests.get("https://graph.facebook.com/v23.0/debug_token", params={
            "input_token": os.environ["PORTAL_FB_PAGE_TOKEN"], "access_token": os.environ["PORTAL_FB_PAGE_TOKEN"]}, timeout=30)
        if dbg.ok:
            data = dbg.json().get("data", {})
            exp = data.get("expires_at", 0)
            print("PORTAL: token", "tidak kedaluwarsa" if not exp else f"kedaluwarsa (epoch {exp}), buat ulang token long-lived!",
                  "| izin:", ", ".join(data.get("scopes", [])))
            if exp:
                ok = False
    else:
        print("PORTAL: GAGAL", r.status_code, r.text[:300]); ok = False
else:
    print("PORTAL: secret belum diisi (PORTAL_FB_PAGE_TOKEN, PORTAL_FB_PAGE_ID)")

if os.environ.get("YT_REFRESH_TOKEN"):
    t = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    if t.ok:
        scopes = t.json().get("scope", "")
        print("YOUTUBE: token OK, scope:", scopes)
        c = requests.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                         headers={"Authorization": "Bearer " + t.json()["access_token"]}, timeout=30)
        if c.ok and c.json().get("items"):
            print("YOUTUBE: channel =", c.json()["items"][0]["snippet"]["title"])
        else:
            print("YOUTUBE: (nama channel tidak bisa dibaca dengan scope upload saja, ini normal)")
    else:
        print("YOUTUBE: GAGAL", t.status_code, t.text[:300]); ok = False
else:
    print("YOUTUBE: secret belum diisi")
raise SystemExit(0 if ok else 1)
