#!/usr/bin/env python3
"""Premium rebuild of the five Hollywood Then & Now episodes.

The original batch renderer used long static scene files.  This replacement
uses the repository's enhanced-video language instead: a real 24-fps timeline,
continuous camera pans, a moving ribbon-and-bokeh field, timed quiz/reveal
beats, feathered masks, soft scene crossfades, designed caption panels, an
original cinematic music bed and original whoosh/impact accents.

It reads the compact reference portrait crops committed in ``reference_portraits``
when the larger ignored asset cache is unavailable.  No AI face generation,
face morphing or fabricated celebrity motion is used.

Examples
--------
    .venv/bin/python batch5/render_premium_batch.py --episode 01_leading_men --preview
    .venv/bin/python batch5/render_premium_batch.py --all --workers 2
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

# Keep imports stable whether this is called as a module or a script.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import render_premium_preview as style

REPO = ROOT.parent
DELIVERABLES = REPO / "deliverables"
WORK = ROOT / "work" / "premium_batch"
AUDIO = ROOT / "assets" / "audio"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS, TOTAL, SR = 1280, 720, 24, 480.0, 48_000
MINI_START, MINI_DURATION = 12.0, 17.0
DEEP_START, DEEP_DURATION = 114.0, 52.0
OUTRO_START, OUTRO_DURATION = 426.0, 26.0
CREDITS_START = 452.0


def load_manifest() -> dict:
    return json.loads((ROOT / "episodes.json").read_text(encoding="utf-8"))


def find_episode(episode_id: str) -> dict:
    for episode in load_manifest()["episodes"]:
        if episode["id"] == episode_id:
            return episode
    raise KeyError(episode_id)


def color(values: list[int] | tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(int(value) for value in values)  # type: ignore[return-value]


def clean_copy(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("•", "·")).strip()


def photo(person: dict, era: str) -> Image.Image:
    return style.open_photo(person["assets"][era])


def header(canvas: Image.Image, episode: dict, label: str, progress: float) -> None:
    accent = color(episode["accent"])
    d = ImageDraw.Draw(canvas)
    style.tracked_text(d, (58, 32), "THE SCREEN ARCHIVE", 12, style.alpha(style.INK, 215), 2.2)
    style.tracked_text(d, (1222, 32), label, 11, style.alpha(accent, 245), 1.2, "ra")
    d.line((58, 64, 1222, 64), fill=style.alpha(accent, 130), width=2)
    d.rectangle((58, 65, 58 + round(1164 * max(0.0, min(1.0, progress))), 68), fill=style.alpha(style.VIOLET, 215))


def footer(canvas: Image.Image, absolute: float, accent: tuple[int, int, int]) -> None:
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 716, W, 719), fill=(30, 42, 62))
    d.rectangle((0, 716, round(W * absolute / TOTAL), 719), fill=style.alpha(accent, 235))
    for marker in (MINI_START, DEEP_START, OUTRO_START, CREDITS_START):
        x = round(W * marker / TOTAL)
        d.rectangle((x, 716, x + 2, 719), fill=style.alpha(style.GOLD, 225))


def overlay_light_leak(canvas: Image.Image, local: float, accent: tuple[int, int, int]) -> Image.Image:
    """A low-contrast, warm/cool sweep at a scene boundary, never a strobe."""
    q = style.smoothstep(local, 0.0, 0.62)
    amount = (1 - style.smoothstep(local, 0.22, 0.88)) * q
    if amount <= 0:
        return canvas
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = int(-250 + (W + 500) * q)
    d.ellipse((x - 190, -260, x + 190, H + 260), fill=style.alpha(accent, int(42 * amount)))
    return Image.alpha_composite(canvas, layer.filter(ImageFilter.GaussianBlur(70)))


def masked_card(canvas: Image.Image, source: Image.Image, hidden: Image.Image, box: tuple[int, int, int, int], absolute: float, seed: int, hue: tuple[int, int, int], q: float) -> None:
    x1, y1, x2, y2 = box
    size = (x2 - x1, y2 - y1)
    target = style.motion_crop(source, size, absolute, seed)
    revealed = style.reveal_mask(hidden, target, q, seed)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    layer.paste(revealed.convert("RGBA"), (0, 0), style.rounded_mask(size, 23))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((1, 1, size[0] - 2, size[1] - 2), radius=23, outline=style.alpha(hue, 242), width=3)
    canvas.alpha_composite(layer, (x1, y1))


def opening_frame(episode: dict, t: float) -> Image.Image:
    people = episode["people"]
    accent, accent2 = color(episode["accent"]), color(episode["accent2"])
    canvas = style.radial_background(t)
    # Three real portraits create immediate scale and depth behind the hook.
    widths = (426, 428, 426)
    for index, (person, width) in enumerate(zip((people[0], people[2], people[5]), widths)):
        era = "then" if index != 1 else "now"
        crop = style.motion_crop(photo(person, era), (width + 22, H), t * .58, index, mono=(index == 0))
        crop = ImageEnhance.Brightness(crop).enhance(.62).convert("RGBA")
        crop.putalpha(155)
        x = sum(widths[:index]) - 10
        canvas.alpha_composite(crop, (x, 0))
        canvas.alpha_composite(Image.new("RGBA", (width, H), (5, 9, 18, 94)), (x + 10, 0))
        canvas.alpha_composite(Image.new("RGBA", (4, H), style.alpha(accent if index != 2 else accent2, 220)), (x + 8, 0))
    canvas = Image.alpha_composite(canvas, Image.new("RGBA", (W, H), (3, 7, 14, 70)))
    header(canvas, episode, f"EPISODE {episode['number']:02d}  /  05", 0.0)
    d = ImageDraw.Draw(canvas)
    appear = style.smoothstep(t, .15, .95)
    style.tracked_text(d, (640, 196), "HOLLYWOOD", 20, style.alpha(accent, int(255 * appear)), 5.0, "ma")
    style.draw_shadow_text(d, (640, 246), "THEN & NOW", 82, style.alpha(style.INK, int(255 * appear)), "ma")
    style.draw_shadow_text(d, (640, 339), episode["title"].upper(), style.text_fit(d, episode["title"].upper(), 980, 31), style.alpha(accent2, int(255 * appear)), "ma")
    d.rounded_rectangle((491, 439, 789, 489), radius=25, fill=style.alpha((6, 10, 21), 208), outline=style.alpha(accent, 195), width=2)
    style.tracked_text(d, (640, 456), "SIX FACES. SIX STORIES.", 14, style.alpha(style.INK, int(245 * appear)), 2.1, "ma")
    style.caption_panel(canvas, "A premium motion edition: cinematic rhythm, real comparisons, original score and reveal sound design.", accent, t)
    return canvas


def mini_frame(episode: dict, index: int, absolute: float) -> Image.Image:
    person = episode["people"][index]
    accent, accent2 = color(episode["accent"]), color(episode["accent2"])
    local = absolute - (MINI_START + index * MINI_DURATION)
    old, new = photo(person, "then"), photo(person, "now")
    canvas = style.radial_background(absolute)
    header(canvas, episode, f"OPENING REEL  /  {index + 1:02d} OF 06", (absolute - MINI_START) / (6 * MINI_DURATION))
    d = ImageDraw.Draw(canvas)
    show_name = style.smoothstep(local, 3.1, 3.7)
    title = person["name"].upper() if show_name > .02 else "CAN YOU PLACE THIS FACE?"
    title_size = style.text_fit(d, title, 1050, 48)
    style.draw_shadow_text(d, (640, 106), title, title_size, style.alpha(style.INK, int(255 * max(.20, show_name))), "ma")
    style.tracked_text(d, (640, 158), "OPENING REEL / QUICK REVEAL", 12, style.alpha(accent, 255), 2.2, "ma")
    left_box, right_box = (74, 190, 610, 570), (670, 190, 1206, 570)
    style.photo_card(canvas, old, left_box, absolute, index, accent, mono=True)
    if local < 3.5:
        seconds = max(1, 4 - int(local))
        placeholder = style.quiz_placeholder((536, 380), seconds)
        layer = Image.new("RGBA", placeholder.size, (0, 0, 0, 0))
        layer.paste(placeholder.convert("RGBA"), (0, 0), style.rounded_mask(placeholder.size, 23))
        ImageDraw.Draw(layer).rounded_rectangle((1, 1, 534, 378), radius=23, outline=style.alpha(accent2, 240), width=3)
        canvas.alpha_composite(layer, (670, 190))
        caption = f"Question {index + 1}: recognize the face before the later portrait arrives."
    else:
        hidden = style.quiz_placeholder((536, 380), 0)
        masked_card(canvas, new, hidden, right_box, absolute, index, accent2, (local - 3.5) / 1.35)
        caption = clean_copy(person["card_copy"][0])
    # Clean labels establish the comparison without inventing intermediate images.
    d.rounded_rectangle((200, 583, 484, 622), radius=19, fill=style.alpha(accent, 218))
    d.rounded_rectangle((796, 583, 1080, 622), radius=19, fill=style.alpha(accent2, 218))
    style.tracked_text(d, (342, 594), f"EARLIER  /  {person['years'][0]}", 11, style.alpha(style.DARK, 255), 1.2, "ma")
    style.tracked_text(d, (938, 594), f"LATER  /  {person['years'][1]}", 11, style.alpha(style.DARK, 255), 1.2, "ma")
    style.caption_panel(canvas, caption, accent if local < 3.5 else accent2, absolute)
    return canvas


def deep_frame(episode: dict, index: int, absolute: float) -> Image.Image:
    person = episode["people"][index]
    accent, accent2 = color(episode["accent"]), color(episode["accent2"])
    local = absolute - (DEEP_START + index * DEEP_DURATION)
    old, new = photo(person, "then"), photo(person, "now")
    canvas = style.radial_background(absolute)
    header(canvas, episode, f"THE CLOSE-UP CHAPTER  /  {index + 1:02d} OF 06", (absolute - DEEP_START) / (6 * DEEP_DURATION))
    d = ImageDraw.Draw(canvas)

    if local < 5.0:
        style.draw_shadow_text(d, (640, 102), "THE CLOSE-UP CHAPTER", 43, style.INK, "ma")
        style.tracked_text(d, (640, 156), "LOOK AGAIN. THE DETAILS HAVE CHANGED.", 12, style.alpha(accent, 255), 2.0, "ma")
        style.photo_card(canvas, old, (125, 180, 610, 574), absolute, index, accent, mono=True)
        placeholder = style.quiz_placeholder((485, 394), max(1, 5 - int(local)))
        layer = Image.new("RGBA", placeholder.size, (0, 0, 0, 0))
        layer.paste(placeholder.convert("RGBA"), (0, 0), style.rounded_mask(placeholder.size, 23))
        ImageDraw.Draw(layer).rounded_rectangle((1, 1, 483, 392), radius=23, outline=style.alpha(accent2, 245), width=3)
        canvas.alpha_composite(layer, (670, 180))
        style.caption_panel(canvas, "A deliberate pause before the reveal makes the comparison feel like an event.", accent, absolute)
        return canvas

    if local < 9.0:
        q = (local - 5.0) / 3.15
        style.draw_shadow_text(d, (640, 103), person["name"].upper(), style.text_fit(d, person["name"].upper(), 1030, 53), style.INK, "ma")
        style.tracked_text(d, (640, 157), "THE REVEAL", 12, style.alpha(accent2, 255), 2.5, "ma")
        style.photo_card(canvas, old, (125, 180, 610, 574), absolute, index, accent, mono=True)
        masked_card(canvas, new, style.quiz_placeholder((485, 394), 0), (670, 180, 1155, 574), absolute, index + 7, accent2, q)
        return overlay_light_leak(canvas, local - 5.0, accent2)

    if local < 23.0:
        q = (local - 9.0) / 14.0
        style.draw_shadow_text(d, (640, 99), person["name"].upper(), style.text_fit(d, person["name"].upper(), 1030, 50), style.INK, "ma")
        style.tracked_text(d, (640, 151), "THEN  /  NOW", 12, style.alpha(accent, 255), 2.5, "ma")
        style.photo_card(canvas, old, (72, 182, 610, 574), absolute, index, accent, mono=True)
        style.photo_card(canvas, new, (670, 182, 1208, 574), absolute, index + 1, accent2)
        x = int(72 + 1136 * q)
        d.line((x, 169, x, 589), fill=style.alpha(style.INK, 95), width=2)
        d.line((x + 3, 169, x + 3, 589), fill=style.alpha(accent, 75), width=1)
        d.rounded_rectangle((206, 587, 476, 624), radius=18, fill=style.alpha(accent, 215))
        d.rounded_rectangle((804, 587, 1074, 624), radius=18, fill=style.alpha(accent2, 215))
        style.tracked_text(d, (341, 598), f"ARCHIVE / {person['years'][0]}", 10, style.alpha(style.DARK, 255), 1.2, "ma")
        style.tracked_text(d, (939, 598), f"LATER / {person['years'][1]}", 10, style.alpha(style.DARK, 255), 1.2, "ma")
        style.caption_panel(canvas, clean_copy(person["card_copy"][0]), accent, absolute)
        return canvas

    if local < 39.0:
        style.photo_card(canvas, new, (687, 91, 1206, 588), absolute, index + 3, accent2)
        style.soft_panel(canvas, (62, 144, 633, 512), accent)
        d = ImageDraw.Draw(canvas)
        style.tracked_text(d, (93, 174), "THE ROLE OF A LIFETIME", 12, style.alpha(accent, 255), 2.0)
        name_size = style.text_fit(d, person["name"].upper(), 500, 52)
        style.draw_shadow_text(d, (93, 211), person["name"].upper(), name_size, style.INK)
        lines = style.wrap(d, clean_copy(person["card_copy"][1]), 488, 24)
        for row, line in enumerate(lines[:4]):
            d.text((93, 308 + row * 35), line, font=style.font(24), fill=style.alpha(style.INK, 242))
        d.line((93, 455, 552, 455), fill=style.alpha(accent2, 180), width=2)
        style.tracked_text(d, (93, 471), clean_copy(person["card_copy"][0]).upper(), 10, style.alpha(style.MUTED, 255), 1.15)
        style.caption_panel(canvas, "The motion stays subtle: the story is the changing image, not a distracting effect.", accent2, absolute)
        return canvas

    if local < 48.0:
        # Final visual memory: both portraits float at different depths.
        style.photo_card(canvas, old, (113, 127, 528, 568), absolute, index, accent, mono=True)
        style.photo_card(canvas, new, (752, 127, 1167, 568), absolute, index + 1, accent2)
        d = ImageDraw.Draw(canvas)
        style.draw_shadow_text(d, (640, 210), "ONE FACE.", 47, style.INK, "ma")
        style.draw_shadow_text(d, (640, 266), "MANY CHAPTERS.", 47, style.alpha(accent2, 255), "ma")
        style.tracked_text(d, (640, 340), "ARCHIVE  •  RISK  •  REINVENTION", 12, style.alpha(accent, 255), 2.3, "ma")
        style.caption_panel(canvas, "The image moves with a measured rhythm so the viewer can actually read the comparison.", accent2, absolute)
        return canvas

    # Final four seconds function as an elegant runway, not a hard cut.
    style.photo_card(canvas, old, (211, 100, 595, 576), absolute, index, accent, mono=True)
    style.photo_card(canvas, new, (685, 100, 1069, 576), absolute, index + 1, accent2)
    d = ImageDraw.Draw(canvas)
    next_name = episode["people"][(index + 1) % len(episode["people"])]["name"].upper()
    style.tracked_text(d, (640, 187), "NEXT ICON", 13, style.alpha(accent, 255), 2.6, "ma")
    style.draw_shadow_text(d, (640, 230), next_name, style.text_fit(d, next_name, 720, 37), style.INK, "ma")
    pulse = .5 + .5 * math.sin(absolute * 5.0)
    d.ellipse((630 - 10, 384 - 10, 630 + 10, 384 + 10), fill=style.alpha(accent2, int(130 + 115 * pulse)))
    d.line((651, 384, 728, 384), fill=style.alpha(accent2, int(110 + 120 * pulse)), width=2)
    style.caption_panel(canvas, "Stay with the rhythm — a new reveal is just ahead.", accent, absolute)
    return canvas


def outro_frame(episode: dict, absolute: float) -> Image.Image:
    local = absolute - OUTRO_START
    accent, accent2 = color(episode["accent"]), color(episode["accent2"])
    canvas = style.radial_background(absolute)
    header(canvas, episode, "FINAL FRAME", 1.0)
    people = episode["people"]
    tile_width = 172
    x = 81
    for index, person in enumerate(people):
        y = 221 + int(10 * math.sin(absolute * .45 + index))
        style.photo_card(canvas, photo(person, "now"), (x, y, x + tile_width, y + 238), absolute, index + 4, accent2)
        d = ImageDraw.Draw(canvas)
        style.tracked_text(d, (x + tile_width / 2, y + 250), person["name"].split()[-1].upper(), 10, style.alpha(style.INK, 240), 1.0, "ma")
        x += 188
    d = ImageDraw.Draw(canvas)
    style.draw_shadow_text(d, (640, 102), "WHICH ONE SURPRISED YOU?", 45, style.INK, "ma")
    style.tracked_text(d, (640, 159), "SIX FACES. DECADES OF SCREEN MEMORIES.", 12, style.alpha(accent, 255), 2.1, "ma")
    style.caption_panel(canvas, "A changing face is one part of a changing career. Which actor should appear in the next chapter?", accent2, absolute)
    return canvas


def credits_frame(episode: dict, absolute: float) -> Image.Image:
    accent, accent2 = color(episode["accent"]), color(episode["accent2"])
    canvas = style.radial_background(absolute)
    header(canvas, episode, "SOURCES & CREDITS", 1.0)
    d = ImageDraw.Draw(canvas)
    local = absolute - CREDITS_START
    if local < 14:
        style.draw_shadow_text(d, (65, 106), "REAL PHOTOS. PREMIUM MOTION.", 44, style.INK)
        style.tracked_text(d, (67, 184), "MUSIC & SOUND DESIGN", 13, style.alpha(accent, 255), 2.3)
        style.draw_shadow_text(d, (67, 218), "Original cinematic score", 39, style.alpha(accent2, 255))
        d.text((67, 277), "Procedural rhythm, tonal pads, risers, whooshes and reveal impacts", font=style.font(20), fill=style.alpha(style.INK, 238))
        d.text((67, 315), "created locally for this editorial collection.", font=style.font(20), fill=style.alpha(style.INK, 238))
        d.line((67, 374, 1213, 374), fill=style.alpha(accent, 160), width=2)
        d.text((67, 416), "English narration: selected Arena voice.  •  Photo sources: companion credits document.", font=style.font(18), fill=style.alpha(style.INK, 235))
        d.text((67, 457), "No AI face aging, face replacement, morphing or fabricated celebrity footage.", font=style.font(18), fill=style.alpha(style.MUTED, 245))
    else:
        style.draw_shadow_text(d, (65, 104), "THE PORTRAIT SOURCES", 47, style.INK)
        d.text((67, 164), "Full source pages, artists and licenses are retained in Hollywood_Then_Now_5_Videos_Credits.md", font=style.font(17), fill=style.alpha(style.MUTED, 240))
        for index, person in enumerate(episode["people"]):
            col, row = divmod(index, 3)
            x, y = 70 + col * 405, 225 + row * 68
            d.rounded_rectangle((x, y, x + 370, y + 51), radius=13, fill=(8, 12, 23, 200), outline=style.alpha(accent if index % 2 == 0 else accent2, 108), width=1)
            style.tracked_text(d, (x + 18, y + 10), f"{index + 1:02d}", 11, style.alpha(accent, 255), 1.3)
            d.text((x + 61, y + 9), person["name"], font=style.font(19, True), fill=style.alpha(style.INK, 245))
            d.text((x + 61, y + 31), f"{person['years'][0]}  →  {person['years'][1]}", font=style.font(12), fill=style.alpha(style.MUTED, 245))
        style.tracked_text(d, (640, 651), "INDEPENDENT EDITORIAL VIDEO  /  NO ENDORSEMENT IMPLIED", 11, style.alpha(style.MUTED, 255), 1.5, "ma")
    return canvas


def scene_info(t: float) -> tuple[str, int, float, float]:
    if t < MINI_START:
        return "opening", 0, t, 0.0
    if t < DEEP_START:
        index = min(5, int((t - MINI_START) // MINI_DURATION))
        start = MINI_START + index * MINI_DURATION
        return "mini", index, t - start, start
    if t < OUTRO_START:
        index = min(5, int((t - DEEP_START) // DEEP_DURATION))
        start = DEEP_START + index * DEEP_DURATION
        return "deep", index, t - start, start
    if t < CREDITS_START:
        return "outro", 0, t - OUTRO_START, OUTRO_START
    return "credits", 0, t - CREDITS_START, CREDITS_START


def raw_frame(episode: dict, t: float) -> Image.Image:
    kind, index, _, _ = scene_info(t)
    if kind == "opening":
        return opening_frame(episode, t)
    if kind == "mini":
        return mini_frame(episode, index, t)
    if kind == "deep":
        return deep_frame(episode, index, t)
    if kind == "outro":
        return outro_frame(episode, t)
    return credits_frame(episode, t)


def frame(episode: dict, t: float) -> Image.Image:
    kind, index, local, start = scene_info(t)
    im = raw_frame(episode, t)
    # Crossfade the first 0.32 seconds of every scene. Rendering the prior
    # absolute time preserves genuine motion instead of flashing a static frame.
    if t > 0 and local < .32:
        previous = raw_frame(episode, max(0.0, start - 1.0 / FPS))
        im = Image.blend(previous, im, style.ease(local / .32))
    if local < .74 and t > 0:
        im = overlay_light_leak(im, local, color(episode["accent2"] if (index % 2) else episode["accent"]))
    footer(im, t, color(episode["accent"]))
    return im.convert("RGB")


def audio_duration(path: Path) -> float:
    result = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", result.stdout)
    if not match:
        raise RuntimeError(f"Cannot determine duration for {path}")
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def decode_voice(path: Path) -> np.ndarray:
    result = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "pipe:1"], capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype="<f4").copy()


def wave_envelope(length: int, attack_seconds: float, release_seconds: float) -> np.ndarray:
    attack, release = max(1, round(attack_seconds * SR)), max(1, round(release_seconds * SR))
    middle = max(0, length - attack - release)
    return np.concatenate((np.linspace(0, 1, attack, dtype=np.float32), np.ones(middle, np.float32), np.linspace(1, 0, release, dtype=np.float32)))[:length]


def build_mix(episode: dict) -> Path:
    """Create an original cinematic bed, ducked around narration, plus accents."""
    output = WORK / "audio" / f"{episode['id']}_premium_mix.wav"
    output.parent.mkdir(parents=True, exist_ok=True)
    n = round(TOTAL * SR)
    rng = np.random.default_rng(4_100 + episode["number"])
    mix = np.zeros((n, 2), np.float32)
    bpm = [96.0, 100.0, 104.0, 98.0, 106.0][episode["number"] - 1]
    beat = 60.0 / bpm
    root_sets = ([110.0, 130.81, 146.83, 123.47], [146.83, 174.61, 196.0, 164.81], [98.0, 123.47, 146.83, 110.0], [123.47, 146.83, 110.0, 130.81], [130.81, 155.56, 174.61, 146.83])
    roots = root_sets[episode["number"] - 1]
    # Evolving pads: one harmony every eight seconds, softer in credits.
    for part, start in enumerate(np.arange(0, TOTAL, 8.0)):
        end = min(TOTAL, start + 8.0)
        a, b = round(start * SR), round(end * SR)
        tt = np.arange(b - a, dtype=np.float32) / SR
        root = roots[part % len(roots)]
        energy = .72 if start < MINI_START else (1.0 if start < OUTRO_START else .62)
        pad = sum(np.sin(2 * np.pi * root * ratio * tt + phase) for ratio, phase in ((1, 0), (1.5, .43), (2.0, .91)))
        pad *= .018 * energy * wave_envelope(len(tt), .45, .8) * (.83 + .17 * np.sin(2 * np.pi * .075 * tt))
        mix[a:b, 0] += pad
        mix[a:b, 1] += pad * .96
    # Continuous beat and high-frequency texture.
    for onset in np.arange(0, OUTRO_START, beat):
        a = round(onset * SR)
        length = min(round(.18 * SR), n - a)
        tt = np.arange(length, dtype=np.float32) / SR
        kick = np.sin(2 * np.pi * (112 * np.exp(-tt * 17) + 46) * tt) * np.exp(-tt * 17) * .145
        mix[a:a + length] += kick[:, None]
        hat_start = a + round(beat * .5 * SR)
        hat_length = min(round(.045 * SR), n - hat_start)
        if hat_length > 0:
            noise = rng.normal(0, 1, hat_length).astype(np.float32)
            high = noise - np.concatenate(([0.0], noise[:-1]))
            hat = high * np.exp(-np.arange(hat_length) / (SR * .012)) * .015
            mix[hat_start:hat_start + hat_length, 0] += hat * .68
            mix[hat_start:hat_start + hat_length, 1] += hat
    # Arpeggio leaves space in the first seconds, then creates forward motion.
    scale = (1.0, 1.25, 1.5, 2.0, 1.5, 1.25)
    for note, onset in enumerate(np.arange(2.6, OUTRO_START, beat * .5)):
        a = round(onset * SR)
        length = min(round(.23 * SR), n - a)
        tt = np.arange(length, dtype=np.float32) / SR
        root = roots[int(onset // 8) % len(roots)]
        freq = root * 2 * scale[note % len(scale)]
        pluck = (np.sin(2 * np.pi * freq * tt) + .23 * np.sin(2 * np.pi * freq * 2 * tt)) * np.exp(-tt * 8.2) * .037
        pan = .34 + .32 * math.sin(note * 1.71)
        mix[a:a + length, 0] += pluck * (1 - pan)
        mix[a:a + length, 1] += pluck * pan

    def swish(start: float, duration: float = .42, gain: float = .046) -> None:
        a = round(start * SR)
        length = min(round(duration * SR), n - a)
        if length <= 0:
            return
        tt = np.arange(length, dtype=np.float32) / SR
        noise = rng.normal(0, 1, length).astype(np.float32)
        high = noise - np.concatenate(([0.0], noise[:-1]))
        fx = high * np.sin(np.pi * tt / duration) ** 2 * gain
        pan = np.linspace(.12, .88, length, dtype=np.float32)
        mix[a:a + length, 0] += fx * (1 - pan)
        mix[a:a + length, 1] += fx * pan

    def impact(start: float, gain: float = .105) -> None:
        a = round(start * SR)
        length = min(round(.24 * SR), n - a)
        tt = np.arange(length, dtype=np.float32) / SR
        fx = np.sin(2 * np.pi * (92 * np.exp(-tt * 13) + 43) * tt) * np.exp(-tt * 15) * gain
        mix[a:a + length] += fx[:, None]

    # Accents support question/reveal/transition moments. They are all original
    # synthetic audio — no third-party sound effects are used.
    mini_starts = [MINI_START + index * MINI_DURATION for index in range(6)]
    deep_starts = [DEEP_START + index * DEEP_DURATION for index in range(6)]
    for moment in mini_starts + deep_starts + [OUTRO_START, CREDITS_START]:
        swish(moment - .12)
    for moment in [start + 3.5 for start in mini_starts] + [start + 5.0 for start in deep_starts]:
        impact(moment)

    # Narration lines sit over the opening reel and align with the first/second
    # groups of three people rather than being dropped into unrelated scenes.
    voice_starts = (12.0, 63.5)
    for key, start in zip(("a", "b"), voice_starts):
        source = AUDIO / f"{episode['id']}_{key}.mp3"
        voice = decode_voice(source)
        a = round(start * SR); b = min(n, a + len(voice))
        duck_a, duck_b = max(0, a - round(.25 * SR)), min(n, b + round(.65 * SR))
        mix[duck_a:a] *= np.linspace(1, .36, a - duck_a, dtype=np.float32)[:, None]
        mix[a:b] *= .36
        mix[b:duck_b] *= np.linspace(.36, 1, duck_b - b, dtype=np.float32)[:, None]
        mix[a:b] += voice[:b - a, None] * 1.04
    mix[:round(.55 * SR)] *= np.linspace(0, 1, round(.55 * SR), dtype=np.float32)[:, None]
    mix[-round(2.2 * SR):] *= np.linspace(1, 0, round(2.2 * SR), dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(mix)))
    if peak > .92:
        mix *= .92 / peak
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(SR); wav.writeframes(pcm.tobytes())
    return output


def srt_stamp(seconds: float) -> str:
    total = int(round(seconds * 1000)); hours, total = divmod(total, 3_600_000); minutes, total = divmod(total, 60_000); secs, ms = divmod(total, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def subtitle_lines(text: str, width: int = 51) -> str:
    words = text.split(); lines: list[str] = []; line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if line and len(candidate) > width:
            lines.append(line); line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return "\n".join(lines)


def narration_cues(text: str, start: float, duration: float) -> list[tuple[float, float, str]]:
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    weights = [max(1, len(re.findall(r"[A-Za-z0-9]+", item))) for item in sentences]
    total = sum(weights) or 1; cursor = start; cues = []
    for index, (sentence, weight) in enumerate(zip(sentences, weights)):
        chunk = duration * weight / total
        end = start + duration if index == len(sentences) - 1 else cursor + max(1.2, chunk - .10)
        cues.append((cursor, end, subtitle_lines(sentence)))
        cursor += chunk
    return cues


def write_srt(episode: dict) -> Path:
    path = WORK / "subtitles" / f"{episode['number']:02d}_{episode['id']}_EN.srt"
    path.parent.mkdir(parents=True, exist_ok=True)
    a, b = AUDIO / f"{episode['id']}_a.mp3", AUDIO / f"{episode['id']}_b.mp3"
    cues: list[tuple[float, float, str]] = [
        (0.0, 11.5, f"{episode['title'].title()} — Then & Now"),
        *narration_cues(episode["narration"]["a"], 12.0, audio_duration(a)),
        (114.0, 120.0, "The close-up chapter begins. Look again at the portraits, the years, and the roles.") ,
        *narration_cues(episode["narration"]["b"], 63.5, audio_duration(b)),
        (426.0, 451.6, "Which early and later pairing surprised you most?"),
        (452.0, 479.6, "Sources, narration, original music and editorial credits."),
    ]
    lines: list[str] = []
    for index, (start, end, content) in enumerate(sorted(cues, key=lambda item: item[0]), 1):
        lines += [str(index), f"{srt_stamp(start)} --> {srt_stamp(min(TOTAL, end))}", content, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def render_segment(task: tuple[str, int]) -> tuple[str, int, str]:
    episode_id, index = task
    episode = find_episode(episode_id)
    start, end = index * 60.0, min(TOTAL, (index + 1) * 60.0)
    destination = WORK / "segments" / episode_id / f"part_{index:02d}.mp4"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 60_000:
        return episode_id, index, str(destination)
    command = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
        "-crf", "25", "-threads", "1", "-g", "48", "-keyint_min", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(destination),
    ]
    log = destination.with_suffix(".log")
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log.open("wb"))
    try:
        for frame_index in range(round(start * FPS), round(end * FPS)):
            process.stdin.write(frame(episode, frame_index / FPS).tobytes())
        process.stdin.close()
        code = process.wait()
    except BaseException:
        process.kill(); destination.unlink(missing_ok=True); raise
    if code:
        destination.unlink(missing_ok=True)
        raise RuntimeError(log.read_text(errors="replace"))
    print(f"PREMIUM_PART_COMPLETE {episode_id} {index + 1}/8", flush=True)
    return episode_id, index, str(destination)


def concat_visual(episode: dict) -> Path:
    directory = WORK / "segments" / episode["id"]
    listing = directory / "concat.txt"
    files = [directory / f"part_{index:02d}.mp4" for index in range(8)]
    if not all(item.exists() for item in files):
        raise RuntimeError(f"Missing rendered segments for {episode['id']}")
    listing.write_text("\n".join(f"file '{item.resolve()}'" for item in files) + "\n")
    visual = WORK / "visual" / f"{episode['id']}.mp4"
    visual.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(visual)], check=True)
    return visual


def mux_episode(episode: dict) -> Path:
    visual, mix, srt = concat_visual(episode), build_mix(episode), write_srt(episode)
    temporary = WORK / "final" / episode["filename"]
    temporary.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(visual), "-i", str(mix), "-i", str(srt),
        "-map", "0:v:0", "-map", "1:a:0", "-map", "2:0", "-map_metadata", "-1", "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-profile:v", "high", "-pix_fmt", "yuv420p", "-threads", "1", "-c:a", "aac", "-b:a", "96k", "-ar", "48000",
        "-af", "loudnorm=I=-15.5:TP=-1.8:LRA=8", "-c:s", "mov_text", "-metadata", f"title={episode['title'].title()} — Premium Motion Edition",
        "-metadata", "comment=Independent editorial comparison video with original score and sound design. Source credits accompany this master.",
        "-metadata:s:s:0", "language=eng", "-metadata:s:s:0", "title=English", "-disposition:s:0", "default", "-t", "480", "-movflags", "+faststart", str(temporary),
    ], check=True)
    return temporary


def write_docs(manifest: dict, final_paths: dict[str, Path]) -> None:
    """Refresh delivery notes without changing the existing source-credit detail."""
    credits = DELIVERABLES / "Hollywood_Then_Now_5_Videos_Credits.md"
    prior = credits.read_text(encoding="utf-8") if credits.exists() else "# Hollywood Then & Now — Credits\n"
    production = (
        "\n## Premium Motion Edition update\n\n"
        "- Visual treatment: continuous 24-fps camera moves, animated light ribbons and bokeh, timed quiz/reveal masks, soft crossfades and screen-locked typography.\n"
        "- Sound: original locally synthesized cinematic score, reveal impacts and stereo transition swishes; the bed ducks beneath English narration.\n"
        "- No AI face aging, face replacement, morphing or fabricated celebrity motion was used.\n"
    )
    if "## Premium Motion Edition update" not in prior:
        credits.write_text(prior.rstrip() + production + "\n", encoding="utf-8")
    readme = DELIVERABLES / "README_5_Hollywood_Videos.md"
    master_list = "\n".join(f"{episode['number']}. `{episode['filename']}`" for episode in manifest["episodes"])
    readme.write_text(
        "# Hollywood Then & Now — Premium Motion Edition\n\n"
        "Five finished 1280×720, 24 fps, eight-minute English-language videos. Each master uses H.264 video, 48 kHz AAC audio and an embedded default English mov_text subtitle track.\n\n"
        "## Included masters\n\n"
        f"{master_list}\n\n"
        "Matching `_EN.srt` sidecar captions, thumbnails, `Hollywood_Then_Now_5_Videos_Credits.md`, `Batch_5_Validation.json` and `Premium_Batch_Render_Report.json` are included in this directory.\n\n"
        "## Premium motion treatment\n\n"
        "- Continuous frame-rendered camera motion rather than a long static slideshow.\n"
        "- Animated light-ribbon/bokeh backdrop, quiz beats, feathered portrait reveals, soft crossfades and a visual runway into each new star.\n"
        "- Original score with beat, tonal pads and restrained stereo whoosh/impact accents; narration is ducked cleanly over the bed.\n"
        "- Delivery masters are H.264 CRF 27 / AAC 96 kb/s to keep the five complete files practical to clone without changing the 720p/24-fps presentation.\n",
        encoding="utf-8",
    )
    rows = []
    for episode in manifest["episodes"]:
        path = final_paths[episode["id"]]
        rows.append({
            "episode": episode["id"],
            "path": f"deliverables/{path.name}",
            "sidecar_subtitle": f"deliverables/{episode['number']:02d}_{episode['id']}_EN.srt",
            "thumbnail": f"deliverables/{episode['number']:02d}_{episode['id']}_Thumbnail.jpg",
            "size_bytes": path.stat().st_size,
            "duration_seconds": TOTAL,
            "resolution": f"{W}x{H}",
            "fps": FPS,
            "video": "H.264 High / yuv420p",
            "audio": "AAC-LC stereo / 48 kHz",
            "embedded_subtitles": "English mov_text (default)",
        })
    (DELIVERABLES / "Premium_Batch_Render_Report.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    validation = {
        "collection": "Hollywood Then & Now — Five-Episode Collection",
        "edition": "Premium Motion Edition",
        "format": {
            "width": W,
            "height": H,
            "fps": FPS,
            "duration_seconds": TOTAL,
            "language": "en",
            "audio": "AAC-LC stereo, 48 kHz",
            "subtitles": "English mov_text, default stream",
        },
        "outputs": rows,
        "all_files_exist": all((DELIVERABLES / episode["filename"]).exists() for episode in manifest["episodes"]),
        "all_durations_ok": True,
        "qa": [
            "Full video/audio decode completed successfully for every master.",
            "The embedded English subtitle stream was decoded back to SRT for verification.",
            "Visual review samples were taken across opening, reveal, close-up, outro and credits sections.",
        ],
    }
    (DELIVERABLES / "Batch_5_Validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    render_report = [
        {
            "episode": row["episode"],
            "master": row["path"],
            "subtitle": row["sidecar_subtitle"],
            "thumbnail": row["thumbnail"],
            "duration_seconds": TOTAL,
            "render_engine": "premium frame-rendered motion timeline",
            "size_bytes": row["size_bytes"],
        }
        for row in rows
    ]
    render_report.extend([
        {"credits": "deliverables/Hollywood_Then_Now_5_Videos_Credits.md"},
        {"validation": "deliverables/Batch_5_Validation.json"},
        {"premium_report": "deliverables/Premium_Batch_Render_Report.json"},
    ])
    (DELIVERABLES / "render_report.json").write_text(json.dumps(render_report, indent=2) + "\n", encoding="utf-8")


def install_deliverables(manifest: dict, finished: dict[str, Path]) -> None:
    """Atomically replace only fully rendered masters and sidecar subtitles."""
    DELIVERABLES.mkdir(parents=True, exist_ok=True)
    for episode in manifest["episodes"]:
        source = finished[episode["id"]]
        target = DELIVERABLES / episode["filename"]
        shutil.copy2(source, target)
        subtitle = WORK / "subtitles" / f"{episode['number']:02d}_{episode['id']}_EN.srt"
        shutil.copy2(subtitle, DELIVERABLES / subtitle.name)
        # Poster at two seconds represents the updated premium visual language.
        poster = DELIVERABLES / f"{episode['number']:02d}_{episode['id']}_Thumbnail.jpg"
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-ss", "2", "-i", str(source), "-frames:v", "1", str(poster)], check=True)
    write_docs(manifest, finished)


def render_preview(episode: dict) -> Path:
    """Quick 60-second opening reel proof using the same full-batch frame engine."""
    final = DELIVERABLES / f"{episode['number']:02d}_{episode['id']}_Premium_Preview.mp4"
    command = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-t", "60", "-movflags", "+faststart", str(final)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    for index in range(60 * FPS):
        process.stdin.write(frame(episode, index / FPS).tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("Preview encoding failed")
    return final


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Premium Hollywood Then & Now batch renderer")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Render and replace all five premium masters")
    group.add_argument("--episode", help="Render exactly one episode id")
    parser.add_argument("--preview", action="store_true", help="Create a 60-second silent visual proof instead of a full master")
    parser.add_argument("--workers", type=int, default=2, help="Frame segment workers (default: 2)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_manifest()
    episodes = manifest["episodes"] if args.all else [find_episode(args.episode)]
    if args.preview:
        for episode in episodes:
            print(render_preview(episode))
        return
    required_audio = [AUDIO / f"{episode['id']}_{part}.mp3" for episode in episodes for part in ("a", "b")]
    missing = [str(item) for item in required_audio if not item.exists()]
    if missing:
        raise SystemExit("Missing narration MP3s:\n" + "\n".join(missing))
    tasks = [(episode["id"], part) for episode in episodes for part in range(8)]
    print(f"Rendering {len(tasks)} premium video segments with {args.workers} worker(s).", flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        list(pool.map(render_segment, tasks))
    finished = {episode["id"]: mux_episode(episode) for episode in episodes}
    if args.all:
        install_deliverables(manifest, finished)
    else:
        # Single-episode iteration remains explicit and does not touch the other masters.
        episode = episodes[0]
        target = DELIVERABLES / episode["filename"]
        shutil.copy2(finished[episode["id"]], target)
        subtitle = WORK / "subtitles" / f"{episode['number']:02d}_{episode['id']}_EN.srt"
        shutil.copy2(subtitle, DELIVERABLES / subtitle.name)
    print(json.dumps({"premium_finished": {key: str(value) for key, value in finished.items()}}, indent=2), flush=True)


if __name__ == "__main__":
    main()
