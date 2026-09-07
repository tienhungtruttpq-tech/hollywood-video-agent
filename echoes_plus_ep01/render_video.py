#!/usr/bin/env python3
"""
render_video.py — Render full EP1 (35 sao) từ timeline.json + episode.json.

Usage:
  python render_video.py --smoke     # render 30s quanh star_12 để QA
  python render_video.py             # render toàn bộ + mux audio (loudnorm)
Xuất: output/pilot_silent.mp4 (cache) → output/GoldenHour_EP1_35Stars.mp4
"""
import json, os, subprocess, sys, time
import numpy as np
import imageio.v2 as imageio

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_episode as R
from render_episode import (W, H, title_frame, end_frame, compose_act_card,
                            compose_break_card, StarCache, star_frame)
FPS = 30
CACHE = "/home/user/.cache/goldenhour"
os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.join(HERE, "output"), exist_ok=True)

def main():
    smoke = "--smoke" in sys.argv
    ep = R.load_episode()
    tl = json.load(open(os.path.join(HERE, "timeline.json")))
    total = tl["total"]; segs = tl["segments"]; ct = tl.get("counter_total", 35)
    stars = {s["no"]: s for s in ep["stars"]}
    acts = {a["no"]: a for a in ep["acts"]}
    breaks = {s["no"]: s for s in segs if s["kind"] == "break"}

    t_lo, t_hi = 0.0, total
    if smoke:
        anchor = next(s for s in segs if s["id"] == "star_12")
        t_lo, t_hi = max(0, anchor["start"] - 2), anchor["start"] + 28
    n0, n1 = int(t_lo * FPS), int(t_hi * FPS)
    print(f"Render frames {n0}..{n1} ({(n1-n0)/FPS:.1f}s of {total:.1f}s)")

    caches, cards, breakcards = {}, {}, {}
    def get_cache(no):
        if no not in caches:
            caches[no] = StarCache(stars[no], ct)
        return caches[no]
    def get_card(an):
        if an not in cards: cards[an] = compose_act_card(acts[an])
        return cards[an]
    def get_break(no):
        if no not in breakcards: breakcards[no] = compose_break_card(no, ct)
        return breakcards[no]

    endcard = end_frame()
    writer = imageio.get_writer(os.path.join(CACHE, "video_silent.mp4"), fps=FPS,
                                codec="libx264", quality=8, macro_block_size=16,
                                ffmpeg_params=["-pix_fmt", "yuv420p"])
    t_start = time.time()
    for fi in range(n0, n1):
        ts = fi / FPS
        seg = next((s for s in segs if s["start"] <= ts < s["start"] + s["dur"]), segs[-1])
        lt = ts - seg["start"]
        k = seg["kind"]
        if k == "title":
            frame = title_frame(lt / seg["dur"], seg["dur"])
        elif k == "card":
            frame = get_card(int(seg["id"].split("act")[1]))
        elif k == "intro":
            if seg["id"] == "cold_open":
                frame = title_frame(lt / seg["dur"], seg["dur"])
            else:
                an = int(seg["id"].replace("act", "").replace("_intro", ""))
                frame = get_card(an)
        elif k == "star":
            frame = star_frame(lt, seg, stars[seg["no"]], get_cache(seg["no"]), ct)
        elif k == "break":
            frame = get_break(seg["no"])
        elif k == "outro":
            frame = endcard  # end visuals over closing narration
        else:
            frame = endcard
        writer.append_data(np.ascontiguousarray(frame))
        if (fi - n0) % 1500 == 0:
            rate = (fi - n0 + 1) / (time.time() - t_start)
            print(f"  {fi-n0}/{n1-n0} ({rate:.1f} fps, eta {(n1-fi)/max(rate,0.01)/60:.1f} min)", flush=True)
    writer.close()
    silent = os.path.join(CACHE, "video_silent.mp4")
    print("Silent:", silent)
    if smoke:
        return
    wav = os.path.join(CACHE, "audio_master.wav")
    final = os.path.join(HERE, "output", "GoldenHour_EP1_35Stars.mp4")
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-v", "error", "-i", silent, "-i", wav,
                    "-c:v", "libx264", "-crf", "24", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-shortest",
                    "-movflags", "+faststart", final], check=True)
    print("FINAL:", final, f"{os.path.getsize(final)/1e6:.1f} MB")

if __name__ == "__main__":
    main()
