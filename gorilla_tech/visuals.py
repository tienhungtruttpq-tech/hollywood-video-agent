"""
Scene renderers — turn one entry of `script.json` into an animated frame stream.

A scene spec looks like:

    {
      "id": "s03",
      "beat": "complication",
      "visual": {"type": "map", ...type specific keys...},
      "narration": "...",
      "on_screen": ["short line", ...]
    }

Every renderer is a class with `.frame(t, duration) -> PIL.Image`. Static layers
are drawn once in `__init__` and cached; only the moving parts are redrawn, so a
14 minute 1080p video stays renderable on a normal CI runner.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import config
import graphics as g
import util

P = config.PALETTE


# ─────────────────────────────────────────────────────────────
# Context
# ─────────────────────────────────────────────────────────────

@dataclass
class SceneContext:
    project: Path
    lang: str = "es"
    size: tuple[int, int] = (1920, 1080)
    brand: str = "GORIZON TECH"
    seed: int = 1234
    images: dict = field(default_factory=dict)   # scene id -> local image path
    show_hud: bool = True
    _photo_cache: dict = field(default_factory=dict)

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    def scale(self, value: float) -> int:
        """Scale a 1080p design value to the active resolution."""
        return max(1, int(round(value * self.height / 1080)))

    def photo(self, scene_id: str) -> Image.Image | None:
        if scene_id in self._photo_cache:
            return self._photo_cache[scene_id]
        path = self.images.get(scene_id)
        image = None
        if path and Path(path).exists():
            try:
                image = Image.open(path).convert("RGB")
                image.load()
            except Exception as exc:
                util.warn("visuals", f"photo {path} unusable: {exc}")
                image = None
        self._photo_cache[scene_id] = image
        return image


# ─────────────────────────────────────────────────────────────
# Chrome shared by every scene (brand tag, timecode, progress)
# ─────────────────────────────────────────────────────────────

def draw_chrome(img: Image.Image, ctx: SceneContext, t: float, duration: float,
                progress: float, scene_label: str = "") -> None:
    if not ctx.show_hud:
        return
    d = ImageDraw.Draw(img, "RGBA")
    w, h = ctx.size
    s = ctx.scale

    # brand tag
    d.rounded_rectangle([s(48), s(40), s(48) + s(26) + len(ctx.brand) * s(15), s(40) + s(44)],
                        radius=s(6), fill=(10, 14, 20, 190), outline=(*P["panel_edge"], 255), width=2)
    d.ellipse([s(58), s(52), s(58) + s(20), s(52) + s(20)], fill=(*P["accent"], 255))
    f_brand = g.font(s(21), "mono")
    d.text((s(88), s(50)), ctx.brand.upper(), font=f_brand, fill=(*P["text"], 235))

    # timecode
    tc = util.clock(t)
    f_tc = g.font(s(22), "mono")
    tw = g.text_size(d, tc, f_tc)[0]
    d.text((w - s(48) - tw, s(50)), tc, font=f_tc, fill=(*P["muted"], 220))
    if g.blink(t, 1.4):
        d.ellipse([w - s(48) - tw - s(30), s(56), w - s(48) - tw - s(16), s(70)],
                  fill=(*P["danger"], 235))

    # scene label bottom-left
    if scene_label:
        f_lab = g.font(s(19), "mono")
        d.text((s(48), h - s(96)), scene_label.upper()[:52], font=f_lab, fill=(*P["muted"], 200))

    # bottom progress hairline
    bar_y = h - s(38)
    d.rectangle([s(48), bar_y, w - s(48), bar_y + s(4)], fill=(38, 47, 60, 200))
    filled = int((w - s(96)) * min(max(progress, 0.0), 1.0))
    if filled > 2:
        d.rectangle([s(48), bar_y, s(48) + filled, bar_y + s(4)], fill=(*P["accent"], 235))


# ─────────────────────────────────────────────────────────────
# Base class
# ─────────────────────────────────────────────────────────────

class BaseScene:
    kind = "base"
    label = ""

    def __init__(self, scene: dict, ctx: SceneContext):
        self.scene = scene
        self.spec = scene.get("visual", {}) or {}
        self.ctx = ctx
        self.size = ctx.size
        self.s = ctx.scale
        self.rng = random.Random(hash(scene.get("id", "x")) & 0xFFFF)
        self.beat = scene.get("beat", "")
        self.base = self.build_base()

    # -- helpers -------------------------------------------------
    def build_base(self) -> Image.Image:
        img = g.dark_base(self.size[0], self.size[1], seed=self.ctx.seed).convert("RGBA")
        g.grid_overlay(img, spacing=self.s(96), alpha=44)
        return img

    def canvas(self) -> Image.Image:
        return self.base.copy()

    def title_text(self) -> str:
        return str(self.spec.get("title") or self.scene.get("title") or "")

    def kicker_text(self) -> str:
        return str(self.spec.get("kicker") or "")

    def frame(self, t: float, duration: float) -> Image.Image:
        raise NotImplementedError

    # shared bits ------------------------------------------------
    def headline_block(self, img: Image.Image, title: str, kicker: str,
                       y_ratio: float = 0.30, max_width_ratio: float = 0.78,
                       reveal: float = 1.0) -> None:
        d = ImageDraw.Draw(img, "RGBA")
        w, h = self.size
        cx = w // 2
        max_w = int(w * max_width_ratio)
        y = int(h * y_ratio)
        alpha = int(255 * g.clamp01(reveal))
        if kicker:
            kf = g.font(self.s(24), "mono")
            text = kicker.upper()
            tw = sum(g.text_size(d, c, kf)[0] + 3 for c in text)
            x = cx - tw // 2
            bar = int(tw * g.ease_out_cubic(reveal))
            d.rectangle([x, y + self.s(38), x + bar, y + self.s(41)], fill=(*P["accent"], alpha))
            for ch in text:
                if x - (cx - tw // 2) > bar:
                    break
                d.text((x, y), ch, font=kf, fill=(*P["accent_alt"], alpha))
                x += g.text_size(d, ch, kf)[0] + 3
            y += self.s(62)
        tf = g.fit_font_size(d, title, max_w, self.s(86), self.s(34))
        lines = g.wrap(d, title, tf, max_w)
        line_h = int(g.text_size(d, "Ag", tf)[1] * 1.12)
        shown = max(1, int(len(lines) * g.ease_out_cubic(min(1.0, reveal * 1.25))))
        for i, line in enumerate(lines[:shown]):
            lw = g.text_size(d, line, tf)[0]
            g.draw_text(d, (cx - lw // 2 + 3, y + 3), line, tf, fill=(0, 0, 0), shadow=0)
            d.text((cx - lw // 2, y), line, font=tf, fill=(*P["text"], alpha))
            y += line_h


# ─────────────────────────────────────────────────────────────
# 1. Title / chapter card
# ─────────────────────────────────────────────────────────────

class TitleScene(BaseScene):
    kind = "title"

    def build_base(self) -> Image.Image:
        img = g.dark_base(self.size[0], self.size[1], seed=self.ctx.seed + 11,
                          terrain=0.22, tint=(20, 27, 33)).convert("RGBA")
        g.grid_overlay(img, spacing=self.s(80), alpha=52)
        # radar sweep cone baked into the background
        sweep = Image.new("RGBA", self.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(sweep)
        cx, cy = self.size[0] // 2, int(self.size[1] * 1.02)
        radius = int(self.size[1] * 1.05)
        d.pieslice([cx - radius, cy - radius, cx + radius, cy + radius], 200, 340,
                   fill=(*P["accent_alt"], 9))
        img.alpha_composite(sweep)
        blurred = img.filter(ImageFilter.GaussianBlur(self.s(2)))
        return blurred

    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        w, h = self.size
        reveal = g.ease_out_cubic(min(1.0, t / 1.1))

        # rotating radar sweep
        sweep = Image.new("RGBA", self.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sweep)
        cx, cy = w // 2, int(h * 1.02)
        radius = int(h * 1.05)
        angle = (t * 26) % 360
        sd.pieslice([cx - radius, cy - radius, cx + radius, cy + radius], angle, angle + 22,
                    fill=(*P["accent_alt"], 16))
        img.alpha_composite(sweep)

        self.headline_block(img, self.title_text(), self.kicker_text(),
                            y_ratio=0.34, reveal=reveal)

        subtitle = self.spec.get("subtitle")
        if subtitle:
            f = g.font(self.s(30), "regular")
            lines = g.wrap(d, str(subtitle), f, int(w * 0.66))
            y = int(h * 0.62)
            for line in lines[:3]:
                lw = g.text_size(d, line, f)[0]
                d.text((cx_lw(w, lw), y), line, font=f, fill=(*P["muted"], int(235 * reveal)))
                y += self.s(44)

        # animated corner brackets
        draw_corners(d, self.size, self.s, reveal, P["accent"])
        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, t / max(duration, 0.001), self.label)
        return out


def cx_lw(width: int, line_width: int) -> int:
    return width // 2 - line_width // 2


def draw_corners(d: ImageDraw.ImageDraw, size: tuple[int, int], s, reveal: float,
                 color=P["accent"], margin: int = 46, length: int = 66, width: int = 4) -> None:
    w, h = size
    m, ln = s(margin), s(length)
    alpha = int(255 * g.clamp01(reveal))
    drawn = int(ln * g.ease_out_cubic(reveal))
    for (x, y, dx, dy) in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
        d.line([(x, y), (x + dx * drawn, y)], fill=(*color, alpha), width=s(width))
        d.line([(x, y), (x, y + dy * drawn)], fill=(*color, alpha), width=s(width))


# ─────────────────────────────────────────────────────────────
# 2. Tactical map
# ─────────────────────────────────────────────────────────────

class MapScene(BaseScene):
    kind = "map"

    def build_base(self) -> Image.Image:
        img = g.dark_base(self.size[0], self.size[1], seed=self.ctx.seed + 5,
                          terrain=0.5, tint=(24, 33, 28)).convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        w, h = self.size
        rng = np.random.default_rng(self.ctx.seed + 21)

        # farmland patches
        for _ in range(26):
            cx = float(rng.integers(0, w))
            cy = float(rng.integers(0, h))
            size = float(rng.integers(self.s(90), self.s(320)))
            tone = (int(rng.integers(30, 52)), int(rng.integers(40, 62)), int(rng.integers(24, 38)),
                  int(rng.integers(18, 46)))
            d.polygon([(cx, cy), (cx + size, cy + size * 0.12),
                       (cx + size * 0.92, cy + size * 0.7), (cx - size * 0.1, cy + size * 0.6)],
                      fill=tone)
        # rivers
        for _ in range(2):
            points = []
            x = float(rng.integers(-100, w // 2))
            y = float(rng.integers(0, h))
            for _ in range(14):
                points.append((x, y))
                x += w / 12.0
                y += float(rng.integers(-90, 90))
            d.line(points, fill=(38, 66, 88, 150), width=self.s(7), joint="curve")

        g.grid_overlay(img, spacing=self.s(120), alpha=34)

        # range rings
        for ring in self.spec.get("rings", []) or []:
            pos = self.project(ring.get("at") or ring.get("center"))
            radius_px = self.km_to_px(float(ring.get("km", 10)))
            if radius_px > 8:
                ring_img = g.range_ring(int(radius_px), color=_side_color(ring.get("side", "neutral")),
                                        alpha=ring.get("alpha", 80), width=self.s(2))
                img.alpha_composite(ring_img, (int(pos[0] - ring_img.width / 2),
                                               int(pos[1] - ring_img.height / 2)))
            if ring.get("label"):
                f = g.font(self.s(19), "mono")
                d.text((pos[0] + 8, pos[1] - radius_px - self.s(26)), str(ring["label"]),
                       font=f, fill=(*P["muted"], 220))

        # static map furniture
        self.draw_scale_bar(d)
        self.draw_compass(d)

        # headline (static, top-left panel)
        title = self.title_text()
        if title:
            f = g.font(self.s(34), "bold")
            panel_w = min(int(w * 0.62), g.text_size(d, title, f)[0] + self.s(120))
            g.rounded_panel(img, (self.s(48), self.s(110), self.s(48) + panel_w, self.s(110) + self.s(98)),
                            radius=self.s(8), alpha=205, accent=P["accent"], accent_side="left")
            d2 = ImageDraw.Draw(img, "RGBA")
            d2.text((self.s(48) + self.s(30), self.s(110) + self.s(38)), title, font=f,
                    fill=(*P["text"], 255))
            if self.kicker_text():
                kf = g.font(self.s(19), "mono")
                d2.text((self.s(48) + self.s(30), self.s(110) + self.s(10)), self.kicker_text().upper(),
                        font=kf, fill=(*P["accent_alt"], 235))
        return img

    # -- projection ----------------------------------------------
    def _center(self) -> tuple[float, float]:
        center = self.spec.get("center")
        if center and self._is_latlon(center):
            return float(center[0]), float(center[1])
        return 0.5, 0.5

    @staticmethod
    def _is_latlon(point) -> bool:
        try:
            return abs(float(point[0])) > 1.6 or abs(float(point[1])) > 1.6
        except Exception:
            return False

    def km_to_px(self, km: float) -> float:
        span_km = float(self.spec.get("zoom_km") or 60.0)
        return self.size[0] * (km / span_km)

    def project(self, point) -> tuple[float, float]:
        """Accepts [lat, lon] or normalised [x, y] in 0..1."""
        if point is None:
            return self.size[0] / 2, self.size[1] / 2
        a, b = float(point[0]), float(point[1])
        w, h = self.size
        if abs(a) > 1.6 or abs(b) > 1.6:  # geographic
            clat, clon = self._center()
            km_per_deg_lon = 111.32 * math.cos(math.radians(clat)) or 111.32
            dx_km = (b - clon) * km_per_deg_lon
            dy_km = (clat - a) * 110.57
            return w / 2 + self.km_to_px(dx_km), h / 2 + self.km_to_px(dy_km)
        margin = 0.12
        return (margin + a * (1 - 2 * margin)) * w, (margin + b * (1 - 2 * margin)) * h

    def draw_scale_bar(self, d: ImageDraw.ImageDraw) -> None:
        span_km = float(self.spec.get("zoom_km") or 60.0)
        bar_km = 10 if span_km <= 80 else 25
        length = self.km_to_px(bar_km)
        x0 = self.size[0] - self.s(70) - length
        y = self.size[1] - self.s(120)
        d.line([(x0, y), (x0 + length, y)], fill=(*P["muted"], 220), width=self.s(3))
        for x in (x0, x0 + length):
            d.line([(x, y - self.s(8)), (x, y + self.s(8))], fill=(*P["muted"], 220), width=self.s(3))
        f = g.font(self.s(19), "mono")
        d.text((x0, y - self.s(34)), f"{bar_km:g} km", font=f, fill=(*P["muted"], 220))

    def draw_compass(self, d: ImageDraw.ImageDraw) -> None:
        x = self.size[0] - self.s(96)
        y = self.s(180)
        r = self.s(34)
        d.ellipse([x - r, y - r, x + r, y + r], outline=(*P["panel_edge"], 235), width=self.s(2))
        d.polygon([(x, y - r + self.s(6)), (x - self.s(9), y + self.s(6)), (x + self.s(9), y + self.s(6))],
                  fill=(*P["accent"], 240))
        f = g.font(self.s(20), "mono")
        d.text((x - self.s(6), y - r - self.s(32)), "N", font=f, fill=(*P["text"], 235))

    # -- animation ------------------------------------------------
    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        spec = self.spec
        progress = g.clamp01(t / max(duration * float(spec.get("draw_time", 0.72)), 0.001))

        routes = []
        for key, color, dash in (("route", P["danger"], False),
                                 ("drone_route", P["friendly"], True),
                                 ("second_route", P["accent_alt"], True)):
            points = spec.get(key)
            if points and len(points) >= 2:
                px = [self.project(p) for p in points]
                routes.append((px, color, dash))
                draw_polyline(d, px, color, progress, width=self.s(5), dashed=dash)

        # moving platform icons along the main route
        movers = spec.get("movers") or []
        for mover in movers:
            route_key = mover.get("route", "route")
            points = spec.get(route_key)
            if not points or len(points) < 2:
                continue
            px = [self.project(p) for p in points]
            frac = g.clamp01((progress - float(mover.get("start", 0.0))) /
                             max(1e-6, float(mover.get("end", 1.0)) - float(mover.get("start", 0.0))))
            pos, angle = point_along(px, frac)
            icon_kind = mover.get("kind", "heli")
            color = _side_color(mover.get("side", "hostile"))
            size = self.s(int(mover.get("size", 96)))
            if icon_kind == "heli":
                icon = g.icon_helicopter(size, color=color)
            elif icon_kind == "recon":
                icon = g.icon_recon_drone(size, color=color)
            else:
                icon = g.icon_drone(size, color=color, fpv=icon_kind != "fixed")
            rotated = icon.rotate(-(angle - 90), resample=Image.BICUBIC, expand=True) \
                if mover.get("rotate", True) else icon
            img.alpha_composite(rotated, (int(pos[0] - rotated.width / 2),
                                          int(pos[1] - rotated.height / 2)))

        # static units
        for unit in spec.get("units", []) or []:
            appear = float(unit.get("appear", 0.0))
            if progress < appear and t < appear * duration:
                continue
            pos = self.project(unit.get("at"))
            color = _side_color(unit.get("side", "neutral"))
            kind = unit.get("kind", "unit")
            size = self.s(int(unit.get("size", 62)))
            if kind in ("heli", "drone", "fpv", "recon"):
                icon = (g.icon_helicopter(size, color=color) if kind == "heli"
                        else g.icon_recon_drone(size, color=color) if kind == "recon"
                        else g.icon_drone(size, color=color, fpv=kind == "fpv"))
                img.alpha_composite(icon, (int(pos[0] - icon.width / 2), int(pos[1] - icon.height / 2)))
            else:
                marker = g.unit_marker(size, str(unit.get("short", "")), color=color,
                                       friendly=unit.get("side") == "friendly")
                img.alpha_composite(marker, (int(pos[0] - marker.width / 2),
                                             int(pos[1] - marker.height / 2)))
            if unit.get("label"):
                d = ImageDraw.Draw(img, "RGBA")
                f = g.font(self.s(21), "mono")
                label = str(unit["label"])
                lw = g.text_size(d, label, f)[0]
                d.rounded_rectangle([pos[0] - lw / 2 - self.s(12), pos[1] + size * 0.75,
                                     pos[0] + lw / 2 + self.s(12), pos[1] + size * 0.75 + self.s(38)],
                                    radius=self.s(5), fill=(8, 12, 17, 205),
                                    outline=(*color, 190), width=1)
                d.text((pos[0] - lw / 2, pos[1] + size * 0.75 + self.s(6)), label, font=f,
                       fill=(*P["text"], 240))

        # impact / reticle events
        for event in spec.get("events", []) or []:
            at = float(event.get("at", 0.5))  # fraction of scene duration
            if t < at * duration:
                continue
            local = g.clamp01((t - at * duration) / max(0.6, duration * (1 - at)))
            pos = self.project(event.get("at_xy"))
            kind = event.get("kind", "impact")
            if kind == "impact":
                burst = g.icon_burst(self.s(int(260 + 220 * local)), t=max(0.15, local))
                img.alpha_composite(burst, (int(pos[0] - burst.width / 2), int(pos[1] - burst.height / 2)))
                if local < 0.5:
                    shock = int(self.s(90) + self.s(420) * local * 2)
                    d.ellipse([pos[0] - shock / 2, pos[1] - shock / 2, pos[0] + shock / 2, pos[1] + shock / 2],
                              outline=(*P["gold"], int(200 * (1 - local * 2))), width=self.s(4))
            else:  # lock / target designation
                reticle = g.icon_target(self.s(190), color=_side_color(event.get("side", "hostile")),
                                        rotation=t * 55)
                img.alpha_composite(reticle, (int(pos[0] - reticle.width / 2),
                                              int(pos[1] - reticle.height / 2)))

        # on-screen keyword chips
        chips = self.scene.get("on_screen") or []
        for i, chip in enumerate(chips[:3]):
            appear = 0.15 + i * 0.22
            if t < appear * duration:
                continue
            alpha = int(235 * g.ease_out_cubic(min(1.0, (t - appear * duration) / 0.6)))
            f = g.font(self.s(28), "bold")
            text = str(chip).upper()
            tw = g.text_size(d, text, f)[0]
            x = self.s(64)
            y = self.size[1] - self.s(210) - i * self.s(66)
            d.rounded_rectangle([x, y, x + tw + self.s(44), y + self.s(52)], radius=self.s(6),
                                fill=(10, 14, 20, int(alpha * 0.86)), outline=(*P["accent"], alpha),
                                width=2)
            d.text((x + self.s(22), y + self.s(9)), text, font=f, fill=(*P["text"], alpha))

        if self.spec.get("flash_on_impact"):
            for event in spec.get("events", []) or []:
                if event.get("kind") != "impact":
                    continue
                delta = t - float(event.get("at", 0.5)) * duration
                if 0 <= delta < 0.28:
                    strength = int(190 * (1 - delta / 0.28))
                    d.rectangle([0, 0, self.size[0], self.size[1]], fill=(255, 214, 160, strength))

        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, t / max(duration, 0.001), self.spec.get("label", self.label))
        return out


def _side_color(side: str) -> tuple[int, int, int]:
    return {"hostile": P["danger"], "friendly": P["friendly"],
            "neutral": P["accent_alt"], "accent": P["accent"]}.get(side, P["accent_alt"])


def draw_polyline(d: ImageDraw.ImageDraw, points: list[tuple[float, float]],
                  color: tuple[int, int, int], progress: float, width: int = 4,
                  dashed: bool = False, alpha: int = 235) -> None:
    if len(points) < 2 or progress <= 0:
        return
    lengths = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    total = sum(lengths) or 1.0
    target = total * g.clamp01(progress)
    travelled = 0.0
    for i, length in enumerate(lengths):
        if travelled >= target:
            break
        seg_end = min(length, target - travelled)
        a = points[i]
        b = points[i + 1]
        ratio = seg_end / length if length else 0
        end = (a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio)
        if dashed:
            draw_dashed(d, a, end, color, width, alpha)
        else:
            d.line([a, end], fill=(*color, alpha), width=width)
            head = g.arrow((width * 8, width * 8), color=color, thickness=max(2, width // 2),
                           head=width * 3)
            angle = math.degrees(math.atan2(end[1] - a[1], end[0] - a[0]))
            head = head.rotate(-angle, resample=Image.BICUBIC, expand=True)
        travelled += length


def draw_dashed(d: ImageDraw.ImageDraw, a: tuple[float, float], b: tuple[float, float],
                color: tuple[int, int, int], width: int, alpha: int = 235,
                dash: float = 18.0, gap: float = 14.0) -> None:
    length = math.dist(a, b)
    if length < 1:
        return
    dx, dy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    travelled = 0.0
    while travelled < length:
        end = min(travelled + dash, length)
        d.line([(a[0] + dx * travelled, a[1] + dy * travelled), (a[0] + dx * end, a[1] + dy * end)],
               fill=(*color, alpha), width=width)
        travelled = end + gap


def point_along(points: list[tuple[float, float]], frac: float) -> tuple[tuple[float, float], float]:
    if len(points) < 2:
        return (points[0] if points else (0.0, 0.0)), 0.0
    lengths = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    total = sum(lengths) or 1.0
    target = total * g.clamp01(frac)
    travelled = 0.0
    for i, length in enumerate(lengths):
        if travelled + length >= target:
            ratio = (target - travelled) / length if length else 0
            a, b = points[i], points[i + 1]
            pos = (a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio)
            return pos, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        travelled += length
    return points[-1], 0.0


# ─────────────────────────────────────────────────────────────
# 3. Photo scene (CC still with Ken Burns + optional drone HUD)
# ─────────────────────────────────────────────────────────────

class PhotoScene(BaseScene):
    kind = "photo"

    def __init__(self, scene: dict, ctx: SceneContext):
        super().__init__(scene, ctx)
        self.photo = ctx.photo(scene.get("id", ""))
        self.zoom_from = float(self.spec.get("zoom_from", 1.02))
        self.zoom_to = float(self.spec.get("zoom_to", 1.18))
        self.pan = tuple(self.spec.get("pan", (0.5, -0.4)))
        if self.photo:
            big = (int(self.size[0] * 1.35), int(self.size[1] * 1.35))
            self.photo = g.cover(g.grade_photo(self.photo), *big)

    def build_base(self) -> Image.Image:
        img = g.dark_base(self.size[0], self.size[1], seed=self.ctx.seed + 3).convert("RGBA")
        g.grid_overlay(img, spacing=self.s(110), alpha=30)
        return img

    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        progress = g.clamp01(t / max(duration, 0.001))

        if self.photo:
            frame_img = g.ken_burns(self.photo, progress, self.zoom_from, self.zoom_to, self.pan)
            card_w = int(self.size[0] * float(self.spec.get("width_ratio", 0.86)))
            card_h = int(self.size[1] * float(self.spec.get("height_ratio", 0.78)))
            frame_img = frame_img.resize((card_w, card_h), Image.BILINEAR)
            caption = str(self.spec.get("caption") or "")
            credit = str(self.spec.get("credit") or "")
            card = g.photo_card(frame_img, card_w, card_h, caption, credit, border=self.s(3))
            x = (self.size[0] - card_w) // 2
            y = int(self.size[1] * 0.09)
            # drop shadow
            shadow = Image.new("RGBA", (card_w + self.s(40), card_h + self.s(40)), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.rectangle([self.s(20), self.s(20), self.s(20) + card_w, self.s(20) + card_h],
                         fill=(0, 0, 0, 150))
            shadow = shadow.filter(ImageFilter.GaussianBlur(self.s(12)))
            img.alpha_composite(shadow, (x - self.s(20), y - self.s(20)))
            img.paste(card, (x, y))

            if self.spec.get("hud"):
                draw_drone_hud(img, self.ctx, t, duration, x, y, card_w, card_h)
        else:
            # no photo available: fall back to a keyword panel
            self.headline_block(img, self.title_text() or str(self.spec.get("fallback_title", "")),
                                self.kicker_text(), y_ratio=0.32,
                                reveal=g.ease_out_cubic(min(1, t / 0.8)))
            note = str(self.spec.get("note") or "")
            if note:
                f = g.font(self.s(27), "regular")
                lines = g.wrap(d, note, f, int(self.size[0] * 0.6))
                y = int(self.size[1] * 0.58)
                for line in lines[:4]:
                    lw = g.text_size(d, line, f)[0]
                    d.text((cx_lw(self.size[0], lw), y), line, font=f, fill=(*P["muted"], 235))
                    y += self.s(42)

        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, progress, self.spec.get("label", self.label))
        return out


def draw_drone_hud(img: Image.Image, ctx: SceneContext, t: float, duration: float,
                   x: int, y: int, w: int, h: int) -> None:
    """FPV style overlay: reticle, telemetry ticker, REC indicator."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    s = ctx.scale
    cx, cy = x + w // 2, y + h // 2

    reticle = g.icon_target(s(150), color=P["friendly"], rotation=t * 12)
    overlay.alpha_composite(reticle, (cx - reticle.width // 2, cy - reticle.height // 2))
    d.line([(cx - s(220), cy), (cx - s(90), cy)], fill=(*P["friendly"], 180), width=s(2))
    d.line([(cx + s(90), cy), (cx + s(220), cy)], fill=(*P["friendly"], 180), width=s(2))
    d.line([(cx, cy - s(220)), (cx, cy - s(90))], fill=(*P["friendly"], 180), width=s(2))
    d.line([(cx, cy + s(90)), (cx, cy + s(220))], fill=(*P["friendly"], 180), width=s(2))

    f = g.font(s(22), "mono")
    telemetry = [
        f"ALT {int(60 + 240 * abs(math.sin(t / 3.4)))} m",
        f"SPD {int(180 + 130 * g.clamp01(t / max(duration, 1)))} km/h",
        f"BAT {max(4, int(96 - 78 * g.clamp01(t / max(duration, 1))))}%",
        f"RNG {int(1900 - 1750 * g.clamp01(t / max(duration, 1)))} m",
    ]
    for i, item in enumerate(telemetry):
        d.text((x + s(26), y + s(24) + i * s(34)), item, font=f, fill=(*P["friendly"], 225))
    if g.blink(t, 1.0):
        d.ellipse([x + w - s(120), y + s(30), x + w - s(100), y + s(50)], fill=(*P["danger"], 255))
    d.text((x + w - s(92), y + s(26)), "REC", font=f, fill=(*P["danger"], 255))
    d.text((x + w - s(190), y + h - s(50)), util.clock(t), font=f, fill=(*P["friendly"], 225))
    img.alpha_composite(overlay)


# ─────────────────────────────────────────────────────────────
# 4. Spec dossier card
# ─────────────────────────────────────────────────────────────

class SpecScene(BaseScene):
    kind = "spec_card"

    def build_base(self) -> Image.Image:
        img = g.dark_base(self.size[0], self.size[1], seed=self.ctx.seed + 9,
                          terrain=0.14, tint=(22, 28, 36)).convert("RGBA")
        g.grid_overlay(img, spacing=self.s(100), alpha=40)
        w, h = self.size
        d = ImageDraw.Draw(img, "RGBA")
        panel = (self.s(110), self.s(150), w - self.s(110), h - self.s(170))
        g.rounded_panel(img, panel, radius=self.s(16), alpha=232,
                        accent=P["accent_alt"], accent_side="top")
        # header
        name = str(self.spec.get("name") or self.title_text())
        sub = str(self.spec.get("subtitle") or "")
        f_name = g.fit_font_size(d, name, panel[2] - panel[0] - self.s(520), self.s(64), self.s(30))
        d.text((panel[0] + self.s(48), panel[1] + self.s(44)), name, font=f_name, fill=(*P["text"], 255))
        if sub:
            f_sub = g.font(self.s(27), "regular")
            d.text((panel[0] + self.s(48), panel[1] + self.s(118)), sub, font=f_sub,
                   fill=(*P["muted"], 235))
        d.line([(panel[0] + self.s(48), panel[1] + self.s(170)),
                (panel[2] - self.s(48), panel[1] + self.s(170))], fill=(*P["panel_edge"], 255),
               width=self.s(2))
        self.panel = panel
        # platform icon on the right
        icon_kind = str(self.spec.get("icon", "heli"))
        icon = (g.icon_helicopter(self.s(230), color=P["accent"]) if icon_kind in ("heli", "helicopter")
                else g.icon_recon_drone(self.s(200), color=P["accent_alt"]) if icon_kind == "recon"
                else g.icon_drone(self.s(200), color=P["friendly"]))
        self.icon = icon
        self.icon_pos = (panel[2] - icon.width - self.s(90), panel[1] + self.s(36))
        img.alpha_composite(icon, self.icon_pos)
        return img

    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        x0, y0, x1, y1 = self.panel
        rows = self.spec.get("stats") or []
        row_top = y0 + self.s(200)
        row_h = self.s(84)
        reveal = g.ease_out_cubic(min(1.0, t / 1.0))

        # gently pulsing icon
        pulse = 1.0 + 0.035 * math.sin(t * 2.2)
        icon = self.icon.resize((int(self.icon.width * pulse), int(self.icon.height * pulse)))
        img.alpha_composite(icon, (self.icon_pos[0] - (icon.width - self.icon.width) // 2,
                                   self.icon_pos[1] - (icon.height - self.icon.height) // 2))

        for i, row in enumerate(rows[:6]):
            appear = 0.10 * i
            if t < appear * duration and t < 0.35 + 0.25 * i:
                continue
            local = g.ease_out_cubic(min(1.0, (t - (0.3 + 0.28 * i)) / 0.5))
            if local <= 0:
                continue
            y = row_top + i * row_h
            label = str(row.get("label", ""))
            value = str(row.get("value", ""))
            meter = row.get("meter")
            f_label = g.font(self.s(27), "regular")
            f_value = g.font(self.s(34), "bold")
            alpha = int(255 * local)
            d.text((x0 + self.s(48), y), label.upper(), font=f_label, fill=(*P["muted"], alpha))
            vw = g.text_size(d, value, f_value)[0]
            value_x = x0 + self.s(620) - vw
            d.text((value_x, y - self.s(4)), value, font=f_value, fill=(*P["text"], alpha))
            bar_x0 = x0 + self.s(660)
            bar_x1 = x1 - self.s(70)
            if meter is not None:
                track = (30, 38, 50, alpha)
                d.rounded_rectangle([bar_x0, y + self.s(14), bar_x1, y + self.s(30)],
                                    radius=self.s(8), fill=track)
                filled = int((bar_x1 - bar_x0) * g.clamp01(float(meter)) * local)
                if filled > 3:
                    color = P["accent"] if float(meter) > 0.75 else P["accent_alt"]
                    d.rounded_rectangle([bar_x0, y + self.s(14), bar_x0 + filled, y + self.s(30)],
                                        radius=self.s(8), fill=(*color, alpha))
            d.line([(x0 + self.s(48), y + self.s(56)), (x1 - self.s(48), y + self.s(56))],
                   fill=(*P["panel_edge"], int(alpha * 0.7)), width=1)

        note = str(self.spec.get("note") or "")
        if note and t > duration * 0.4:
            f = g.font(self.s(22), "regular")
            lines = g.wrap(d, note, f, x1 - x0 - self.s(120))
            y = y1 - self.s(52) - len(lines[:2]) * self.s(32)
            for line in lines[:2]:
                d.text((x0 + self.s(48), y), line, font=f, fill=(*P["muted"], 215))
                y += self.s(32)

        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, t / max(duration, 0.001),
                    self.spec.get("label", "FICHA TÉCNICA"))
        return out


# ─────────────────────────────────────────────────────────────
# 5. Big stat / counter
# ─────────────────────────────────────────────────────────────

class StatScene(BaseScene):
    kind = "stat"

    def build_base(self) -> Image.Image:
        img = g.dark_base(self.size[0], self.size[1], seed=self.ctx.seed + 17).convert("RGBA")
        # radial burst behind the number
        burst = Image.new("RGBA", self.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(burst)
        cx, cy = self.size[0] // 2, int(self.size[1] * 0.48)
        rng = np.random.default_rng(4)
        for i in range(64):
            angle = i / 64 * math.tau
            length = int(self.size[1] * (0.35 + rng.random() * 0.5))
            d.line([(cx, cy), (cx + math.cos(angle) * length, cy + math.sin(angle) * length)],
                   fill=(*P["accent"], int(rng.integers(6, 22))), width=self.s(6))
        burst = burst.filter(ImageFilter.GaussianBlur(self.s(3)))
        img.alpha_composite(burst)
        g.grid_overlay(img, spacing=self.s(90), alpha=30)
        return img

    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        spec = self.spec
        w, h = self.size
        target = float(spec.get("value", 0))
        count_time = float(spec.get("count_time", 1.8))
        progress = g.ease_out_cubic(min(1.0, t / count_time))
        current = target * progress
        decimals = int(spec.get("decimals", 0))
        suffix = str(spec.get("suffix", ""))
        prefix = str(spec.get("prefix", ""))
        text = prefix + util.format_number(current, self.ctx.lang, decimals) + suffix

        f_big = g.fit_font_size(d, text, int(w * 0.8), self.s(230), self.s(60))
        tw, th = g.text_size(d, text, f_big)
        y = int(h * 0.36)
        color = _side_color(spec.get("tone", "accent"))
        # glow
        glow_layer = Image.new("RGBA", self.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.text((cx_lw(w, tw), y), text, font=f_big, fill=(*color, 200))
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(self.s(18)))
        img.alpha_composite(glow_layer)
        d.text((cx_lw(w, tw) + 4, y + 5), text, font=f_big, fill=(0, 0, 0, 200))
        d.text((cx_lw(w, tw), y), text, font=f_big, fill=(*P["text"], 255))

        label = str(spec.get("label", ""))
        if label:
            f_lab = g.font(self.s(40), "bold")
            lines = g.wrap(d, label.upper(), f_lab, int(w * 0.72))
            ly = y + th + self.s(50)
            for line in lines[:2]:
                lw = g.text_size(d, line, f_lab)[0]
                d.text((cx_lw(w, lw), ly), line, font=f_lab, fill=(*color, 245))
                ly += self.s(52)

        note = str(spec.get("note", ""))
        if note and t > 0.8:
            f_note = g.font(self.s(27), "regular")
            lines = g.wrap(d, note, f_note, int(w * 0.6))
            ny = int(h * 0.855)
            for line in lines[:2]:
                lw = g.text_size(d, line, f_note)[0]
                d.text((cx_lw(w, lw), ny), line, font=f_note, fill=(*P["muted"], 230))
                ny += self.s(40)

        # comparison bars
        bars = spec.get("bars") or []
        if bars:
            bar_w = int(w * 0.5)
            bx = (w - bar_w) // 2
            by = int(h * 0.66)
            top = max(float(b.get("value", 0)) for b in bars) or 1.0
            for i, bar in enumerate(bars[:2]):
                value = float(bar.get("value", 0)) * progress
                length = int(bar_w * (value / top))
                color_bar = P["friendly"] if i == 0 else P["danger"]
                d.rounded_rectangle([bx, by, bx + max(self.s(6), length), by + self.s(34)],
                                    radius=self.s(16), fill=(*color_bar, 235))
                f = g.font(self.s(24), "mono")
                d.text((bx, by - self.s(36)), str(bar.get("label", ""))[:46], font=f,
                       fill=(*P["muted"], 235))
                by += self.s(96)

        draw_corners(d, self.size, self.s, min(1.0, t / 0.9), color)
        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, t / max(duration, 0.001),
                    spec.get("hud_label") or "DATO CLAVE")
        return out


# ─────────────────────────────────────────────────────────────
# 6. Timeline / countdown
# ─────────────────────────────────────────────────────────────

class TimelineScene(BaseScene):
    kind = "timeline"

    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        w, h = self.size
        spec = self.spec
        progress = g.clamp01(t / max(duration * float(spec.get("draw_time", 0.85)), 0.001))

        title = self.title_text()
        if title:
            f = g.font(self.s(44), "bold")
            tw = g.text_size(d, title, f)[0]
            d.text((cx_lw(w, tw), int(h * 0.12)), title, font=f, fill=(*P["text"], 255))
        if self.kicker_text():
            g.kicker(d, (cx_lw(w, len(self.kicker_text()) * self.s(16)), int(h * 0.085)),
                     self.kicker_text(), color=P["accent"], size=self.s(23))

        events = spec.get("events") or []
        mode = str(spec.get("mode", "line"))
        if mode == "clock":
            self.draw_clock(img, d, t, duration, progress)
        else:
            line_y = int(h * 0.56)
            x0, x1 = int(w * 0.10), int(w * 0.90)
            d.line([(x0, line_y), (x0 + int((x1 - x0) * progress), line_y)],
                   fill=(*P["accent_alt"], 235), width=self.s(5))
            d.line([(x0, line_y), (x1, line_y)], fill=(*P["panel_edge"], 200), width=self.s(2))
            for i, event in enumerate(events):
                frac = float(event.get("at", i / max(1, len(events) - 1)))
                if frac > progress:
                    continue
                x = x0 + int((x1 - x0) * frac)
                color = _side_color(event.get("side", "neutral"))
                d.ellipse([x - self.s(12), line_y - self.s(12), x + self.s(12), line_y + self.s(12)],
                          fill=(*color, 255))
                up = i % 2 == 0
                stem = self.s(90) if up else self.s(90)
                d.line([(x, line_y), (x, line_y - stem if up else line_y + stem)],
                       fill=(*color, 200), width=self.s(2))
                f_time = g.font(self.s(28), "mono")
                f_text = g.font(self.s(24), "regular")
                label = str(event.get("time", ""))
                text = str(event.get("text", ""))
                ty = line_y - stem - self.s(76) if up else line_y + stem + self.s(16)
                lw = max(g.text_size(d, label, f_time)[0], g.text_size(d, text, f_text)[0])
                lx = min(max(x - lw // 2, self.s(40)), w - lw - self.s(40))
                d.text((lx, ty), label, font=f_time, fill=(*color, 255))
                d.text((lx, ty + self.s(36)), text[:44], font=f_text, fill=(*P["text"], 235))

        note = str(spec.get("note", ""))
        if note:
            f = g.font(self.s(26), "regular")
            lines = g.wrap(d, note, f, int(w * 0.6))
            y = int(h * 0.84)
            for line in lines[:2]:
                lw = g.text_size(d, line, f)[0]
                d.text((cx_lw(w, lw), y), line, font=f, fill=(*P["muted"], 225))
                y += self.s(38)

        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, t / max(duration, 0.001),
                    spec.get("label", "CRONOLOGÍA"))
        return out

    def draw_clock(self, img: Image.Image, d: ImageDraw.ImageDraw, t: float,
                   duration: float, progress: float) -> None:
        w, h = self.size
        spec = self.spec
        cx, cy = w // 2, int(h * 0.52)
        radius = int(min(w, h) * 0.24)
        total = float(spec.get("total_seconds", 540))
        remaining = max(0.0, total * (1 - progress))
        d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                  outline=(*P["panel_edge"], 255), width=self.s(4))
        d.arc([cx - radius, cy - radius, cx + radius, cy + radius], -90,
              -90 + 360 * progress, fill=(*P["danger"], 255), width=self.s(14))
        f = g.font(self.s(96), "mono")
        text = util.clock(remaining)
        tw, th = g.text_size(d, text, f)
        d.text((cx - tw // 2, cy - th // 2 - self.s(10)), text, font=f,
               fill=(*P["text"], 255))
        caption = str(spec.get("clock_label", ""))
        if caption:
            fc = g.font(self.s(30), "bold")
            cw = g.text_size(d, caption.upper(), fc)[0]
            d.text((cx - cw // 2, cy + radius + self.s(46)), caption.upper(), font=fc,
                   fill=(*P["accent"], 245))


# ─────────────────────────────────────────────────────────────
# 7. Comparison (A vs B)
# ─────────────────────────────────────────────────────────────

class ComparisonScene(BaseScene):
    kind = "comparison"

    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        w, h = self.size
        spec = self.spec
        progress = g.ease_out_cubic(min(1.0, t / 1.1))
        left, right = spec.get("left", {}), spec.get("right", {})

        title = self.title_text()
        if title:
            f = g.font(self.s(44), "bold")
            tw = g.text_size(d, title, f)[0]
            d.text((cx_lw(w, tw), int(h * 0.10)), title, font=f, fill=(*P["text"], 255))

        col_w = int(w * 0.40)
        gap = int(w * 0.06)
        top = int(h * 0.22)
        bottom = int(h * 0.80)
        for i, side in enumerate((left, right)):
            x = (w - col_w * 2 - gap) // 2 + i * (col_w + gap)
            color = P["friendly"] if i == 0 else P["danger"]
            g.rounded_panel(img, (x, top, x + col_w, bottom), radius=self.s(14), alpha=228,
                            accent=color, accent_side="top")
            d = ImageDraw.Draw(img, "RGBA")
            name = str(side.get("name", ""))
            f_name = g.fit_font_size(d, name, col_w - self.s(80), self.s(44), self.s(24))
            nw = g.text_size(d, name, f_name)[0]
            d.text((x + (col_w - nw) // 2, top + self.s(44)), name, font=f_name,
                   fill=(*P["text"], 255))
            value = float(side.get("value", 0)) * progress
            value_text = str(side.get("value_text") or
                             util.format_number(value, self.ctx.lang, int(side.get("decimals", 0))))
            f_value = g.fit_font_size(d, value_text, col_w - self.s(60), self.s(88), self.s(34))
            vw = g.text_size(d, value_text, f_value)[0]
            d.text((x + (col_w - vw) // 2, top + self.s(130)), value_text, font=f_value,
                   fill=(*color, 255))
            unit = str(side.get("unit", ""))
            if unit:
                f_unit = g.font(self.s(26), "regular")
                uw = g.text_size(d, unit, f_unit)[0]
                d.text((x + (col_w - uw) // 2, top + self.s(232)), unit, font=f_unit,
                       fill=(*P["muted"], 230))
            for j, line in enumerate((side.get("notes") or [])[:4]):
                f_note = g.font(self.s(23), "regular")
                wrapped = g.wrap(d, str(line), f_note, col_w - self.s(80))
                y = bottom - self.s(60) - (len((side.get("notes") or [])[:4]) - j) * self.s(46)
                for wl in wrapped[:2]:
                    lw = g.text_size(d, wl, f_note)[0]
                    d.text((x + (col_w - lw) // 2, y), wl, font=f_note, fill=(*P["muted"], 225))
                    y += self.s(32)

        # versus badge
        badge = self.s(74)
        cx, cy = w // 2, (top + bottom) // 2
        d.ellipse([cx - badge, cy - badge, cx + badge, cy + badge], fill=(10, 14, 20, 245),
                  outline=(*P["accent"], 255), width=self.s(4))
        f_vs = g.font(self.s(56), "bold")
        vw2, vh2 = g.text_size(d, "VS", f_vs)
        d.text((cx - vw2 // 2, cy - vh2 // 2 - self.s(6)), "VS", font=f_vs, fill=(*P["accent"], 255))

        ratio = spec.get("ratio")
        if ratio and t > duration * 0.35:
            text = str(ratio.get("text", ""))
            f = g.font(self.s(40), "mono")
            tw = g.text_size(d, text, f)[0]
            y = bottom + self.s(40)
            d.rounded_rectangle([cx_lw(w, tw) - self.s(30), y, cx_lw(w, tw) + tw + self.s(30),
                                 y + self.s(64)], radius=self.s(8), fill=(12, 16, 22, 235),
                                outline=(*P["gold"], 255), width=self.s(3))
            d.text((cx_lw(w, tw), y + self.s(12)), text, font=f, fill=(*P["gold"], 255))

        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, t / max(duration, 0.001),
                    spec.get("label", "COMPARATIVA"))
        return out


# ─────────────────────────────────────────────────────────────
# 8. Quote card
# ─────────────────────────────────────────────────────────────

class QuoteScene(BaseScene):
    kind = "quote"

    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        w, h = self.size
        spec = self.spec
        reveal = g.ease_out_cubic(min(1.0, t / 0.9))
        text = str(spec.get("text") or self.scene.get("narration", ""))
        f = g.fit_font_size(d, f"“{text}”", int(w * 0.72), self.s(64), self.s(28), "regular")
        lines = g.wrap(d, f"“{text}”", f, int(w * 0.72))
        line_h = int(g.text_size(d, "Ag", f)[1] * 1.3)
        total_h = line_h * len(lines)
        y = int(h * 0.5) - total_h // 2
        shown = max(1, int(len(lines) * min(1.0, reveal * 1.4)))
        d.text((int(w * 0.13), y - self.s(120)), "“", font=g.font(self.s(190), "bold"),
               fill=(*P["accent"], int(150 * reveal)))
        for line in lines[:shown]:
            lw = g.text_size(d, line, f)[0]
            d.text((cx_lw(w, lw), y), line, font=f, fill=(*P["text"], int(255 * reveal)))
            y += line_h
        author = str(spec.get("author", ""))
        if author and shown >= len(lines):
            fa = g.font(self.s(28), "mono")
            aw = g.text_size(d, author.upper(), fa)[0]
            d.text((cx_lw(w, aw), y + self.s(30)), author.upper(), font=fa,
                   fill=(*P["accent_alt"], 240))
        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, t / max(duration, 0.001),
                    spec.get("label", "TESTIMONIO"))
        return out


# ─────────────────────────────────────────────────────────────
# 9. Keyword / text-only beat (used when no visual asset exists)
# ─────────────────────────────────────────────────────────────

class TextScene(BaseScene):
    kind = "text"

    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        w, h = self.size
        reveal = g.ease_out_cubic(min(1.0, t / 0.7))
        headline = str(self.spec.get("headline") or self.title_text() or
                       (self.scene.get("on_screen") or [""])[0])
        if headline:
            self.headline_block(img, headline, self.kicker_text(), y_ratio=0.30, reveal=reveal)
        bullets = self.spec.get("bullets") or self.scene.get("on_screen") or []
        if bullets:
            f = g.font(self.s(30), "regular")
            y = int(h * 0.58)
            for i, bullet in enumerate(bullets[:5]):
                appear = 0.25 + i * 0.14
                if t < appear * duration:
                    continue
                local = g.ease_out_cubic(min(1.0, (t - appear * duration) / 0.5))
                text = str(bullet)
                lines = g.wrap(d, text, f, int(w * 0.6))
                for line in lines[:2]:
                    lw = g.text_size(d, line, f)[0]
                    x = cx_lw(w, lw) - self.s(40)
                    d.ellipse([x - self.s(22), y + self.s(14), x - self.s(8), y + self.s(28)],
                              fill=(*P["accent"], int(255 * local)))
                    d.text((x, y), line, font=f, fill=(*P["text"], int(245 * local)))
                    y += self.s(44)
                y += self.s(12)
        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, t / max(duration, 0.001),
                    self.spec.get("label", ""))
        return out


# ─────────────────────────────────────────────────────────────
# 10. End card / CTA
# ─────────────────────────────────────────────────────────────

class OutroScene(BaseScene):
    kind = "cta"

    def frame(self, t: float, duration: float) -> Image.Image:
        img = self.canvas()
        d = ImageDraw.Draw(img, "RGBA")
        w, h = self.size
        spec = self.spec
        reveal = g.ease_out_cubic(min(1.0, t / 0.8))

        title = str(spec.get("title") or "SUSCRÍBETE")
        f = g.fit_font_size(d, title.upper(), int(w * 0.7), self.s(96), self.s(40))
        tw = g.text_size(d, title.upper(), f)[0]
        d.text((cx_lw(w, tw) + 4, int(h * 0.28) + 4), title.upper(), font=f, fill=(0, 0, 0, 220))
        d.text((cx_lw(w, tw), int(h * 0.28)), title.upper(), font=f, fill=(*P["text"], int(255 * reveal)))

        # subscribe button
        btn_w, btn_h = self.s(420), self.s(96)
        bx, by = (w - btn_w) // 2, int(h * 0.46)
        pulse = 1.0 + 0.02 * math.sin(t * 3.2)
        d.rounded_rectangle([bx - self.s(6) * pulse, by - self.s(6) * pulse,
                             bx + btn_w + self.s(6) * pulse, by + btn_h + self.s(6) * pulse],
                            radius=self.s(14), fill=(*P["danger"], 255))
        fb = g.font(self.s(40), "bold")
        label = str(spec.get("button", "SUSCRIBIRSE"))
        lw = g.text_size(d, label, fb)[0]
        d.text((bx + (btn_w - lw) // 2, by + self.s(24)), label, font=fb, fill=(255, 255, 255, 255))

        for i, line in enumerate((spec.get("lines") or [])[:3]):
            f2 = g.font(self.s(28), "regular")
            lw2 = g.text_size(d, str(line), f2)[0]
            if t > 0.6 + 0.35 * i:
                d.text((cx_lw(w, lw2), int(h * 0.64) + i * self.s(52)), str(line), font=f2,
                       fill=(*P["muted"], 235))

        draw_corners(d, self.size, self.s, reveal, P["accent_alt"])
        out = img.convert("RGB")
        draw_chrome(out, self.ctx, t, duration, t / max(duration, 0.001), "")
        return out


# ─────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────

REGISTRY: dict[str, type[BaseScene]] = {
    "title": TitleScene,
    "chapter": TitleScene,
    "map": MapScene,
    "photo": PhotoScene,
    "image": PhotoScene,
    "spec_card": SpecScene,
    "spec": SpecScene,
    "stat": StatScene,
    "timeline": TimelineScene,
    "comparison": ComparisonScene,
    "quote": QuoteScene,
    "text": TextScene,
    "cta": OutroScene,
    "outro": OutroScene,
}


def build_scene(scene: dict, ctx: SceneContext) -> BaseScene:
    kind = str((scene.get("visual") or {}).get("type", "text")).lower()
    # If a photo was requested but never downloaded, degrade to a text/map scene.
    if kind in ("photo", "image") and not ctx.photo(scene.get("id", "")):
        fallback = str((scene.get("visual") or {}).get("fallback", "text"))
        kind = fallback if fallback in REGISTRY else "text"
    klass = REGISTRY.get(kind, TextScene)
    return klass(scene, ctx)
