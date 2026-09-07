#!/usr/bin/env python3
"""
render_episode.py v2 — Visual system "Golden Hour" (tối ưu render).

Mỗi sao:
  0 → 1.5s   THEN full-frame push-in (live)
  1.5 → 2.35 vạch quét hé split THEN|NOW (live)
  2.35s → hết  split tĩnh đã pre-render (badge năm, THEN/NOW, name plate,
          MEMORY COUNTER nn/35) + grain xoay 4 khung → rất nhanh.
Act card / Memory Break card / title / end card: pre-render 1 lần.
"""
import json, math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1280, 720
BG = (13, 11, 8)
CREAM = (245, 234, 209)
GOLD = (217, 164, 65)
GOLD_DIM = (140, 105, 45)
DIVIDER = (240, 220, 170)
SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

from PIL import ImageFont
def F(path, size): return ImageFont.truetype(path, size)

def load_episode():
    return json.load(open(os.path.join(HERE, "episode.json"), encoding="utf-8"))

def load_photo(slug, phase):
    for base in ("assets/photos", "assets/pilot_photos"):
        p = os.path.join(HERE, base, f"{slug}_{phase}.jpg")
        if os.path.exists(p):
            return Image.open(p).convert("RGB")
    raise FileNotFoundError(f"{slug}_{phase}.jpg")

def cover_crop(im, w, h, focus=(0.5, 0.42), sharpen=True):
    ar_t, ar_i = w / h, im.width / im.height
    if ar_i > ar_t:
        nw = int(im.height * ar_t)
        cx = int(focus[0] * im.width)
        x = max(0, min(im.width - nw, cx - nw // 2))
        box = (x, 0, x + nw, im.height)
    else:
        nh = int(im.width / ar_t)
        cy = int(focus[1] * im.height)
        y = max(0, min(im.height - nh, cy - nh // 2))
        box = (0, y, im.width, y + nh)
    out = im.crop(box).resize((w, h), Image.LANCZOS)
    if sharpen and (w / max(1, box[2] - box[0]) > 1.6 or h / max(1, box[3] - box[1]) > 1.6):
        out = out.filter(ImageFilter.UnsharpMask(2, 55, 2))
    return out

def push(im, w, h, progress, z_from=1.0, z_to=1.07, pan=(0.5, 0.42)):
    z = z_from + (z_to - z_from) * float(progress)
    cw, ch = max(8, int(w / z)), max(8, int(h / z))
    if im.width < cw or im.height < ch:
        return cover_crop(im, w, h, focus=pan).resize((w, h), Image.LANCZOS)
    cx, cy = int(pan[0] * im.width), int(pan[1] * im.height)
    x = max(0, min(im.width - cw, cx - cw // 2))
    y = max(0, min(im.height - ch, cy - ch // 2))
    return im.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS)

_vig = None
def vig_mask():
    global _vig
    if _vig is None:
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        d.ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
        m = m.filter(ImageFilter.GaussianBlur(180))
        _vig = m.point(lambda v: int(255 - (255 - v) * 0.32))
    return _vig

def vignette(img, strength=0.32):
    if strength != 0.32:
        m = vig_mask().point(lambda v: int(255 - (255 - v) * strength / 0.32))
    else:
        m = vig_mask()
    return Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), m)

_rng = np.random.default_rng(11)
NOISE = [_rng.integers(-6, 7, (H, W, 1), dtype=np.int16) for _ in range(4)]
_grain_i = 0
def grain_arr(arr):
    global _grain_i
    out = arr.astype(np.int16) + NOISE[_grain_i % 4]
    _grain_i += 1
    return np.clip(out, 0, 255).astype(np.uint8)

def chip(d, xy, text, fnt, pad=10, outline=None):
    x0, y0 = xy
    tb = d.textbbox((0, 0), text, font=fnt)
    box = (x0, y0, x0 + tb[2] - tb[0] + pad * 2, y0 + tb[3] - tb[1] + pad)
    d.rounded_rectangle(box, radius=6, fill=(0, 0, 0), outline=outline, width=2)
    d.text((x0 + pad, y0 + pad // 2 - tb[1]), text, font=fnt, fill=CREAM)

def fit_font(d, text, path, size, max_w):
    f = F(path, size)
    while size > 16:
        bb = d.textbbox((0, 0), text, font=f)
        if bb[2] - bb[0] <= max_w: break
        size -= 2; f = F(path, size)
    return f

# ---------- act / break / title / end cards ----------

def _card_base():
    fr = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(fr)
    for i in range(H):
        k = 1 - abs(i - H * 0.62) / (H * 0.55)
        if k > 0:
            d.line((0, i, W, i), fill=tuple(int(BG[j] + 40 * k * k) for j in range(3)))
    return vignette(fr, 0.45)

def compose_act_card(act):
    fr = _card_base(); d = ImageDraw.Draw(fr)
    sub = act["card_subtitle"]
    f_small, f_big = F(SANS_BOLD, 26), fit_font(d, sub, SERIF_BOLD, 58, W - 200)
    bb = d.textbbox((0, 0), act["card_title"], font=f_small)
    d.text(((W - bb[2] + bb[0]) / 2, H * 0.36), act["card_title"], font=f_small, fill=GOLD)
    bb = d.textbbox((0, 0), sub, font=f_big)
    d.text(((W - bb[2] + bb[0]) / 2, H * 0.44), sub, font=f_big, fill=CREAM)
    d.line((W * 0.38, H * 0.60, W * 0.62, H * 0.60), fill=GOLD, width=2)
    return np.asarray(grain_arr(np.asarray(fr)))

def compose_break_card(count, total):
    fr = _card_base(); d = ImageDraw.Draw(fr)
    f_l, f_n, f_s = F(SANS_BOLD, 30), F(SERIF_BOLD, 150), F(SERIF, 38)
    t = "MEMORY BREAK"
    bb = d.textbbox((0, 0), t, font=f_l)
    d.text(((W - bb[2] + bb[0]) / 2, H * 0.16), t, font=f_l, fill=GOLD)
    n = f"{count}"
    bb = d.textbbox((0, 0), n, font=f_n)
    d.text(((W - bb[2] + bb[0]) / 2, H * 0.26), n, font=f_n, fill=CREAM)
    t2 = f"of {total} — how many do you remember?"
    bb = d.textbbox((0, 0), t2, font=f_s)
    d.text(((W - bb[2] + bb[0]) / 2, H * 0.62), t2, font=f_s, fill=GOLD)
    d.line((W * 0.40, H * 0.74, W * 0.60, H * 0.74), fill=GOLD_DIM, width=2)
    return np.asarray(grain_arr(np.asarray(fr)))

def title_frame(t01, dur=6.0):
    fr = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(fr)
    a = min(1.0, t01 * 3)
    f_big, f_small = F(SERIF_BOLD, 92), F(SANS_BOLD, 30)
    t1 = "GOLDEN HOUR"
    bb = d.textbbox((0, 0), t1, font=f_big)
    col = tuple(int(c * a + 13 * (1 - a)) for c in CREAM)
    d.text(((W - bb[2] + bb[0]) / 2, H * 0.33), t1, font=f_big, fill=col)
    t2 = "HOLLYWOOD  THEN  &  NOW"
    bb = d.textbbox((0, 0), t2, font=f_small)
    col2 = tuple(int(c * a + 13 * (1 - a)) for c in GOLD)
    d.text(((W - bb[2] + bb[0]) / 2, H * 0.52), t2, font=f_small, fill=col2)
    if t01 > 0.5:  # promise line appears mid-cold-open
        b2 = min(1.0, (t01 - 0.5) * 3)
        f3 = F(SERIF, 34)
        t3 = "35 LEGENDS — STILL WITH US IN 2026"
        bb = d.textbbox((0, 0), t3, font=f3)
        col3 = tuple(int(c * b2 + 13 * (1 - b2)) for c in GOLD_DIM)
        d.text(((W - bb[2] + bb[0]) / 2, H * 0.64), t3, font=f3, fill=col3)
    lw = int(W * 0.16 * min(1.0, t01 * 2))
    d.line((W // 2 - lw, H * 0.60, W // 2 + lw, H * 0.60), fill=GOLD_DIM, width=2)
    fr = vignette(fr)
    return np.asarray(grain_arr(np.asarray(fr)))

def end_frame():
    fr = _card_base(); d = ImageDraw.Draw(fr)
    f_big, f_small = F(SERIF_BOLD, 60), F(SERIF, 34)
    t1 = "HOW MANY DID YOU REMEMBER?"
    bb = d.textbbox((0, 0), t1, font=f_big)
    d.text(((W - bb[2] + bb[0]) / 2, H * 0.36), t1, font=f_big, fill=CREAM)
    t2 = "Comment your number  ·  Part two coming — subscribe"
    bb = d.textbbox((0, 0), t2, font=f_small)
    d.text(((W - bb[2] + bb[0]) / 2, H * 0.52), t2, font=f_small, fill=GOLD)
    return np.asarray(grain_arr(np.asarray(fr)))

# ---------- star frames ----------

class StarCache:
    def __init__(self, star, total):
        then_im = load_photo(star["slug"], "then")
        now_im = load_photo(star["slug"], "now")
        self.then = then_im
        self.then_end = push(then_im, W, H, 1.0, 1.0, 1.06)
        th = cover_crop(then_im, 640, 720, focus=(0.5, 0.40))
        nw = cover_crop(now_im, 640, 720, focus=(0.5, 0.40))
        th = push(th, 640, 720, 1.0, 1.0, 1.025)
        nw = push(nw, 640, 720, 1.0, 1.0, 1.025)
        split = Image.new("RGB", (W, H))
        split.paste(th, (0, 0)); split.paste(nw, (640, 0))
        d = ImageDraw.Draw(split)
        d.rectangle((637, 0, 642, H), fill=DIVIDER)
        d.ellipse((634, H // 2 - 5, 646, H // 2 + 5), fill=GOLD)
        split = vignette(split)
        self.split_reveal = split  # no overlays — used during wipe
        # baked overlays
        st = split.copy(); d = ImageDraw.Draw(st)
        f_year, f_lab = F(SANS_BOLD, 22), F(SANS_BOLD, 20)
        chip(d, (24, H - 54), str(star["photos"]["then_year"]), f_year)
        chip(d, (664, H - 54), str(star["photos"]["now_year"]), f_year)
        d.text((24, H - 100), "THEN", font=f_lab, fill=GOLD)
        d.text((664, H - 100), "NOW", font=f_lab, fill=GOLD)
        plate_h = 108
        d.rectangle((0, H - plate_h - 46, W, H), fill=(0, 0, 0))
        d.line((0, H - plate_h - 46, W, H - plate_h - 46), fill=GOLD_DIM, width=2)
        f_name, f_meta = F(SERIF_BOLD, 52), F(SERIF, 30)
        d.text((48, H - plate_h - 18), star["name"].upper(), font=f_name, fill=CREAM)
        d.text((50, H - 52), f'b. {star["born"][:4]}  ·  NOW {star["age_2026"]}', font=f_meta, fill=GOLD)
        self._counter_text = "MEMORY COUNTER  {:02d}/{}".format(star["no"], total)
        self._cnt_pos, self._cnt_font = (W - 340, 22), F(SANS_BOLD, 22)
        dd = ImageDraw.Draw(st)
        bb = dd.textbbox((0, 0), self._counter_text, font=self._cnt_font)
        self._cnt_pos = (W - (bb[2] - bb[0]) - 28, 22)
        dd.text(self._cnt_pos, self._counter_text, font=self._cnt_font, fill=GOLD)
        self.split_static = np.asarray(st)
        st2 = split.copy(); d2 = ImageDraw.Draw(st2)
        chip(d2, (24, H - 54), str(star["photos"]["then_year"]), f_year)
        chip(d2, (664, H - 54), str(star["photos"]["now_year"]), f_year)
        d2.text((24, H - 100), "THEN", font=f_lab, fill=GOLD)
        d2.text((664, H - 100), "NOW", font=f_lab, fill=GOLD)
        d2.rectangle((0, H - plate_h - 46, W, H), fill=(0, 0, 0))
        d2.line((0, H - plate_h - 46, W, H - plate_h - 46), fill=GOLD_DIM, width=2)
        d2.text((48, H - plate_h - 18), star["name"].upper(), font=f_name, fill=CREAM)
        d2.text((50, H - 52), f'b. {star["born"][:4]}  ·  NOW {star["age_2026"]}', font=f_meta, fill=GOLD)
        self.split_nocnt = np.asarray(st2)

    def fade_arr(self, fade):
        if fade >= 1.0:
            return self.split_static
        a = self.split_static.astype(np.float32) * fade + self.split_nocnt.astype(np.float32) * (1 - fade)
        return a.astype(np.uint8)

def star_frame(tl, seg, star, cache, total):
    w0, w1 = seg["wipe0"], seg["wipe1"]
    if tl < w0:
        f = push(cache.then, W, H, tl / max(0.1, w0), 1.0, 1.06)
        f = vignette(f); d = ImageDraw.Draw(f)
        chip(d, (24, H - 54), str(star["photos"]["then_year"]), F(SANS_BOLD, 22))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
        ds.text((50, H - 120), star["name"].upper(), font=F(SERIF_BOLD, 52), fill=(0, 0, 0, 200))
        f = Image.alpha_composite(f.convert("RGBA"), sh).convert("RGB")
        d = ImageDraw.Draw(f)
        d.text((48, H - 122), star["name"].upper(), font=F(SERIF_BOLD, 52), fill=CREAM)
        d.text((W - 340, 22), f"MEMORY COUNTER  {star['no']:02d}/{total}", font=F(SANS_BOLD, 22), fill=GOLD)
        return np.asarray(grain_arr(np.asarray(f)))
    if tl < w1:
        x = int((W + 60) * (tl - w0) / (w1 - w0))
        mask = Image.new("L", (W, H), 0)
        dm = ImageDraw.Draw(mask)
        dm.rectangle((0, 0, min(x, W), H), fill=255)
        grad = Image.linear_gradient("L").rotate(90, expand=True).resize((40, H))
        if x < W:
            mask.paste(grad, (max(0, x - 40), 0))
        base = Image.composite(cache.split_reveal, cache.then_end, mask)
        base = vignette(base)
        d = ImageDraw.Draw(base)
        f_year, f_lab = F(SANS_BOLD, 22), F(SANS_BOLD, 20)
        chip(d, (24, H - 54), str(star["photos"]["then_year"]), f_year)
        if x > 700:
            chip(d, (664, H - 54), str(star["photos"]["now_year"]), f_year)
            d.text((664, H - 100), "NOW", font=f_lab, fill=GOLD)
        d.text((24, H - 100), "THEN", font=f_lab, fill=GOLD)
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
        ds.text((50, H - 120), star["name"].upper(), font=F(SERIF_BOLD, 52), fill=(0, 0, 0, 200))
        base = Image.alpha_composite(base.convert("RGBA"), sh).convert("RGB")
        d = ImageDraw.Draw(base)
        d.text((48, H - 122), star["name"].upper(), font=F(SERIF_BOLD, 52), fill=CREAM)
        d.text((W - 340, 22), f"MEMORY COUNTER  {star['no']:02d}/{total}", font=F(SANS_BOLD, 22), fill=GOLD)
        return np.asarray(grain_arr(np.asarray(base)))
    # static split phase
    fade = 1.0
    remain = seg["dur"] - tl
    if remain < 4.0:
        fade = max(0.0, remain / 4.0)
    return grain_arr(cache.fade_arr(fade))
