"""
Stage 4 — narration.

Providers
  edge        Microsoft neural voices via `edge-tts` (free, no API key) — default
  elevenlabs  ELEVENLABS_API_KEY, character-level timestamps
  openai      OPENAI_API_KEY, /v1/audio/speech (no timestamps -> proportional estimate)
  none        timed silence; keeps the whole pipeline runnable offline

Every provider produces the same artefacts:
  audio/<scene>.mp3       one file per scene
  timing.json             per-scene audio duration + word boundaries (absolute times)
"""

from __future__ import annotations

import asyncio
import json
import math
import shutil
import subprocess
import wave
from pathlib import Path

import config
import util

LEAD_IN = 0.45      # silence before the narrator speaks in each scene
TAIL_PAD = 0.55     # silence after the narration, before the next scene


# ─────────────────────────────────────────────────────────────
# Provider implementations
# ─────────────────────────────────────────────────────────────

def _edge_synthesise(text: str, voice: str, destination: Path) -> list[dict]:
    import edge_tts  # imported lazily so the rest works without it

    words: list[dict] = []

    async def run() -> None:
        communicate = edge_tts.Communicate(text, voice, rate=config.TTS_RATE, pitch=config.TTS_PITCH)
        with open(destination, "wb") as handle:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    handle.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    words.append({
                        "text": chunk["text"],
                        "start": chunk["offset"] / 10_000_000,
                        "end": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                    })

    asyncio.run(run())
    return words


def _elevenlabs_synthesise(text: str, voice: str, destination: Path) -> list[dict]:
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    payload = util.http_post_json(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with_timestamps",
        {"text": text, "model_id": config.ELEVENLABS_MODEL,
         "voice_settings": {"stability": 0.45, "similarity_boost": 0.8}},
        headers={"xi-api-key": config.ELEVENLABS_API_KEY}, timeout=300,
    )
    audio_b64 = payload.get("audio_base64") or payload.get("audio")
    if audio_b64:
        import base64

        destination.write_bytes(base64.b64decode(audio_b64))
    characters = payload.get("character_timings") or payload.get("characters") or []
    words = [{"text": c.get("text", ""), "start": float(c.get("start", 0)),
              "end": float(c.get("end", 0))} for c in characters]
    return words


def _openai_synthesise(text: str, voice: str, destination: Path) -> list[dict]:
    api_key = config.LLM_API_KEY
    if not api_key:
        raise RuntimeError("no API key for OpenAI TTS")
    body = {"model": "gpt-4o-mini-tts", "voice": voice or "onyx", "input": text,
            "response_format": "mp3"}
    import urllib.request

    request = urllib.request.Request(
        f"{config.LLM_API_BASE}/audio/speech",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        destination.write_bytes(response.read())
    return []


def _silent(duration: float, destination: Path, sample_rate: int = 24000) -> None:
    """Write a silent WAV so the mixer always has an input for every scene."""
    destination = destination.with_suffix(".wav")
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * int(duration * sample_rate))


def _probe_duration(path: Path) -> float:
    measured = util.media_duration(path)
    if measured > 0:
        return measured
    if path.suffix == ".wav":
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate())
    return 0.0


def _estimate_words(text: str, duration: float) -> list[dict]:
    """Distribute word timings proportionally by character length (offline mode)."""
    tokens = text.split()
    if not tokens or duration <= 0:
        return []
    weights = [max(1, len(t)) for t in tokens]
    total = sum(weights)
    cursor = 0.0
    words = []
    for token, weight in zip(tokens, weights):
        span = duration * weight / total
        words.append({"text": token, "start": cursor, "end": cursor + span})
        cursor += span
    return words


# ─────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────

def synthesise_scenes(script: dict, project: Path, provider: str | None = None,
                      voice: str | None = None, force: bool = False) -> dict:
    """Render narration for every scene and build the master timeline."""
    provider = (provider or config.TTS_PROVIDER).lower()
    lang = script["meta"].get("lang", config.DEFAULT_LANG)
    voice = voice or config.voice_for(lang)
    if provider == "elevenlabs" and not config.ELEVENLABS_API_KEY:
        util.warn("voice", "no ElevenLabs key — falling back to edge")
        provider = "edge"

    audio_dir = Path(project) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    timeline: list[dict] = []
    cursor = 0.0
    failures = 0

    for index, scene in enumerate(script.get("scenes", [])):
        scene_id = scene["id"]
        text = (scene.get("narration") or "").strip()
        mp3 = audio_dir / f"{scene_id}.mp3"
        wav = audio_dir / f"{scene_id}.wav"
        existing = mp3 if mp3.exists() else (wav if wav.exists() else None)

        if existing and not force:
            duration = _probe_duration(existing)
            words = _estimate_words(text, duration)
            util.log("voice", f"{scene_id}: cached {existing.name} ({util.clock(duration)})")
        elif not text:
            duration = float(scene.get("duration_hint") or 5.0)
            _silent(duration, audio_dir / f"{scene_id}.wav")
            existing = (audio_dir / f"{scene_id}.wav").with_suffix(".wav")
            words = []
            util.log("voice", f"{scene_id}: no narration, {duration:.1f}s of room tone")
        else:
            words, duration, existing = _synthesise_one(provider, voice, text, mp3, lang)
            if existing is None:
                failures += 1

        start = cursor + LEAD_IN
        scene["audio"] = str(existing) if existing else ""
        timeline.append({
            "id": scene_id,
            "index": index,
            "beat": scene.get("beat", ""),
            "visual": (scene.get("visual") or {}).get("type", "text"),
            "chapter": scene.get("chapter", ""),
            "scene_start": round(cursor, 3),
            "audio_file": str(existing) if existing else "",
            "audio_start": round(start, 3),
            "audio_duration": round(duration, 3),
            "scene_duration": round(LEAD_IN + duration + TAIL_PAD, 3),
            "words": [{"text": w["text"], "start": round(start + w["start"], 3),
                       "end": round(start + w["end"], 3)} for w in words],
            "provider": provider if existing and existing.suffix == ".mp3" else "silence",
            "voice": voice,
        })
        cursor += LEAD_IN + duration + TAIL_PAD
        scene["duration_hint"] = round(LEAD_IN + duration + TAIL_PAD, 3)

    if failures:
        util.warn("voice", f"{failures} scene(s) failed TTS — silent placeholders used")

    result = {
        "provider": provider,
        "voice": voice,
        "language": lang,
        "total_seconds": round(cursor, 3),
        "scenes": timeline,
    }
    util.write_json(Path(project) / "timing.json", result)
    util.ok("voice", f"narration ready · {util.clock(cursor)} · provider={provider} · voice={voice}")
    return result


def _synthesise_one(provider: str, voice: str, text: str, destination: Path,
                    lang: str) -> tuple[list[dict], float, Path | None]:
    if provider == "none":
        duration = max(3.0, len(text) / config.language(lang)["chars_per_sec"])
        wav = destination.with_suffix(".wav")
        _silent(duration, wav)
        return _estimate_words(text, duration), duration, wav

    attempters = {
        "edge": lambda: _edge_synthesise(text, voice, destination),
        "elevenlabs": lambda: _elevenlabs_synthesise(text, config.ELEVENLABS_VOICE_ID or voice, destination),
        "openai": lambda: _openai_synthesise(text, voice, destination),
    }
    try:
        words = attempters[provider]()
    except Exception as exc:
        util.warn("voice", f"{provider} failed ({str(exc)[:100]}) — silent placeholder")
        duration = max(3.0, len(text) / config.language(lang)["chars_per_sec"])
        wav = destination.with_suffix(".wav")
        _silent(duration, wav)
        return _estimate_words(text, duration), duration, wav

    if not destination.exists() or destination.stat().st_size < 512:
        util.warn("voice", f"{provider} produced no audio for {destination.name}")
        duration = max(3.0, len(text) / config.language(lang)["chars_per_sec"])
        wav = destination.with_suffix(".wav")
        _silent(duration, wav)
        return _estimate_words(text, duration), duration, wav

    duration = _probe_duration(destination)
    if duration <= 0:
        duration = max(3.0, len(text) / config.language(lang)["chars_per_sec"])
    if not words:
        words = _estimate_words(text, duration)
    elif words[-1]["end"] < duration - 0.6:
        # trust the measured file length, stretch the boundary map to fit
        scale = duration / max(words[-1]["end"], 1e-6)
        words = [{"text": w["text"], "start": w["start"] * scale, "end": w["end"] * scale} for w in words]
    util.ok("voice", f"{destination.stem}: {util.clock(duration)}, {len(words)} word marks")
    return words, duration, destination


# ─────────────────────────────────────────────────────────────
# Narration bus: concatenated, sample-accurate, aligned to the timeline
# ─────────────────────────────────────────────────────────────

def build_narration_track(timing: dict, project: Path, sample_rate: int = 48000) -> Path:
    """Concatenate every scene clip into one WAV placed exactly on the timeline."""
    audio_dir = Path(project) / "audio"
    output = audio_dir / "narration.wav"
    total = float(timing.get("total_seconds", 0.0))
    ffmpeg = util.ffmpeg_exe()
    inputs: list[str] = []
    parts: list[str] = []
    index = 0
    for scene in timing.get("scenes", []):
        file = scene.get("audio_file")
        if not file or not Path(file).exists():
            continue
        inputs += ["-i", file]
        delay_ms = int(round(float(scene["audio_start"]) * 1000))
        parts.append(f"[{index}:a]aresample={sample_rate},adelay={delay_ms}|{delay_ms}[a{index}]")
        index += 1
    if not parts:
        with wave.open(str(output), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(b"\x00\x00" * int(total * sample_rate))
        return output

    mix_inputs = "".join(f"[a{i}]" for i in range(index))
    filtergraph = ";".join(parts) + f";{mix_inputs}amix=inputs={index}:duration=longest:" \
                                    f"normalize=0,volume=1.6[out]"
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *inputs,
               "-filter_complex", filtergraph, "-map", "[out]",
               "-ac", "1", "-ar", str(sample_rate), str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(f"narration mix failed: {result.stderr[:400]}")
    return output


def voice_preview(project: Path) -> str:
    """Small helper used by the CLI `--list-voices` flag."""
    try:
        import edge_tts
    except Exception:
        return "edge-tts is not installed"
    rows = []
    for lang, profile in config.LANGUAGES.items():
        rows.append(f"{lang}: " + ", ".join(profile["tts_voices"]))
    return "\n".join(rows)
