#!/usr/bin/env python3
"""
Kotak masuk dari Google Drive -> repo (dijalankan GitHub Actions "Kotak Masuk" tiap 15 menit).
Agen di cloud (tanpa Mac) mengunggah file JSON ke folder Drive "_inbox" (publik, link-view),
lalu skrip ini menaruhnya ke folder repo yang benar:

  Nama file di Drive:  <dir>__<nama>[__<stamp>].json
  Hasil di repo:       <dir>/<nama>.json
  dir yang diizinkan:  specs | motion | edits | queue
  contoh:              specs__BW-261027-02__202610271205.json  ->  specs/BW-261027-02.json
                       queue__BW-261027-01__threads__202610271240.json -> queue/BW-261027-01__threads.json

Aturan:
- Isi harus JSON valid dan punya "id" yang sama dengan <nama> (untuk queue: nama diawali id). Gagal -> inbox_gagal.txt.
- queue/: file yang sudah berstatus posted/failed TIDAK ditimpa (hasil publish tidak boleh hilang);
  yang masih approved/cancelled boleh ditimpa (untuk membatalkan atau mengubah jadwal).
- md5 file yang sudah diproses dicatat di inbox/imported.json, jadi file lama di Drive tidak diproses ulang.
- gdown hanya bisa mengambil 50 file pertama per folder -> Produser merapikan folder (file yang sudah
  tercatat di inbox/imported.json dipindah ke sampah).
"""
import os, re, sys, json, glob, hashlib, shutil, subprocess, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.environ.get("INBOX_FOLDER_ID", "1sd0X_qci1M688kGryJgqdDug6wMQfCOV")
ALLOW = {"specs", "motion", "edits", "queue"}
LINDUNGI = {"posted", "failed"}          # status queue yang tidak boleh ditimpa
REC = os.path.join(ROOT, "inbox", "imported.json")
os.makedirs(os.path.dirname(REC), exist_ok=True)
done = json.load(open(REC)) if os.path.exists(REC) else {}

tmp = tempfile.mkdtemp()
r = subprocess.run(["gdown", "--folder", f"https://drive.google.com/drive/folders/{FOLDER}", "-O", tmp,
                    "--quiet", "--remaining-ok"], capture_output=True, text=True)
if r.returncode != 0:
    print("gdown gagal:", (r.stderr or r.stdout)[-800:]); sys.exit(0)  # folder kosong juga bisa bikin gdown exit != 0

files = sorted(glob.glob(os.path.join(tmp, "**", "*.json"), recursive=True))
print(f"{len(files)} file di inbox")
if len(files) > 40:
    print("PERINGATAN: kotak masuk hampir penuh (batas gdown 50 file); rapikan folder _inbox")
gagal, masuk = [], 0
for f in files:
    name = os.path.basename(f)
    raw = open(f, "rb").read()
    md5 = hashlib.md5(raw).hexdigest()
    if md5 in done:
        continue
    parts = name[:-5].split("__")
    if len(parts) > 2 and re.fullmatch(r"\d{4,14}", parts[-1]):
        parts = parts[:-1]
    d = parts[0]
    rest = "__".join(parts[1:])
    try:
        if d not in ALLOW or not rest or not re.fullmatch(r"[A-Za-z0-9_-]+", rest):
            raise ValueError("nama file tidak sesuai pola <dir>__<nama>[__stamp].json")
        spec = json.loads(raw.decode("utf-8"))
        sid = str(spec.get("id", ""))
        if not sid or not rest.startswith(sid):
            raise ValueError(f"field id ({sid!r}) tidak cocok dengan nama file ({rest!r})")
        dest = os.path.join(ROOT, d, rest + ".json")
        if d == "queue" and os.path.exists(dest):
            try:
                lama = json.load(open(dest, encoding="utf-8")).get("status", "")
            except Exception:
                lama = ""
            if lama in LINDUNGI:
                raise ValueError(f"queue sudah berstatus {lama}, tidak ditimpa")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest) and open(dest, "rb").read() == raw:
            done[md5] = name; continue
        open(dest, "wb").write(raw)
        done[md5] = name; masuk += 1
        print("masuk:", name, "->", os.path.relpath(dest, ROOT))
    except Exception as e:
        done[md5] = name  # jangan diulang terus
        gagal.append(f"{name}: {e}")
        print("GAGAL:", name, e)

json.dump(done, open(REC, "w"), indent=1)
if gagal:
    with open(os.path.join(ROOT, "inbox_gagal.txt"), "a", encoding="utf-8") as fh:
        fh.write("\n".join(gagal) + "\n")
shutil.rmtree(tmp, ignore_errors=True)
print(f"selesai: {masuk} file diimpor, {len(gagal)} gagal")
