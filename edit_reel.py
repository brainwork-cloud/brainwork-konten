#!/usr/bin/env python3
"""
Editor Reels otomatis @nopal.brainwork  (dijalankan GitHub Actions / mesin dengan internet)

Pemakaian:
  python3 edit_reel.py edits/<ID>.json            -> aset/<ID>/<ID>.mp4 + <ID>_tiktok.mp4 + <ID>_ig.mp4 (<= 3,3 MB untuk API Instagram) + <ID>_cover.jpg
  python3 edit_reel.py edits/<ID>.json --words w.json   (lewati transkripsi; untuk uji)

Spec edit (ditulis agen Produser):
{
  "id": "BW-261014-01",
  "mode": "faceless",                  # faceless | talking_head | activity
  "audio": "rekaman/BW-261014-01/vo.m4a",          # faceless: file voice over
  "broll": ["rekaman/BW-261014-01/layar1.mp4"],    # faceless: rekaman layar, urut
  "camera": "rekaman/BW-261014-01/kamera.mp4",     # talking_head: video + suara
  "hook": "Matiin 1 setting ini",       # teks besar 3 detik pertama (<= 6 kata)
  "highlight_words": ["pixel", "gratis"],          # kata yang diberi warna emas di subtitle
  "cut_silence": true,                  # buang jeda > 0.6 dtk
  "fix": {"cloud": "Claude", "perating jauhnya": "pratinjaunya"},   # koreksi salah dengar (kunci boleh >1 kata)
  "cut_ranges": [[57.8, 64.9]],         # buang rentang detik (waktu rekaman asli), mis. kalimat yang diulang
  "max_sec": 60,                        # batas durasi video akhir (termasuk penutup 1,8 dtk). Default 60. Kalau lebih: jeda dipadatkan otomatis,
                                        # sisanya dilaporkan di <ID>_peringatan.txt supaya Produser memotong lewat cut_ranges (daftar kalimat: <ID>_kalimat.txt)
  "outro": "Follow @nopal.brainwork buat tips ads & AI",
  # talking_head: sisipan B-roll (dibuat make_broll.py) yang menimpa gambar wajah, suara tetap jalan
  "cutaways": [{"after_word": "Library", "dur": 4, "clip": "rekaman/BW-261014-01/b1.mp4"},
               {"at": 12.5, "dur": 3, "clip": "rekaman/BW-261014-01/b2.mp4"}],
  # talking_head, MODE WAJAH HANYA DI PEMBUKA & PENUTUP: tengah video penuh animasi/grafis (scene render_motion + scenes_extra).
  # Tiap item menutup layar dari akhir kata pemicu sampai item berikutnya (item terakhir sampai penutup).
  # Durasi scene dihitung otomatis dari ucapan, jadi tidak perlu "dur". Kata pemicu: "kata", "dua kata", atau "kata#2" (kemunculan ke-2).
  "cover": [{"from_word": "editor", "scene": {"type": "icon", "icon": "image", "kicker": "Advantage+", "text": "Foto statis jadi **video ads**"}},
            {"at": 12.5, "scene": {"type": "steps", "title": "Caranya", "items": ["...", "..."]}}],
  "close_sec": 6,                       # wajah kembali di N detik terakhir (default 6)
  "close_from_word": "Simpan",          # atau: wajah kembali mulai akhir kata ini (menggantikan close_sec)
  # activity: klip aktivitas Naufal (tanpa bicara) + teks di layar + musik otomatis
  "clips": [{"file": "rekaman/<ID>/a1.mp4", "dur": 2.5, "start": 0, "text": "08.30, buka report ads dulu"}]
}
Hasil: MP4 H.264 1080x1920 30fps + AAC, subtitle tertanam, siap IG Reels / TikTok / Shorts.
"""
import sys, os, json, subprocess, tempfile, shutil, re, difflib
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
W, H, FPS = 1080, 1920, 30
GOLD_ASS = "&H0007C1F5&"   # BGR untuk #F5C107
WHITE_ASS = "&H00FFFFFF&"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("FFMPEG GAGAL:\n" + " ".join(cmd) + "\n" + r.stderr[-3000:])
    return r.stdout


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(out.strip())


# ---------- 1. Transkripsi ----------
def transcribe(audio, prompt=None):
    from faster_whisper import WhisperModel
    model = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    kw = dict(language="id", word_timestamps=True, vad_filter=True)
    if prompt:
        kw["initial_prompt"] = prompt   # memandu ejaan istilah (Claude, Meta Ad Library, dst)
    segs, _ = model.transcribe(audio, **kw)
    words = []
    for s in segs:
        for w in s.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
    return words


# ---------- 2. Potong jeda ----------
def keep_segments(words, total, gap=0.6, pad=0.15):
    if not words:
        return [(0, total)]
    segs, start = [], max(0, words[0]["s"] - pad)
    for a, b in zip(words, words[1:]):
        if b["s"] - a["e"] > gap:
            segs.append((start, min(total, a["e"] + pad)))
            start = max(0, b["s"] - pad)
    segs.append((start, min(total, words[-1]["e"] + pad)))
    return segs


OUTRO_SEC = 1.8                        # panjang klip penutup (outro) yang ditambahkan finish()
FILLERS = {"eh", "ehm", "em", "emm", "hm", "hmm", "mm", "mmm", "uh", "uhm", "umm", "anu", "ee", "eee"}


def plan_segments(words, total, cut, limit, spec):
    """Tentukan bagian yang dipertahankan. Kalau terlalu panjang (> limit), padatkan jeda (dua tahap) lalu buang kata isian (eh, hmm, anu).
    Isi kalimat TIDAK dihapus otomatis: itu keputusan Produser lewat cut_ranges.
    -> (words, segs, catatan)"""
    notes = []
    if not spec.get("cut_silence", True):
        return words, subtract_ranges([(0, total)], cut), notes
    segs = subtract_ranges(keep_segments(words, total), cut)
    cur = sum(e - b for b, e in segs)
    if cur <= limit or not spec.get("auto_tighten", True):
        return words, segs, notes
    for gap, pad in ((0.45, 0.12), (0.32, 0.08)):
        segs2 = subtract_ranges(keep_segments(words, total, gap, pad), cut)
        new = sum(e - b for b, e in segs2)
        notes.append(f"jeda > {gap:.2f} dtk dipotong (hemat {cur - new:.1f} dtk)")
        segs, cur = segs2, new
        if cur <= limit:
            return words, segs, notes
    fill = [(w["s"], w["e"]) for w in words if _norm(w["w"]) in FILLERS]
    if fill:
        words = drop_ranges(words, fill)
        segs2 = subtract_ranges(keep_segments(words, total, 0.32, 0.08), cut + fill)
        new = sum(e - b for b, e in segs2)
        notes.append(f"{len(fill)} kata isian dibuang (hemat {cur - new:.1f} dtk)")
        segs, cur = segs2, new
    return words, segs, notes


def sentence_list(words, cut, gap=0.4):
    """Kalimat berwaktu (waktu rekaman ASLI) untuk memilih cut_ranges. Baris bertanda [SUDAH DIPOTONG] ada di cut_ranges."""
    out, cur = [], []
    for w in words:
        if cur and (w["s"] - cur[-1]["e"] > gap or len(cur) >= 16):
            out.append(cur); cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    lines = []
    for sn in out:
        a, b = sn[0]["s"], sn[-1]["e"]
        gone = any(c0 - 0.05 <= a and b <= c1 + 0.05 for c0, c1 in cut)
        lines.append(f"[{a:6.1f} - {b:6.1f}] {b - a:4.1f} dtk{'  [SUDAH DIPOTONG]' if gone else ''} | " + " ".join(x["w"] for x in sn))
    return lines


def remap(t, segs):
    acc = 0
    for s, e in segs:
        if t < s:
            return acc
        if t <= e:
            return acc + (t - s)
        acc += e - s
    return acc


# ---------- 2b. Koreksi transkrip ----------
def load_glossary():
    try:
        return json.load(open(os.path.join(HERE, "glossary.json"), encoding="utf-8"))
    except Exception:
        return {"terms": [], "fix": {}}


def _norm(t):
    return re.sub(r"^[^\w+]+|[^\w+]+$", "", t.lower())


def apply_fix(words, fix):
    """Ganti salah dengar. Kunci boleh beberapa kata ("perating jauhnya": "pratinjaunya"); waktu dibagi rata."""
    rules = sorted(((k.lower().split(), v.split()) for k, v in (fix or {}).items() if k.strip() and v.strip()),
                   key=lambda r: -len(r[0]))
    out, i = [], 0
    while i < len(words):
        for key, val in rules:
            n = len(key)
            if i + n <= len(words) and all(_norm(words[i + j]["w"]) == key[j] for j in range(n)):
                s, e = words[i]["s"], words[i + n - 1]["e"]
                m = re.search(r"[.,?!:;]+$", words[i + n - 1]["w"])
                trail = m.group(0) if m else ""
                step = (e - s) / len(val)
                for k, tok in enumerate(val):
                    out.append({"w": tok + (trail if k == len(val) - 1 else ""),
                                "s": round(s + k * step, 3), "e": round(s + (k + 1) * step, 3)})
                i += n
                break
        else:
            out.append(words[i])
            i += 1
    return out


def drop_ranges(words, ranges):
    """Buang kata yang titik tengahnya jatuh di rentang (detik rekaman asli): kalimat yang diulang (retake)."""
    if not ranges:
        return words
    return [w for w in words if not any(a <= (w["s"] + w["e"]) / 2 <= b for a, b in ranges)]


def subtract_ranges(segs, ranges):
    out = []
    for s, e in segs:
        cur = [(s, e)]
        for a, b in ranges or []:
            nxt = []
            for x, y in cur:
                if b <= x or a >= y:
                    nxt.append((x, y))
                else:
                    if a > x:
                        nxt.append((x, a))
                    if b < y:
                        nxt.append((b, y))
            cur = nxt
        out += cur
    return [(x, y) for x, y in out if y - x > 0.05]


def find_word_end(new_words, after_word):
    """Akhir kata pemicu sisipan/cover. Boleh "kata", "dua kata" (berurutan), atau "kata#2" (kemunculan ke-2).
    Cocok persis dulu, lalu yang mirip (>= 0,75, hanya kata pertama). None kalau tidak ketemu."""
    spec, nth = after_word.strip(), 1
    m = re.match(r"^(.*)#(\d+)$", spec)
    if m:
        spec, nth = m.group(1).strip(), max(1, int(m.group(2)))
    keys = [_norm(x) for x in spec.split()]
    if not keys or not all(keys):
        return None
    n, seen = len(keys), 0
    for i in range(len(new_words) - n + 1):
        if all(keys[j] in _norm(new_words[i + j]["w"]) for j in range(n)):
            seen += 1
            if seen == nth:
                return new_words[i + n - 1]["e"]
    if nth > 1:
        return None
    best, score = None, 0.0
    for w in new_words:
        r = difflib.SequenceMatcher(None, keys[0], _norm(w["w"])).ratio()
        if r > score:
            best, score = w, r
    return best["e"] if best and score >= 0.75 else None


def plan_cover(spec, new_words, main_len, tmp, out_dir):
    """Mode wajah hanya di pembuka dan penutup: tiap item cover menutup layar dari kata pemicunya sampai item berikutnya,
    item terakhir sampai penutup. Scene dirender di sini dengan durasi yang pas dengan ucapan.
    -> (daftar (mulai, durasi, klip, fade_masuk, fade_keluar), peringatan)"""
    sys.path.insert(0, HERE)
    import render_motion
    warns, plan = [], []
    for c in spec["cover"]:
        st = c.get("at")
        if st is None and c.get("from_word"):
            st = find_word_end(new_words, c["from_word"])
            if st is None:
                warns.append(f"cover dari kata '{c['from_word']}' tidak ketemu di transkrip, dilewati (perbaiki 'fix' atau pakai 'at' detik)")
        if st is not None and c.get("scene"):
            plan.append((float(st), c))
    close = find_word_end(new_words, spec["close_from_word"]) if spec.get("close_from_word") else None
    if close is None:
        if spec.get("close_from_word"):
            warns.append(f"close_from_word '{spec['close_from_word']}' tidak ketemu, pakai close_sec")
        close = main_len - float(spec.get("close_sec", 6))
    plan.sort(key=lambda x: x[0])
    plan = [(st, c) for st, c in plan if st < close - 0.8]
    if plan and plan[0][0] < 2.0:
        warns.append(f"cover pertama mulai {plan[0][0]:.1f} dtk: wajah perlu tampil di pembuka (minimal 2 dtk)")
    res, lines = [], []
    for i, (st, c) in enumerate(plan):
        end = plan[i + 1][0] if i + 1 < len(plan) else close
        du = end - st
        if du < 0.8:
            warns.append(f"cover pada {st:.1f} dtk hanya {du:.1f} dtk, dilewati (geser kata pemicu)")
            continue
        if du > 8.5:
            warns.append(f"cover pada {st:.1f} dtk berdurasi {du:.1f} dtk (> 8,5): tambah item cover supaya layar tidak diam lama")
        last = i + 1 == len(plan)
        scene = dict(c["scene"]); scene["dur"] = round(du + (0 if last else 0.06), 3)   # tumpang tindih 0,06 dtk: tidak ada kedipan wajah
        path = os.path.join(tmp, f"cover{i}.mp4")
        render_motion.render_clip([scene], path)
        res.append((st, scene["dur"], path))
        lines.append(f"{st:6.1f} dtk | {du:4.1f} dtk | {scene.get('type')} | {(scene.get('text') or scene.get('title') or '')[:60]}")
    out = [(st, du, path, k == 0, k == len(res) - 1) for k, (st, du, path) in enumerate(res)]
    open(os.path.join(out_dir, f"{spec['id']}_cover.txt"), "w", encoding="utf-8").write(
        f"wajah tampil: 0-{(res[0][0] if res else main_len):.1f} dtk dan {close:.1f}-{main_len:.1f} dtk\n" + "\n".join(lines) + "\n")
    return out, warns


# ---------- 3. Subtitle ASS ----------
def ass_time(t):
    h, r = divmod(max(t, 0), 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_ass(words, hook, highlights, total, path):
    hl = {h.lower() for h in highlights or []}
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Poppins Black,92,&H00FFFFFF,&H00FFFFFF,&H00140814,&H96000000,-1,0,0,0,100,100,0,0,1,7,3,2,80,80,560,1
Style: Hook,Poppins Black,104,&H00FFFFFF,&H00FFFFFF,&H0080184A,&H96000000,-1,0,0,0,100,100,0,0,3,26,0,8,70,70,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if hook:
        lines.append(f"Dialogue: 1,{ass_time(0)},{ass_time(min(3.0, total))},Hook,,0,0,0,,{{\\fad(120,200)}}{hook.upper()}")
    # potong per 3 kata, maksimal 1,6 detik
    chunk = []
    for w in words + [None]:
        if w is not None:
            chunk.append(w)
        if chunk and (w is None or len(chunk) == 3 or chunk[-1]["e"] - chunk[0]["s"] > 1.6
                      or re.search(r"[.,?!]$", chunk[-1]["w"])):
            st, en = chunk[0]["s"], chunk[-1]["e"]
            for i, cw in enumerate(chunk):
                # karaoke: kata yang sedang diucapkan berwarna emas
                parts = []
                for j, x in enumerate(chunk):
                    txt = re.sub(r"[{}\\]", "", x["w"]).upper()
                    gold = j == i or x["w"].lower().strip(".,?!") in hl
                    parts.append(("{\\c" + GOLD_ASS + "}" if gold else "{\\c" + WHITE_ASS + "}") + txt)
                s2 = cw["s"] if i else st
                e2 = chunk[i + 1]["s"] if i + 1 < len(chunk) else en
                lines.append(f"Dialogue: 0,{ass_time(s2)},{ass_time(max(e2, s2 + 0.05))},Cap,,0,0,0,,{' '.join(parts)}")
            chunk = []
    open(path, "w", encoding="utf-8").write(head + "\n".join(lines) + "\n")


def activity_ass(hook, items, path):
    """items: [(start, end, text)]"""
    build_ass([], hook, [], items[-1][1] if items else 3, path)
    style = "Style: Txt,Poppins Black,78,&H00FFFFFF,&H00FFFFFF,&H0080184A,&H96000000,-1,0,0,0,100,100,0,0,3,22,0,2,90,90,620,1\n"
    head, ev = open(path, encoding="utf-8").read().split("[Events]")
    head = head.rstrip("\n") + "\n" + style + "\n"
    clean = lambda x: re.sub(r"[{}\\]", "", x)
    fad = "{\\fad(150,150)}"
    lines = ["Dialogue: 0,%s,%s,Txt,,0,0,0,,%s%s" % (ass_time(a + (0.6 if i == 0 and hook else 0)), ass_time(b), fad, clean(t))
             for i, (a, b, t) in enumerate(items) if t]
    open(path, "w", encoding="utf-8").write(head + "[Events]" + ev.rstrip("\n") + "\n" + "\n".join(lines) + "\n")


# ---------- 4. Outro ----------
def outro_png(text, path):
    img = Image.new("RGB", (W, H), (10, 8, 20))
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 90):
        d.line([(gx, 0), (gx, H)], fill=(40, 22, 74))
    for gy in range(0, H, 90):
        d.line([(0, gy), (W, gy)], fill=(40, 22, 74))
    f1 = ImageFont.truetype(os.path.join(FONTS, "Poppins-Black.ttf"), 92)
    f2 = ImageFont.truetype(os.path.join(FONTS, "Poppins-SemiBold.ttf"), 52)
    d.text((W / 2, H / 2 - 120), "@nopal.brainwork", font=f1, fill=(245, 193, 7), anchor="mm")
    # bungkus teks
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f2) > W - 200:
            lines.append(cur); cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    y = H / 2 + 10
    for ln in lines:
        d.text((W / 2, y), ln, font=f2, fill=(255, 255, 255), anchor="mm"); y += 72
    img.save(path)


def main():
    spec_path = sys.argv[1]
    spec = json.load(open(spec_path, encoding="utf-8"))
    words_override = sys.argv[sys.argv.index("--words") + 1] if "--words" in sys.argv else None
    root = os.path.dirname(os.path.dirname(os.path.abspath(spec_path)))  # repo root
    P = lambda p: p if os.path.isabs(p) else os.path.join(root, p)
    out_dir = os.path.join(root, "aset", spec["id"]); os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp()

    mode = spec.get("mode", "faceless")
    if mode == "activity":
        return activity(spec, P, out_dir, tmp)
    src_audio = P(spec["audio"] if mode == "faceless" else spec["camera"])
    wav = os.path.join(tmp, "a.wav")
    run(["ffmpeg", "-y", "-i", src_audio, "-vn", "-ac", "1", "-ar", "16000", wav])
    total = duration(wav)

    gl = load_glossary()
    prompt = None
    if spec.get("whisper_prompt", True) and gl.get("terms"):
        prompt = "Video edukasi digital marketing berbahasa Indonesia. Istilah: " + ", ".join(gl["terms"]) + "."
    words = json.load(open(words_override)) if words_override else transcribe(wav, prompt)
    # _words.json = hasil mentah Whisper (untuk diperiksa); koreksi dipakai untuk subtitle dan pemicu sisipan
    json.dump(words, open(os.path.join(out_dir, f"{spec['id']}_words.json"), "w"), ensure_ascii=False)
    words = apply_fix(words, {**gl.get("fix", {}), **spec.get("fix", {})})
    words_all = list(words)
    cut = [(float(a), float(b)) for a, b in spec.get("cut_ranges", [])]
    words = drop_ranges(words, cut)

    max_sec = float(spec.get("max_sec", 60))
    outro_len = OUTRO_SEC if spec.get("outro") else 0.0
    words, segs, tight_notes = plan_segments(words, total, cut, max_sec - outro_len - 1.0, spec)   # sasaran 1 dtk di bawah batas supaya aman
    new_words = [{"w": w["w"], "s": remap(w["s"], segs), "e": remap(w["e"], segs)} for w in words]
    main_len = sum(e - s for s, e in segs)
    final_len = main_len + outro_len

    # filter potong audio
    sel = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in segs)

    # visual dasar
    base = os.path.join(tmp, "base.mp4")
    if mode == "faceless":
        clips = [P(b) for b in spec["broll"]]
        lst = os.path.join(tmp, "list.txt")
        norm = []
        for i, c in enumerate(clips):
            n = os.path.join(tmp, f"n{i}.mp4")
            # layar di tengah, latar = versi blur gelap dari rekaman itu sendiri
            run(["ffmpeg", "-y", "-i", c, "-an", "-filter_complex",
                 f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.35[bg];"
                 f"[0:v]scale={W - 60}:-2:force_original_aspect_ratio=decrease[fg];"
                 f"[bg][fg]overlay=(W-w)/2:(H-h)/2-80,fps={FPS},setsar=1,format=yuv420p",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", n])
            norm.append(n)
        open(lst, "w").write("".join(f"file '{n}'\n" for n in norm))
        cat = os.path.join(tmp, "cat.mp4")
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", cat])
        # ulang/potong supaya sama panjang dengan audio yang sudah dipotong
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", cat, "-t", f"{main_len:.3f}", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "20", "-an", base])
        run(["ffmpeg", "-y", "-i", base, "-i", wav, "-filter_complex",
             f"[1:a]aselect='{sel}',asetpts=N/SR/TB,loudnorm=I=-14:TP=-1.5,aresample=48000[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
             os.path.join(tmp, "main.mp4")])
    else:
        run(["ffmpeg", "-y", "-i", src_audio, "-filter_complex",
             f"[0:v]select='{sel}',setpts=N/FRAME_RATE/TB,scale={W}:{H}:force_original_aspect_ratio=increase,"
             f"crop={W}:{H},fps={FPS},format=yuv420p[v];[0:a]aselect='{sel}',asetpts=N/SR/TB,loudnorm=I=-14:TP=-1.5,aresample=48000[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", os.path.join(tmp, "main.mp4")])

    # sisipan B-roll (talking head)
    cuts, warns = [], []
    for c in spec.get("cutaways", []):
        st = c.get("at")
        if st is None and c.get("after_word"):
            st = find_word_end(new_words, c["after_word"])
            if st is None:
                warns.append(f"sisipan setelah kata '{c['after_word']}' tidak ketemu di transkrip, dilewati (tambah koreksi di 'fix' atau pakai 'at')")
        if st is not None and os.path.exists(P(c["clip"])):
            cuts.append((max(0, st), min(float(c.get("dur", 3)), main_len - st), P(c["clip"])))
        elif st is not None:
            warns.append(f"klip sisipan tidak ada: {c['clip']}")
    if spec.get("cover"):
        cv, cw = plan_cover(spec, new_words, main_len, tmp, out_dir)
        cuts += cv
        warns += cw
    # batas durasi Reels (default 60 dtk): bagian yang tak penting dipotong Produser lewat cut_ranges
    if final_len > max_sec + 0.05:
        warns.append(f"DURASI {final_len:.1f} dtk melebihi batas {max_sec:.0f} dtk: potong minimal {final_len - max_sec + 0.5:.1f} dtk lagi lewat 'cut_ranges' "
                     f"(detik rekaman asli; daftar kalimat berwaktu ada di {spec['id']}_kalimat.txt). Buang dulu rekaman ulang atau kalimat berulang, basa-basi, "
                     "penjelasan kedua untuk poin yang sama, lalu poin paling tidak berdampak. Jangan buang kalimat pembuka dan penutup.")
    open(os.path.join(out_dir, f"{spec['id']}_kalimat.txt"), "w", encoding="utf-8").write(
        f"durasi akhir: {final_len:.1f} dtk (batas {max_sec:.0f} dtk; isi {main_len:.1f} + penutup {outro_len:.1f}); rekaman asli {total:.1f} dtk\n"
        + ("".join(f"pemadatan otomatis: {n}\n" for n in tight_notes))
        + "\n".join(sentence_list(words_all, cut)) + "\n")
    # catatan untuk Produser: teks subtitle akhir + peringatan
    open(os.path.join(out_dir, f"{spec['id']}_teks.txt"), "w", encoding="utf-8").write(" ".join(w["w"] for w in new_words) + "\n")
    pf = os.path.join(out_dir, f"{spec['id']}_peringatan.txt")
    if warns:
        open(pf, "w", encoding="utf-8").write("\n".join(warns) + "\n")
        print("PERINGATAN:", *warns, sep="\n  ", file=sys.stderr)
    elif os.path.exists(pf):
        os.remove(pf)
    if cuts:
        ins, fl, last = ["-i", os.path.join(tmp, "main.mp4")], [], "[0:v]"
        for i, cu in enumerate(cuts, 1):
            st, du, clip = cu[:3]
            fin, fout = (cu[3], cu[4]) if len(cu) > 3 else (False, False)
            fx = ""
            if fin or fout:
                fx = ",format=yuva420p"
                if fin:
                    fx += f",fade=t=in:st={st:.3f}:d=0.2:alpha=1"
                if fout:
                    fx += f",fade=t=out:st={st + du - 0.2:.3f}:d=0.2:alpha=1"
            ins += ["-i", clip]
            fl.append(f"[{i}:v]trim=0:{du:.3f},setpts=PTS-STARTPTS+{st:.3f}/TB,scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}{fx}[c{i}]")
            fl.append(f"{last}[c{i}]overlay=0:0:eof_action=pass:enable='between(t,{st:.3f},{st + du:.3f})'[o{i}]")
            last = f"[o{i}]"
        run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fl), "-map", last, "-map", "0:a", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "20", "-c:a", "copy", os.path.join(tmp, "main2.mp4")])
        shutil.move(os.path.join(tmp, "main2.mp4"), os.path.join(tmp, "main.mp4"))

    # subtitle + hook
    ass = os.path.join(tmp, "cap.ass")
    build_ass(new_words, spec.get("hook"), spec.get("highlight_words"), main_len, ass)
    subbed = os.path.join(tmp, "sub.mp4")
    run(["ffmpeg", "-y", "-i", os.path.join(tmp, "main.mp4"), "-vf", f"subtitles={ass}:fontsdir={FONTS}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-c:a", "copy", subbed])

    finish(spec, subbed, out_dir, tmp, len(words))


def finish(spec, subbed, out_dir, tmp, nwords):
    final = os.path.join(out_dir, f"{spec['id']}.mp4")
    if spec.get("outro"):
        png = os.path.join(tmp, "outro.png"); outro_png(spec["outro"], png)
        ov = os.path.join(tmp, "outro.mp4")
        run(["ffmpeg", "-y", "-loop", "1", "-i", png, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
             "-t", "1.8", "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
             "-c:a", "aac", "-ar", "48000", "-shortest", ov])
        run(["ffmpeg", "-y", "-i", subbed, "-i", ov, "-filter_complex",
             "[0:v]setsar=1[v0];[1:v]setsar=1[v1];[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-c:a", "aac", "-b:a", "160k",
             "-movflags", "+faststart", final])
    else:
        run(["ffmpeg", "-y", "-i", subbed, "-c", "copy", "-movflags", "+faststart", final])

    # versi kecil (< 9,5 MB) untuk upload TikTok lewat Chrome (batas upload 10 MB per file)
    dur = duration(final)
    vbit = int(min(3500, max(600, (9.5 * 8000 / dur) - 140)))  # kbps
    tiktok = os.path.join(out_dir, f"{spec['id']}_tiktok.mp4")
    run(["ffmpeg", "-y", "-i", final, "-vf", "scale=720:1280", "-c:v", "libx264", "-preset", "slow",
         "-b:v", f"{vbit}k", "-maxrate", f"{vbit}k", "-bufsize", f"{vbit * 2}k", "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", tiktok])

    # versi Instagram (<= 3,3 MB): API Instagram menolak unggahan video di atas +-4 MB (ProcessingFailedError sejak 30 Sep 2026).
    # 720x1280, dua lintasan supaya ukurannya pas; SSIM terhadap file penuh ~0,99 (tampak sama di layar ponsel).
    ig = os.path.join(out_dir, f"{spec['id']}_ig.mp4")
    ig_vbit = int(max(250, 3.3 * 8000 / dur - 72))
    ig_log = os.path.join(tmp, "ig2pass")
    ig_args = ["-vf", "scale=720:1280:flags=lanczos", "-c:v", "libx264", "-preset", "slow", "-b:v", f"{ig_vbit}k",
               "-maxrate", f"{ig_vbit * 3 // 2}k", "-bufsize", f"{ig_vbit * 2}k", "-passlogfile", ig_log]
    run(["ffmpeg", "-y", "-i", final, *ig_args, "-pass", "1", "-an", "-f", "null", os.devnull])
    run(["ffmpeg", "-y", "-i", final, *ig_args, "-pass", "2", "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-movflags", "+faststart", ig])
    if os.path.getsize(ig) > 3.6e6:
        with open(os.path.join(out_dir, f"{spec['id']}_peringatan.txt"), "a", encoding="utf-8") as pw:
            pw.write(f"Versi IG {os.path.getsize(ig) / 1e6:.1f} MB (batas aman 3,6 MB): Instagram bisa menolak. Pendekkan video.\n")

    cover = os.path.join(out_dir, f"{spec['id']}_cover.jpg")
    run(["ffmpeg", "-y", "-ss", "0.8", "-i", final, "-frames:v", "1", "-q:v", "3", cover])
    size_mb = os.path.getsize(final) / 1e6
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps({"video": final, "cover": cover, "duration": round(duration(final), 2),
                      "size_mb": round(size_mb, 1), "words": nwords}))


def activity(spec, P, out_dir, tmp):
    import numpy  # noqa: F401  (dipakai render_motion.score)
    sys.path.insert(0, HERE)
    import render_motion
    norm, items, t = [], [], 0.0
    for i, c in enumerate(spec["clips"]):
        d = float(c.get("dur", 2.5)); n = os.path.join(tmp, f"a{i}.mp4")
        run(["ffmpeg", "-y", "-ss", str(c.get("start", 0)), "-i", P(c["file"]), "-t", f"{d:.3f}", "-an", "-vf",
             f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", n])
        norm.append(n); items.append((t, t + d, c.get("text", ""))); t += d
    lst = os.path.join(tmp, "list.txt"); open(lst, "w").write("".join(f"file '{n}'\n" for n in norm))
    cat = os.path.join(tmp, "cat.mp4"); run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", cat])
    scenes = [{"type": "hook", "dur": items[0][1]}] + [{"type": "statement", "dur": b - a} for a, b, _ in items[1:-1]] + [{"type": "end", "dur": items[-1][1] - items[-1][0]}]
    wav = os.path.join(tmp, "m.wav"); render_motion.score({"scenes": scenes}, wav)
    run(["ffmpeg", "-y", "-i", cat, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-ar", "48000", "-shortest", os.path.join(tmp, "main.mp4")])
    ass = os.path.join(tmp, "cap.ass"); activity_ass(spec.get("hook"), items, ass)
    subbed = os.path.join(tmp, "sub.mp4")
    run(["ffmpeg", "-y", "-i", os.path.join(tmp, "main.mp4"), "-vf", f"subtitles={ass}:fontsdir={FONTS}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-c:a", "copy", subbed])
    finish(spec, subbed, out_dir, tmp, 0)


if __name__ == "__main__":
    main()
