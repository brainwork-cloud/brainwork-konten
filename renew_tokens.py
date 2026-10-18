#!/usr/bin/env python3
"""
Perpanjang token otomatis (GitHub Actions "Perpanjang token", tiap Senin).
- Threads: token long-lived berlaku 60 hari; di-refresh lewat /refresh_access_token lalu disimpan ulang
  ke secret THREADS_ACCESS_TOKEN memakai BOT_PAT (izin Secrets: write). Nilai token tidak pernah dicetak.
- Facebook Page token long-lived tidak kedaluwarsa; hanya dicek. YouTube refresh token: hanya dicek.
Ringkasan ditulis ke tokens/status.txt (tanpa nilai token).
"""
import os, json, base64, datetime as dt, requests

REPO = os.environ.get("GITHUB_REPOSITORY", "brainwork-cloud/brainwork-konten")
PAT = os.environ.get("BOT_PAT")
lines, ok = [], True
today = dt.date.today()


def simpan_secret(nama, nilai):
    from nacl import encoding, public
    h = {"Authorization": f"Bearer {PAT}", "Accept": "application/vnd.github+json"}
    pk = requests.get(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key", headers=h, timeout=30).json()
    box = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder()))
    enc = base64.b64encode(box.encrypt(nilai.encode())).decode()
    r = requests.put(f"https://api.github.com/repos/{REPO}/actions/secrets/{nama}", headers=h,
                     json={"encrypted_value": enc, "key_id": pk["key_id"]}, timeout=30)
    return r.status_code in (201, 204)


tok = os.environ.get("THREADS_ACCESS_TOKEN")
if tok:
    r = requests.get("https://graph.threads.net/refresh_access_token",
                     params={"grant_type": "th_refresh_token", "access_token": tok}, timeout=30)
    if r.ok and r.json().get("access_token"):
        baru, exp = r.json()["access_token"], int(r.json().get("expires_in", 0))
        sampai = today + dt.timedelta(seconds=exp)
        if PAT and simpan_secret("THREADS_ACCESS_TOKEN", baru):
            lines.append(f"THREADS: diperbarui {today}, berlaku sampai {sampai}")
        else:
            lines.append(f"THREADS: refresh OK tapi GAGAL simpan secret (BOT_PAT?) {today}; token lama masih berlaku"); ok = False
    else:
        lines.append(f"THREADS: refresh GAGAL {today}: {r.status_code} {r.text[:200]}"); ok = False
else:
    lines.append("THREADS: secret belum diisi")

fbt, fbp = os.environ.get("FB_PAGE_TOKEN"), os.environ.get("FB_PAGE_ID")
if fbt and fbp:
    d = requests.get("https://graph.facebook.com/v23.0/debug_token",
                     params={"input_token": fbt, "access_token": fbt}, timeout=30).json().get("data", {})
    if d.get("is_valid"):
        exp = d.get("expires_at", 0)
        lines.append("FACEBOOK: token valid, " + ("tidak kedaluwarsa" if not exp else
                     f"KEDALUWARSA {dt.datetime.utcfromtimestamp(exp).date()} -> buat ulang (setup/fb_auth.py)"))
        ok &= not exp
    else:
        lines.append(f"FACEBOOK: token TIDAK valid {today} -> buat ulang (setup/fb_auth.py)"); ok = False
else:
    lines.append("FACEBOOK: secret belum diisi")

if os.environ.get("YT_REFRESH_TOKEN"):
    t = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ.get("YT_CLIENT_ID"), "client_secret": os.environ.get("YT_CLIENT_SECRET"),
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    lines.append("YOUTUBE: refresh token OK" if t.ok else f"YOUTUBE: refresh token GAGAL {today}: {t.text[:200]} -> jalankan ulang setup/yt_auth.py")
    ok &= t.ok
else:
    lines.append("YOUTUBE: secret belum diisi")

os.makedirs("tokens", exist_ok=True)
open("tokens/status.txt", "w", encoding="utf-8").write(f"Cek terakhir: {today}\n" + "\n".join(lines) + "\n")
print("\n".join(lines))
raise SystemExit(0 if ok else 1)
