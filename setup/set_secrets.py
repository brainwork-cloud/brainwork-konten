#!/usr/bin/env python3
"""
Unggah rahasia (token) ke GitHub Actions secrets repo brainwork-cloud/brainwork-konten.
Baca file  agen_konten/rahasia.txt  berisi baris KEY=VALUE (hanya kunci di IZIN di bawah).
Nilai tidak pernah dicetak. Setelah sukses, file rahasia.txt dihapus isinya (dikosongkan).
Butuh: pip install pynacl ; token GitHub di agen_konten/.github_token.txt (permission Secrets: write)
  --bot-pat : unggah juga token GitHub itu sendiri sebagai secret BOT_PAT (dipakai workflow "Kotak Masuk"
              untuk push, supaya commit-nya memicu workflow render/publish). Tidak butuh rahasia.txt.
"""
import os, sys, json, base64, urllib.request
from nacl import encoding, public

A = os.path.expanduser("~/mnt/Nopal Brainwork/agen_konten")
REPO = "brainwork-cloud/brainwork-konten"
IZIN = {"THREADS_ACCESS_TOKEN", "THREADS_USER_ID", "FB_PAGE_TOKEN", "FB_PAGE_ID",
        "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"}

tokf = next(p for p in (os.path.join(A, ".github_token.txt"), os.path.join(A, ".github_token")) if os.path.exists(p))
GH = open(tokf).read().strip()
H = {"Authorization": f"Bearer {GH}", "Accept": "application/vnd.github+json", "User-Agent": "brainwork-agen"}


def api(method, path, body=None):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{path}", method=method, headers=H,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req) as r:
        return r.status, (json.loads(r.read() or b"{}"))


pairs = {}
if "--bot-pat" in sys.argv:
    pairs["BOT_PAT"] = GH
src = os.path.join(A, "rahasia.txt")
if not os.path.exists(src) and not pairs:
    sys.exit("rahasia.txt belum ada")
for line in (open(src, encoding="utf-8") if os.path.exists(src) else []):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    k, v = k.strip().upper(), v.strip().strip('"').strip("'")
    if k in IZIN and v:
        pairs[k] = v
if not pairs:
    sys.exit("tidak ada KEY=VALUE yang valid di rahasia.txt")

_, pk = api("GET", "/actions/secrets/public-key")
box = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder()))
for k, v in pairs.items():
    enc = base64.b64encode(box.encrypt(v.encode())).decode()
    st, _ = api("PUT", f"/actions/secrets/{k}", {"encrypted_value": enc, "key_id": pk["key_id"]})
    print(f"{k}: {'OK' if st in (201, 204) else 'GAGAL ' + str(st)} (panjang {len(v)} karakter)")

if any(k != "BOT_PAT" for k in pairs):
    open(src, "w").write("# sudah diunggah ke GitHub secrets & dikosongkan otomatis\n")
_, lst = api("GET", "/actions/secrets")
print("secrets di repo:", ", ".join(s["name"] for s in lst.get("secrets", [])))
