#!/usr/bin/env python3
"""
Pembuat B-roll otomatis (pengganti rekam layar manual), dijalankan GitHub Actions sebelum edit_reel.py.
  python make_broll.py            -> semua edits/*.json yang belum punya video hasil

Di edits/<ID>.json:
  "make_broll": [
    {"name": "b1", "type": "web", "url": "https://www.facebook.com/ads/library/", "seconds": 6, "mobile": true},
    {"name": "b2", "type": "motion", "scenes": [{"type": "mock", "screen": "...", "rows": [...], "dur": 4}]}
  ]
Hasil: rekaman/<ID>/<name>.mp4 (1080x1920, tanpa suara), dipakai lewat "cutaways"/"broll" di spec.
web    = rekam halaman PUBLIK (tanpa login) sambil scroll pelan. Jangan pakai halaman yang butuh login.
motion = animasi mockup/teks dari render_motion.py (scene type "mock", "stat", "points", "statement", "hook").
"""
import os, sys, json, glob, subprocess, tempfile, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def web_clip(url, seconds, out, mobile=True):
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp()
    vw, vh = (540, 960) if mobile else (1080, 1920)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=1,
                            is_mobile=mobile, has_touch=mobile, locale="id-ID",
                            record_video_dir=tmp, record_video_size={"width": vw, "height": vh})
        pg = ctx.new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print("peringatan halaman:", e)
        pg.wait_for_timeout(2500)
        steps = max(1, int(seconds * 10))
        for _ in range(steps):
            pg.mouse.wheel(0, 18)
            pg.wait_for_timeout(100)
        pg.wait_for_timeout(500)
        vid = pg.video.path()
        ctx.close(); b.close()
    # buang 2 detik awal (loading), samakan fps & ukuran
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2", "-i", vid, "-t", str(seconds),
                    "-vf", "scale=1080:1920:flags=lanczos,fps=30,format=yuv420p", "-an", "-c:v", "libx264", "-crf", "20", out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    import render_motion
    ok = True
    for sp in sorted(glob.glob(os.path.join(ROOT, "edits", "*.json"))):
        spec = json.load(open(sp, encoding="utf-8"))
        sid = spec["id"]
        if os.path.exists(os.path.join(ROOT, "aset", sid, f"{sid}.mp4")):
            continue
        for b in spec.get("make_broll", []):
            out = os.path.join(ROOT, "rekaman", sid, b["name"] + ".mp4")
            if os.path.exists(out):
                continue
            os.makedirs(os.path.dirname(out), exist_ok=True)
            print("b-roll", sid, b["name"], b["type"])
            try:
                if b["type"] == "web":
                    web_clip(b["url"], float(b.get("seconds", 5)), out, b.get("mobile", True))
                elif b["type"] == "motion":
                    for sc in b["scenes"]:   # foto Faceless/Aktivitas/Talking Head dipasang edit_reel.py (cover atau kartu berfoto, dicatat di .foto.txt), bukan di B-roll
                        if sc.pop("foto", None):
                            print("catatan: field foto diabaikan di make_broll", sid, b["name"])
                    render_motion.render_clip(b["scenes"], out)
            except Exception as e:
                print("GAGAL b-roll", sid, b["name"], e); ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
