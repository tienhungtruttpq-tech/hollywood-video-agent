#!/usr/bin/env python3
"""
build_audio.py — Dựng timeline + audio master + SRT cho pilot/full episode.

Đầu vào : assets/audio/<id>.mp3 (cold_open, act1, star_<no>, break_<n>, outro)
Đầu ra  : timeline.json, output/audio_master.wav, output/subtitles.srt

Underscore: pad 4 hợp âm (Am F C G) sinh bằng numpy, lowpass, duck −18 dB dưới lời.
"""
import json, os, subprocess, wave
import numpy as np
from PIL import Image  # noqa (keeps parity if run inside venv without numpy-only tooling)

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, "assets", "audio")
OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)
SR = 48000

def ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def decode(path):
    """MP3 -> float32 mono numpy at SR."""
    cmd = [ff(), "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

def save_wav(path, stereo):
    stereo = np.clip(stereo, -1, 1)
    pcm = (stereo * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())

def underscore(n_samples, seed=7):
    """Warm slow pad, Am–F–C–G, one chord per 8 s, simple additive synth + lowpass."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_samples) / SR
    chords = [110.0, 87.31, 65.41, 98.0]  # A2, F2, C2, G2 roots
    seg = 8.0
    sig = np.zeros(n_samples, dtype=np.float32)
    for i in range(int(np.ceil(n_samples / SR / seg))):
        a, b = int(i * seg * SR), min(n_samples, int((i + 1) * seg * SR))
        root = chords[i % 4]
        freqs = [root, root * 1.5, root * 2.0, root * 2.5]  # fifth, octave, tenth-ish
        for k, f in enumerate(freqs):
            vib = 1 + 0.0015 * np.sin(2 * np.pi * (0.13 + 0.01 * k) * t[a:b])
            amp = 0.05 / (k + 1)
            sig[a:b] += amp * np.sin(2 * np.pi * f * vib * t[a:b]).astype(np.float32)
    # slow attack per chord
    edge = int(0.8 * SR)
    for i in range(1, int(np.ceil(n_samples / SR / seg))):
        s0 = int(i * seg * SR)
        if s0 < n_samples:
            e = min(n_samples, s0 + edge)
            ramp = np.linspace(0, 1, e - s0, dtype=np.float32)
            sig[s0:e] *= ramp
    # one-pole lowpass
    alpha = 0.12
    out = np.empty_like(sig)
    acc = 0.0
    for i in range(len(sig)):  # small n → ok (30 min ≈ 86M — too slow!) → use FFT filter instead
        break
    # FFT lowpass (fast)
    S = np.fft.rfft(sig)
    freqs_fft = np.fft.rfftfreq(len(sig), 1 / SR)
    S *= 1 / (1 + (freqs_fft / 900) ** 4)
    sig = np.fft.irfft(S, len(sig)).astype(np.float32)
    sig *= 0.5
    return sig

def build(pilot=True):
    ep = json.load(open(os.path.join(HERE, "episode.json"), encoding="utf-8"))
    segs = []  # (id, kind, path_or_None, extra_seconds)
    segs.append(("cold_open", "speech", os.path.join(AUD, "cold_open.mp3"), 1.0))
    acts = ep["acts"][:1] if pilot else ep["acts"]
    for act in acts:
        segs.append((f"card_act{act['no']}", "card", None, 3.0))
        segs.append((f"act{act['no']}_intro", "speech", os.path.join(AUD, f"act{act['no']}_intro.mp3"), 0.6))
        act_stars = [s for s in ep["stars"] if s["act"] == act["no"]]
        if pilot:
            lo, hi = ep.get("pilot", {}).get("star_range", [1, 8])
            act_stars = [s for s in act_stars if lo <= s["no"] <= hi]
        for s in act_stars:
            segs.append((f"star_{s['no']:02d}", "star", os.path.join(AUD, f"star_{s['no']:02d}.mp3"), 1.2))
        if pilot:
            break
    segs.append(("end", "end", None, 8.0))
    # build audio track + timeline
    timeline = []
    speech_spans = []
    cursor = 0.0
    pieces = []
    for sid, kind, path, extra in segs:
        dur = extra
        speech = None
        if kind in ("speech", "star"):
            speech = decode(path)
            dur = len(speech) / SR + extra
            speech_spans.append((cursor, cursor + len(speech) / SR))
        timeline.append({"id": sid, "kind": kind, "start": round(cursor, 3),
                         "dur": round(dur, 3), "path": path})
        if speech is not None:
            pieces.append((cursor, speech))
        cursor += dur
    total = int(cursor * SR) + SR * 4
    mix = np.zeros(total, dtype=np.float32)
    for start, sp in pieces:
        i0 = int(start * SR)
        mix[i0:i0 + len(sp)] += sp
    mus = underscore(total)
    # ducking envelope
    env = np.ones(total, dtype=np.float32) * 0.16   # music level under silence
    for a, b in speech_spans:
        i0, i1 = int(a * SR), int(b * SR)
        env[i0:i1] = 0.055                            # duck under speech
    # smooth envelope (250 ms)
    k = int(0.25 * SR)
    kernel = np.hanning(k).astype(np.float32); kernel /= kernel.sum()
    env = np.convolve(env, kernel, mode="same").astype(np.float32)
    mix += mus * env
    # gentle fade in/out
    f = int(1.5 * SR)
    mix[:f] *= np.linspace(0, 1, f, dtype=np.float32)
    mix[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    wav_path = os.path.join(OUT, "audio_master.wav")
    save_wav(wav_path, np.stack([mix, mix], axis=1))
    json.dump({"total": cursor, "segments": timeline},
              open(os.path.join(HERE, "timeline.json"), "w"), indent=2)
    print(f"timeline: {cursor:.1f}s → {wav_path}")

if __name__ == "__main__":
    import sys
    build(pilot=("--full" not in sys.argv))
