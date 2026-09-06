#!/usr/bin/env python3
"""Premium style-review renderer for the Hollywood Then & Now collection.

This is deliberately frame-rendered (rather than a still-image zoompan
slideshow) so the background, masks, typography and photo camera moves share
one continuous 24 fps clock.  It is a review edit for Episode 01 and borrows
the editorial language of the repository's enhanced episode: a cinematic
opening, quiz/reveal beats, moving light ribbons, readable caption panels,
subtle light leaks, a ducked music bed and original transition accents.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
DELIVERY = ROOT.parent / "deliverables"
ASSETS = ROOT / "assets"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS, DURATION, SR = 1280, 720, 24, 60.0, 48_000
DARK = (10, 13, 23)
INK = (240, 245, 252)
MUTED = (163, 179, 199)
CYAN = (73, 216, 255)
VIOLET = (181, 112, 255)
GOLD = (255, 193, 91)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTS: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}
PHOTO_CACHE: dict[str, Image.Image] = {}
MASK_CACHE: dict[tuple[tuple[int, int], int], Image.Image] = {}
SHADOW_CACHE: dict[tuple[int, int], Image.Image] = {}
PREPARED_CROPS: dict[tuple[int, tuple[int, int], bool], Image.Image] = {}
PANEL_SHADOW_CACHE: dict[tuple[int, int], Image.Image] = {}
CAPTION_CACHE: dict[tuple[str, tuple[int, int, int]], Image.Image] = {}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (int(size), bold)
    if key not in FONTS:
        FONTS[key] = ImageFont.truetype(FONT_BOLD if bold else FONT, int(size))
    return FONTS[key]


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def smoothstep(value: float, start: float, end: float) -> float:
    return ease((value - start) / max(1e-6, end - start))


def alpha(color: tuple[int, int, int], amount: int) -> tuple[int, int, int, int]:
    return (*color, int(max(0, min(255, amount))))


def tracked_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, size: int, fill: tuple, spacing: float = 1.5, anchor: str = "la") -> None:
    face = font(size, True)
    width = sum(draw.textlength(letter, font=face) for letter in value) + spacing * max(0, len(value) - 1)
    x, y = xy
    if anchor in {"ma", "mm", "ms"}:
        x -= width / 2
    elif anchor in {"ra", "rm", "rs"}:
        x -= width
    for letter in value:
        draw.text((x, y), letter, font=face, fill=fill)
        x += draw.textlength(letter, font=face) + spacing


def draw_shadow_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, size: int, fill: tuple, anchor: str = "la") -> None:
    draw.text((xy[0] + 3, xy[1] + 4), value, font=font(size, True), fill=(0, 0, 0, 130), anchor=anchor)
    draw.text(xy, value, font=font(size, True), fill=fill, anchor=anchor)


def text_fit(draw: ImageDraw.ImageDraw, value: str, max_width: int, start: int) -> int:
    size = start
    while size > 18 and draw.textlength(value, font=font(size, True)) > max_width:
        size -= 1
    return size


def wrap(draw: ImageDraw.ImageDraw, value: str, width: int, size: int) -> list[str]:
    words = value.split()
    lines: list[str] = []
    line = ""
    for word in words:
        proposal = word if not line else f"{line} {word}"
        if line and draw.textlength(proposal, font=font(size)) > width:
            lines.append(line)
            line = word
        else:
            line = proposal
    if line:
        lines.append(line)
    return lines


def radial_background(t: float) -> Image.Image:
    """Low-resolution, smooth animated ribbons + bokeh; no frame-to-frame grain."""
    hh, ww = 180, 320
    y, x = np.mgrid[0:hh, 0:ww].astype(np.float32)
    nx, ny = x / ww, y / hh
    arr = np.empty((hh, ww, 3), np.float32)
    arr[:] = np.array(DARK, np.float32)
    centres = (
        (0.18 + .10 * math.sin(t * .19), 0.18 + .04 * math.cos(t * .16), CYAN, .42),
        (0.82 + .08 * math.cos(t * .14), 0.67 + .07 * math.sin(t * .17), VIOLET, .35),
        (0.50, 1.12, GOLD, .17),
    )
    for cx, cy, color, strength in centres:
        halo = np.exp(-(((nx - cx) / .37) ** 2 + ((ny - cy) / .45) ** 2) * 3.2)[..., None]
        arr += halo * np.asarray(color, np.float32) * strength
    # Two continuous sine ribbons live in the lower third.
    phase = t * .54
    ridge_a = .77 + .075 * np.sin(nx * 11.5 + phase)
    ridge_b = .87 + .055 * np.sin(nx * 21.0 - phase * 1.45)
    ribbon_a = np.exp(-((ny - ridge_a) / .10) ** 2)[..., None] * .24
    ribbon_b = np.exp(-((ny - ridge_b) / .065) ** 2)[..., None] * .17
    arr = arr * (1 - ribbon_a) + np.asarray(VIOLET, np.float32) * ribbon_a
    arr = arr * (1 - ribbon_b) + np.asarray(CYAN, np.float32) * ribbon_b
    vignette = ((nx - .5) ** 2 + (ny - .46) ** 2)[..., None]
    arr *= 1 - np.clip(vignette * .34, 0, .3)
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((W, H), Image.Resampling.BILINEAR).convert("RGBA")

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for index in range(9):
        px = 100 + ((index * 211 + t * (18 + index * 2.5)) % 1140)
        py = 470 + 110 * math.sin(t * (.34 + index * .025) + index * 1.8)
        radius = 4 + (index % 3) * 3
        d.ellipse((px - radius * 4, py - radius * 4, px + radius * 4, py + radius * 4), fill=alpha(CYAN if index % 2 else GOLD, 13))
        d.ellipse((px - radius, py - radius, px + radius, py + radius), fill=alpha((255, 255, 255), 60))
    return Image.alpha_composite(im, overlay)


def motion_crop(source: Image.Image, size: tuple[int, int], t: float, seed: int, mono: bool = False) -> Image.Image:
    """Continuous pan over a pre-scaled source; avoids per-frame resampling."""
    target_w, target_h = size
    key = (id(source), size, mono)
    if key not in PREPARED_CROPS:
        work = source.convert("RGB")
        if mono:
            work = ImageEnhance.Contrast(ImageOps.grayscale(work)).enhance(1.22).convert("RGB")
        # A 15% overscan reservoir permits a smooth pan with no resize jitter.
        scale = max((target_w * 1.18) / work.width, (target_h * 1.18) / work.height)
        resized = work.resize((round(work.width * scale), round(work.height * scale)), Image.Resampling.LANCZOS)
        PREPARED_CROPS[key] = resized
    work = PREPARED_CROPS[key]
    cx = .50 + .095 * math.sin(t * .17 + seed * 2.1)
    cy = .38 + .070 * math.cos(t * .13 + seed * .87)
    x = round((work.width - target_w) * max(0.0, min(1.0, cx)))
    y = round((work.height - target_h) * max(0.0, min(1.0, cy)))
    return work.crop((x, y, x + target_w, y + target_h))


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    key = (size, radius)
    if key not in MASK_CACHE:
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
        MASK_CACHE[key] = mask
    return MASK_CACHE[key]


def card_shadow(width: int, height: int) -> Image.Image:
    key = (width, height)
    if key not in SHADOW_CACHE:
        shadow = Image.new("RGBA", (width + 38, height + 38), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((18, 18, width + 18, height + 18), radius=28, fill=(0, 0, 0, 150))
        SHADOW_CACHE[key] = shadow.filter(ImageFilter.GaussianBlur(14))
    return SHADOW_CACHE[key]


def photo_card(canvas: Image.Image, source: Image.Image, box: tuple[int, int, int, int], t: float, seed: int, hue: tuple[int, int, int], mono: bool = False, dim: float = 0.0) -> None:
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    canvas.alpha_composite(card_shadow(width, height), (x1 - 18, y1 - 8))
    content = motion_crop(source, (width, height), t, seed, mono)
    if dim:
        content = ImageEnhance.Brightness(content).enhance(1 - dim)
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    card.paste(content.convert("RGBA"), (0, 0), rounded_mask((width, height), 23))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((1, 1, width - 2, height - 2), radius=23, outline=alpha(hue, 236), width=3)
    cd.rounded_rectangle((7, 7, width - 8, height - 8), radius=18, outline=(255, 255, 255, 38), width=1)
    canvas.alpha_composite(card, (x1, y1))


def soft_panel(canvas: Image.Image, box: tuple[int, int, int, int], accent: tuple[int, int, int], amount: int = 208) -> None:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    shadow_key = (w, h)
    if shadow_key not in PANEL_SHADOW_CACHE:
        shadow = Image.new("RGBA", (w + 24, h + 24), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((12, 12, w + 10, h + 10), radius=21, fill=(0, 0, 0, 135))
        PANEL_SHADOW_CACHE[shadow_key] = shadow.filter(ImageFilter.GaussianBlur(12))
    canvas.alpha_composite(PANEL_SHADOW_CACHE[shadow_key], (x1 - 12, y1 - 4))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((0, 0, w - 1, h - 1), radius=19, fill=(7, 10, 20, amount), outline=alpha(accent, 126), width=2)
    ld.rectangle((0, 15, 5, h - 15), fill=alpha(accent, 245))
    canvas.alpha_composite(layer, (x1, y1))


def caption_panel(canvas: Image.Image, text: str, accent: tuple[int, int, int], t: float) -> None:
    key = (text, accent)
    if key not in CAPTION_CACHE:
        layer = Image.new("RGBA", (W, 88), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((52, 6, 1228, 82), radius=20, fill=(5, 8, 16, 190), outline=alpha(accent, 102), width=2)
        lines = wrap(d, text, 1080, 23)[:2]
        first_y = 21 if len(lines) == 1 else 11
        for index, line in enumerate(lines):
            draw_shadow_text(d, (640, first_y + index * 30), line, 23, INK, anchor="ma")
        d.rounded_rectangle((69, 21, 74, 66), radius=3, fill=alpha(accent, 150))
        CAPTION_CACHE[key] = layer
    canvas.alpha_composite(CAPTION_CACHE[key], (0, 622))


def header(canvas: Image.Image, right: str, progress: float) -> None:
    d = ImageDraw.Draw(canvas)
    tracked_text(d, (58, 32), "THE SCREEN ARCHIVE", 12, alpha(INK, 215), 2.2)
    tracked_text(d, (1222, 32), right, 11, alpha(CYAN, 235), 1.2, "ra")
    d.line((58, 64, 1222, 64), fill=alpha(CYAN, 115), width=2)
    d.rectangle((58, 65, 58 + round(1164 * max(0, min(1, progress))), 68), fill=alpha(VIOLET, 210))


def photo_background(canvas: Image.Image, source: Image.Image, t: float, seed: int) -> Image.Image:
    # Blur at quarter resolution before upscaling: visually soft, much faster.
    backdrop = motion_crop(source, (320, 180), t * .52, seed)
    backdrop = ImageEnhance.Color(backdrop).enhance(.55)
    backdrop = ImageEnhance.Brightness(backdrop).enhance(.34).filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.Resampling.BILINEAR).convert("RGBA")
    backdrop.putalpha(104)
    overlay = Image.alpha_composite(canvas, backdrop)
    overlay = Image.alpha_composite(overlay, Image.new("RGBA", (W, H), (8, 12, 22, 92)))
    return overlay


def montage_frame(t: float, people: list[dict]) -> Image.Image:
    canvas = radial_background(t)
    widths = [420, 420, 440]
    for index, (person, width) in enumerate(zip((people[0], people[1], people[3]), widths)):
        source = open_photo(person["assets"]["then" if index != 1 else "now"])
        x = sum(widths[:index])
        crop = motion_crop(source, (width + 28, H), t * .55, index, mono=(index == 0))
        crop = ImageEnhance.Brightness(crop).enhance(.68).convert("RGBA")
        crop.putalpha(165)
        canvas.alpha_composite(crop, (x - 14, 0))
        canvas.alpha_composite(Image.new("RGBA", (width, H), alpha(DARK, 86)), (x, 0))
        canvas.alpha_composite(Image.new("RGBA", (4, H), alpha(CYAN if index != 2 else GOLD, 190)), (max(0, x - 2), 0))
    veil = Image.new("RGBA", (W, H), (3, 7, 14, 82))
    canvas = Image.alpha_composite(canvas, veil)
    d = ImageDraw.Draw(canvas)
    header(canvas, "STYLE PREVIEW  /  01", 0.0)
    start = smoothstep(t, 0.2, 1.0)
    y = 202 - round(22 * (1 - start))
    tracked_text(d, (640, y), "HOLLYWOOD", 20, alpha(CYAN, int(255 * start)), 5, "ma")
    draw_shadow_text(d, (640, y + 42), "THEN & NOW", 82, alpha(INK, int(255 * start)), "ma")
    draw_shadow_text(d, (640, y + 132), "SIX ICONS. SIX CHANGING STORIES.", 22, alpha(GOLD, int(255 * start)), "ma")
    d.rounded_rectangle((484, 440, 796, 488), radius=24, fill=alpha((8, 12, 24), 202), outline=alpha(VIOLET, 190), width=2)
    tracked_text(d, (640, 455), "PLAY ALONG", 15, alpha(INK, int(245 * start)), 2.5, "ma")
    caption_panel(canvas, "A cinematic quiz format with real portrait comparisons, original music and transition sound design.", CYAN, t)
    return canvas


def reveal_mask(blank: Image.Image, photo: Image.Image, q: float, mode: int) -> Image.Image:
    if q <= 0:
        return blank
    if q >= 1:
        return photo
    p = ease(q)
    aa, bb = np.asarray(blank.convert("RGB"), dtype=np.float32), np.asarray(photo.convert("RGB"), dtype=np.float32)
    h, w = aa.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    if mode % 3 == 0:
        plane = xx / w + .48 * yy / h
        mask = np.clip((1.20 * p - .12 - plane) / .055, 0, 1)[..., None]
    elif mode % 3 == 1:
        distance = np.sqrt((xx - w * .5) ** 2 + (yy - h * .45) ** 2)
        mask = np.clip((p * max(w, h) * .78 - distance) / 18, 0, 1)[..., None]
    else:
        edge = (w + 60) * p - 30
        mask = np.clip((edge - xx) / 20, 0, 1)[..., None]
    return Image.fromarray(np.clip(aa * (1 - mask) + bb * mask, 0, 255).astype(np.uint8))


def quiz_placeholder(size: tuple[int, int], seconds: int) -> Image.Image:
    w, h = size
    im = Image.new("RGB", size, (20, 22, 35))
    d = ImageDraw.Draw(im)
    for x in range(-h, w + h, 44):
        d.line((x, 0, x - h, h), fill=(44, 39, 62), width=1)
    tracked_text(d, (w / 2, h * .22), "WHO IS THIS?", 15, alpha(VIOLET, 255), 2.2, "ma")
    d.ellipse((w / 2 - 62, h / 2 - 34, w / 2 + 62, h / 2 + 90), outline=alpha(CYAN, 220), width=3)
    d.arc((w / 2 - 62, h / 2 - 34, w / 2 + 62, h / 2 + 90), -90, 220, fill=alpha(GOLD, 255), width=6)
    draw_shadow_text(d, (w / 2, h / 2 - 12), str(seconds), 74, INK, "mm")
    tracked_text(d, (w / 2, h * .75), "SECONDS", 11, alpha(MUTED, 255), 2.0, "ma")
    return im


def profile_frame(t: float, person: dict, progress: float) -> Image.Image:
    old, new = open_photo(person["assets"]["then"]), open_photo(person["assets"]["now"])
    canvas = photo_background(radial_background(t), new, t, 4)
    local = t - 8.0
    header(canvas, "PORTRAIT REVEAL  /  01 OF 06", progress)
    d = ImageDraw.Draw(canvas)
    if local < 4.0:
        # Quiz beat: old portrait establishes a face while the later card stays concealed.
        draw_shadow_text(d, (640, 104), "CAN YOU PLACE THIS FACE?", 43, INK, "ma")
        tracked_text(d, (640, 159), "A MOVIE STAR BEFORE THE NEXT CHAPTER", 13, alpha(CYAN, 255), 2.0, "ma")
        photo_card(canvas, old, (94, 194, 592, 565), t, 0, CYAN, mono=True)
        seconds = max(1, 4 - int(local))
        blank = quiz_placeholder((498, 371), seconds)
        card = Image.new("RGBA", blank.size, (0, 0, 0, 0)); card.paste(blank.convert("RGBA"), (0, 0), rounded_mask(blank.size, 23))
        ImageDraw.Draw(card).rounded_rectangle((1, 1, 496, 369), radius=23, outline=alpha(VIOLET, 240), width=3)
        canvas.alpha_composite(card, (688, 194))
        caption_panel(canvas, "Look for the expression, the silhouette and the screen presence before the reveal.", VIOLET, t)
        return canvas

    if local < 8.0:
        q = (local - 4.0) / 3.2
        draw_shadow_text(d, (640, 104), person["name"].upper(), 52, INK, "ma")
        tracked_text(d, (640, 162), "THE REVEAL", 13, alpha(GOLD, 255), 2.6, "ma")
        photo_card(canvas, old, (94, 194, 592, 565), t, 0, CYAN, mono=True)
        target = motion_crop(new, (498, 371), t, 1)
        hidden = quiz_placeholder((498, 371), 0)
        shown = reveal_mask(hidden, target, q, 0)
        layer = Image.new("RGBA", (498, 371), (0, 0, 0, 0)); layer.paste(shown.convert("RGBA"), (0, 0), rounded_mask((498, 371), 23))
        ld = ImageDraw.Draw(layer); ld.rounded_rectangle((1, 1, 496, 369), radius=23, outline=alpha(GOLD, 245), width=3)
        canvas.alpha_composite(layer, (688, 194))
        # Soft light leak sweeps the reveal rather than using a harsh flash.
        leak = smoothstep(q, .0, 1.0) * (1 - smoothstep(q, .72, 1.0))
        if leak:
            strip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            x = int(500 + 900 * ease(q))
            ImageDraw.Draw(strip).ellipse((x - 180, -240, x + 180, 980), fill=alpha(GOLD, int(65 * leak)))
            canvas = Image.alpha_composite(canvas, strip.filter(ImageFilter.GaussianBlur(80)))
        caption_panel(canvas, "The familiar face returns — now with years of roles, risks and reinvention behind it.", GOLD, t)
        return canvas

    if local < 22.0:
        q = (local - 8.0) / 14.0
        draw_shadow_text(d, (640, 102), person["name"].upper(), 49, INK, "ma")
        tracked_text(d, (640, 156), "THEN  /  NOW", 13, alpha(CYAN, 255), 2.6, "ma")
        photo_card(canvas, old, (73, 188, 610, 568), t, 0, CYAN, mono=True)
        photo_card(canvas, new, (670, 188, 1207, 568), t, 1, GOLD)
        d.rounded_rectangle((214, 579, 469, 620), radius=20, fill=alpha(CYAN, 210))
        d.rounded_rectangle((811, 579, 1066, 620), radius=20, fill=alpha(GOLD, 210))
        tracked_text(d, (342, 590), "EARLIER PORTRAIT", 11, alpha(DARK, 255), 1.3, "ma")
        tracked_text(d, (939, 590), "LATER PORTRAIT", 11, alpha(DARK, 255), 1.3, "ma")
        # Smooth scan-line traverses the frame with the continuous profile clock.
        x = int(73 + 1134 * q)
        d.line((x, 176, x, 605), fill=alpha(INK, 95), width=2)
        d.line((x + 3, 176, x + 3, 605), fill=alpha(CYAN, 82), width=1)
        caption_panel(canvas, person["card_copy"][0], CYAN, t)
        return canvas

    if local < 36.0:
        q = (local - 22.0) / 14.0
        canvas = photo_background(radial_background(t), new, t * 1.08, 3)
        header(canvas, "CAREER MOMENT  /  01", progress)
        photo_card(canvas, new, (679, 98, 1208, 588), t, 3, GOLD)
        soft_panel(canvas, (62, 154, 624, 486), VIOLET)
        d = ImageDraw.Draw(canvas)
        tracked_text(d, (93, 185), "A CAREER IN MOTION", 13, alpha(CYAN, 255), 2.0)
        title_size = text_fit(d, person["name"].upper(), 502, 52)
        draw_shadow_text(d, (93, 222), person["name"].upper(), title_size, INK)
        lines = wrap(d, person["card_copy"][1], 478, 25)
        for index, line in enumerate(lines[:4]):
            d.text((93, 315 + index * 36), line, font=font(25), fill=alpha(INK, 242))
        d.line((93, 453, 512, 453), fill=alpha(GOLD, 170), width=2)
        tracked_text(d, (93, 467), "ARCHIVE  •  REINVENTION  •  SCREEN PRESENCE", 10, alpha(MUTED, 255), 1.3)
        caption_panel(canvas, "Smooth camera drift, layered depth and a deliberate pause give each comparison room to land.", VIOLET, t)
        return canvas

    # A polished exit card becomes the runway into the next icon rather than a cut.
    q = (local - 36.0) / 8.0
    canvas = photo_background(radial_background(t), old, t, 0)
    header(canvas, "NEXT ICON  /  02 OF 06", progress)
    photo_card(canvas, old, (129, 128, 535, 576), t, 0, CYAN, mono=True)
    photo_card(canvas, new, (745, 128, 1151, 576), t, 1, GOLD)
    d = ImageDraw.Draw(canvas)
    draw_shadow_text(d, (640, 208), "ONE FACE.", 50, INK, "ma")
    draw_shadow_text(d, (640, 268), "MANY CHAPTERS.", 50, alpha(GOLD, 255), "ma")
    tracked_text(d, (640, 350), "THE NEXT REVEAL IS ALREADY ON ITS WAY", 12, alpha(CYAN, 255), 2.2, "ma")
    pulse = .5 + .5 * math.sin(t * 4.5)
    d.ellipse((630 - 12, 423 - 12, 630 + 12, 423 + 12), fill=alpha(GOLD, int(120 + 115 * pulse)))
    d.line((652, 423, 735, 423), fill=alpha(GOLD, int(110 + 120 * pulse)), width=2)
    caption_panel(canvas, "A premium edit should feel like a guided journey, not a sequence of frozen slides.", GOLD, t)
    return canvas


def next_teaser(t: float, person: dict) -> Image.Image:
    canvas = photo_background(radial_background(t), open_photo(person["assets"]["then"]), t, 9)
    header(canvas, "NEXT  /  02 OF 06", (t - 8) / 52)
    d = ImageDraw.Draw(canvas)
    photo_card(canvas, open_photo(person["assets"]["then"]), (294, 90, 986, 588), t, 9, VIOLET, mono=True, dim=.22)
    draw_shadow_text(d, (640, 149), "NEXT UP", 25, alpha(CYAN, 255), "ma")
    draw_shadow_text(d, (640, 550), person["name"].upper(), 49, INK, "ma")
    caption_panel(canvas, "The full rebuild keeps this rhythm across all five episodes — with varied reveal masks, music accents and chapter transitions.", VIOLET, t)
    return canvas


def open_photo(relative: str) -> Image.Image:
    if relative not in PHOTO_CACHE:
        path = ROOT / relative
        if not path.exists():
            # Stable compact crops are committed for premium rebuilds; the
            # larger local asset cache is optional and intentionally ignored.
            path = ROOT / "reference_portraits" / Path(relative).relative_to("assets/photos")
        with Image.open(path) as im:
            PHOTO_CACHE[relative] = ImageOps.exif_transpose(im).convert("RGB")
    return PHOTO_CACHE[relative]


def frame(t: float, episode: dict) -> Image.Image:
    people = episode["people"]
    if t < 8.0:
        im = montage_frame(t, people)
    elif t < 52.0:
        im = profile_frame(t, people[0], (t - 8) / 52)
    else:
        im = next_teaser(t, people[1])
    # A restrained footer indicator continuously confirms editorial progress.
    d = ImageDraw.Draw(im)
    d.rectangle((0, 716, W, 719), fill=(30, 42, 62))
    d.rectangle((0, 716, round(W * t / DURATION), 719), fill=alpha(CYAN, 230))
    return im.convert("RGB")


def decode_mono(path: Path) -> np.ndarray:
    result = subprocess.run(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "pipe:1"],
        capture_output=True,
        check=True,
    )
    return np.frombuffer(result.stdout, dtype="<f4").copy()


def envelope(length: int, attack: float, release: float, sr: int = SR) -> np.ndarray:
    rise = max(1, round(attack * sr)); fall = max(1, round(release * sr))
    body = max(0, length - rise - fall)
    return np.concatenate((np.linspace(0, 1, rise, dtype=np.float32), np.ones(body, np.float32), np.linspace(1, 0, fall, dtype=np.float32)))[:length]


def build_soundtrack() -> Path:
    """Create a richer original music bed and restrained non-verbal effects."""
    destination = ROOT / "work" / "premium_preview_mix.wav"
    destination.parent.mkdir(parents=True, exist_ok=True)
    n = round(DURATION * SR)
    rng = np.random.default_rng(8241)
    music = np.zeros((n, 2), np.float32)
    beat = 60.0 / 96.0
    chord_roots = [110.0, 130.81, 146.83, 123.47]
    # Warm pad changes every eight seconds.
    for segment, start in enumerate(np.arange(0, DURATION, 8.0)):
        end = min(DURATION, start + 8.0)
        a, b = round(start * SR), round(end * SR)
        tt = np.arange(b - a, dtype=np.float32) / SR
        root = chord_roots[segment % len(chord_roots)]
        fade = envelope(len(tt), .42, .8)
        pad = sum(np.sin(2 * np.pi * root * ratio * tt + phase) for ratio, phase in ((1, 0), (1.5, .45), (2.0, .9)))
        pad *= (.018 * fade * (0.80 + .20 * np.sin(2 * np.pi * .09 * tt)))
        music[a:b, 0] += pad
        music[a:b, 1] += pad * .96
    # Kicks, hats and a filtered noise snare establish a film-trailer pulse.
    for start in np.arange(.0, DURATION, beat):
        a = round(start * SR); length = min(round(.18 * SR), n - a)
        tt = np.arange(length, dtype=np.float32) / SR
        pitch = 112 * np.exp(-tt * 17) + 46
        kick = np.sin(2 * np.pi * pitch * tt) * np.exp(-tt * 17) * .17
        music[a:a + length] += kick[:, None]
        hstart = a + round(beat * .5 * SR)
        hlen = min(round(.045 * SR), n - hstart)
        if hlen > 0:
            noise = rng.normal(0, 1, hlen).astype(np.float32)
            high = noise - np.concatenate(([0.0], noise[:-1]))
            hat = high * np.exp(-np.arange(hlen) / (SR * .012)) * .018
            music[hstart:hstart + hlen, 0] += hat * .70
            music[hstart:hstart + hlen, 1] += hat
    # A small syncopated arpeggio opens up after the title.
    scale = [1.0, 1.25, 1.5, 2.0, 1.5, 1.25]
    for note_index, start in enumerate(np.arange(2.5, 52.0, beat * .5)):
        a = round(start * SR); length = min(round(.23 * SR), n - a)
        tt = np.arange(length, dtype=np.float32) / SR
        root = chord_roots[int(start // 8) % len(chord_roots)]
        freq = root * 2 * scale[note_index % len(scale)]
        env = np.exp(-tt * 8.5)
        pluck = (np.sin(2 * np.pi * freq * tt) + .22 * np.sin(2 * np.pi * freq * 2 * tt)) * env * .040
        pan = .35 + .3 * math.sin(note_index * 1.7)
        music[a:a + length, 0] += pluck * (1 - pan)
        music[a:a + length, 1] += pluck * pan

    def swish(start: float, duration: float = .46, gain: float = .055) -> None:
        a = round(start * SR); length = min(round(duration * SR), n - a)
        if length <= 0:
            return
        tt = np.arange(length, dtype=np.float32) / SR
        noise = rng.normal(0, 1, length).astype(np.float32)
        high = noise - np.concatenate(([0.0], noise[:-1]))
        sweep = high * np.sin(np.pi * tt / duration) ** 2 * gain
        pan = np.linspace(.12, .88, length, dtype=np.float32)
        music[a:a + length, 0] += sweep * (1 - pan)
        music[a:a + length, 1] += sweep * pan

    def impact(start: float, gain: float = .12) -> None:
        a = round(start * SR); length = min(round(.24 * SR), n - a)
        tt = np.arange(length, dtype=np.float32) / SR
        tone = np.sin(2 * np.pi * (88 * np.exp(-tt * 13) + 44) * tt) * np.exp(-tt * 15) * gain
        music[a:a + length] += tone[:, None]

    for event in (7.55, 12.0, 16.0, 30.0, 44.0, 52.0):
        swish(event)
    for event in (12.0, 16.0, 52.0):
        impact(event)

    # The spoken style-review line remains the focus through a smooth duck.
    voice = decode_mono(ASSETS / "audio" / "premium_style_preview_voice.mp3")
    voice_start = round(2.0 * SR)
    voice_end = min(n, voice_start + len(voice))
    voice_track = np.zeros(n, np.float32)
    voice_track[voice_start:voice_end] = voice[:voice_end - voice_start]
    bed_gain = np.ones(n, np.float32)
    duck_start, duck_end = max(0, voice_start - round(.25 * SR)), min(n, voice_end + round(.55 * SR))
    bed_gain[duck_start:voice_start] = np.linspace(1, .36, voice_start - duck_start, dtype=np.float32)
    bed_gain[voice_start:voice_end] = .36
    bed_gain[voice_end:duck_end] = np.linspace(.36, 1, duck_end - voice_end, dtype=np.float32)
    music *= bed_gain[:, None]
    music[:round(.55 * SR)] *= np.linspace(0, 1, round(.55 * SR), dtype=np.float32)[:, None]
    music[-round(1.6 * SR):] *= np.linspace(1, 0, round(1.6 * SR), dtype=np.float32)[:, None]
    mix = music + voice_track[:, None] * 1.04
    peak = float(np.max(np.abs(mix)))
    if peak > .92:
        mix *= .92 / peak
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    with wave.open(str(destination), "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(pcm.tobytes())
    return destination


def write_srt() -> Path:
    path = DELIVERY / "Premium_Style_Preview_EN.srt"
    cues = [
        (0, 7.7, "Hollywood Then & Now — premium motion and sound-design style preview."),
        (8, 12, "Can you place this face?"),
        (12, 22, "Tom Cruise — earlier portrait and later chapter."),
        (22, 44, "A premium edit should let the comparison breathe, then guide the viewer forward."),
        (52, 59.7, "Next up: Leonardo DiCaprio."),
    ]
    def stamp(value: float) -> str:
        ms = int(round(value * 1000)); h, ms = divmod(ms, 3_600_000); m, ms = divmod(ms, 60_000); s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines = []
    for index, (start, end, text) in enumerate(cues, 1):
        lines += [str(index), f"{stamp(start)} --> {stamp(end)}", text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def render() -> Path:
    manifest = json.loads((ROOT / "episodes.json").read_text())
    episode = manifest["episodes"][0]
    DELIVERY.mkdir(parents=True, exist_ok=True)
    soundtrack, subtitles = build_soundtrack(), write_srt()
    temporary = ROOT / "work" / "premium_style_preview_video.mp4"
    temporary.parent.mkdir(parents=True, exist_ok=True)
    command = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
        "-i", str(soundtrack), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-af", "loudnorm=I=-15.5:TP=-1.8:LRA=8",
        "-t", f"{DURATION:.3f}", "-movflags", "+faststart", str(temporary),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for index in range(round(DURATION * FPS)):
            if index % (FPS * 5) == 0:
                print(f"PREMIUM_FRAME {index // FPS:02d}/{int(DURATION):02d}", flush=True)
            process.stdin.write(frame(index / FPS, episode).tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("FFmpeg video encode failed")
    except BaseException:
        process.kill()
        raise
    final = DELIVERY / "Premium_Style_Preview.mp4"
    mux = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(temporary), "-i", str(subtitles),
        "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0", "-c", "copy", "-c:s", "mov_text",
        "-metadata", "title=Hollywood Then & Now — Premium Style Preview",
        "-metadata:s:s:0", "language=eng", "-disposition:s:0", "default", "-movflags", "+faststart", str(final),
    ]
    subprocess.run(mux, check=True)
    print(final, flush=True)
    return final


if __name__ == "__main__":
    render()
