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
- Ringkasan run terakhir ditulis ke inbox/terakhir.txt (tanpa jam, supaya tidak bikin commit baru tiap 15 menit).
- Daftar isi folder diambil dari tampilan publik embeddedfolderview (cadangan: gdown --folder, maks 50 file).
  Produser merapikan folder: file yang sudah tercatat di inbox/imported.json dipindah ke sampah.
"""
import os, re, sys, json, glob, html, hashlib, shutil, subprocess, tempfile, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.environ.get("INBOX_FOLDER_ID", "1sd0X_qci1M688kGryJgqdDug6wMQfCOV")
ALLOW = {"specs", "motion", "edits", "queue"}
LINDUNGI = {"posted", "failed"}          # status queue yang tidak boleh ditimpa
REC = os.path.join(ROOT, "inbox", "imported.json")
LOG = os.path.join(ROOT, "inbox", "terakhir.txt")
os.makedirs(os.path.dirname(REC), exist_ok=True)
done = json.load(open(REC)) if os.path.exists(REC) else {}
lines = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s); lines.append(s)


def selesai(masuk=0, gagal=()):
    log(f"selesai: {masuk} file diimpor, {len(gagal)} gagal")
    open(LOG, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def daftar_embedded():
    """[(file_id, nama)] dari tampilan publik folder. Butuh folder dibagikan 'siapa saja yang punya link'."""
    url = f"https://drive.google.com/embeddedfolderview?id={FOLDER}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 brainwork-inbox"})
    page = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    out = []
    for m in re.finditer(r'id="entry-([\w-]+)".*?class="flip-entry-title">(.*?)</div>', page, re.S):
        out.append((m.group(1), html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()))
    if not out:
        log(f"embeddedfolderview: 0 entri (panjang html {len(page)}, ada 'flip-entry': {'flip-entry' in page})")
    return out


tmp = tempfile.mkdtemp()
files = []
try:
    import gdown
    for fid, nama in daftar_embedded():
        if not nama.endswith(".json"):
            continue
        dest = os.path.join(tmp, nama)
        if gdown.download(id=fid, output=dest, quiet=True):
            files.append(dest)
        else:
            log("GAGAL unduh:", nama, fid)
except Exception as e:
    log("daftar embedded gagal:", repr(e)[:300])

if not files:  # cadangan: gdown --folder (maks 50 file)
    r = subprocess.run(["gdown", "--folder", f"https://drive.google.com/drive/folders/{FOLDER}", "-O", tmp,
                        "--quiet", "--remaining-ok"], capture_output=True, text=True)
    if r.returncode != 0:
        log("gdown --folder gagal:", (r.stderr or r.stdout)[-600:].strip())
    files = sorted(glob.glob(os.path.join(tmp, "**", "*.json"), recursive=True))

files = sorted(files, key=os.path.basename)
log(f"{len(files)} file di inbox")
if len(files) > 40:
    log("PERINGATAN: kotak masuk hampir penuh (batas gdown 50 file); rapikan folder _inbox")
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
        log("masuk:", name, "->", os.path.relpath(dest, ROOT))
    except Exception as e:
        done[md5] = name  # jangan diulang terus
        gagal.append(f"{name}: {e}")
        log("GAGAL:", name, e)

json.dump(done, open(REC, "w"), indent=1)
if gagal:
    with open(os.path.join(ROOT, "inbox_gagal.txt"), "a", encoding="utf-8") as fh:
        fh.write("\n".join(gagal) + "\n")
shutil.rmtree(tmp, ignore_errors=True)
selesai(masuk, gagal)
