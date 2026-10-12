#!/usr/bin/env python3
"""
Jalankan SEKALI di Terminal Mac (bukan di Claude) untuk mendapat YT_REFRESH_TOKEN.

1. Google Cloud Console -> buat project -> aktifkan "YouTube Data API v3".
2. OAuth consent screen: External, tambahkan email channel YouTube kamu sebagai Test user,
   lalu Publish app (supaya refresh token tidak kedaluwarsa 7 hari).
3. Credentials -> Create OAuth client ID -> Desktop app -> unduh JSON, simpan sebagai client_secret.json di folder ini.
4. pip3 install google-auth-oauthlib
5. python3 yt_auth.py   -> browser terbuka, login akun YouTube @nopal.brainwork, izinkan.
6. Salin 3 nilai yang tercetak ke GitHub repo -> Settings -> Secrets and variables -> Actions.
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", scopes=["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
cfg = json.load(open("client_secret.json"))
c = cfg.get("installed") or cfg.get("web")
print("\nYT_CLIENT_ID     =", c["client_id"])
print("YT_CLIENT_SECRET =", c["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
