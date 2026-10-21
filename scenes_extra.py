#!/usr/bin/env python3
"""
Scene tambahan untuk B-roll penuh (ilustrasi + animasi) @nopal.brainwork.
Didaftarkan ke render_motion.SCENES, jadi dipakai di motion/*.json, make_broll (type "motion") dan "cover" di edits/*.json.

  icon   {"type":"icon","icon":"image","kicker":"Advantage+ creative","text":"Foto statis jadi **video ads**","note":"opsional"}
  flow   {"type":"flow","kicker":"Alurnya","title":"Dari foto ke video","items":[{"icon":"image","label":"Foto produk"},{"icon":"video","label":"Video ads"}]}   (2-3 item)
  steps  {"type":"steps","kicker":"Caranya","title":"Di **Ads Manager**","items":["Pakai foto produkmu","Buka Advantage+","Aktifkan opsinya"]}   (2-4 item, muncul satu per satu mengikuti durasi scene)
  vs     {"type":"vs","kicker":"Ingat","title":"opsional","yes":{"title":"Bahan tes"},"no":{"title":"Pengganti video asli"}}

Ikon: image, video, search, chat, bulb, chart, check, cross, target, sparkle, cursor, doc, warning, clock, arrow, phone
(alias: foto, gambar, cari, riset, ai, claude, ide, grafik, dokumen, catatan, hp, waktu, peringatan, ya, tidak).
Area aman: konten di y 250-1130 (subtitle talking head memakai y 1170-1360). Teks di antara **...** berwarna emas.
"""
import math
from functools import lru_cache
from PIL import Image, ImageDraw

SS = 3  # supersample ikon supaya tepinya halus
ALIAS = {"foto": "image", "gambar": "image", "cari": "search", "riset": "search", "ai": "sparkle", "claude": "sparkle",
         "ide": "bulb", "grafik": "chart", "dokumen": "doc", "catatan": "doc", "hp": "phone", "waktu": "clock",
         "peringatan": "warning", "ya": "check", "tidak": "cross", "play": "video"}


@lru_cache(maxsize=512)
def icon(name, size, col, inner):
    """Ikon vektor sederhana, digambar di grid 100x100. col = warna isi, inner = warna lubang (samakan dengan latar kartu)."""
    name = ALIAS.get(name, name)
    S = max(8, int(size)) * SS
    k = S / 100.0
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    P = lambda *pts: [(x * k, y * k) for x, y in pts]
    R = lambda x0, y0, x1, y1: [x0 * k, y0 * k, x1 * k, y1 * k]
    w = lambda v: max(1, int(v * k))
    if name == "image":
        d.rounded_rectangle(R(8, 16, 92, 84), radius=w(10), outline=col, width=w(6))
        d.ellipse(R(60, 28, 76, 44), fill=col)
        d.polygon(P((16, 76), (38, 50), (54, 68), (66, 56), (84, 76)), fill=col)
    elif name == "video":
        d.rounded_rectangle(R(8, 20, 92, 80), radius=w(12), fill=col)
        d.polygon(P((42, 36), (42, 64), (68, 50)), fill=inner)
    elif name == "search":
        d.ellipse(R(12, 12, 66, 66), outline=col, width=w(9))
        d.line(P((58, 58), (86, 86)), fill=col, width=w(11))
        d.ellipse(R(79, 79, 93, 93), fill=col)
    elif name == "chat":
        d.rounded_rectangle(R(8, 14, 92, 68), radius=w(14), fill=col)
        d.polygon(P((26, 62), (26, 88), (52, 62)), fill=col)
        for cx in (32, 50, 68):
            d.ellipse(R(cx - 5, 36, cx + 5, 46), fill=inner)
    elif name == "bulb":
        d.ellipse(R(24, 6, 76, 58), fill=col)
        d.polygon(P((36, 48), (64, 48), (58, 70), (42, 70)), fill=col)
        d.rounded_rectangle(R(40, 72, 60, 80), radius=w(4), fill=col)
        d.rounded_rectangle(R(43, 83, 57, 91), radius=w(4), fill=col)
    elif name == "chart":
        for i, hh in enumerate((28, 46, 66)):
            x = 14 + i * 28
            d.rounded_rectangle(R(x, 84 - hh, x + 20, 84), radius=w(4), fill=col)
        d.line(P((8, 90), (92, 90)), fill=col, width=w(4))
    elif name == "check":
        d.ellipse(R(6, 6, 94, 94), fill=col)
        d.line(P((28, 52), (44, 68), (72, 34)), fill=inner, width=w(10), joint="curve")
    elif name == "cross":
        d.ellipse(R(6, 6, 94, 94), fill=col)
        d.line(P((34, 34), (66, 66)), fill=inner, width=w(10))
        d.line(P((66, 34), (34, 66)), fill=inner, width=w(10))
    elif name == "target":
        for r_, f_ in ((44, col), (32, inner), (21, col), (11, inner), (5, col)):
            d.ellipse(R(50 - r_, 50 - r_, 50 + r_, 50 + r_), fill=f_)
    elif name == "sparkle":
        d.polygon(P((46, 8), (56, 38), (86, 48), (56, 58), (46, 88), (36, 58), (6, 48), (36, 38)), fill=col)
        d.polygon(P((80, 6), (84, 15), (93, 19), (84, 23), (80, 32), (76, 23), (67, 19), (76, 15)), fill=col)
    elif name == "cursor":
        d.polygon(P((26, 8), (26, 80), (44, 64), (56, 90), (68, 84), (56, 60), (80, 58)), fill=col)
    elif name == "doc":
        d.polygon(P((20, 6), (62, 6), (82, 26), (82, 94), (20, 94)), fill=col)
        d.polygon(P((62, 6), (62, 26), (82, 26)), fill=inner)
        for y_ in (46, 60, 74):
            d.line(P((32, y_), (70, y_)), fill=inner, width=w(5))
    elif name == "warning":
        d.polygon(P((50, 8), (95, 88), (5, 88)), fill=col)
        d.line(P((50, 38), (50, 62)), fill=inner, width=w(8))
        d.ellipse(R(45, 69, 55, 79), fill=inner)
    elif name == "clock":
        d.ellipse(R(8, 8, 92, 92), outline=col, width=w(8))
        d.line(P((50, 50), (50, 26)), fill=col, width=w(7))
        d.line(P((50, 50), (68, 60)), fill=col, width=w(7))
    elif name == "arrow":
        d.polygon(P((6, 38), (56, 38), (56, 18), (94, 50), (56, 82), (56, 62), (6, 62)), fill=col)
    elif name == "phone":
        d.rounded_rectangle(R(26, 4, 74, 96), radius=w(10), fill=col)
        d.rounded_rectangle(R(32, 14, 68, 80), radius=w(4), fill=inner)
        d.ellipse(R(45, 84, 55, 92), fill=inner)
    else:  # cadangan: lingkaran
        d.ellipse(R(10, 10, 90, 90), fill=col)
    return im.resize((int(size), int(size)), Image.LANCZOS)


def register(rm):
    W, H = rm.W, rm.H
    GOLD, INK, MUTE, CARD, PANEL, BG, X0, XW = rm.GOLD, rm.INK, rm.MUTE, rm.CARD, rm.PANEL, rm.BG, rm.X0, rm.XW
    font, eo, eob, seg, clamp = rm.font, rm.eo, rm.eob, rm.seg, rm.clamp

    def blend(c, p, base=BG):
        p = clamp(p)
        return tuple(int(base[k] + (c[k] - base[k]) * p) for k in range(3))

    def paste(fr, im, x, y, al=1.0):
        al = clamp(al)
        if al <= 0:
            return
        if al < 1:
            im = im.copy()
            im.putalpha(im.split()[3].point(lambda v: int(v * al)))
        fr.img.paste(im, (int(x), int(y)), im)

    def cwrap(d, text, f, maxw):
        sp = d.textlength(" ", font=f)
        lines, cur, cw = [], [], 0
        for w_, g in rm.words(text):
            ww = d.textlength(w_, font=f)
            if cur and cw + sp + ww > maxw:
                lines.append((cur, cw)); cur, cw = [], 0
            cur.append((w_, g, ww)); cw += (sp if len(cur) > 1 else 0) + ww
        if cur:
            lines.append((cur, cw))
        return lines, sp

    def cfit(d, text, wt, sizes, maxw, maxlines):
        for s_ in sizes:
            f = font(wt, s_)
            if len(cwrap(d, text, f, maxw)[0]) <= maxlines:
                return f
        return font(wt, sizes[-1])

    def ctext(fr, cx, y, text, f, maxw, t, t0, color=INK, stagger=0.06, dur=0.4, dy=24, lh=1.15):
        """Teks rata tengah, kata muncul bergantian. Mengembalikan y di bawah teks."""
        lines, sp = cwrap(fr.d, text or "", f, maxw)
        i = 0
        for ln, lw in lines:
            x = cx - lw / 2
            for w_, g, ww in ln:
                p = eo(seg(t, t0 + i * stagger, t0 + i * stagger + dur)); i += 1
                if p > 0:
                    fr.d.text((x, y + (1 - p) * dy), w_, font=f, fill=blend(GOLD if g else color, p))
                x += ww + sp
            y += int(f.size * lh)
        return y

    def head(fr, s, t, title_sizes=(84, 76, 68, 60), maxlines=3):
        fr.fade_text(X0, 340, s.get("kicker", "").upper(), font("s", 32), t, 0, GOLD)
        if s.get("title"):
            f = rm.fit(fr.d, s["title"], "x", list(title_sizes), XW, maxlines)
            return fr.text_anim(X0, 410, s["title"], f, XW, t, 0.1)
        return 410

    # ---- icon: satu ilustrasi besar + judul ----
    def sc_icon(fr, s, t, dur):
        cx, cy = W // 2, 560
        disc = blend(PANEL, 0.5)
        r0 = int(265 * eo(seg(t, 0, 0.55)))
        if r0 > 0:
            fr.d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], fill=disc)
        if t > 0.5:
            for j in range(2):
                ph = (t * 0.42 + j * 0.5) % 1.0
                rr = 265 + int(120 * ph)
                fr.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=blend(GOLD, 0.5 * (1 - ph)), width=4)
            for k in range(3):
                ang = t * 0.9 + k * 2.094
                ox, oy = cx + 330 * math.cos(ang), cy + 330 * math.sin(ang) * 0.92
                a = seg(t, 0.5 + k * 0.1, 0.9 + k * 0.1)
                fr.d.ellipse([ox - 11, oy - 11, ox + 11, oy + 11], fill=blend(GOLD, a))
        pi = eob(seg(t, 0.12, 0.75))
        sz = int(310 * max(0.05, 0.45 + 0.55 * pi))
        dy = 14 * math.sin(t * 2.3) * seg(t, 0.7, 1.2)
        paste(fr, icon(s.get("icon", "sparkle"), sz, GOLD, disc), cx - sz / 2, cy - sz / 2 + dy, seg(t, 0.12, 0.4))
        y = ctext(fr, W // 2, 910, s.get("kicker", "").upper(), font("s", 32), XW, t, 0.5, GOLD)
        f = cfit(fr.d, s["text"], "x", [84, 76, 68, 60], XW, 3)
        y = ctext(fr, W // 2, y + 14, s["text"], f, XW, t, 0.65)
        if s.get("note"):
            ctext(fr, W // 2, y + 16, s["note"], font("r", 36), XW, t, 1.3, MUTE, stagger=0.04)

    # ---- flow: 2-3 ikon dihubungkan panah ----
    def sc_flow(fr, s, t, dur):
        items = s.get("items", [])[:3]
        n = len(items)
        if n == 0:
            return
        head(fr, s, t)
        cs = {1: 380, 2: 320, 3: 230}[n]
        gap = (XW - n * cs) / (n - 1) if n > 1 else 0
        cy = 860
        pace = max(0.6, min(1.5, (dur - 1.2) / max(1, n)))
        ti = [0.6 + i * pace for i in range(n)]
        for i, it in enumerate(items):
            a = seg(t, ti[i], ti[i] + 0.5)
            if a <= 0:
                continue
            sc = max(0.05, 0.55 + 0.45 * eob(a))
            sz = int(cs * sc)
            xc = X0 + i * (cs + gap) + cs / 2
            last = n > 1 and i == n - 1
            base = PANEL if last else CARD
            fr.d.rounded_rectangle([xc - sz / 2, cy - sz / 2, xc + sz / 2, cy + sz / 2], radius=int(38 * sc),
                                   fill=blend(base, a * 1.6), outline=blend(GOLD, a * 1.6) if last else None, width=4)
            isz = int(cs * 0.52 * sc)
            paste(fr, icon(it.get("icon", "sparkle"), isz, GOLD, base), xc - isz / 2, cy - isz / 2, a * 1.6)
            ctext(fr, xc, cy + cs / 2 + 30, it.get("label", ""), font("s", 38), cs + 70, t, ti[i] + 0.25, INK, stagger=0.05)
        for i in range(n - 1):
            q = seg(t, ti[i + 1] - 0.4, ti[i + 1])
            asz = int(min(90, gap * 0.6))
            if q <= 0 or asz < 16:
                continue
            zx = X0 + i * (cs + gap) + cs
            dx = 8 * math.sin(t * 4 + i) * seg(t, ti[i + 1], ti[i + 1] + 0.5)
            paste(fr, icon("arrow", asz, GOLD, BG), zx + gap / 2 - asz / 2 + dx, cy - asz / 2, q)

    # ---- steps: langkah bernomor, muncul satu per satu sesuai durasi ----
    def sc_steps(fr, s, t, dur):
        y = head(fr, s, t, (80, 72, 64, 56), 2) + 40
        items = s.get("items", [])[:4]
        n = len(items)
        itf = font("s", 46)
        pace = max(0.6, (dur - 1.4) / max(1, n))
        for i, it in enumerate(items):
            ti = 0.9 + i * pace
            a = eo(seg(t, ti, ti + 0.45))
            lines, h = rm.layout(fr.d, it, itf, XW - 210, 1.2)
            bh = max(160, h + 64)
            if a > 0:
                active = t >= ti and (i == n - 1 or t < 0.9 + (i + 1) * pace)
                x = X0 + int((1 - a) * 60)
                fr.d.rounded_rectangle([x, y, x + XW, y + bh], radius=26, fill=blend(PANEL if active else CARD, a),
                                       outline=blend(GOLD, a) if active else None, width=4)
                bx, by = x + 70, y + bh / 2
                fr.d.ellipse([bx - 40, by - 40, bx + 40, by + 40], fill=blend(GOLD if active else (60, 58, 72), a))
                fr.d.text((bx, by + 2), str(i + 1), font=font("x", 46), fill=blend((20, 18, 28), a), anchor="mm")
                for (w_, g, wx, wy) in lines:
                    fr.d.text((x + 140 + wx, y + (bh - h) / 2 + wy), w_, font=itf, fill=blend(GOLD if g else INK, a))
            y += bh + 22

    # ---- vs: dua panel (ya / tidak) ----
    def sc_vs(fr, s, t, dur):
        y0 = max(head(fr, s, t, (76, 68, 60), 2) + 60, 540) if s.get("title") else 500
        ph = 300
        pace = max(0.8, (dur - 1.2) / 2)
        for i, (pn, ok) in enumerate(((s.get("yes", {}), True), (s.get("no", {}), False))):
            ti = 0.6 + i * pace
            a = eo(seg(t, ti, ti + 0.5))
            if a <= 0:
                continue
            yy = y0 + i * (ph + 36)
            x = X0 + int((1 - a) * (-80 if ok else 80))
            base = PANEL if ok else CARD
            fr.d.rounded_rectangle([x, yy, x + XW, yy + ph], radius=36, fill=blend(base, a),
                                   outline=blend(GOLD, a) if ok else None, width=4)
            isz = 140
            paste(fr, icon("check" if ok else "cross", isz, GOLD if ok else (120, 116, 134), base), x + 50, yy + ph / 2 - isz / 2, a)
            f = cfit(fr.d, pn.get("title", ""), "x", [58, 52, 46, 40], XW - 300, 3)
            lines, _ = cwrap(fr.d, pn.get("title", ""), f, XW - 300)
            hh = len(lines) * int(f.size * 1.15)
            ctext_left(fr, x + 240, yy + ph / 2 - hh / 2, pn.get("title", ""), f, XW - 300, t, ti + 0.2, INK if ok else MUTE)

    def ctext_left(fr, x0, y, text, f, maxw, t, t0, color=INK, stagger=0.06, dur=0.4, dy=24, lh=1.15):
        lines, sp = cwrap(fr.d, text or "", f, maxw)
        i = 0
        for ln, lw in lines:
            x = x0
            for w_, g, ww in ln:
                p = eo(seg(t, t0 + i * stagger, t0 + i * stagger + dur)); i += 1
                if p > 0:
                    fr.d.text((x, y + (1 - p) * dy), w_, font=f, fill=blend(GOLD if g else color, p))
                x += ww + sp
            y += int(f.size * lh)
        return y

    rm.SCENES.update({"icon": sc_icon, "flow": sc_flow, "steps": sc_steps, "vs": sc_vs})
