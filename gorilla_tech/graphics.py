"""
Procedural graphics toolkit — the "military-tech documentary" look.

Everything is drawn locally (Pillow + numpy), so the pipeline never depends on
stock footage or third-party templates. The visual vocabulary mirrors the
reference channel: dark tactical maps, HUD panels, spec dossiers, animated
counters, timeline clocks and big stat callouts.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

import config
import util

P = config.PALETTE
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


# ─────────────────────────────────────────────────────────────
# Fonts & text
# ─────────────────────────────────────────────────────────────

def font(size: int, kind: str = "bold") -> ImageFont.FreeTypeFont:
    name = {"bold": config.FONT_BOLD, "regular": config.FONT_REGULAR,
            "mono": config.FONT_MONO}.get(kind, config.FONT_BOLD)
    key = (name, size)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached
    path = util.find_font(name) or util.find_font("DejaVuSans-Bold.ttf")
    loaded = ImageFont.truetype(str(path), size) if path else ImageFont.load_default()
    _FONT_CACHE[key] = loaded
    return loaded


def text_size(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
    return right - left, bottom - top


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if text_size(draw, trial, f)[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_font_size(draw: ImageDraw.ImageDraw, text: str, max_width: int,
                  max_size: int, min_size: int = 14, kind: str = "bold") -> ImageFont.FreeTypeFont:
    size = max_size
    while size > min_size:
        candidate = font(size, kind)
        if text_size(draw, text, candidate)[0] <= max_width:
            return candidate
        size -= 2
    return font(min_size, kind)


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str,
              f: ImageFont.FreeTypeFont, fill=P["text"], anchor: str | None = None,
              shadow: int = 3, shadow_color=(0, 0, 0), stroke: int = 0) -> tuple[int, int]:
    x, y = xy
    if shadow:
        draw.text((x + shadow, y + shadow), text, font=f, fill=shadow_color, anchor=anchor)
    draw.text((x, y), text, font=f, fill=fill, anchor=anchor,
              stroke_width=stroke, stroke_fill=shadow_color)
    return text_size(draw, text, f)


def draw_wrapped(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str,
                 f: ImageFont.FreeTypeFont, fill=P["text"], align: str = "left",
                 line_spacing: float = 1.22, shadow: int = 2) -> int:
    """Draw wrapped text inside box; returns the y coordinate after the last line."""
    x0, y0, x1, _ = box
    width = max(10, x1 - x0)
    lines = wrap(draw, text, f, width)
    line_h = int(text_size(draw, "Ag", f)[1] * line_spacing)
    y = y0
    for line in lines:
        w = text_size(draw, line, f)[0]
        x = x0 + {"left": 0, "center": (width - w) // 2, "right": width - w}[align]
        draw_text(draw, (x, y), line, f, fill=fill, shadow=shadow)
        y += line_h
    return y


# ─────────────────────────────────────────────────────────────
# Base surfaces
# ─────────────────────────────────────────────────────────────

def value_noise(width: int, height: int, cells: float = 6.0, octaves: int = 4,
                persistence: float = 0.52, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros((height, width), np.float32)
    amplitude, total, freq = 1.0, 0.0, cells
    for _ in range(octaves):
        gh = max(2, int(freq) + 2)
        gw = max(2, int(freq * width / max(1, height)) + 2)
        grid = rng.random((gh, gw), dtype=np.float32)
        smooth = np.asarray(
            Image.fromarray((grid * 255).astype(np.uint8)).resize((width, height), Image.BICUBIC),
            dtype=np.float32,
        ) / 255.0
        out += smooth * amplitude
        total += amplitude
        amplitude *= persistence
        freq *= 2.05
    return out / max(total, 1e-6)


def gradient(width: int, height: int, top=P["bg_top"], bottom=P["bg_bottom"],
             angle: float = 90.0) -> np.ndarray:
    if angle == 90:
        t = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None].repeat(width, 1)
    else:
        t = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :].repeat(height, 0)
    a = np.asarray(top, np.float32)[None, None, :]
    b = np.asarray(bottom, np.float32)[None, None, :]
    return (a + (b - a) * t[..., None]).astype(np.uint8)


def vignette(arr: np.ndarray, strength: float = 0.55) -> np.ndarray:
    h, w = arr.shape[:2]
    y = np.linspace(-1, 1, h, dtype=np.float32)[:, None]
    x = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
    d = np.sqrt((x * 1.06) ** 2 + (y * 1.06) ** 2)
    mask = 1.0 - strength * np.clip((d - 0.35) / 1.05, 0, 1) ** 1.7
    return (arr.astype(np.float32) * mask[..., None]).astype(np.uint8)


def grain(arr: np.ndarray, amount: float = 3.2, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, amount, arr.shape[:2]).astype(np.float32)
    return np.clip(arr.astype(np.float32) + noise[..., None], 0, 255).astype(np.uint8)


def scanlines(arr: np.ndarray, alpha: float = 0.05, period: int = 3) -> np.ndarray:
    h = arr.shape[0]
    mask = np.ones(h, np.float32)
    mask[::period] = 1.0 - alpha
    return (arr.astype(np.float32) * mask[:, None, None]).astype(np.uint8)


def grid_overlay(img: Image.Image, spacing: int = 80, color=P["grid"], alpha: int = 60) -> None:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    w, h = img.size
    for x in range(0, w, spacing):
        d.line([(x, 0), (x, h)], fill=(*color, alpha), width=1)
    for y in range(0, h, spacing):
        d.line([(0, y), (w, y)], fill=(*color, alpha), width=1)
    img.alpha_composite(overlay)


def dark_base(width: int, height: int, seed: int = 3, terrain: float = 0.0,
              tint: tuple[int, int, int] | None = None) -> Image.Image:
    """Standard scene background: vertical gradient + optional terrain noise + vignette."""
    arr = gradient(width, height)
    if terrain > 0:
        noise = value_noise(width, height, cells=4.5, octaves=5, seed=seed)
        shade = (noise - 0.5) * 2.0 * terrain * 96.0
        base = np.asarray(tint or (22, 30, 26), np.float32)[None, None, :]
        land = np.clip(base + shade[..., None], 0, 255)
        # contour isolines give the topographic-map read
        bands = noise * 9.0
        contour = np.abs(bands - np.round(bands)) < 0.05
        land = np.where(contour[..., None], np.clip(land * 1.5 + 16, 0, 255), land)
        weight = np.clip(0.62 + noise * 0.38, 0, 1)[..., None] * min(1.0, terrain * 1.7)
        arr = (arr.astype(np.float32) * (1 - weight * 0.82) + land * weight * 0.82).astype(np.uint8)
    arr = vignette(arr, 0.5)
    return Image.fromarray(arr, "RGB")


# ─────────────────────────────────────────────────────────────
# HUD components
# ─────────────────────────────────────────────────────────────

def rounded_panel(img: Image.Image, box: tuple[int, int, int, int], radius: int = 14,
                  fill=P["panel"], edge=P["panel_edge"], alpha: int = 225,
                  edge_width: int = 2, accent: tuple[int, int, int] | None = None,
                  accent_side: str = "left") -> ImageDraw.ImageDraw:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=radius, fill=(*fill, alpha), outline=(*edge, 255), width=edge_width)
    if accent:
        x0, y0, x1, y1 = box
        if accent_side == "left":
            d.rounded_rectangle((x0, y0, x0 + 8, y1), radius=4, fill=(*accent, 255))
        elif accent_side == "top":
            d.rounded_rectangle((x0, y0, x1, y0 + 7), radius=3, fill=(*accent, 255))
        elif accent_side == "bottom":
            d.rounded_rectangle((x0, y1 - 7, x1, y1), radius=3, fill=(*accent, 255))
    img.alpha_composite(layer)
    return ImageDraw.Draw(img)


def kicker(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
           color=P["accent"], size: int = 22, letter_gap: int = 3) -> int:
    """Small caps tracking label used above headlines."""
    f = font(size, "mono")
    x, y = xy
    for ch in text.upper():
        draw.text((x, y), ch, font=f, fill=color)
        x += text_size(draw, ch, f)[0] + letter_gap
    return x


def progress_bar(img: Image.Image, box: tuple[int, int, int, int], value: float,
                 color=P["accent_alt"], track=(30, 38, 50), label: str = "",
                 value_text: str = "") -> None:
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=(y1 - y0) // 2, fill=track)
    width = int((x1 - x0) * max(0.0, min(1.0, value)))
    if width > 4:
        d.rounded_rectangle((x0, y0, x0 + width, y1), radius=(y1 - y0) // 2, fill=color)
    if label:
        f = font(max(16, (y1 - y0) + 6), "regular")
        draw_text(d, (x0, y0 - (y1 - y0) - 12), label, f, fill=P["muted"], shadow=0)
    if value_text:
        f = font(max(18, (y1 - y0) + 8), "bold")
        w = text_size(d, value_text, f)[0]
        draw_text(d, (x1 - w, y0 - (y1 - y0) - 12), value_text, f, fill=P["text"], shadow=0)


def glow(img: Image.Image, radius: int = 18, alpha: float = 0.5) -> None:
    """Additive bloom pass — cheap but effective on bright HUD elements."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius))
    arr = np.asarray(img, np.float32)
    bloom = np.asarray(blurred, np.float32)
    out = np.clip(arr + bloom * alpha, 0, 255).astype(np.uint8)
    img.paste(Image.fromarray(out, "RGB"), (0, 0))


# ─────────────────────────────────────────────────────────────
# Icons (vector silhouettes, top view)
# ─────────────────────────────────────────────────────────────

def icon_helicopter(size: int = 120, color=P["accent"], attack: bool = True) -> Image.Image:
    """Top-view attack helicopter glyph."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 100.0
    c = (*color, 255)
    # fuselage
    d.ellipse([38 * s, 26 * s, 62 * s, 70 * s], fill=c)
    d.polygon([(44 * s, 26 * s), (56 * s, 26 * s), (52 * s, 12 * s), (48 * s, 12 * s)], fill=c)
    # tail boom + tail rotor
    d.rectangle([47 * s, 66 * s, 53 * s, 92 * s], fill=c)
    d.rectangle([40 * s, 86 * s, 60 * s, 92 * s], fill=c)
    # main rotor blades
    d.rectangle([8 * s, 46 * s, 92 * s, 51 * s], fill=(*color, 190))
    d.rectangle([47 * s, 8 * s, 52 * s, 92 * s], fill=(*color, 190))
    d.ellipse([45 * s, 45 * s, 55 * s, 55 * s], fill=c)
    if attack:
        # stub wings with hardpoints
        d.rectangle([22 * s, 44 * s, 40 * s, 50 * s], fill=c)
        d.rectangle([60 * s, 44 * s, 78 * s, 50 * s], fill=c)
        for x in (26, 34, 66, 74):
            d.ellipse([x * s - 2.5 * s, 50 * s, x * s + 2.5 * s, 58 * s], fill=c)
    return img


def icon_drone(size: int = 90, color=P["friendly"], fpv: bool = True) -> Image.Image:
    """Top-view quadcopter / FPV drone glyph."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 100.0
    c = (*color, 255)
    cx = cy = 50 * s
    arms = [(24, 24), (76, 24), (24, 76), (76, 76)]
    for ax, ay in arms:
        d.line([(cx, cy), (ax * s, ay * s)], fill=c, width=int(5 * s))
        d.ellipse([ax * s - 15 * s, ay * s - 15 * s, ax * s + 15 * s, ay * s + 15 * s],
                  outline=(*color, 160), width=int(2.5 * s))
    if fpv:
        d.polygon([(38 * s, 42 * s), (62 * s, 42 * s), (56 * s, 66 * s), (44 * s, 66 * s)], fill=c)
        d.ellipse([44 * s, 34 * s, 56 * s, 46 * s], fill=(*color, 255))
    else:
        d.rounded_rectangle([38 * s, 38 * s, 62 * s, 62 * s], radius=6 * s, fill=c)
    return img


def icon_recon_drone(size: int = 90, color=P["danger"]) -> Image.Image:
    """Fixed-wing reconnaissance UAV glyph (Orlan-10 style)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 100.0
    c = (*color, 255)
    d.polygon([(50 * s, 8 * s), (58 * s, 52 * s), (50 * s, 70 * s), (42 * s, 52 * s)], fill=c)
    d.rectangle([10 * s, 38 * s, 90 * s, 47 * s], fill=c)
    d.polygon([(42 * s, 74 * s), (58 * s, 74 * s), (54 * s, 88 * s), (46 * s, 88 * s)], fill=c)
    d.ellipse([44 * s, 40 * s, 56 * s, 52 * s], fill=(255, 255, 255, 200))
    return img


def icon_target(size: int = 110, color=P["danger"], rotation: float = 0.0) -> Image.Image:
    """Rotating HUD reticle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = (*color, 230)
    pad = size * 0.08
    d.arc([pad, pad, size - pad, size - pad], rotation, rotation + 70, fill=c, width=3)
    d.arc([pad, pad, size - pad, size - pad], rotation + 90, rotation + 160, fill=c, width=3)
    d.arc([pad, pad, size - pad, size - pad], rotation + 180, rotation + 250, fill=c, width=3)
    d.arc([pad, pad, size - pad, size - pad], rotation + 270, rotation + 340, fill=c, width=3)
    mid = size / 2
    inner = size * 0.2
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        d.line([(mid + dx * inner, mid + dy * inner), (mid + dx * inner * 1.9, mid + dy * inner * 1.9)],
               fill=c, width=3)
    d.ellipse([mid - 3, mid - 3, mid + 3, mid + 3], fill=c)
    return img


def icon_burst(size: int = 200, color=(255, 170, 60), t: float = 1.0) -> Image.Image:
    """Explosion / impact burst scaled by t (0..1)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rng = random.Random(11)
    mid = size / 2
    grow = 0.55 + 0.45 * min(max(t, 0.0), 1.0)
    rays = 26
    for i in range(rays):
        angle = (i / rays) * math.tau + rng.uniform(-0.06, 0.06)
        length = mid * (0.5 + rng.random() * 0.5) * grow
        width = max(2, int(size * 0.045 * (1.1 - 0.5 * t)))
        alpha = int(235 * max(0.0, 1.0 - t * 0.5))
        shade = (255, int(205 - 115 * rng.random()), 60)
        x2 = mid + math.cos(angle) * length
        y2 = mid + math.sin(angle) * length
        d.line([(mid, mid), (x2, y2)], fill=(*shade, alpha), width=width)
    core = mid * (0.52 * (1.15 - 0.45 * t))
    steps = 6
    for k in range(steps, 0, -1):
        radius = core * k / steps
        frac = k / steps
        col = (255, int(238 - 165 * (1 - frac)), int(150 - 130 * (1 - frac)))
        alpha = int(250 * max(0.0, 1.0 - t * 0.55) * (1.2 - frac))
        d.ellipse([mid - radius, mid - radius, mid + radius, mid + radius],
                  fill=(*col, min(255, max(0, alpha))))
    return img


def arrow(size: tuple[int, int], color=P["accent"], thickness: int = 6,
          head: int = 22, dashed: bool = False) -> Image.Image:
    """Straight tactical arrow inside a transparent canvas of given size."""
    w, h = size
    img = Image.new("RGBA", (max(8, w), max(8, h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 6, h / 2, w - 6 - head, h / 2
    if dashed:
        x = x0
        while x < x1:
            d.line([(x, y0), (min(x + 14, x1), y0)], fill=(*color, 255), width=thickness)
            x += 24
    else:
        d.line([(x0, y0), (x1, y1)], fill=(*color, 255), width=thickness)
    d.polygon([(x1, y1 - head * 0.62), (x1, y1 + head * 0.62), (x1 + head, y1)], fill=(*color, 255))
    return img


def unit_marker(size: int, label: str, color=P["accent_alt"], friendly: bool = True,
                scale: float = 1.0) -> Image.Image:
    """NATO-style APP-6 inspired unit box with a short label underneath."""
    w = int(size * 1.6 * scale)
    h = int(size * 1.5 * scale)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bw, bh = int(size * scale), int(size * 0.62 * scale)
    x0, y0 = (w - bw) // 2, int(h * 0.18)
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=3, fill=(12, 16, 22, 210),
                        outline=(*color, 255), width=max(2, int(2 * scale)))
    if friendly:
        d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=int(bh * 0.5),
                            outline=(*color, 255), width=max(2, int(2 * scale)))
    else:
        d.rectangle([x0, y0, x0 + bw, y0 + bh], outline=(*color, 255), width=max(2, int(2 * scale)))
    if label:
        f = font(max(11, int(15 * scale)), "mono")
        tw = text_size(d, label, f)[0]
        draw_text(d, ((w - tw) // 2, y0 + bh + int(4 * scale)), label, f, fill=(*color, 255), shadow=0)
    return img


def range_ring(radius: int, color=P["accent_alt"], alpha: int = 90,
               dashed: bool = True, width: int = 2) -> Image.Image:
    size = radius * 2 + 8
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = [4, 4, size - 4, size - 4]
    if not dashed:
        d.ellipse(box, outline=(*color, alpha), width=width)
        return img
    steps = 72
    for i in range(0, steps, 2):
        a0 = i / steps * 360
        a1 = (i + 1) / steps * 360
        d.arc(box, a0, a1, fill=(*color, alpha), width=width)
    return img


# ─────────────────────────────────────────────────────────────
# Photo treatment
# ─────────────────────────────────────────────────────────────

def cover(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize/crop to exactly cover width x height."""
    ratio = max(width / img.width, height / img.height)
    resized = img.resize((int(img.width * ratio) + 1, int(img.height * ratio) + 1), Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def grade_photo(img: Image.Image, cool: float = 0.92, contrast: float = 1.12,
                saturation: float = 0.82) -> Image.Image:
    """Desaturated cold grade so photos sit inside the HUD palette."""
    from PIL import ImageEnhance

    out = ImageOps.autocontrast(img.convert("RGB"), cutoff=1)
    out = ImageEnhance.Color(out).enhance(saturation)
    out = ImageEnhance.Contrast(out).enhance(contrast)
    arr = np.asarray(out, np.float32)
    tint = np.asarray((0.94, 0.99, 1.08), np.float32) * cool + (1 - cool)
    arr = np.clip(arr * tint[None, None, :], 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def ken_burns(img: Image.Image, t: float, zoom_from: float = 1.0, zoom_to: float = 1.14,
              pan: tuple[float, float] = (0.0, 0.0)) -> Image.Image:
    """Crop a moving window out of a larger source image (t = 0..1)."""
    eased = 0.5 - math.cos(math.pi * min(max(t, 0.0), 1.0)) / 2
    zoom = zoom_from + (zoom_to - zoom_from) * eased
    w, h = img.size
    cw, ch = int(w / zoom), int(h / zoom)
    max_dx, max_dy = w - cw, h - ch
    left = int(max_dx * (0.5 + pan[0] * (eased - 0.5)))
    top = int(max_dy * (0.5 + pan[1] * (eased - 0.5)))
    left = max(0, min(left, max_dx))
    top = max(0, min(top, max_dy))
    crop = img.crop((left, top, left + cw, top + ch))
    return crop.resize((w, h), Image.BILINEAR)


def photo_card(img: Image.Image, width: int, height: int, caption: str = "",
               credit: str = "", border: int = 3) -> Image.Image:
    """Framed photo with caption bar — used for CC licensed stills."""
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    photo = cover(grade_photo(img), width - border * 2, height - border * 2).convert("RGBA")
    card.alpha_composite(photo, (border, border))
    d = ImageDraw.Draw(card)
    d.rectangle([0, 0, width - 1, height - 1], outline=(*P["panel_edge"], 255), width=border)
    if caption:
        bar_h = int(height * 0.13)
        d.rectangle([border, height - border - bar_h, width - border, height - border],
                    fill=(8, 11, 16, 215))
        f = font(max(16, int(bar_h * 0.42)), "bold")
        draw_text(d, (border + 16, height - border - bar_h + int(bar_h * 0.16)), caption[:88], f,
                  fill=P["text"], shadow=1)
        if credit:
            fc = font(max(12, int(bar_h * 0.26)), "regular")
            draw_text(d, (border + 16, height - border - int(bar_h * 0.42)), credit[:110], fc,
                      fill=P["muted"], shadow=0)
    return card.convert("RGB")


# ─────────────────────────────────────────────────────────────
# Easing & animation helpers
# ─────────────────────────────────────────────────────────────

def ease_out_cubic(t: float) -> float:
    return 1 - (1 - min(max(t, 0.0), 1.0)) ** 3


def ease_in_out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 0.5 - math.cos(math.pi * t) / 2


def clamp01(t: float) -> float:
    return min(max(t, 0.0), 1.0)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * clamp01(t)


def blink(t_sec: float, period: float = 1.1, duty: float = 0.55) -> bool:
    return (t_sec % period) < period * duty


def fade_alpha(t: float, duration: float, fade_in: float = 0.5, fade_out: float = 0.6) -> float:
    """Scene-level opacity envelope used for cross dissolves."""
    if duration <= 0:
        return 1.0
    if t < fade_in:
        return clamp01(t / fade_in)
    if t > duration - fade_out:
        return clamp01((duration - t) / fade_out)
    return 1.0
