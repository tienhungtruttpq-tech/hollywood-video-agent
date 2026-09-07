#!/usr/bin/env python3
"""
make_srt.py — Sinh phụ đề SRT cho pilot/full từ timeline.json + episode.json.
Chia câu theo dấu chấm; thời gian phân bổ theo số từ.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))

def fmt(t):
    ms = int(round(t * 1000))
    return f"{ms//3600000:02d}:{(ms//60000)%60:02d}:{(ms//1000)%60:02d},{ms%1000:03d}"

def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]

def main():
    tl = json.load(open(os.path.join(HERE, "timeline.json")))
    ep = json.load(open(os.path.join(HERE, "episode.json"), encoding="utf-8"))
    segs = tl["segments"]
    cues = []
    for i, s in enumerate(segs):
        if s["kind"] not in ("speech", "star"):
            continue
        if s["id"] == "cold_open":
            text = ep["cold_open"]["text"]
        elif s["id"].startswith("act") and s["id"].endswith("_intro"):
            no = int(s["id"].replace("act", "").replace("_intro", ""))
            text = next(a for a in ep["acts"] if a["no"] == no)["intro"]
        elif s["id"].startswith("star_"):
            no = int(s["id"].split("_")[1])
            text = next(x for x in ep["stars"] if x["no"] == no)["narration"]
        else:
            continue
        # speech window = segment minus trailing pad (1.2s)
        speech_dur = max(2.0, s["dur"] - (1.2 if s["kind"] == "star" else 0.6))
        sents = sentences(text)
        words = [len(x.split()) for x in sents]
        tw = sum(words) or 1
        cur = s["start"]
        for sent, w in zip(sents, words):
            d = speech_dur * w / tw
            cues.append((cur, cur + d, sent))
            cur += d
    out = os.path.join(HERE, "output", "subtitles.srt")
    with open(out, "w", encoding="utf-8") as f:
        for i, (a, b, txt) in enumerate(cues, 1):
            f.write(f"{i}\n{fmt(a)} --> {fmt(b)}\n{txt}\n\n")
    print(f"{len(cues)} cues → {out}")

if __name__ == "__main__":
    main()
