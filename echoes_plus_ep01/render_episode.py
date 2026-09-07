#!/usr/bin/env python3
"""
Golden Hour — Hollywood Then & Now :: Episode renderer
======================================================
Implements the visual system from 02_FORMAT_BLUEPRINT.md:
  - THEN full-frame with slow Ken Burns push  (0–6 s)
  - vertical soft wipe revealing NOW          (6–7.2 s)
  - split THEN|NOW with divider               (rest of segment)
  - year badges on both photos, name + "NOW <age>" captions
  - Act cards, MEMORY COUNTER chip, film grain, vignette
  - golden-hour palette (#0d0b08 bg, cream text, gold accents)

Modes:
  python render_episode.py --frames           # sample keyframes from pilot data (fast preview)
  python render_episode.py --render           # full episode video (needs all photos + audio)
  python render_episode.py --card ACT_ONE     # render one act card png

Photos expected at assets/pilot_photos/<slug>_then.jpg / <slug>_now.jpg
Full-episode photos:  assets/photos/<slug>_then.jpg / <slug>_now.jpg
"""
import json, math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1280, 720
FPS = 30
SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# palette
BG = (13, 11, 8)
CREAM = (245, 234, 209)
GOLD = (217, 164, 65)
GOLD_DIM = (140, 105, 45)
DIVIDER = (240, 220, 170)

def font(path, size): return ImageFont.truetype(path, size)

def load_episode():
    with open(os.path.join(HERE, "episode.json"), encoding="utf-8") as f:
        return json.load(f)

def load_photo(slug, phase):
    """phase: 'then' | 'now'. Falls back to pilot folder."""
    for base in ("assets/photos", "assets/pilot_photos"):
        p = os.path.join(HERE, base, f"{slug}_{phase}.jpg")
        if os.path.exists(p):
            return Image.open(p).convert("RGB")
    raise FileNotFoundError(f"{slug}_{phase}.jpg not found")

# ---------- imaging helpers ----------

def cover_crop(im, w, h, focus=(0.5, 0.42), sharpen=True):
    """Crop im to cover w×h using focal point. Mild unsharp when upscaling hard."""
    ar_t = w / h
    ar_i = im.width / im.height
    if ar_i > ar_t:  # wider -> crop sides
        nw = int(im.height * ar_t)
        cx = int(focus[0] * im.width)
        x = max(0, min(im.width - nw, cx - nw // 2))
        box = (x, 0, x + nw, im.height)
    else:            # taller -> crop top/bottom
        nh = int(im.width / ar_t)
        cy = int(focus[1] * im.height)
        y = max(0, min(im.height - nh, cy - nh // 2))
        box = (0, y, im.width, y + nh)
    out = im.crop(box).resize((w, h), Image.LANCZOS)
    if sharpen and (w / max(1, box[2] - box[0]) > 1.6 or h / max(1, box[3] - box[1]) > 1.6):
        out = out.filter(ImageFilter.UnsharpMask(radius=2, percent=55, threshold=2))
    return out

def fit_font(draw, text, path, size, max_w):
    f = font(path, size)
    while size > 16:
        bb = draw.textbbox((0, 0), text, font=f)
        if bb[2] - bb[0] <= max_w:
            break
        size -= 2
        f = font(path, size)
    return f

def push(im, w, h, progress, z_from=1.00, z_to=1.07, pan=(0.5, 0.42), sharpen=True):
    """Slow Ken-Burns push rendered AT the target size (w×h).
    Never upscales beyond the crop box: works in the target's own pixel space,
    so half-frame pushes stay half-frame (no blurry blow-ups)."""
    z = z_from + (z_to - z_from) * float(progress)
    cw, ch = max(8, int(w / z)), max(8, int(h / z))
    if im.width < cw or im.height < ch:
        im = cover_crop(im, cw, ch, focus=pan, sharpen=sharpen)
        cw, ch = im.size
    cx, cy = int(pan[0] * im.width), int(pan[1] * im.height)
    x = max(0, min(im.width - cw, cx - cw // 2))
    y = max(0, min(im.height - ch, cy - ch // 2))
    return im.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS)

def vignette(img, strength=0.32):
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(180))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(img, black, mask.point(lambda v: int(255 - (255 - v) * strength)))

def film_grain(img, amount=6):
    noise = (np.random.randn(H, W, 1) * amount).astype(np.int16)
    arr = np.asarray(img).astype(np.int16) + noise
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def rounded_chip(draw, xy, text, fnt, pad=10, fill=(0, 0, 0), outline=None, alpha=None):
    x0, y0 = xy
    tb = draw.textbbox((0, 0), text, font=fnt)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    box = (x0, y0, x0 + tw + pad * 2, y0 + th + pad)
    draw.rounded_rectangle(box, radius=6, fill=fill, outline=outline, width=2)
    draw.text((x0 + pad, y0 + pad // 2 - tb[1]), text, font=fnt, fill=CREAM)
    return box

def soft_wipe_mask(x_pos, feather=42):
    """L mask: 255 = show NOW image right of x_pos with soft edge."""
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.rectangle((x_pos + feather, 0, W, H), fill=255)
    if feather and x_pos > -feather:
        grad = Image.linear_gradient("L").rotate(90, expand=True).resize((feather, H))
        mask.paste(grad, (max(0, x_pos), 0))
    return mask

# ---------- segment composition ----------

def compose_segment(star, index, t, photos=None):
    """t = progress through segment [0,1].
    0.00–0.18 THEN full + push-in
    0.18–0.26 wipe NOW reveal
    0.26–1.00 split screen with divider + captions + counter
    """
    if photos is None:
        photos = (load_photo(star["slug"], "then"), load_photo(star["slug"], "now"))
    then_im, now_im = photos

    wipe_start, wipe_end = 0.20, 0.27

    if t < wipe_start:
        frame = push(then_im, W, H, t / wipe_start, 1.0, 1.06)
    else:
        # pre-compose split THEN|NOW (each 640×720) and reveal it with a soft
        # scan line — NOW is never shown larger than half-frame (no upscale blur)
        th = cover_crop(then_im, 640, 720, focus=(0.5, 0.40))
        nw_ = cover_crop(now_im, 640, 720, focus=(0.5, 0.40))
        kb = min(1.0, (t - wipe_end) / 0.6 + 0.5) if t >= wipe_end else 0.5
        th = push(th, 640, 720, kb, 1.0, 1.025)
        nw_ = push(nw_, 640, 720, kb, 1.0, 1.025)
        split = Image.new("RGB", (W, H))
        split.paste(th, (0, 0)); split.paste(nw_, (640, 0))
        sd = ImageDraw.Draw(split)
        sd.rectangle((637, 0, 642, H), fill=DIVIDER)
        sd.ellipse((634, H // 2 - 5, 646, H // 2 + 5), fill=GOLD)

        if t < wipe_end:
            # reveal the split layout from the LEFT over the still-running
            # full-frame THEN (base stays at z=1.0 to match the split's zoom)
            x = max(0, int((W + 80) * (t - wipe_start) / (wipe_end - wipe_start)) - 40)
            mask = Image.new("L", (W, H), 0)
            dm = ImageDraw.Draw(mask)
            dm.rectangle((0, 0, x, H), fill=255)
            grad = Image.linear_gradient("L").rotate(90, expand=True).resize((42, H))
            mask.paste(grad, (max(0, x), 0))
            frame = Image.composite(split, push(then_im, W, H, 0.0, 1.0, 1.06), mask)
        else:
            frame = split

    frame = vignette(frame)
    d = ImageDraw.Draw(frame)

    # year badges + phase labels (labels sit above year chips — no collision
    # with the MEMORY COUNTER in the top corners)
    f_year = font(SANS_BOLD, 22)
    f_lab = font(SANS_BOLD, 20)
    if t < wipe_end:
        rounded_chip(d, (24, H - 54), str(star["photos"]["then_year"]), f_year, fill=(0, 0, 0))
    else:
        rounded_chip(d, (24, H - 54), str(star["photos"]["then_year"]), f_year, fill=(0, 0, 0))
        rounded_chip(d, (664, H - 54), str(star["photos"]["now_year"]), f_year, fill=(0, 0, 0))
        d.text((24, H - 100), "THEN", font=f_lab, fill=GOLD)
        d.text((664, H - 100), "NOW", font=f_lab, fill=GOLD)

    # name + age captions
    f_name = font(SERIF_BOLD, 52)
    f_meta = font(SERIF, 30)
    label = star["name"].upper()
    meta = f'b. {star["born"][:4]}  ·  NOW {star["age_2026"]}'
    if t >= wipe_end:
        # plate behind text
        bb = d.textbbox((0, 0), label, font=f_name)
        plate_h = 108
        d.rectangle((0, H - plate_h - 46, W, H), fill=(0, 0, 0))
        d.line((0, H - plate_h - 46, W, H - plate_h - 46), fill=GOLD_DIM, width=2)
        d.text((48, H - plate_h - 18), label, font=f_name, fill=CREAM)
        d.text((50, H - 52), meta, font=f_meta, fill=GOLD)
    else:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sh)
        ds.text((50, H - 120), label, font=f_name, fill=(0, 0, 0, 200))
        frame = Image.alpha_composite(frame.convert("RGBA"), sh).convert("RGB")
        d = ImageDraw.Draw(frame)
        d.text((48, H - 122), label, font=f_name, fill=CREAM)

    # memory counter chip (top-right)
    f_cnt = font(SANS_BOLD, 22)
    chip = f"MEMORY COUNTER  {index:02d}/50"
    bb = d.textbbox((0, 0), chip, font=f_cnt)
    cw_ = bb[2] - bb[0]
    fade = 1.0 if t < 0.75 else max(0.0, 1 - (t - 0.75) / 0.2)
    if fade > 0:
        col = tuple(int(c * fade + 20 * (1 - fade)) for c in GOLD)
        d.text((W - cw_ - 28, 22), chip, font=f_cnt, fill=col)

    frame = film_grain(frame)
    return frame

# ---------- act card ----------

def compose_act_card(act, sub=None):
    frame = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(frame)
    # golden light band
    for i in range(H):
        k = 1 - abs(i - H * 0.62) / (H * 0.55)
        if k > 0:
            c = tuple(int(BG[j] + (40 * k * k)) for j in range(3))
            d.line((0, i, W, i), fill=c)
    f_small = font(SANS_BOLD, 26)
    sub = sub or act["card_subtitle"]
    title = act["card_title"]
    f_big = fit_font(d, sub, SERIF_BOLD, 58, W - 200)
    f_sub = font(SERIF, 34)
    bb = d.textbbox((0, 0), title, font=f_small)
    d.text(((W - (bb[2] - bb[0])) / 2, H * 0.36), title, font=f_small, fill=GOLD)
    bb = d.textbbox((0, 0), sub, font=f_big)
    d.text(((W - (bb[2] - bb[0])) / 2, H * 0.44), sub, font=f_big, fill=CREAM)
    d.line((W * 0.38, H * 0.60, W * 0.62, H * 0.60), fill=GOLD, width=2)
    frame = vignette(frame, 0.45)
    return film_grain(frame, 5)

# ---------- modes ----------

def mode_frames():
    ep = load_episode()
    stars = ep["stars"]
    out = os.path.join(HERE, "assets", "preview")
    os.makedirs(out, exist_ok=True)
    # pick pilot samples: Van Dyke mid-wipe, Novak full split, Fonda split, act card
    samples = []
    act1 = ep["acts"][0]
    compose_act_card(act1).save(os.path.join(out, "frame_act_card.jpg"), quality=90)
    print("frame_act_card.jpg")
    for slug, t, name in [("dick_van_dyke", 0.22, "dvd_wipe"), ("kim_novak", 0.55, "novak_split"),
                          ("jane_fonda", 0.85, "fonda_split")]:
        star = next(s for s in stars if s["slug"] == slug)
        idx = star["no"]
        compose_segment(star, idx, t).save(os.path.join(out, f"frame_{name}.jpg"), quality=90)
        print(f"frame_{name}.jpg")
    print("Preview frames in", out)

def mode_card(key):
    ep = load_episode()
    act = next(a for a in ep["acts"] if a["card_title"].lower().startswith(key.lower()) or key.lower() in a["card_title"].lower())
    compose_act_card(act).save(os.path.join(HERE, "assets", "preview", f"card_{act['no']}.jpg"), quality=90)

def mode_render():
    raise SystemExit(
        "Full render requires: all 50 stars' photos in assets/photos + narration audio mix.\n"
        "Pipeline: fetch_photos_wikimedia.py → build_audio.py → render_episode.py --render\n"
        "(see 05_PRODUCTION_GUIDE.md — audio/TTS budget limits full render to user machine or later turns)")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--frames"
    if mode == "--frames":
        mode_frames()
    elif mode == "--card" and len(sys.argv) > 2:
        mode_card(sys.argv[2])
    elif mode == "--render":
        mode_render()
    else:
        print(__doc__)
