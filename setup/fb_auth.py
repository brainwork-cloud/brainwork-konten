#!/usr/bin/env python3
"""
Dapatkan token halaman Facebook (long-lived, tidak kedaluwarsa). Jalankan SEKALI per halaman. Nilai token tidak pernah dicetak.

Ada DUA halaman Facebook yang tidak boleh tertukar:
  python3 setup/fb_auth.py          -> halaman mirror @nopal.brainwork (nama mengandung "brainwork", BUKAN brainwork.id)
                                       menulis FB_PAGE_ID dan FB_PAGE_TOKEN
  python3 setup/fb_auth.py portal   -> halaman PORTAL berita Brainwork.id (username "brainwork.id", facebook.com/brainwork.id)
                                       menulis PORTAL_FB_PAGE_ID dan PORTAL_FB_PAGE_TOKEN
                                       (opsional: tambah id halaman, mis. `portal 61500000000000`, kalau username tidak terbaca)

Langkah Naufal (±5 menit):
1. developers.facebook.com -> My Apps -> pilih app yang ada atau Create App (tipe "Business").
   Settings -> Basic: catat App ID dan App secret (klik Show).
2. Tools -> Graph API Explorer -> pilih app itu -> di "Permissions" tambahkan:
   pages_show_list, pages_read_engagement, pages_manage_posts, publish_video
   -> klik "Generate Access Token" -> login, di daftar halaman centang HANYA halaman yang akan dipakai
      (untuk portal: halaman Brainwork.id yang pengikutnya 0) -> salin token yang muncul (User Token).
3. Isi file agen_konten/rahasia.txt (3 baris):
     FB_APP_ID=...
     FB_APP_SECRET=...
     FB_USER_TOKEN=...
4. Jalankan: python3 setup/fb_auth.py portal      (atau tanpa "portal" untuk halaman mirror Nopal)
   -> token ditukar jadi long-lived, halaman yang benar dicari (skrip menolak kalau halamannya tertukar),
      id dan token halaman ditulis ke rahasia.txt (3 baris sementara dihapus). Lalu: python3 setup/set_secrets.py
"""
import os, sys, json, urllib.request, urllib.parse

A = os.path.expanduser("~/mnt/Nopal Brainwork/agen_konten")
if not os.path.isdir(A):
    A = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(A, "rahasia.txt")
G = "https://graph.facebook.com/v23.0"
ARGS = [a.lower() for a in sys.argv[1:]]
PORTAL = "portal" in ARGS
EXPLICIT = next((a for a in ARGS if a.isdigit()), None)
KEYS = ("PORTAL_FB_PAGE_ID", "PORTAL_FB_PAGE_TOKEN") if PORTAL else ("FB_PAGE_ID", "FB_PAGE_TOKEN")


def get(path, **params):
    url = f"{G}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "brainwork-agen"}), timeout=60) as r:
        return json.loads(r.read())


def is_portal(p):
    return (p.get("username") or "").lower() == "brainwork.id" or (p.get("link") or "").lower().rstrip("/").endswith("/brainwork.id")


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
pages = get("me/accounts", fields="id,name,username,link,access_token", limit="100", access_token=ll).get("data", [])
print("halaman yang bisa diakses token ini:",
      ", ".join(f"{p['name']} (id {p['id']}, @{p.get('username') or '-'})" for p in pages) or "(tidak ada)")

if PORTAL:
    cand = [p for p in pages if p["id"] == EXPLICIT] if EXPLICIT else [p for p in pages if is_portal(p)]
    if len(cand) != 1:
        sys.exit("halaman portal brainwork.id tidak ditemukan (atau lebih dari satu). Ulangi Generate Access Token dan centang halaman "
                 "Brainwork.id (pengikut 0); atau jalankan: python3 setup/fb_auth.py portal <id halaman>.")
    if not is_portal(cand[0]):
        print("PERINGATAN: halaman ini tidak berusername brainwork.id; publish.py akan menolak posting ke sana.")
else:
    cand = [p for p in pages if "brainwork" in p["name"].lower() and not is_portal(p)]
    if len(cand) != 1:
        sys.exit("halaman mirror Nopal tidak ditemukan atau ada lebih dari satu kandidat "
                 f"({', '.join(p['name'] for p in cand) or 'tidak ada'}). Centang hanya halaman Nopal saat Generate Access Token.")
page = cand[0]

keep = [l for l in lines if not l.split("=", 1)[0].strip().upper() in {*need, *KEYS}]
keep += [f"{KEYS[0]}={page['id']}", f"{KEYS[1]}={page['access_token']}"]
open(SRC, "w", encoding="utf-8").write("\n".join(keep).rstrip("\n") + "\n")
dbg = get("debug_token", input_token=page["access_token"], access_token=page["access_token"]).get("data", {})
print(f"OK ({'PORTAL' if PORTAL else 'mirror Nopal'}): halaman '{page['name']}' id {page['id']}, "
      f"token {'tidak kedaluwarsa' if not dbg.get('expires_at') else 'KEDALUWARSA (bukan long-lived?)'}, "
      f"izin: {', '.join(dbg.get('scopes', []))}")
print("Tersimpan ke rahasia.txt. Sekarang jalankan: python3 setup/set_secrets.py")
