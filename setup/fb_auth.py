#!/usr/bin/env python3
"""
Dapatkan token halaman Facebook (long-lived, tidak kedaluwarsa) untuk mirror otomatis ke Page Brainwork.id.
Jalankan SEKALI. Nilai token tidak pernah dicetak.

Langkah Naufal (±5 menit):
1. developers.facebook.com -> My Apps -> pilih app yang ada atau Create App (tipe "Business").
   Settings -> Basic: catat App ID dan App secret (klik Show).
2. Tools -> Graph API Explorer -> pilih app itu -> di "Permissions" tambahkan:
   pages_show_list, pages_read_engagement, pages_manage_posts, publish_video
   -> klik "Generate Access Token" -> login, centang halaman Brainwork.id -> salin token yang muncul (User Token).
3. Isi file agen_konten/rahasia.txt (3 baris):
     FB_APP_ID=...
     FB_APP_SECRET=...
     FB_USER_TOKEN=...
4. Jalankan: python3 setup/fb_auth.py
   -> token ditukar jadi long-lived, halaman Brainwork dicari, FB_PAGE_TOKEN & FB_PAGE_ID ditulis ke rahasia.txt
      (3 baris sementara dihapus). Lalu: python3 setup/set_secrets.py
"""
import os, sys, json, urllib.request, urllib.parse

A = os.path.expanduser("~/mnt/Nopal Brainwork/agen_konten")
if not os.path.isdir(A):
    A = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(A, "rahasia.txt")
G = "https://graph.facebook.com/v23.0"


def get(path, **params):
    url = f"{G}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "brainwork-agen"}), timeout=60) as r:
        return json.loads(r.read())


vals, lines = {}, []
for line in open(SRC, encoding="utf-8") if os.path.exists(SRC) else []:
    s = line.strip()
    if s and not s.startswith("#") and "=" in s:
        k, v = s.split("=", 1)
        vals[k.strip().upper()] = v.strip().strip('"').strip("'")
    lines.append(line.rstrip("\n"))
need = ["FB_APP_ID", "FB_APP_SECRET", "FB_USER_TOKEN"]
if any(not vals.get(k) for k in need):
    sys.exit("rahasia.txt belum lengkap: butuh " + ", ".join(need))

try:
    ll = get("oauth/access_token", grant_type="fb_exchange_token", client_id=vals["FB_APP_ID"],
             client_secret=vals["FB_APP_SECRET"], fb_exchange_token=vals["FB_USER_TOKEN"])["access_token"]
except Exception as e:
    sys.exit(f"tukar token gagal: {e}")
pages = get("me/accounts", fields="id,name,access_token", limit="100", access_token=ll).get("data", [])
print("halaman yang bisa diakses token ini:", ", ".join(f"{p['name']} ({p['id']})" for p in pages) or "(tidak ada)")
page = next((p for p in pages if "brainwork" in p["name"].lower()), None)
if not page:
    sys.exit("halaman Brainwork tidak ditemukan. Ulangi Generate Access Token dan centang halaman Brainwork.id.")

keep = [l for l in lines if not l.split("=", 1)[0].strip().upper() in {*need, "FB_PAGE_TOKEN", "FB_PAGE_ID"}]
keep += [f"FB_PAGE_ID={page['id']}", f"FB_PAGE_TOKEN={page['access_token']}"]
open(SRC, "w", encoding="utf-8").write("\n".join(keep).rstrip("\n") + "\n")
dbg = get("debug_token", input_token=page["access_token"], access_token=page["access_token"]).get("data", {})
print(f"OK: halaman '{page['name']}' id {page['id']}, token {'tidak kedaluwarsa' if not dbg.get('expires_at') else 'KEDALUWARSA (bukan long-lived?)'}, "
      f"izin: {', '.join(dbg.get('scopes', []))}")
print("Tersimpan ke rahasia.txt. Sekarang jalankan: python3 setup/set_secrets.py")
