#!/usr/bin/env python3
"""
Jalankan SEKALI di Terminal Mac (butuh browser untuk login Google) untuk mendapat YT_REFRESH_TOKEN.
Nilai tidak dicetak; langsung ditulis ke agen_konten/rahasia.txt, lalu unggah dengan setup/set_secrets.py.

1. console.cloud.google.com -> buat project -> APIs & Services -> Library -> aktifkan "YouTube Data API v3".
2. APIs & Services -> OAuth consent screen: External; isi nama app & email; tambahkan email channel YouTube
   @nopal.brainwork sebagai Test user; lalu klik "Publish app" (status In production, supaya refresh token
   tidak kedaluwarsa 7 hari). Peringatan "unverified app" saat login nanti wajar: klik Advanced -> Go to ... (unsafe).
3. Credentials -> Create credentials -> OAuth client ID -> Desktop app -> Download JSON -> simpan sebagai
   client_secret.json di folder agen_konten/setup/.
4. Di Terminal:  cd "~/Documents/Claude/Projects/Nopal Brainwork/agen_konten"
                 pip3 install google-auth-oauthlib
                 python3 setup/yt_auth.py     -> browser terbuka, login akun YouTube @nopal.brainwork, izinkan.
5. Lalu minta Claude menjalankan:  python3 setup/set_secrets.py   (atau jalankan sendiri).
"""
import os, json
from google_auth_oauthlib.flow import InstalledAppFlow

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = os.path.join(HERE, "client_secret.json")
RAHASIA = os.path.join(HERE, "..", "rahasia.txt")
flow = InstalledAppFlow.from_client_secrets_file(SECRET, scopes=["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
cfg = json.load(open(SECRET))
c = cfg.get("installed") or cfg.get("web")
with open(RAHASIA, "a", encoding="utf-8") as fh:
    fh.write(f"\nYT_CLIENT_ID={c['client_id']}\nYT_CLIENT_SECRET={c['client_secret']}\nYT_REFRESH_TOKEN={creds.refresh_token}\n")
print("OK: 3 nilai YouTube tersimpan ke rahasia.txt (tidak ditampilkan). Sekarang jalankan: python3 setup/set_secrets.py")
