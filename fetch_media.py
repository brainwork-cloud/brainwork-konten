#!/usr/bin/env python3
"""
Unduh file dari Google Drive sebelum render (dijalankan GitHub Actions).
  python fetch_media.py          -> rekaman reels (edits/*.json)
  python fetch_media.py specs    -> screenshot ilustrasi carousel (specs/*.json, "sources": {"ilustrasi/<ID>/x.png": "<DRIVE_FILE_ID>"})
Spec edits/<ID>.json memuat:
  "sources": {"rekaman/<ID>/vo.m4a": "<DRIVE_FILE_ID>", "rekaman/<ID>/layar1.mp4": "<DRIVE_FILE_ID>"}
File Drive harus berada di folder yang dibagikan "Siapa saja yang memiliki link: Pelihat".
Folder rekaman/ tidak di-commit (.gitignore), jadi rekaman mentah tidak ikut publik.
"""
import os, sys, json, glob
import gdown

ROOT = os.path.dirname(os.path.abspath(__file__))
ok = True
KIND = sys.argv[1] if len(sys.argv) > 1 else "edits"
for spec_path in sorted(glob.glob(os.path.join(ROOT, KIND, "*.json"))):
    spec = json.load(open(spec_path, encoding="utf-8"))
    if KIND == "edits" and os.path.exists(os.path.join(ROOT, "aset", spec["id"], f"{spec['id']}.mp4")):
        continue
    for rel, fid in (spec.get("sources") or {}).items():
        dest = os.path.join(ROOT, rel)
        if os.path.exists(dest):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        print("unduh", rel)
        if not gdown.download(id=fid, output=dest, quiet=True):
            print("GAGAL unduh", rel, fid)
            ok = False
sys.exit(0 if ok else 1)
