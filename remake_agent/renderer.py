"""Fast media-free draft renderer.

The renderer creates only procedural gradients, shapes and text from the project
configuration. It never opens the reference URL or source media.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Iterable

from .errors import RemakeAgentError
from .planner import read_project_json


def _dependencies():
    try:
        import imageio_ffmpeg
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RemakeAgentError("Renderer requires Pillow and imageio-ffmpeg. Run: python -m pip install -r requirements.txt") from exc
    return imageio_ffmpeg, Image, ImageDraw, ImageFont


def _load_font(ImageFont, size: int, bold: bool = False):
    names = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "DejaVuSans.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_bbox(draw, text: str, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _wrap(draw, text: str, font, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _text_bbox(draw, candidate, font)[0] <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_lines(draw, text: str, ImageFont, max_width: int, max_lines: int, initial: int, minimum: int, bold: bool = False):
    for size in range(initial, minimum - 1, -2):
        font = _load_font(ImageFont, size, bold=bold)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
    font = _load_font(ImageFont, minimum, bold=bold)
    lines = _wrap(draw, text, font, max_width)
    if len(lines) > max_lines:
        clipped = lines[:max_lines]
        clipped[-1] = clipped[-1].rstrip(" .") + "…"
        return font, clipped
    return font, lines


def _centered(draw, lines: Iterable[str], font, x: int, y: int, color, gap: int) -> int:
    current_y = y
    for line in lines:
        width, height = _text_bbox(draw, line, font)
        draw.text((x - width // 2, current_y), line, font=font, fill=color)
        current_y += height + gap
    return current_y


def _background(Image, ImageDraw, width: int, height: int, progress: float):
    """A distinctive, original abstract background made at render time."""
    image = Image.new("RGB", (width, height), (9, 14, 31))
    draw = ImageDraw.Draw(image, "RGBA")
    # A layered, slow-moving wave pattern. It is intentionally graphic, not a
    # generated or simulated real-world scene.
    for y in range(0, height, max(3, height // 120)):
        wave = (math.sin(y / max(height, 1) * math.pi * 2 + progress * math.pi * 2) + 1) / 2
        color = (12 + int(12 * wave), 20 + int(18 * wave), 47 + int(36 * wave), 255)
        draw.line([(0, y), (width, y)], fill=color, width=max(3, height // 120))
    for index in range(10):
        x = int((index * 0.127 + progress * (0.05 + index * 0.004)) % 1.15 * width) - width // 12
        radius = max(40, width // 13) + int(math.sin(progress * 9 + index) * width // 45)
        color = (77 + index * 8, 119, 255 - index * 7, 25)
        draw.ellipse((x - radius, height // 2 - radius, x + radius, height // 2 + radius), fill=color)
    for index in range(4):
        offset = math.sin(progress * math.pi * 2 + index * 1.4) * height * 0.12
        points = []
        for x in range(-width // 8, width + width // 8, max(8, width // 100)):
            y = int(height * (0.18 + index * 0.18) + offset + math.sin(x / width * 9 + progress * 8 + index) * height * 0.035)
            points.append((x, y))
        draw.line(points, fill=(111, 239, 215, 42), width=max(2, width // 640))
    return image


def _card_frame(Image, ImageDraw, ImageFont, width: int, height: int, card: dict[str, str], elapsed: float, card_seconds: float, overall: float):
    image = _background(Image, ImageDraw, width, height, overall)
    draw = ImageDraw.Draw(image, "RGBA")
    margin = int(width * 0.115)
    panel_top = int(height * 0.17)
    panel_bottom = int(height * 0.80)
    draw.rounded_rectangle(
        (margin, panel_top, width - margin, panel_bottom),
        radius=max(20, width // 70),
        fill=(5, 10, 27, 196),
        outline=(130, 245, 217, 105),
        width=max(2, width // 640),
    )
    kicker_font = _load_font(ImageFont, max(16, width // 54), bold=True)
    title_font, title_lines = _fit_lines(
        draw, str(card.get("headline", "Original video")), ImageFont, int(width * 0.68), 3, max(28, width // 20), max(22, width // 33), bold=True
    )
    body_font, body_lines = _fit_lines(
        draw, str(card.get("body", "")), ImageFont, int(width * 0.67), 5, max(19, width // 39), max(15, width // 54), bold=False
    )

    # Gentle content entrance; card text stays legible and does not imitate a source edit.
    fade = min(1.0, elapsed / 0.45, (card_seconds - elapsed) / 0.45)
    alpha = max(0, min(255, int(255 * fade)))
    kicker = str(card.get("kicker", "ORIGINAL DRAFT")).upper()
    kicker_w, kicker_h = _text_bbox(draw, kicker, kicker_font)
    draw.text((width // 2 - kicker_w // 2, int(height * 0.245)), kicker, font=kicker_font, fill=(130, 245, 217, alpha))
    title_y = int(height * 0.33)
    end_title = _centered(draw, title_lines, title_font, width // 2, title_y, (244, 247, 255, alpha), max(8, height // 90))
    divider_y = end_title + int(height * 0.03)
    draw.line((int(width * 0.30), divider_y, int(width * 0.70), divider_y), fill=(246, 190, 90, alpha), width=max(2, width // 700))
    _centered(draw, body_lines, body_font, width // 2, divider_y + int(height * 0.055), (215, 225, 241, alpha), max(6, height // 110))

    footer_font = _load_font(ImageFont, max(12, width // 85), bold=True)
    footer = "DRAFT • ADD ORIGINAL VOICEOVER • VERIFY RIGHTS"
    footer_w, _ = _text_bbox(draw, footer, footer_font)
    draw.text((width // 2 - footer_w // 2, int(height * 0.89)), footer, font=footer_font, fill=(158, 176, 207, 190))
    return image


def _parse_resolution(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except (ValueError, AttributeError) as exc:
        raise RemakeAgentError("Resolution must have the form WIDTHxHEIGHT, for example 1280x720.") from exc
    if width < 320 or height < 180 or width > 3840 or height > 2160:
        raise RemakeAgentError("Resolution must be between 320x180 and 3840x2160.")
    return width, height


def render_project(project_dir: Path, *, duration_seconds: int | None = None, resolution: str = "1280x720", fps: int = 24) -> Path:
    if not project_dir.is_dir():
        raise RemakeAgentError(f"Project directory not found: {project_dir}")
    config = read_project_json(project_dir, "render_config.json")
    cards = config.get("cards")
    if not isinstance(cards, list) or not cards:
        raise RemakeAgentError("render_config.json must contain at least one card.")
    duration = duration_seconds or int(config.get("draft_duration_seconds", 45))
    if not 5 <= duration <= 3600:
        raise RemakeAgentError("Render duration must be between 5 and 3600 seconds.")
    if not 12 <= fps <= 60:
        raise RemakeAgentError("--fps must be between 12 and 60.")
    width, height = _parse_resolution(resolution)
    imageio_ffmpeg, Image, ImageDraw, ImageFont = _dependencies()
    output = project_dir / "output" / "original_draft.mp4"
    output.parent.mkdir(exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{width}x{height}", "-pix_fmt", "rgb24", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-metadata", "title=Original video draft", str(output),
    ]
    total_frames = duration * fps
    frames_per_card = total_frames / len(cards)
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert process.stdin is not None
        for frame_number in range(total_frames):
            card_index = min(len(cards) - 1, int(frame_number / frames_per_card))
            local_frame = frame_number - int(card_index * frames_per_card)
            local_seconds = local_frame / fps
            card_seconds = frames_per_card / fps
            progress = frame_number / max(total_frames - 1, 1)
            frame = _card_frame(Image, ImageDraw, ImageFont, width, height, cards[card_index], local_seconds, card_seconds, progress)
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        return_code = process.wait()
    except (BrokenPipeError, OSError) as exc:
        process.kill()
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        raise RemakeAgentError(f"FFmpeg failed while rendering: {stderr[-500:]}") from exc
    if return_code != 0:
        raise RemakeAgentError(f"FFmpeg failed while rendering: {stderr[-500:]}")
    if not output.exists() or output.stat().st_size == 0:
        raise RemakeAgentError("Renderer completed without creating an MP4.")
    return output
