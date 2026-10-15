#!/usr/bin/env python3
"""Jalankan workflow (atau --tunggu: hanya tunggu run yang dipicu push) GitHub Actions (workflow_dispatch), tunggu selesai, cetak log langkahnya.
   python3 setup/gh_run.py cek-koneksi.yml   |   python3 setup/gh_run.py publish.yml"""
import os, sys, json, time, urllib.request
A = os.path.expanduser("~/mnt/Nopal Brainwork/agen_konten")
REPO = "brainwork-cloud/brainwork-konten"
tokf = next(p for p in (os.path.join(A, ".github_token.txt"), os.path.join(A, ".github_token")) if os.path.exists(p))
TOK = open(tokf).read().strip()
H = {"Authorization": f"Bearer {TOK}", "Accept": "application/vnd.github+json", "User-Agent": "brainwork-agen"}
def api(m, path, body=None, raw=False):
    req = urllib.request.Request(path if path.startswith("http") else f"https://api.github.com/repos/{REPO}{path}", method=m, headers=H,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req) as r:
        b = r.read(); return b if raw else (json.loads(b) if b else {})
wf = sys.argv[1]
t0 = time.time() - 5
if "--tunggu" not in sys.argv:
    api("POST", f"/actions/workflows/{wf}/dispatches", {"ref": "main"})
run = None
for _ in range(60):
    time.sleep(5)
    rs = api("GET", f"/actions/workflows/{wf}/runs?per_page=3")["workflow_runs"]
    rs = [r for r in rs if time.mktime(time.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone >= t0 - 60]
    if rs:
        run = rs[0]
        if run["status"] == "completed": break
print("run:", run and run["status"], run and run["conclusion"])
if run:
    for j in api("GET", f"/actions/runs/{run['id']}/jobs")["jobs"]:
        try:
            log = api("GET", f"/actions/jobs/{j['id']}/logs", raw=True).decode(errors="replace")
            keep = [l[29:] if len(l) > 29 and l[4] == "-" else l for l in log.splitlines()]
            print("\n".join(l for l in keep if l.startswith(("THREADS", "YOUTUBE", "BW-", "selesai", "Traceback", "Error")) or "rror" in l)[-3000:])
        except Exception as e:
            print("log tidak bisa diambil:", e, "| langkah:", [(s["name"], s["conclusion"]) for s in j["steps"]])
