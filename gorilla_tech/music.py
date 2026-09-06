"""
Stage 6 — score & mix.

No stock music is used: the bed is synthesised here (dark drone, slow minor pad,
soft pulse, tension risers and impact hits), so the pipeline has zero licensing
exposure and works offline. Mixing and ducking are done by ffmpeg
(sidechaincompress + loudnorm) to broadcast-ish levels.
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

import util

SR = 48000
CHUNK = 20.0          # seconds rendered at a time (keeps RAM flat)
CROSSFADE = 0.25      # seconds of overlap between chunks


# ─────────────────────────────────────────────────────────────
# Synthesis primitives
# ─────────────────────────────────────────────────────────────

def _lowpass_fft(block: np.ndarray, cutoff: float) -> np.ndarray:
    spectrum = np.fft.rfft(block, axis=0)
    freqs = np.fft.rfftfreq(block.shape[0], 1.0 / SR)
    response = 1.0 / np.sqrt(1.0 + (freqs / max(cutoff, 20.0)) ** 4)
    return np.fft.irfft(spectrum * response[:, None], n=block.shape[0], axis=0).astype(np.float32)


def _highpass_fft(block: np.ndarray, cutoff: float) -> np.ndarray:
    spectrum = np.fft.rfft(block, axis=0)
    freqs = np.fft.rfftfreq(block.shape[0], 1.0 / SR)
    response = 1.0 - 1.0 / np.sqrt(1.0 + (freqs / max(cutoff, 20.0)) ** 4)
    return np.fft.irfft(spectrum * response[:, None], n=block.shape[0], axis=0).astype(np.float32)


def _envelope(length: int, attack: float, release: float) -> np.ndarray:
    env = np.ones(length, np.float32)
    a = max(1, int(attack * SR))
    r = max(1, int(release * SR))
    env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    env[-r:] = np.linspace(1, 0, r, dtype=np.float32)
    return env


def _kick(t: np.ndarray, when: float, gain: float = 0.5) -> np.ndarray:
    dt = t - when
    active = (dt >= 0) & (dt < 0.42)
    freq = 118.0 * np.exp(-dt * 7.5) + 42.0
    phase = 2 * np.pi * np.cumsum(np.where(active, freq, 0.0)) / SR
    body = np.sin(phase) * np.exp(-np.clip(dt, 0.0, None) * 9.0) * gain
    click = np.where(active & (dt < 0.012), (1 - dt / 0.012) * 0.22, 0.0)
    return np.where(active, body + click, 0.0).astype(np.float32)


def _hat(t: np.ndarray, when: float, gain: float = 0.05, rng=None) -> np.ndarray:
    dt = t - when
    active = (dt >= 0) & (dt < 0.09)
    noise = (rng.standard_normal(dt.shape) if rng is not None else np.random.standard_normal(dt.shape))
    return np.where(active, noise * np.exp(-np.clip(dt, 0.0, None) * 62.0) * gain,
                    0.0).astype(np.float32)


def _riser(t: np.ndarray, when: float, length: float = 5.0, gain: float = 0.30,
           rng=None) -> np.ndarray:
    dt = t - (when - length)
    active = (dt >= 0) & (dt < length)
    progress = np.clip(dt / length, 0, 1)
    noise = (rng.standard_normal(dt.shape) if rng is not None else np.random.standard_normal(dt.shape))
    sweep = noise * (0.15 + 0.85 * progress ** 2.2)
    tone = np.sin(2 * np.pi * np.cumsum(60 + 420 * progress ** 2.0) / SR) * 0.18 * progress
    return np.where(active, (sweep + tone) * gain, 0.0).astype(np.float32)


def _impact(t: np.ndarray, when: float, gain: float = 0.75, rng=None) -> np.ndarray:
    dt = t - when
    active = (dt >= 0) & (dt < 2.2)
    noise = (rng.standard_normal(dt.shape) if rng is not None else np.random.standard_normal(dt.shape))
    boom = np.sin(2 * np.pi * np.cumsum(np.where(active, 90 * np.exp(-dt * 3.4) + 28, 0.0)) / SR)
    crack = noise * np.exp(-np.clip(dt, 0.0, None) * 5.0)
    decay = np.exp(-np.clip(dt, 0.0, None) * 1.5)
    return np.where(active, (boom * 0.85 + crack * 0.35) * gain * decay, 0.0).astype(np.float32)


# ─────────────────────────────────────────────────────────────
# Score
# ─────────────────────────────────────────────────────────────

CHORDS = [
    (55.00, 65.41, 82.41, 110.00),   # A minor add9 flavour
    (49.00, 58.27, 73.42, 98.00),    # G
    (51.91, 61.74, 77.78, 103.83),   # Ab / tension
    (46.25, 58.27, 69.30, 92.50),    # Gb low
]


def render_score(duration: float, destination: Path, seed: int = 2024,
                 risers: list[float] | None = None, impacts: list[float] | None = None,
                 pulse_bpm: float = 62.0, intensity: float = 1.0,
                 quiet_intro: float = 2.5) -> Path:
    """Write a stereo WAV score of exactly `duration` seconds."""
    risers = sorted(risers or [])
    impacts = sorted(impacts or [])
    rng = np.random.default_rng(seed)
    destination.parent.mkdir(parents=True, exist_ok=True)

    beat = 60.0 / pulse_bpm
    total_samples = int(duration * SR)
    written = 0
    tail = None

    with wave.open(str(destination), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SR)

        while written < total_samples:
            length = min(int(CHUNK * SR), total_samples - written)
            t0 = written / SR
            t = (np.arange(length, dtype=np.float64) / SR) + t0

            # 1. sub drone
            lfo = 0.6 + 0.4 * np.sin(2 * np.pi * t / 34.0)
            drone = (np.sin(2 * np.pi * 41.2 * t) * 0.30 +
                     np.sin(2 * np.pi * 41.2 * 1.005 * t) * 0.20 * lfo +
                     np.sin(2 * np.pi * 82.4 * t) * 0.10)

            # 2. slow minor pad (chord every 18 s)
            chord_index = int(t0 // 18) % len(CHORDS)
            chord = CHORDS[chord_index]
            pad = np.zeros(length, np.float32)
            local = t - (t0 - (t0 % 18))
            swell = np.clip(np.sin(np.pi * np.clip(local / 18.0, 0, 1)), 0, 1) ** 0.7
            for partial, freq in enumerate(chord):
                detune = 1.0 + 0.0016 * np.sin(2 * np.pi * t / (7.0 + partial))
                pad += (np.sin(2 * np.pi * freq * detune * t) *
                        (0.16 / (1 + partial * 0.55))).astype(np.float32)
            pad *= swell.astype(np.float32)

            # 3. air / texture
            air = rng.standard_normal(length).astype(np.float32)
            air = _lowpass_fft(air[:, None], 420.0)[:, 0] * 0.10
            hiss = _highpass_fft(rng.standard_normal(length).astype(np.float32)[:, None], 5200.0)[:, 0] * 0.018

            # 4. pulse
            pulse = np.zeros(length, np.float32)
            first = int(t0 // beat)
            for k in range(first, int((t0 + CHUNK) // beat) + 2):
                when = k * beat
                if not (t0 - 0.5 <= when < t0 + CHUNK + 0.5):
                    continue
                pulse += _kick(t, when, gain=0.30 if k % 4 == 0 else 0.16)
                if k % 2 == 1:
                    pulse += _hat(t, when, gain=0.035, rng=rng)

            # 5. risers + impacts
            fx = np.zeros(length, np.float32)
            for when in risers:
                if t0 - 6.0 <= when <= t0 + CHUNK + 1.0:
                    fx += _riser(t, when, length=5.0, gain=0.34, rng=rng)
            for when in impacts:
                if t0 - 3.0 <= when <= t0 + CHUNK + 3.0:
                    fx += _impact(t, when, gain=0.80, rng=rng)

            mono = (drone * 0.42 + pad * 0.34 + air + hiss + pulse * 0.55 + fx) * intensity

            # stereo widening: tiny delay + level difference
            delay = int(0.011 * SR)
            left = mono
            right = np.concatenate([np.zeros(delay, np.float32), mono[:-delay]]) * 0.94 + mono * 0.06

            # intro silence ramp (the cold open must breathe)
            if t0 < quiet_intro:
                ramp = np.clip(t / max(quiet_intro, 0.001), 0, 1) ** 1.6
                left *= ramp
                right *= ramp

            block = np.stack([left, right], axis=1)
            block = np.tanh(block * 1.05) * 0.86

            # fade out the very end
            remaining = total_samples - written
            if remaining <= int(4.0 * SR):
                block *= np.linspace(1.0, 0.0, remaining, dtype=np.float32)[:, None] ** 1.4

            if tail is not None:
                overlap = min(tail.shape[0], block.shape[0], int(CROSSFADE * SR))
                fade = np.linspace(0, 1, overlap, dtype=np.float32)[:, None]
                block[:overlap] = block[:overlap] * fade + tail[-overlap:] * (1 - fade)

            pcm = (np.clip(block, -1, 1) * 32767).astype("<i2")
            wav.writeframes(pcm.tobytes())
            tail = block
            written += length

    util.ok("music", f"score rendered · {util.clock(duration)} · {util.human_size(destination.stat().st_size)}")
    return destination


# ─────────────────────────────────────────────────────────────
# Mix
# ─────────────────────────────────────────────────────────────

def mix_audio(narration: Path, score: Path, destination: Path,
              music_gain: float = 0.30, duck_ratio: float = 9.0,
              threshold: float = 0.02, target_i: float = -15.0) -> Path:
    """Narration + ducked score -> stereo AAC-ready WAV."""
    if not narration.exists() and not score.exists():
        raise RuntimeError("nothing to mix")
    destination.parent.mkdir(parents=True, exist_ok=True)

    inputs, graph = [], []
    index = 0
    if score.exists():
        inputs += ["-i", str(score)]
        graph.append(f"[{index}:a]aresample={SR},volume={music_gain}[mus]")
        index += 1
    if narration.exists():
        inputs += ["-i", str(narration)]
        graph.append(f"[{index}:a]aresample={SR},highpass=f=70,"
                     f"pan=stereo|c0=c0|c1=c0[nar]")
        index += 1

    if score.exists() and narration.exists():
        graph.append("[nar]asplit=2[nar1][sc]")
        graph.append(f"[mus][sc]sidechaincompress=threshold={threshold}:ratio={duck_ratio}:"
                     f"attack=18:release=420:knee=6[ducked]")
        graph.append("[ducked][nar1]amix=inputs=2:duration=longest:normalize=0[mixed]")
    elif score.exists():
        graph.append("[mus]apad[mixed]")
    else:
        graph.append("[nar]apad[mixed]")

    graph.append(f"[mixed]alimiter=limit=0.94,loudnorm=I={target_i}:TP=-1.5:LRA=11[out]")

    command = [util.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *inputs,
               "-filter_complex", ";".join(graph), "-map", "[out]",
               "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(f"mix failed: {result.stderr[:400]}")
    util.ok("mix", f"{destination.name} · {util.clock(util.media_duration(destination))}")
    return destination


def sfx_accents(project: Path, timeline: dict) -> tuple[list[float], list[float]]:
    """Where to place risers and impacts: before climax beats, on impact scenes."""
    risers, impacts = [], []
    for scene in timeline.get("scenes", []):
        beat = scene.get("beat", "")
        start = float(scene.get("scene_start", 0.0))
        if beat in ("climax", "escalation", "cost"):
            risers.append(start + 1.0)
        visual_events = scene.get("visual_events") or []
        if "impact" in visual_events or beat == "climax":
            impacts.append(start + float(scene.get("scene_duration", 6.0)) * 0.72)
        if beat in ("title", "cta"):
            risers.append(start + 0.4)
    return sorted(set(round(x, 3) for x in risers)), sorted(set(round(x, 3) for x in impacts))
