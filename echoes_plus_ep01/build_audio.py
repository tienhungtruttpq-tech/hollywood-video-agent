#!/usr/bin/env python3
"""
build_audio.py v2 — Timeline + audio master cho EP1 (35 sao).

Bundle TTS: 1 file mp3 chứa nhiều phần (act intro + 2-4 star + break/outro).
Tách bundle theo tỉ lệ ký tự, snap vào điểm im ảng (RMS thấp nhất) trong ±2.5s.
Segment sao: preroll 2.6s (visual trước, wipe 1.5→2.35s) + speech + tail 1.4s.
Underscore: pad Am-F-C-G, lowpass FFT, duck khi có lời.
Xuất: timeline.json, .cache/audio_master.wav (intermediate ngoài repo).
"""
import json, os, subprocess, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, "assets", "audio")
CACHE = os.path.join("/home/user/.cache", "goldenhour")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
SR = 48000
PREROLL, TAIL = 2.6, 1.4
WIPE0, WIPE1 = 1.5, 2.35

def ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def decode(path):
    cmd = [ff(), "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

def save_wav(path, stereo):
    stereo = np.clip(stereo, -1, 1)
    pcm = (stereo * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())

def snap_bounds(speech, parts, n_parts):
    """Char-proportional boundaries snapped to lowest-RMS point ±2.5s."""
    total_chars = sum(p["chars"] for p in parts)
    cum = np.cumsum([p["chars"] for p in parts])[:-1] / total_chars * len(speech)
    hop = SR // 8
    bounds = []
    for est in cum:
        w = int(2.5 * SR)
        lo, hi = int(max(0, est - w)), int(min(len(speech) - hop, est + w))
        best, bestv = est, 1e9
        for s0 in range(lo, hi, hop):
            v = float(np.sqrt(np.mean(speech[s0:s0 + hop] ** 2)) + 1e-9)
            if v < bestv:
                bestv, best = v, s0 + hop / 2
        bounds.append(int(best))
    return bounds

def underscore(n_samples):
    t = np.arange(n_samples) / SR
    chords = [110.0, 87.31, 65.41, 98.0]  # A2 F2 C2 G2
    seg = 8.0
    sig = np.zeros(n_samples, dtype=np.float32)
    for i in range(int(np.ceil(n_samples / SR / seg))):
        a, b = int(i * seg * SR), min(n_samples, int((i + 1) * seg * SR))
        root = chords[i % 4]
        for k, f in enumerate([root, root * 1.5, root * 2.0, root * 2.5]):
            vib = 1 + 0.0015 * np.sin(2 * np.pi * (0.13 + 0.01 * k) * t[a:b])
            sig[a:b] += (0.05 / (k + 1)) * np.sin(2 * np.pi * f * vib * t[a:b]).astype(np.float32)
    edge = int(0.8 * SR)
    for i in range(1, int(np.ceil(n_samples / SR / seg))):
        s0 = int(i * seg * SR)
        if s0 < n_samples:
            e = min(n_samples, s0 + edge)
            sig[s0:e] *= np.linspace(0, 1, e - s0, dtype=np.float32)
    S = np.fft.rfft(sig)
    fr = np.fft.rfftfreq(len(sig), 1 / SR)
    S *= 1 / (1 + (fr / 900) ** 4)
    return (np.fft.irfft(S, len(sig)).astype(np.float32) * 0.5)

def main():
    ep = json.load(open(os.path.join(HERE, "episode.json"), encoding="utf-8"))
    stars = {s["no"]: s for s in ep["stars"]}
    breaks = ep["memory_breaks"]
    segs, pieces = [], []
    cursor = 0.0

    def add_speech(id_, kind, audio, pre, post, extra=None):
        nonlocal cursor
        start = cursor + pre
        seg = {"id": id_, "kind": kind, "start": round(cursor, 3),
               "speech_start": round(start, 3), "speech_end": round(start + len(audio) / SR, 3),
               "dur": round(pre + len(audio) / SR + post, 3)}
        if extra: seg.update(extra)
        segs.append(seg); pieces.append((start, audio))
        cursor += seg["dur"]

    def add_file(fname, spec):
        audio = decode(os.path.join(AUD, fname))
        parts = spec["parts"]
        if len(parts) == 1:
            p = parts[0]
            kind = p["kind"]
            if kind == "star":
                add_speech(p["id"], "star", audio, PREROLL, TAIL,
                           {"no": int(p["id"].split("_")[1]), "wipe0": WIPE0, "wipe1": WIPE1})
            elif kind == "break":
                add_speech(p["id"], "break", audio, 1.0, 5.0, {"no": p.get("no", 0)})
            elif p["id"] == "outro":
                add_speech("outro", "outro", audio, 1.0, 0.8)
            else:
                add_speech(p["id"], "intro", audio, 0.4, 0.8)
            return
        speech = audio
        total_chars = sum(p["chars"] for p in parts)
        bounds = snap_bounds(speech, parts, len(parts))
        edges = [0] + bounds + [len(speech)]
        for i, p in enumerate(parts):
            a = speech[edges[i]:edges[i + 1]]
            kind = p["kind"]
            if kind == "star":
                add_speech(p["id"], "star", a, PREROLL, TAIL,
                           {"no": int(p["id"].split("_")[1]), "wipe0": WIPE0, "wipe1": WIPE1})
            elif kind == "break":
                add_speech(p["id"], "break", a, 1.0, 5.0, {"no": p.get("no", 0)})
            elif p["id"] == "outro":
                add_speech("outro", "outro", a, 1.0, 0.8)
            else:
                add_speech(p["id"], "intro", a, 0.4, 0.8)

    # 1) cold open
    add_file("cold_open.mp3", {"parts": [{"id": "cold_open", "kind": "speech", "chars": 1}]})

    # 2) acts
    for act in ep["acts"]:
        an = act["no"]
        segs.append({"id": f"card_act{an}", "kind": "card", "start": round(cursor, 3),
                     "speech_start": None, "speech_end": None, "dur": 3.5})
        cursor += 3.5
        if an == 1:
            add_file("act1_intro.mp3", {"parts": [{"id": "act1_intro", "kind": "speech", "chars": 1}]})
            for no in range(1, 9):
                add_file(f"star_{no:02d}.mp3", {"parts": [{"id": f"star_{no:02d}", "kind": "star", "chars": 1}]})
        else:
            for fname, spec in ep["audio_bundles"].items():
                if isinstance(spec, dict) and spec.get("act") == an:
                    add_file(fname, spec)

    # 3) end card
    segs.append({"id": "end", "kind": "end", "start": round(cursor, 3), "speech_start": None,
                 "speech_end": None, "dur": 9.0})
    cursor += 9.0

    # ---- mix ----
    total_n = int((cursor + 1) * SR)
    mix = np.zeros(total_n, dtype=np.float32)
    spans = []
    for start, a in pieces:
        i0 = int(start * SR); i1 = min(total_n, i0 + len(a))
        mix[i0:i1] += a[:i1 - i0]
        spans.append((i0, i1))
    mus = underscore(total_n)
    env = np.full(total_n, 0.15, dtype=np.float32)
    for i0, i1 in spans:
        env[i0:i1] = 0.05
    k = int(0.3 * SR)
    ker = np.hanning(k).astype(np.float32); ker /= ker.sum()
    env = np.convolve(env, ker, mode="same").astype(np.float32)
    mix += mus * env
    f_ = int(1.5 * SR)
    mix[:f_] *= np.linspace(0, 1, f_, dtype=np.float32)
    mix[-f_:] *= np.linspace(1, 0, f_, dtype=np.float32)
    wav = os.path.join(CACHE, "audio_master.wav")
    save_wav(wav, np.stack([mix, mix], axis=1))
    json.dump({"total": round(cursor, 2), "counter_total": 35, "segments": segs},
              open(os.path.join(HERE, "timeline.json"), "w"), indent=1)
    sd = [s for s in segs if s["kind"] == "star"]
    print(f"total {cursor:.0f}s = {cursor/60:.1f} min | {len(sd)} star segs (avg {sum(x['dur'] for x in sd)/len(sd):.1f}s)")
    bad = [s["id"] for s in sd if (s["speech_end"] - s["speech_start"]) < 8]
    print("suspicious short speech:", bad if bad else "none")

if __name__ == "__main__":
    main()
