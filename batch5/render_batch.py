#!/usr/bin/env python3
"""Render the five self-contained Hollywood Then & Now episodes.

Design goals
------------
* 1280x720, 24 fps, 480 seconds per episode.
* Real portrait assets are normalized locally before rendering; no network
  request is made by this script.
* Slow, purposeful camera drift is applied by FFmpeg's zoompan filter rather
  than writing millions of duplicate frames from Python.
* The two user-approved English narration clips are mixed with a quiet,
  original procedural ambient score. English SRT subtitles are both sidecar
  files and embedded mov_text subtitle tracks.

Use the workspace virtual environment because it contains Pillow, NumPy and
imageio-ffmpeg::

    .venv/bin/python batch5/render_batch.py --all
    .venv/bin/python batch5/render_batch.py --episode 01_leading_men --preview
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import wave
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUTPUT = ROOT / "output"
WORK = ROOT / "work"
ASSETS = ROOT / "assets"
W, H, FPS = 1280, 720, 24
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


@dataclass
class Scene:
    label: str
    image: Path
    duration: float


# ---------------------------------------------------------------------------
# Manifest / typography helpers
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    return json.loads((ROOT / "episodes.json").read_text(encoding="utf-8"))


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)


def rgba(color: tuple[int, int, int] | list[int], alpha: int) -> tuple[int, int, int, int]:
    return (int(color[0]), int(color[1]), int(color[2]), alpha)


def text_width(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), value, font=font)
    return int(box[2] - box[0])


def wrap_text(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    """Word-wrap against actual glyph widths, retaining deliberate newlines."""
    lines: list[str] = []
    for paragraph in value.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            test = current + " " + word
            if text_width(draw, test, font) <= width:
                current = test
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    width: int,
    spacing: int = 8,
    anchor: str | None = None,
) -> int:
    """Draw wrapped text and return the y coordinate after the final line."""
    x, y = xy
    lines = wrap_text(draw, value, font, width)
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_height = int((bbox[3] - bbox[1]) * 1.22)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill, anchor=anchor)
        y += line_height + spacing
    return y


def draw_pill(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    text_fill: tuple[int, int, int] | tuple[int, int, int, int] = (255, 255, 255, 255),
) -> None:
    draw.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    cx = (box[0] + box[2]) // 2
    cy = (box[1] + box[3]) // 2 + 1
    draw.text((cx, cy), text, font=font, fill=text_fill, anchor="mm")


# ---------------------------------------------------------------------------
# Image composition helpers
# ---------------------------------------------------------------------------

def gradient_background(accent: list[int], accent2: list[int], phase: float = 0.0) -> Image.Image:
    """Create a dark cinematic field with two gently colored light pools."""
    yy, xx = np.mgrid[0:H, 0:W]
    x = xx / W
    y = yy / H
    arr = np.zeros((H, W, 3), dtype=np.float32)
    arr[:] = np.array([10.0, 14.0, 25.0])
    centers = [
        (0.14 + 0.05 * math.sin(phase), 0.17, np.array(accent, dtype=np.float32), 0.38),
        (0.84, 0.72 + 0.05 * math.cos(phase), np.array(accent2, dtype=np.float32), 0.28),
        (0.48, 0.95, np.array(accent, dtype=np.float32), 0.11),
    ]
    for cx, cy, color, strength in centers:
        dist = ((x - cx) ** 2 / 0.22 + (y - cy) ** 2 / 0.30)
        glow = np.exp(-dist * 5.5)[..., None]
        arr += glow * color * strength
    # Vignette preserves contrast behind captions.
    vignette = ((x - 0.5) ** 2 + (y - 0.5) ** 2)[..., None]
    arr *= 1.0 - np.clip(vignette * 0.36, 0, 0.33)
    im = Image.fromarray(np.uint8(np.clip(arr, 0, 255)), "RGB").convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for offset in range(-H, W + H, 74):
        od.line((offset, 0, offset - H, H), fill=(255, 255, 255, 7), width=1)
    return Image.alpha_composite(im, overlay)


def open_photo(relative_path: str, person: str) -> Image.Image:
    path = ROOT / relative_path
    if path.exists():
        with Image.open(path) as image:
            return ImageOps.exif_transpose(image).convert("RGB")
    # Deliberately obvious safe fallback if a source asset is ever removed.
    fallback = Image.new("RGB", (900, 1200), (31, 38, 57))
    d = ImageDraw.Draw(fallback)
    d.rectangle((35, 35, 865, 1165), outline=(140, 153, 178), width=4)
    d.text((450, 540), "SOURCE\nPORTRAIT", font=get_font(56, True), anchor="mm", align="center", fill="white")
    d.text((450, 700), person, font=get_font(34), anchor="mm", align="center", fill=(190, 202, 220))
    return fallback


def background_from_photo(base: Image.Image, photo: Image.Image, accent: list[int]) -> Image.Image:
    photo_bg = ImageOps.fit(photo, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.34))
    photo_bg = ImageEnhance.Color(photo_bg).enhance(0.55)
    photo_bg = ImageEnhance.Brightness(photo_bg).enhance(0.42)
    photo_bg = photo_bg.filter(ImageFilter.GaussianBlur(20)).convert("RGBA")
    photo_bg.putalpha(94)
    output = Image.alpha_composite(base, photo_bg)
    tint = Image.new("RGBA", (W, H), rgba(accent, 28))
    return Image.alpha_composite(output, tint)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def paste_photo_card(
    canvas: Image.Image,
    photo: Image.Image,
    box: tuple[int, int, int, int],
    accent: list[int],
    centering: tuple[float, float] = (0.5, 0.32),
    mono: bool = False,
) -> None:
    """Paste a covered, rounded portrait with a thin accent frame and shadow."""
    x1, y1, x2, y2 = box
    pw, ph = x2 - x1, y2 - y1
    shadow = Image.new("RGBA", (pw + 24, ph + 24), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((12, 12, pw + 10, ph + 10), radius=25, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(11))
    canvas.alpha_composite(shadow, (x1 - 12, y1 - 2))

    fitted = ImageOps.fit(photo, (pw, ph), method=Image.Resampling.LANCZOS, centering=centering)
    if mono:
        fitted = ImageEnhance.Contrast(ImageOps.grayscale(fitted)).enhance(1.15).convert("RGB")
    card = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    card.paste(fitted.convert("RGBA"), (0, 0), rounded_mask((pw, ph), 20))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((1, 1, pw - 2, ph - 2), radius=20, outline=rgba(accent, 220), width=3)
    canvas.alpha_composite(card, (x1, y1))


def draw_header(canvas: Image.Image, ep: dict, section: str) -> None:
    d = ImageDraw.Draw(canvas)
    label_font = get_font(17, True)
    d.text((60, 43), f"EPISODE {ep['number']:02d}  /  05", font=label_font, fill=(219, 229, 244, 225))
    d.text((1220, 43), section, font=label_font, fill=rgba(ep["accent"], 255), anchor="ra")
    d.line((60, 70, 1220, 70), fill=rgba(ep["accent"], 110), width=2)


def base_scene(ep: dict, photo: Image.Image | None = None, phase: float = 0.0) -> Image.Image:
    canvas = gradient_background(ep["accent"], ep["accent2"], phase)
    if photo is not None:
        canvas = background_from_photo(canvas, photo, ep["accent"])
    return canvas


def draw_caption_card(
    canvas: Image.Image,
    title: str,
    body: str,
    x: int,
    y: int,
    width: int,
    accent: list[int],
    title_size: int = 28,
    body_size: int = 20,
) -> None:
    # Estimate height from text before constructing the translucent panel.
    probe = Image.new("RGBA", (1, 1))
    pd = ImageDraw.Draw(probe)
    body_lines = wrap_text(pd, body, get_font(body_size), width - 58)
    body_line_h = int(get_font(body_size).getbbox("Ag")[3] * 1.22)
    height = 74 + len(body_lines) * (body_line_h + 6) + 28
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((0, 0, width - 1, height - 1), radius=20, fill=(7, 11, 21, 210), outline=rgba(accent, 135), width=2)
    ld.rectangle((0, 0, 8, height), fill=rgba(accent, 255))
    ld.text((30, 23), title, font=get_font(title_size, True), fill=(255, 255, 255, 255))
    draw_wrapped(ld, (30, 61), body, get_font(body_size), (221, 229, 240, 245), width - 58, spacing=5)
    canvas.alpha_composite(layer, (x, y))


def scene_title(ep: dict) -> Image.Image:
    first = ep["people"][0]
    last = ep["people"][-1]
    p1 = open_photo(first["assets"]["then"], first["name"])
    p2 = open_photo(last["assets"]["now"], last["name"])
    canvas = base_scene(ep, p1, phase=0.2)
    draw_header(canvas, ep, "THE COLLECTION")
    # A strong two-portrait hook gives the opening a human face immediately.
    paste_photo_card(canvas, p1, (70, 128, 438, 600), ep["accent"], (0.5, 0.30), mono=True)
    paste_photo_card(canvas, p2, (843, 128, 1210, 600), ep["accent2"], (0.5, 0.28))
    d = ImageDraw.Draw(canvas)
    d.text((640, 175), ep["title"], font=get_font(48, True), anchor="ma", align="center", fill="white")
    d.text((640, 240), ep["strapline"], font=get_font(31, True), anchor="ma", fill=rgba(ep["accent"], 255))
    d.line((512, 302, 768, 302), fill=rgba(ep["accent"], 240), width=4)
    draw_wrapped(
        d,
        (640, 342),
        "Six faces. Six changing careers. Take a closer look at the portraits, the roles, and the years in between.",
        get_font(24),
        (226, 233, 244, 245),
        430,
        spacing=8,
        anchor="ma",
    )
    draw_pill(d, (545, 530, 735, 576), "PLAY ALONG", get_font(18, True), rgba(ep["accent2"], 220))
    d.text((640, 648), "HOLLYWOOD THEN & NOW", font=get_font(16, True), anchor="ma", fill=(205, 215, 230, 220))
    return canvas


def scene_compare(ep: dict, person: dict, position: int) -> Image.Image:
    old = open_photo(person["assets"]["then"], person["name"])
    new = open_photo(person["assets"]["now"], person["name"])
    canvas = base_scene(ep, old, phase=position * 0.6)
    draw_header(canvas, ep, f"PORTRAIT PAIR  {position + 1:02d} / 06")
    d = ImageDraw.Draw(canvas)
    d.text((640, 113), person["name"].upper(), font=get_font(47, True), anchor="ma", fill="white")
    d.text((640, 161), "THEN  •  NOW", font=get_font(20, True), anchor="ma", fill=rgba(ep["accent"], 255))
    paste_photo_card(canvas, old, (104, 202, 548, 528), ep["accent"], (0.5, 0.30), mono=True)
    paste_photo_card(canvas, new, (732, 202, 1176, 528), ep["accent2"], (0.5, 0.30))
    draw_pill(d, (185, 542, 467, 584), "EARLIER PORTRAIT", get_font(17, True), rgba(ep["accent"], 210))
    draw_pill(d, (815, 542, 1097, 584), "LATER PORTRAIT", get_font(17, True), rgba(ep["accent2"], 210))
    draw_caption_card(canvas, "ON SCREEN", person["card_copy"][0], 244, 612, 792, ep["accent"], 20, 19)
    return canvas


def scene_focus(ep: dict, person: dict, era: str, position: int) -> Image.Image:
    photo = open_photo(person["assets"][era], person["name"])
    is_then = era == "then"
    canvas = base_scene(ep, photo, phase=position + (0 if is_then else 0.8))
    draw_header(canvas, ep, "ARCHIVE FOCUS" if is_then else "LATER CHAPTER")
    d = ImageDraw.Draw(canvas)
    kicker = "EARLIER PORTRAIT" if is_then else "LATER PORTRAIT"
    d.text((68, 132), kicker, font=get_font(19, True), fill=rgba(ep["accent" if is_then else "accent2"], 255))
    d.text((68, 173), person["name"].upper(), font=get_font(43, True), fill="white")
    # Images alternate sides to keep the visual rhythm moving.
    if position % 2 == 0:
        photo_box = (584, 112, 1195, 605)
        text_x, text_w = 68, 460
    else:
        photo_box = (85, 112, 696, 605)
        text_x, text_w = 751, 450
    paste_photo_card(canvas, photo, photo_box, ep["accent"] if is_then else ep["accent2"], (0.5, 0.30), mono=is_then)
    chapter = "A FRAME FROM THE EARLIER STORY" if is_then else "A VIEW FROM THE LATER CHAPTER"
    insight = (
        "Compare the silhouette, the expression, and the way the public image has shifted. "
        "The person is familiar; the context is never quite the same."
        if is_then
        else "Careers do not move in straight lines. A newer portrait can hold the memory of every earlier role, while making room for a fresh chapter."
    )
    draw_caption_card(canvas, chapter, insight, text_x, 278, text_w, ep["accent"] if is_then else ep["accent2"], 18, 20)
    d.text((text_x, 612), "SOURCE DETAILS IN THE END CREDITS", font=get_font(14, True), fill=(206, 217, 232, 210))
    return canvas


def scene_story(ep: dict, person: dict, position: int) -> Image.Image:
    old = open_photo(person["assets"]["then"], person["name"])
    new = open_photo(person["assets"]["now"], person["name"])
    canvas = base_scene(ep, new, phase=position * 1.3)
    draw_header(canvas, ep, "THE YEARS IN BETWEEN")
    d = ImageDraw.Draw(canvas)
    d.text((70, 128), person["name"].upper(), font=get_font(48, True), fill="white")
    d.text((72, 184), "A CAREER IN MOTION", font=get_font(20, True), fill=rgba(ep["accent"], 255))
    paste_photo_card(canvas, old, (70, 235, 345, 568), ep["accent"], (0.5, 0.30), mono=True)
    paste_photo_card(canvas, new, (372, 235, 647, 568), ep["accent2"], (0.5, 0.30))
    d.line((70, 600, 647, 600), fill=rgba(ep["accent"], 180), width=2)
    d.text((70, 620), "EARLIER", font=get_font(15, True), fill=(211, 220, 235, 230))
    d.text((647, 620), "LATER", font=get_font(15, True), anchor="ra", fill=(211, 220, 235, 230))
    draw_caption_card(canvas, "WHY THIS FACE STAYS FAMILIAR", person["card_copy"][1], 710, 248, 492, ep["accent2"], 21, 24)
    draw_caption_card(canvas, "MEMORY CUE", person["card_copy"][0], 710, 466, 492, ep["accent"], 19, 19)
    return canvas


def scene_interlude(ep: dict) -> Image.Image:
    canvas = base_scene(ep, phase=2.7)
    draw_header(canvas, ep, "HALFWAY")
    d = ImageDraw.Draw(canvas)
    d.text((640, 250), "THREE MORE ICONS", font=get_font(55, True), anchor="ma", fill="white")
    d.text((640, 325), "Every face carries a different route through the movies.", font=get_font(25), anchor="ma", fill=(220, 230, 244, 240))
    draw_pill(d, (508, 405, 772, 453), "KEEP WATCHING", get_font(19, True), rgba(ep["accent"], 220))
    return canvas


def scene_outro(ep: dict) -> Image.Image:
    people = ep["people"]
    canvas = base_scene(ep, open_photo(people[-1]["assets"]["now"], people[-1]["name"]), phase=3.4)
    draw_header(canvas, ep, "END CARD")
    d = ImageDraw.Draw(canvas)
    d.text((640, 135), "WHICH ONE SURPRISED YOU?", font=get_font(43, True), anchor="ma", fill="white")
    d.text((640, 193), "A changing face is only one part of a changing career.", font=get_font(23), anchor="ma", fill=(221, 230, 244, 240))
    start_x = 113
    for index, person in enumerate(people):
        photo = open_photo(person["assets"]["now"], person["name"])
        x = start_x + index * 180
        paste_photo_card(canvas, photo, (x, 280, x + 144, 462), ep["accent2"], (0.5, 0.30))
        d.text((x + 72, 482), person["name"].split()[-1].upper(), font=get_font(14, True), anchor="ma", fill=(224, 232, 245, 245))
    d.text((640, 588), "SUBSCRIBE FOR THE NEXT THEN & NOW STORY", font=get_font(20, True), anchor="ma", fill=rgba(ep["accent"], 255))
    d.text((640, 640), "Narration and original score created for this collection. Photo sources are listed in the credits.", font=get_font(14), anchor="ma", fill=(201, 212, 229, 220))
    return canvas


# ---------------------------------------------------------------------------
# Scene, captions and credit output
# ---------------------------------------------------------------------------

def make_scenes(ep: dict, preview: bool = False) -> tuple[list[Scene], Path]:
    target = WORK / ep["id"] / "scenes"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[str, float, Image.Image]] = [("title", 12.0, scene_title(ep))]
    for index, person in enumerate(ep["people"][:3]):
        jobs += [
            (f"{index:02d}_comparison", 18.0, scene_compare(ep, person, index)),
            (f"{index:02d}_then", 14.0, scene_focus(ep, person, "then", index)),
            (f"{index:02d}_now", 14.0, scene_focus(ep, person, "now", index)),
            (f"{index:02d}_story", 29.0, scene_story(ep, person, index)),
        ]
    jobs.append(("interlude", 6.0, scene_interlude(ep)))
    for index, person in enumerate(ep["people"][3:], start=3):
        jobs += [
            (f"{index:02d}_comparison", 18.0, scene_compare(ep, person, index)),
            (f"{index:02d}_then", 14.0, scene_focus(ep, person, "then", index)),
            (f"{index:02d}_now", 14.0, scene_focus(ep, person, "now", index)),
            (f"{index:02d}_story", 29.0, scene_story(ep, person, index)),
        ]
    jobs.append(("outro", 12.0, scene_outro(ep)))

    total = sum(duration for _, duration, _ in jobs)
    if abs(total - 480.0) > 0.001:
        raise RuntimeError(f"Unexpected episode duration {total}; expected 480 seconds")

    if preview:
        # A useful review sample: immediate hook plus the first comparison.
        jobs = [("preview_title", 6.0, jobs[0][2]), ("preview_pair", 18.0, jobs[1][2])]

    scenes: list[Scene] = []
    for number, (label, duration, image) in enumerate(jobs):
        path = target / f"{number:02d}_{label}.jpg"
        image.convert("RGB").save(path, quality=94, optimize=True, progressive=True)
        scenes.append(Scene(label, path, duration))
    return scenes, target


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def audio_duration(path: Path) -> float:
    """Read a short narration clip's duration through the bundled FFmpeg."""
    result = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", result.stdout)
    if not match:
        raise RuntimeError(f"Could not determine narration duration: {path}")
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def subtitle_wrap(value: str, width: int = 49) -> str:
    words = value.split()
    lines: list[str] = []
    current = ""
    for word in words:
        proposal = word if not current else f"{current} {word}"
        if len(proposal) <= width:
            current = proposal
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def narration_cues(text: str, start: float, duration: float) -> list[tuple[float, float, str]]:
    """Distribute full-sentence captions in proportion to spoken word count."""
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    weights = [max(1, len(re.findall(r"[A-Za-z0-9]+", sentence))) for sentence in sentences]
    total = sum(weights) or 1
    cursor = start
    cues: list[tuple[float, float, str]] = []
    for index, (sentence, weight) in enumerate(zip(sentences, weights)):
        chunk = duration * weight / total
        # Preserve a small visual gap between sentences without losing the
        # final word of the preceding cue.
        end = start + duration if index == len(sentences) - 1 else cursor + max(1.20, chunk - 0.10)
        cues.append((cursor, end, subtitle_wrap(sentence)))
        cursor += chunk
    return cues


def write_srt(ep: dict, duration: float, preview: bool = False) -> Path:
    suffix = "_Preview" if preview else ""
    path = OUTPUT / f"{ep['number']:02d}_{ep['id']}_EN{suffix}.srt"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if preview:
        cues = [
            (0.0, 6.0, f"{ep['title'].title()} — Then & Now"),
            (6.0, 24.0, subtitle_wrap(f"{ep['people'][0]['name']} — {ep['people'][0]['card_copy'][1]}")),
        ]
    else:
        cues: list[tuple[float, float, str]] = [(0.0, 11.5, f"{ep['title'].title()} — Then & Now")]
        # The video uses atempo=0.94; captions follow the post-tempo length
        # rather than the original MP3 container duration.
        first_seconds = audio_duration(ROOT / ep["audio"]["a"]) / 0.94
        second_seconds = audio_duration(ROOT / ep["audio"]["b"]) / 0.94
        cues.extend(narration_cues(ep["narration"]["a"], 12.0, first_seconds))
        cues.append((237.0, 243.0, "Three more icons. Look closely at the portraits and the roles that made them familiar."))
        cues.extend(narration_cues(ep["narration"]["b"], 243.0, second_seconds))
        cues.append((468.0, 479.7, "Which early and later pairing surprised you most?"))

    chunks: list[str] = []
    for index, (start, end, text) in enumerate(cues, start=1):
        chunks += [str(index), f"{srt_time(start)} --> {srt_time(min(end, duration))}", text, ""]
    path.write_text("\n".join(chunks), encoding="utf-8")
    return path


def license_text(photo: dict) -> str:
    license_name = photo.get("license") or "Source page"
    artist = photo.get("artist") or "Credit on source page"
    title = photo.get("title") or "Portrait source"
    source = photo.get("source") or photo.get("url") or ""
    if source:
        return f"[{title}]({source}) — {artist}; {license_name}."
    return f"{title} — {artist}; {license_name}."


def write_credits(manifest: dict) -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Hollywood Then & Now — Five-Episode Collection Credits",
        "",
        "## Production",
        "- Format: 1280×720, 24 fps, 480 seconds per episode.",
        "- Narration: English synthetic narration rendered with the user-selected Arena voice.",
        "- Score: original procedural ambient instrumental generated locally for this collection; no third-party music recording is included.",
        "- Visual treatment: crop, layout, colour and motion treatment by this production. No AI face replacement or fabricated celebrity footage was used.",
        "",
        "## Photo-source note",
        "The primary sources for Episodes 1–4 are the already researched Wikimedia Commons records in this repository. Portrait working copies were normalized locally for video framing. For Episode 5, the linked Wikimedia Commons file pages are the authoritative license and attribution records. Retain this document with any public redistribution and re-check source-page license terms if replacing images.",
        "",
    ]
    for ep in manifest["episodes"]:
        lines += [f"## Episode {ep['number']:02d}: {ep['title'].title()}", ""]
        for person in ep["people"]:
            lines += [f"### {person['name']}", f"- Earlier portrait: {license_text(person['then'])}", f"- Later portrait: {license_text(person['now'])}", ""]
    lines += [
        "## Editorial note",
        "Film titles are used as factual references to the performers' careers. The video is an independent editorial compilation and implies no endorsement by featured people or rights holders.",
        "",
    ]
    path = OUTPUT / "Hollywood_Then_Now_5_Videos_Credits.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_collection_readme(manifest: dict) -> Path:
    lines = [
        "# Five Hollywood Then & Now Videos",
        "",
        "Five finished 8-minute English-language, 1280×720 videos created from this repository's Then & Now format.",
        "",
        "## Delivered MP4s",
    ]
    for ep in manifest["episodes"]:
        lines.append(f"- `{ep['filename']}` — {ep['title'].title()}")
    lines += [
        "",
        "Every MP4 contains an embedded English subtitle track; matching `.srt` files are included for upload platforms. The collection uses a user-approved English narration voice and an original procedural ambient score.",
        "",
        "## Re-render",
        "",
        "```bash",
        ".venv/bin/python batch5/create_manifest.py",
        ".venv/bin/python batch5/import_assets.py",
        ".venv/bin/python batch5/render_batch.py --all",
        "```",
        "",
        "See `Hollywood_Then_Now_5_Videos_Credits.md` for source/attribution records and `Batch_5_Validation.json` for the encoded-file checks.",
        "",
    ]
    path = OUTPUT / "README_5_Hollywood_Videos.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Audio / FFmpeg rendering helpers
# ---------------------------------------------------------------------------

def create_ambient_score() -> Path:
    """Generate a calm, royalty-free 72-second stereo loop once per batch."""
    path = ASSETS / "audio" / "original_ambient_score.wav"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    sr = 22_050
    seconds = 72
    t = np.arange(sr * seconds, dtype=np.float64) / sr
    # A slow chord progression with very low-level pulses. This is not sampled
    # music and has no melodic vocal content.
    chords = [(110.0, 138.59, 164.81), (98.0, 123.47, 146.83), (130.81, 164.81, 196.0), (110.0, 146.83, 174.61)]
    signal = np.zeros_like(t)
    for part, freqs in enumerate(chords):
        start = part * 18.0
        phase_t = np.clip(t - start, 0, 18)
        window = np.exp(-((phase_t - 9.0) / 7.8) ** 8)
        active = (t >= start) & (t < start + 18)
        for n, freq in enumerate(freqs):
            wobble = 0.10 * np.sin(2 * np.pi * (0.023 + n * 0.004) * phase_t)
            tone = np.sin(2 * np.pi * freq * (1 + wobble * 0.003) * phase_t + n * 0.8)
            signal += active * window * tone * (0.035 / (n + 1))
    # A faint synthetic shimmer, shaped into wide breaths instead of beats.
    shimmer = np.sin(2 * np.pi * 440 * t + 0.22 * np.sin(2 * np.pi * 0.08 * t))
    signal += shimmer * (0.004 + 0.004 * np.sin(2 * np.pi * t / 18.0) ** 2)
    fade = np.minimum(1.0, np.minimum(t / 2.0, (seconds - t) / 2.0))
    signal *= np.clip(fade, 0, 1)
    left = signal * (0.97 + 0.03 * np.sin(2 * np.pi * 0.031 * t))
    right = signal * (0.97 + 0.03 * np.cos(2 * np.pi * 0.027 * t))
    stereo = np.stack([left, right], axis=1)
    pcm = np.int16(np.clip(stereo, -1.0, 1.0) * 32767)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(sr)
        out.writeframes(pcm.tobytes())
    return path


def ffmpeg_output(command: list[str], title: str) -> None:
    print(f"\n[{title}]\n$ {' '.join(command[:8])} ...")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        print(result.stdout[-7000:])
        raise RuntimeError(f"FFmpeg failed while {title}")
    if result.stdout.strip():
        print(result.stdout[-1400:])


def build_filter(scenes: list[Scene], total_duration: float, include_second_voice: bool) -> str:
    visual_filters = []
    visual_labels = []
    for index, scene in enumerate(scenes):
        frames = max(1, int(round(scene.duration * FPS)))
        direction = 1 if index % 2 == 0 else -1
        # The generated scene is already 1280×720. A 6.5% zoom plus a tiny
        # sine-camera shift prevents long text cards from looking frozen.
        zoom = "min(zoom+0.00042,1.065)"
        x_expr = f"iw/2-(iw/zoom/2)+({direction})*sin(on/29)*6"
        y_expr = f"ih/2-(ih/zoom/2)+cos(on/37)*4"
        visual_filters.append(
            f"[{index}:v]zoompan=z='{zoom}':x='{x_expr}':y='{y_expr}':d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p[v{index}]"
        )
        visual_labels.append(f"[v{index}]")
    visual_filters.append("".join(visual_labels) + f"concat=n={len(scenes)}:v=1:a=0[vout]")

    ambient_index = len(scenes)
    voice_a_index = ambient_index + 1
    voice_b_index = ambient_index + 2
    # First narration begins on the first portrait pair. The second begins
    # immediately after the midpoint card. A gentle 0.94 tempo is intentional:
    # it retains natural articulation while giving the viewer time to read.
    audio_filters = [
        f"[{ambient_index}:a]aformat=channel_layouts=stereo,volume=0.26,atrim=duration={total_duration:.3f},afade=t=out:st={max(0, total_duration - 5):.3f}:d=5[bed]",
        f"[{voice_a_index}:a]aformat=channel_layouts=stereo,atempo=0.94,volume=1.0,adelay=12000|12000[voicea]",
    ]
    mix_labels = "[bed][voicea]"
    if include_second_voice:
        audio_filters.append(
            f"[{voice_b_index}:a]aformat=channel_layouts=stereo,atempo=0.94,volume=1.0,adelay=243000|243000[voiceb]"
        )
        mix_labels += "[voiceb]"
        count = 3
    else:
        count = 2
    audio_filters.append(
        f"{mix_labels}amix=inputs={count}:duration=first:normalize=0,alimiter=limit=0.96,atrim=duration={total_duration:.3f}[aout]"
    )
    return ";".join(visual_filters + audio_filters)


def render_episode(ep: dict, preview: bool = False) -> dict:
    scenes, work_scenes = make_scenes(ep, preview=preview)
    total_duration = sum(scene.duration for scene in scenes)
    srt = write_srt(ep, total_duration, preview=preview)
    ambient = create_ambient_score()
    audio_a = ROOT / ep["audio"]["a"]
    audio_b = ROOT / ep["audio"]["b"]
    for audio in (audio_a, audio_b):
        if not audio.exists():
            raise FileNotFoundError(f"Missing narration file: {audio}")

    temp = WORK / ep["id"] / ("preview_av.mp4" if preview else "master_av.mp4")
    temp.parent.mkdir(parents=True, exist_ok=True)
    final_name = (f"{ep['number']:02d}_{ep['id']}_Preview.mp4" if preview else ep["filename"])
    final = OUTPUT / final_name

    command = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    for scene in scenes:
        command += ["-i", str(scene.image)]
    command += ["-stream_loop", "-1", "-i", str(ambient), "-i", str(audio_a), "-i", str(audio_b)]
    include_second = total_duration > 243.5
    command += [
        "-filter_complex", build_filter(scenes, total_duration, include_second),
        "-map", "[vout]", "-map", "[aout]",
        "-t", f"{total_duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "112k", "-movflags", "+faststart",
        "-metadata", f"title={ep['title'].title()} — Then & Now",
        "-metadata", "comment=Independent editorial video; source credits supplied alongside.",
        str(temp),
    ]
    ffmpeg_output(command, f"render {ep['id']}")

    # Sidecar subtitles are also muxed into the master for media-player use.
    mux = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(temp), "-i", str(srt),
        "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0",
        "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
        "-metadata:s:s:0", "language=eng", "-metadata:s:s:0", "title=English",
        "-movflags", "+faststart", str(final),
    ]
    ffmpeg_output(mux, f"mux subtitles {ep['id']}")

    # The first frame is already a designed title frame and makes a consistent
    # thumbnail that accurately represents each episode.
    thumbnail = OUTPUT / f"{ep['number']:02d}_{ep['id']}_Thumbnail.jpg"
    with Image.open(scenes[0].image) as title_frame:
        title_frame.convert("RGB").save(thumbnail, quality=94, optimize=True, progressive=True)

    return {
        "episode": ep["id"],
        "output": str(final.relative_to(ROOT)),
        "subtitle": str(srt.relative_to(ROOT)),
        "thumbnail": str(thumbnail.relative_to(ROOT)),
        "duration_seconds": total_duration,
        "scene_count": len(scenes),
        "size_bytes": final.stat().st_size,
        "preview": preview,
    }


# ---------------------------------------------------------------------------
# Validation / packaging
# ---------------------------------------------------------------------------

def inspect_media(path: Path) -> dict:
    result = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = result.stdout
    duration_match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", output)
    stream_lines = [line.strip() for line in output.splitlines() if "Stream #" in line]
    duration = None
    if duration_match:
        duration = int(duration_match.group(1)) * 3600 + int(duration_match.group(2)) * 60 + float(duration_match.group(3))
    return {"path": str(path.relative_to(ROOT)), "size_bytes": path.stat().st_size, "duration_seconds": duration, "streams": stream_lines}


def validate_outputs(manifest: dict) -> Path:
    results = []
    for ep in manifest["episodes"]:
        path = OUTPUT / ep["filename"]
        if not path.exists():
            results.append({"episode": ep["id"], "exists": False})
            continue
        media = inspect_media(path)
        media["episode"] = ep["id"]
        media["expected_duration_seconds"] = 480
        media["duration_ok"] = media["duration_seconds"] is not None and abs(media["duration_seconds"] - 480) < 0.15
        media["has_h264"] = any("h264" in line for line in media["streams"])
        media["has_aac"] = any("aac" in line for line in media["streams"])
        media["has_english_subtitles"] = any("mov_text" in line for line in media["streams"])
        results.append(media)
    payload = {
        "collection": manifest["series"],
        "format": manifest["format"],
        "outputs": results,
        "all_files_exist": all(row.get("exists", True) for row in results),
        "all_durations_ok": all(row.get("duration_ok", False) for row in results),
    }
    path = OUTPUT / "Batch_5_Validation.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def package_outputs(manifest: dict) -> Path:
    zip_path = OUTPUT / "Hollywood_Then_Now_5_Video_Package.zip"
    wanted: list[Path] = []
    for ep in manifest["episodes"]:
        wanted += [OUTPUT / ep["filename"], OUTPUT / f"{ep['number']:02d}_{ep['id']}_EN.srt", OUTPUT / f"{ep['number']:02d}_{ep['id']}_Thumbnail.jpg"]
    wanted += [OUTPUT / "Hollywood_Then_Now_5_Videos_Credits.md", OUTPUT / "README_5_Hollywood_Videos.md", OUTPUT / "Batch_5_Validation.json"]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in wanted:
            if item.exists():
                archive.write(item, arcname=item.name)
    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render five Hollywood Then & Now videos")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--all", action="store_true", help="Render all five finished episodes")
    group.add_argument("--episode", help="Render a single episode id, e.g. 01_leading_men")
    parser.add_argument("--preview", action="store_true", help="Render a 24-second visual/audio review excerpt")
    parser.add_argument("--validate-only", action="store_true", help="Only inspect already-rendered full MP4 files")
    parser.add_argument("--package", action="store_true", help="Also create a ZIP copy of all finished deliverables")
    parser.add_argument("--package-only", action="store_true", help="Only create the collection ZIP from existing outputs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_manifest()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    if args.validate_only:
        path = validate_outputs(manifest)
        print(f"Validation written: {path}")
        return
    if args.package_only:
        path = package_outputs(manifest)
        print(f"Package written: {path}")
        return

    targets = manifest["episodes"]
    if args.episode:
        targets = [ep for ep in targets if ep["id"] == args.episode]
        if not targets:
            raise SystemExit(f"Unknown episode id: {args.episode}")
    elif not args.all:
        # Safe default for someone running the script locally: do not make all
        # five long encodes unless requested.
        targets = [manifest["episodes"][0]]

    report = []
    for ep in targets:
        print(f"\n{'=' * 72}\nRendering {ep['title']}\n{'=' * 72}")
        report.append(render_episode(ep, preview=args.preview))

    if not args.preview and len(targets) == len(manifest["episodes"]):
        credits = write_credits(manifest)
        readme = write_collection_readme(manifest)
        validation = validate_outputs(manifest)
        report.extend([
            {"credits": str(credits.relative_to(ROOT))},
            {"readme": str(readme.relative_to(ROOT))},
            {"validation": str(validation.relative_to(ROOT))},
        ])
        # A ZIP duplicates the five MP4 masters. It is deliberately opt-in so
        # ordinary renders do not retain another ~100 MB copy in the workspace.
        if args.package:
            package = package_outputs(manifest)
            report.append({"package": str(package.relative_to(ROOT))})
    report_path = OUTPUT / ("preview_render_report.json" if args.preview else "render_report.json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\nCompleted:")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
