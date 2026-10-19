#!/usr/bin/env python3
"""
Renderer konten berita Brainwork.id (portal media, produksi sendiri, terpisah dari @nopal.brainwork)
Pemakaian:  python3 render_portal.py portal/<ID>.json [folder_output] [--frames 1.0,5.0]
Hasil (semua format selalu menulis <ID>.jpg sebagai sampul/kartu, dipakai kolom Kartu di Sheet):
  single    -> <ID>.jpg                       kartu 1080x1350 (4:5)
  carousel  -> <ID>.jpg (= slide 1), <ID>_01.jpg ... <ID>_NN.jpg   slide 1080x1350 (4:5), 4-6 slide (sampul + 2-4 fakta + penutup)
  motion    -> <ID>.mp4 (1080x1920, 30 fps, musik latar), <ID>.jpg (sampul)   Reels Motion, 12-32 dtk
  --frames  : khusus motion, hanya simpan PNG di detik tertentu (QA cepat, tanpa ffmpeg)

Format portal/<ID>.json:
{
  "id": "PT-261020-01",
  "format": "single",                        # "single" (default) | "carousel" | "motion"; rotasi dipilih agen 5
  "kategori": "IKLAN",                       # label kecil (IKLAN, MEDIA SOSIAL, AI, E-COMMERCE, PLATFORM, REGULASI)
  "judul": "Meta uji **iklan video** otomatis dari foto produk",   # judul berita, **kata penting** berwarna emas, maks ~16 kata
  "ringkas": ["Fitur tersedia umum di Ads Manager.", "Pengiklan bisa mengubah gambar jadi video."],   # 1-3 poin, tiap poin satu kalimat
  "sumber": "Meta for Business",             # nama sumber utama
  "tanggal": "20 Okt 2026",                  # tanggal rilis sumber
  "status": "Sudah rilis untuk semua",       # opsional: "Sudah rilis ...", "Bertahap", "Masih uji coba"; tampil di slide/scene terakhir (kartu single mengabaikannya)
  "slides": [{"judul": "Apa yang berubah", "isi": "kalimat fakta"}],   # hanya carousel: 2-4 slide isi (default: dari "ringkas")
  "music": true,                             # hanya motion (default true)
  "caption": "teks postingan"                # dipakai agen redaktur untuk antrian, tidak digambar
}
Gaya media netral: tanpa aku/kamu, tanpa wajah, tanpa nama pribadi.
Carousel: slide 1 sampul (judul), slide isi (satu fakta per slide), slide terakhir (status, sumber, ajakan ikuti).
Motion: scene pembuka (judul), satu scene per fakta (dari "ringkas"), scene status (bila ada), scene penutup (sumber + ajakan ikuti).
Semua teks berasal dari field yang sama dengan kartu, jadi tidak ada fakta baru yang muncul hanya di slide/video.
"""
import sys, os, json, shutil, tempfile
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_carousel import (font, wrap_rich, draw_rich, fit, pill, W, H, M, BG, BG2, PURPLE, PURPLE_D,
                             PURPLE_L, GRID, GOLD, WHITE, MUTE)

FOOT = 190  # tinggi footer
CTA = "Ikuti **Brainwork.id** untuk kabar marketing dan AI tiap hari."
FORMATS = ("single", "carousel", "motion")


def base():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for yy in range(0, 620):
        a = 1 - yy / 620
        d.line([(0, yy), (W, yy)], fill=tuple(int(BG[i] + (BG2[i] - BG[i]) * a) for i in range(3)))
    for gx in range(0, W, 90):
        d.line([(gx, 0), (gx, H - FOOT)], fill=GRID, width=1)
    for gy in range(0, H - FOOT, 90):
        d.line([(0, gy), (W, gy)], fill=GRID, width=1)
    d.rectangle([0, H - FOOT, W, H], fill=(8, 6, 16))
    d.rectangle([0, H - FOOT, W, H - FOOT + 4], fill=PURPLE)
    return img, d


def wordmark(d, x, y):
    d.rounded_rectangle([x, y, x + 52, y + 52], radius=12, fill=PURPLE)
    d.polygon([(x + 14, y + 36), (x + 26, y + 12), (x + 38, y + 36)], fill=GOLD)
    f1, f2 = font("black", 38), font("black", 38)
    tx = x + 70
    d.text((tx, y + 26), "BRAINWORK", font=f1, fill=WHITE, anchor="lm")
    d.text((tx + d.textlength("BRAINWORK", font=f1), y + 26), ".ID", font=f2, fill=GOLD, anchor="lm")


def footer(d, spec, with_source=True):
    fy = H - FOOT + 46
    if with_source:
        d.text((M, fy), "SUMBER", font=font("bold", 24), fill=PURPLE_L)
        sf = fit(d, spec.get("sumber", ""), "bold", [40, 36, 32, 28], W - 2 * M - 300, 1)
        d.text((M, fy + 40), spec.get("sumber", ""), font=sf, fill=WHITE)
        d.text((W - M, fy + 64), "brainwork.id", font=font("semi", 30), fill=PURPLE_L, anchor="rm")
    else:
        d.text((W // 2, H - FOOT // 2 + 4), "brainwork.id", font=font("bold", 36), fill=PURPLE_L, anchor="mm")


def render(spec, out_path):
    """Format single: satu kartu berita."""
    img, d = base()
    wordmark(d, M, 64)
    d.text((W - M, 90), spec.get("tanggal", ""), font=font("semi", 30), fill=MUTE, anchor="rm")
    y = 200
    y = pill(d, M, y, spec.get("kategori", "BERITA").upper(), font("bold", 30)) + 46
    tf = fit(d, spec["judul"], "black", [84, 76, 70, 64, 58, 52], W - 2 * M, 4)
    y = draw_rich(d, M, y, spec["judul"], tf, W - 2 * M, lh=1.13) + 34
    d.rounded_rectangle([M, y, M + 170, y + 12], radius=6, fill=GOLD)
    y += 62
    bf = font("reg", 42)
    limit = H - FOOT - 50
    for b in spec.get("ringkas", [])[:3]:
        lines = wrap_rich(d, b, bf, W - 2 * M - 52)
        need = len(lines) * int(42 * 1.32) + 28
        if y + need > limit:
            break
        d.regular_polygon((M + 12, y + 30, 12), 4, fill=GOLD)
        y = draw_rich(d, M + 52, y, b, bf, W - 2 * M - 52, color=(226, 220, 240), lh=1.32) + 28
    footer(d, spec)
    img.save(out_path, "JPEG", quality=90, optimize=True)


# ---------------------------------------------------------------- carousel

def _facts(spec):
    """Daftar (label, isi) untuk slide isi. Prioritas: spec['slides'], cadangan: 'ringkas'."""
    out = []
    for i, s in enumerate(spec.get("slides") or []):
        if isinstance(s, dict) and s.get("isi"):
            out.append(((s.get("judul") or f"FAKTA {i + 1}").upper(), s["isi"]))
    if not out:
        for i, b in enumerate(spec.get("ringkas", [])[:4]):
            out.append((f"FAKTA {i + 1}", b))
    return out[:4]


def slide_cover(spec, idx, total):
    img, d = base()
    wordmark(d, M, 64)
    d.text((W - M, 90), spec.get("tanggal", ""), font=font("semi", 30), fill=MUTE, anchor="rm")
    y = 220
    y = pill(d, M, y, spec.get("kategori", "BERITA").upper(), font("bold", 32)) + 56
    avail = (H - FOOT - 190) - y - 70  # sisakan ruang untuk garis emas dan tombol "geser"
    tf = None
    for sz in (100, 92, 84, 76, 70, 64, 58, 52):
        ff = font("black", sz)
        if len(wrap_rich(d, spec["judul"], ff, W - 2 * M)) * int(sz * 1.13) <= avail:
            tf = ff
            break
    tf = tf or font("black", 48)
    y = draw_rich(d, M, y, spec["judul"], tf, W - 2 * M, lh=1.13) + 40
    d.rounded_rectangle([M, y, M + 190, y + 14], radius=7, fill=GOLD)
    hf = font("bold", 34)
    pill(d, M, H - FOOT - 120,"GESER UNTUK DETAIL  ›", hf, fg=WHITE, bg=PURPLE_D)
    footer(d, spec)
    return img


def slide_fact(spec, label, isi, idx, total):
    img, d = base()
    wordmark(d, M, 64)
    d.text((W - M, 90), f"{idx} / {total}", font=font("semi", 30), fill=MUTE, anchor="rm")
    y = 220
    y = pill(d, M, y, label[:30], font("bold", 30)) + 56
    avail = H - FOOT - 60 - y
    f = None
    for sz in (68, 62, 58, 54, 50, 46, 42):
        ff = font("bold", sz)
        n = len(wrap_rich(d, isi, ff, W - 2 * M - 40))
        if n * int(sz * 1.3) <= avail:
            f = ff
            break
    f = f or font("bold", 40)
    lines = len(wrap_rich(d, isi, f, W - 2 * M - 40))
    th = lines * int(f.size * 1.3)
    y0 = y + max(0, (avail - th) // 2 - 20)
    d.rounded_rectangle([M, y0 + 6, M + 12, y0 + th - 6], radius=6, fill=GOLD)
    draw_rich(d, M + 40, y0, isi, f, W - 2 * M - 40, lh=1.3)
    footer(d, spec)
    return img


def slide_close(spec, idx, total):
    img, d = base()
    wordmark(d, M, 64)
    d.text((W - M, 90), f"{idx} / {total}", font=font("semi", 30), fill=MUTE, anchor="rm")
    y = 220
    if spec.get("status"):
        y = pill(d, M, y, "STATUS", font("bold", 30)) + 44
        sf = fit(d, spec["status"], "black", [72, 64, 58, 52], W - 2 * M, 3)
        y = draw_rich(d, M, y, spec["status"], sf, W - 2 * M, lh=1.15) + 50
    d.rounded_rectangle([M, y, M + 170, y + 12], radius=6, fill=GOLD)
    y += 62
    d.text((M, y), "SUMBER", font=font("bold", 26), fill=PURPLE_L)
    y += 44
    nf = fit(d, spec.get("sumber", ""), "bold", [46, 40, 36, 32], W - 2 * M, 2)
    y = draw_rich(d, M, y, spec.get("sumber", ""), nf, W - 2 * M, lh=1.2)
    if spec.get("tanggal"):
        d.text((M, y + 8), f"Rilis sumber: {spec['tanggal']}", font=font("reg", 34), fill=MUTE)
        y += 64
    y += 56
    cf = fit(d, CTA, "black", [60, 54, 50, 46], W - 2 * M, 4)
    draw_rich(d, M, y, CTA, cf, W - 2 * M, lh=1.18)
    footer(d, spec, with_source=False)
    return img


def render_carousel(spec, out_dir):
    facts = _facts(spec)
    if len(facts) < 2:
        sys.exit("carousel butuh minimal 2 fakta di 'slides' atau 'ringkas'")
    total = len(facts) + 2
    sid = spec["id"]
    files = []
    imgs = [slide_cover(spec, 1, total)]
    for i, (lab, isi) in enumerate(facts):
        imgs.append(slide_fact(spec, lab, isi, i + 2, total))
    imgs.append(slide_close(spec, total, total))
    for i, im in enumerate(imgs):
        p = os.path.join(out_dir, f"{sid}_{i + 1:02d}.jpg")
        im.save(p, "JPEG", quality=90, optimize=True)
        files.append(p)
    shutil.copyfile(files[0], os.path.join(out_dir, f"{sid}.jpg"))
    return files


# ---------------------------------------------------------------- motion

def _register_scene(rm):
    """Scene 'fakta' untuk Reels Motion portal: satu fakta besar per scene."""
    def sc_fakta(fr, s, t, dur):
        f = rm.fit(fr.d, s["text"], "x", [84, 76, 70, 64, 58, 52], rm.XW - 44, 8)
        _, th = rm.layout(fr.d, s["text"], f, rm.XW - 44)
        y = max(330, int((rm.H - th) / 2) - 170)  # blok teks di tengah, aman dari antarmuka Reels
        fr.fade_text(rm.X0, y, s.get("kicker", "").upper(), rm.font("s", 32), t, 0, rm.GOLD)
        p = rm.eo(rm.seg(t, 0.1, 0.6))
        if p > 0:
            fr.d.rounded_rectangle([rm.X0, y + 86, rm.X0 + 14, y + 86 + max(40, int((th - 10) * p))], radius=7, fill=rm.GOLD)
        fr.text_anim(rm.X0 + 44, y + 80, s["text"], f, rm.XW - 44, t, 0.2)
    rm.SCENES["fakta"] = sc_fakta


def build_scenes(spec):
    facts = [b for b in spec.get("ringkas", [])[:3] if b]
    if len(facts) < 2:
        sys.exit("motion butuh minimal 2 poin di 'ringkas'")
    sc = [{"type": "hook", "kicker": spec.get("kategori", "BERITA"), "text": spec["judul"], "dur": 3.6}]
    if spec.get("tanggal"):
        sc[0]["sub"] = spec["tanggal"]
    for i, b in enumerate(facts):
        dur = max(3.8, min(6.5, 2.4 + len(b) / 20.0))
        sc.append({"type": "fakta", "kicker": f"FAKTA {i + 1} DARI {len(facts)}", "text": b, "dur": round(dur, 1)})
    if spec.get("status"):
        sc.append({"type": "fakta", "kicker": "STATUS", "text": spec["status"], "dur": 3.2})
    src = spec.get("sumber", "")
    end = {"type": "end", "kicker": "IKUTI", "text": CTA, "dur": 4.0}
    if src:
        end["source"] = f"Sumber: {src}" + (f" · {spec['tanggal']}" if spec.get("tanggal") else "")
    sc.append(end)
    total = sum(s["dur"] for s in sc)
    if total < 12.5:
        sc[-1]["dur"] = round(sc[-1]["dur"] + (12.5 - total), 1)
    return sc


def render_motion(spec, out_dir, frames=None):
    import render_motion as rm
    rm.HANDLE = "brainwork.id"
    _register_scene(rm)
    mspec = {"id": spec["id"], "music": spec.get("music", True), "scenes": spec.get("scenes") or build_scenes(spec)}
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, spec["id"] + ".json")
    json.dump(mspec, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    argv = ["render_motion.py", p, out_dir] + (["--frames", frames] if frames else [])
    old = sys.argv
    sys.argv = argv
    try:
        rm.main()
    finally:
        sys.argv = old
        shutil.rmtree(tmp, ignore_errors=True)
    if frames:
        return []
    sid = spec["id"]
    tk = os.path.join(out_dir, f"{sid}_tiktok.mp4")
    if os.path.exists(tk):
        os.remove(tk)  # portal tidak memakai versi TikTok
    os.replace(os.path.join(out_dir, f"{sid}_cover.jpg"), os.path.join(out_dir, f"{sid}.jpg"))
    return [os.path.join(out_dir, f"{sid}.mp4")]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    frames = None
    if "--frames" in sys.argv:
        frames = sys.argv[sys.argv.index("--frames") + 1]
        args = [a for a in args if a != frames]
    spec = json.load(open(args[0], encoding="utf-8"))
    out = args[1] if len(args) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", spec["id"])
    os.makedirs(out, exist_ok=True)
    fmt = spec.get("format", "single")
    if fmt not in FORMATS:
        sys.exit(f"format tidak dikenal: {fmt!r} (pilih {', '.join(FORMATS)})")
    if fmt == "carousel":
        files = render_carousel(spec, out)
    elif fmt == "motion":
        files = render_motion(spec, out, frames)
    else:
        p = os.path.join(out, f"{spec['id']}.jpg")
        render(spec, p)
        files = [p]
    print(json.dumps({"format": fmt, "file": files[0] if files else None, "files": files}))


if __name__ == "__main__":
    main()
