#!/usr/bin/env python3
"""
render_pilot.py — Render video pilot (cold open + Hồi I) khớp timeline.json.

Usage:
  python render_pilot.py --smoke          # render 8 giây đầu để test tốc độ/ảnh
  python render_pilot.py                  # render toàn bộ pilot (silent), mux audio nếu có
Tạo: output/pilot_silent.mp4 (+ output/GoldenHour_Pilot.mp4 nếu có output/audio_master.wav)
"""
import json, math, os, subprocess, sys, time
import numpy as np
import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_episode as R
from render_episode import (W, H, FPS, BG, CREAM, GOLD, GOLD_DIM, font,
                            compose_segment, compose_act_card, push, load_photo)

OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)

# ---- performance caches (monkey-patch R's per-frame costs) ----
_vig_mask = None
_noise = None
def _vig_mask_once():
    global _vig_mask
    if _vig_mask is None:
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        d.ellipse((-W * 0.25, -H * 0.35, W * 1.25, H * 1.35), fill=255)
        m = m.filter(ImageFilter.GaussianBlur(180)).point(lambda v: int(255 - (255 - v) * 0.32))
        _vig_mask = m
    return _vig_mask

def vignette_fast(img, strength=0.32):
    black = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(img, black, _vig_mask_once())

_noise_stack = None
def grain_fast(img):
    global _noise_stack
    if _noise_stack is None:
        rng = np.random.default_rng(11)
        _noise_stack = [rng.randint(-6, 7, (H // 2, W // 2, 1), dtype=np.int16) for _ in range(4)]
    n = _noise_stack[_grain_i % 4]
    arr = np.asarray(img.resize((W // 2, H // 2))).astype(np.int16) + n
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H))

_grain_i = 0

def grain_fast16(img, amount=6):
    global _noise_stack, _grain_i
    if _noise_stack is None:
        rng = np.random.default_rng(11)
        _noise_stack = [rng.integers(-6, 7, (H, W, 1), dtype=np.int16) for _ in range(4)]
    n = _noise_stack[_grain_i % 4]
    _grain_i += 1
    arr = np.asarray(img).astype(np.int16) + n
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def fast_compose_segment(star, index, t, photos):
    return compose_segment(star, index, t, photos)

# monkey-patch expensive per-frame helpers with cached/fast versions
R.vignette = vignette_fast
R.film_grain = grain_fast16

# ---- title / end visuals ----
def title_frame(t01, total=6.0):
    frame = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(frame)
    breathe = 0.9 + 0.1 * math.sin(t01 * math.pi * 2)
    f_big = font(R.SERIF_BOLD, 92)
    f_small = font(R.SANS_BOLD, 30)
    f_gold = font(R.SERIF, 34)
    t1 = "GOLDEN HOUR"
    bb = d.textbbox((0, 0), t1, font=f_big)
    alpha = min(1.0, t01 * 4)
    col = tuple(int(c * alpha + 13 * (1 - alpha)) for c in CREAM)
    d.text(((W - (bb[2] - bb[0])) / 2, H * 0.34), t1, font=f_big, fill=col)
    t2 = "HOLLYWOOD  THEN  &  NOW"
    bb = d.textbbox((0, 0), t2, font=f_small)
    col2 = tuple(int(c * alpha + 13 * (1 - alpha)) for c in GOLD)
    d.text(((W - (bb[2] - bb[0])) / 2, H * 0.52), t2, font=f_small, fill=col2)
    lw = int(W * 0.16 * min(1.0, t01 * 2))
    d.line((W // 2 - lw, H * 0.62, W // 2 + lw, H * 0.62), fill=GOLD_DIM, width=2)
    frame = vignette_fast(frame)
    return R.film_grain(frame, 5)

def end_frame(t01):
    frame = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(frame)
    f_big = font(R.SERIF_BOLD, 62)
    f_small = font(R.SERIF, 34)
    t1 = "HOW MANY DID YOU REMEMBER?"
    bb = d.textbbox((0, 0), t1, font=f_big)
    d.text(((W - (bb[2] - bb[0])) / 2, H * 0.36), t1, font=f_big, fill=CREAM)
    t2 = "Comment your number  ·  Golden hour never really ends"
    bb = d.textbbox((0, 0), t2, font=f_small)
    d.text(((W - (bb[2] - bb[0])) / 2, H * 0.52), t2, font=f_small, fill=GOLD)
    frame = vignette_fast(frame, )
    return R.film_grain(frame, 5)

def main():
    smoke = "--smoke" in sys.argv
    tl_file = "timeline_smoke.json" if smoke and not os.path.exists("timeline.json") else "timeline.json"
    tl = json.load(open(os.path.join(HERE, tl_file)))
    ep = json.load(open(os.path.join(HERE, "episode.json"), encoding="utf-8"))
    stars_by_no = {s["no"]: s for s in ep["stars"]}
    total = tl["total"]
    segs = tl["segments"]
    limit = 8.0 if smoke else None
    if limit:
        total = min(total, limit)
    n_frames = int(total * FPS)
    print(f"Rendering {n_frames} frames ({total:.1f}s) ...")
    photo_cache = {}
    writer = imageio.get_writer(os.path.join(OUT, "pilot_silent.mp4"),
                                fps=FPS, codec="libx264", quality=7,
                                macro_block_size=16, ffmpeg_params=["-pix_fmt", "yuv420p"])
    t_start = time.time()
    for fi in range(n_frames):
        ts = fi / FPS
        # find segment
        seg = None
        for s in segs:
            if s["start"] <= ts < s["start"] + s["dur"]:
                seg = s; break
        if seg is None:
            seg = segs[-1]
        lt = (ts - seg["start"]) / max(0.001, seg["dur"])
        if seg["kind"] == "speech" and seg["id"] == "cold_open":
            frame = title_frame(lt)
        elif seg["kind"] == "card":
            act_no = int(seg["id"].split("act")[1])
            act = next(a for a in ep["acts"] if a["no"] == act_no)
            frame = compose_act_card(act)
        elif seg["id"] == "star_%02d" % 0 or seg["kind"] == "star":
            no = int(seg["id"].split("_")[1])
            star = stars_by_no[no]
            if no not in photo_cache:
                photo_cache[no] = (load_photo(star["slug"], "then"), load_photo(star["slug"], "now"))
            frame = fast_compose_segment(star, no, lt, photo_cache[no])
        elif seg["kind"] == "speech":  # act intro → act card visual
            act_no = int(seg["id"].replace("act", "").replace("_intro", ""))
            act = next(a for a in ep["acts"] if a["no"] == act_no)
            frame = compose_act_card(act)
        else:
            frame = end_frame(lt)
        writer.append_data(np.asarray(frame))
        if fi % 300 == 0:
            rate = (fi + 1) / (time.time() - t_start)
            print(f"  frame {fi}/{n_frames}  ({rate:.1f} fps, eta {(n_frames-fi)/max(rate,0.01)/60:.1f} min)", flush=True)
    writer.close()
    print("Silent video:", os.path.join(OUT, "pilot_silent.mp4"))
    # mux audio if exists
    wav = os.path.join(OUT, "audio_master.wav")
    final = os.path.join(OUT, "GoldenHour_Pilot.mp4")
    if os.path.exists(wav) and not smoke:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ff, "-y", "-v", "error", "-i", os.path.join(OUT, "pilot_silent.mp4"),
               "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-shortest", final]
        subprocess.run(cmd, check=True)
        print("Final:", final)

if __name__ == "__main__":
    main()
