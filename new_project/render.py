import os
import sys
import json
import glob
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import imageio_ffmpeg

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 1280, 720
FPS = 30
ACTOR_SECONDS = 15
TITLE_SECONDS = 5
OUTRO_SECONDS = 5
FADE_SECONDS = 0.75

PHOTO_SIZE = 460
PHOTO_GAP = 80
PHOTO_TOP = 125

BG_COLOR = (18, 18, 24)
WHITE = (255, 255, 255)
GOLD = (230, 190, 90)
LIGHT_GRAY = (215, 215, 220)
LABEL_COLOR = (170, 170, 185)

PHOTO_DIR = os.path.join("assets", "photos")
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Hollywood_Then_Now.mp4")


# ---------------------------------------------------------------------------
# Font handling
# ---------------------------------------------------------------------------
def load_font(size, bold=False):
    win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    if bold:
        names = ["arialbd.ttf", "segoeuib.ttf", "calibrib.ttf", "verdanab.ttf",
                 "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
    else:
        names = ["arial.ttf", "segoeui.ttf", "calibri.ttf", "verdana.ttf",
                 "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
    search_dirs = [
        win_fonts,
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation",
        "/Library/Fonts",
        "/System/Library/Fonts",
        "",
    ]
    for name in names:
        for d in search_dirs:
            path = os.path.join(d, name) if d else name
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


FONT_TITLE = load_font(72, bold=True)
FONT_NAME = load_font(56, bold=True)
FONT_LABEL = load_font(28, bold=True)
FONT_BODY = load_font(24)
FONT_INTRO = load_font(30)
FONT_SMALL = load_font(20)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        w, _ = text_size(draw, trial, font)
        if w <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_centered_text(draw, text, font, y, color, cx=WIDTH // 2):
    w, h = text_size(draw, text, font)
    draw.text((cx - w // 2, y), text, font=font, fill=color)
    return h


def draw_wrapped_centered(draw, text, font, y, color, max_width, line_spacing=8):
    lines = wrap_text(draw, text, font, max_width)
    for line in lines:
        h = draw_centered_text(draw, line, font, y, color)
        y += h + line_spacing
    return y


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_name(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def resolve_photo_path(value):
    if not value:
        return None
    if os.path.isfile(value):
        return value
    candidate = os.path.join(PHOTO_DIR, os.path.basename(value))
    if os.path.isfile(candidate):
        return candidate
    candidate = os.path.join(PHOTO_DIR, value)
    if os.path.isfile(candidate):
        return candidate
    return None


def guess_photo(name, kind):
    """Fallback: search assets/photos for a file matching the actor and kind."""
    if not os.path.isdir(PHOTO_DIR):
        return None
    key = normalize_name(name)
    for path in glob.glob(os.path.join(PHOTO_DIR, "*")):
        base = os.path.basename(path).lower()
        if kind in base and key in normalize_name(base):
            return path
    return None


def build_actor_records(actors_data, narrative):
    if isinstance(actors_data, dict):
        actor_list = actors_data.get("actors", [])
    else:
        actor_list = actors_data

    lookup = {}
    for entry in actor_list:
        if isinstance(entry, dict):
            nm = entry.get("name", "")
            lookup[normalize_name(nm)] = entry

    records = []
    for item in narrative.get("actors", []):
        name = item.get("name", "Unknown")
        narration = item.get("narration", "")
        entry = lookup.get(normalize_name(name), {})
        then_path = resolve_photo_path(entry.get("then_photo") or entry.get("then")) \
            or guess_photo(name, "then")
        now_path = resolve_photo_path(entry.get("now_photo") or entry.get("now")) \
            or guess_photo(name, "now")
        records.append({
            "name": name,
            "narration": narration,
            "then_photo": then_path,
            "now_photo": now_path,
        })
    return records


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------
def load_square_photo(path, size):
    if path and os.path.isfile(path):
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img).convert("RGB")
            return ImageOps.fit(img, (size, size), method=Image.LANCZOS, centering=(0.5, 0.4))
        except Exception as exc:
            print("  Warning: could not load %s (%s)" % (path, exc))
    placeholder = Image.new("RGB", (size, size), (50, 50, 60))
    d = ImageDraw.Draw(placeholder)
    draw_centered_text(d, "No Photo", FONT_LABEL, size // 2 - 16, LABEL_COLOR, cx=size // 2)
    return placeholder


def paste_with_frame(canvas, photo, x, y):
    border = 4
    draw = ImageDraw.Draw(canvas)
    draw.rectangle(
        [x - border, y - border, x + photo.width + border - 1, y + photo.height + border - 1],
        fill=(235, 235, 240),
    )
    canvas.paste(photo, (x, y))


def make_background():
    """Dark background with a subtle vertical gradient."""
    top = np.array([26, 26, 36], dtype=np.float32)
    bottom = np.array([10, 10, 14], dtype=np.float32)
    t = np.linspace(0.0, 1.0, HEIGHT, dtype=np.float32)[:, None, None]
    grad = top[None, None, :] * (1 - t) + bottom[None, None, :] * t
    arr = np.repeat(grad, WIDTH, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


BACKGROUND = make_background()


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------
def build_title_card(title, intro):
    img = BACKGROUND.copy()
    draw = ImageDraw.Draw(img)
    draw_centered_text(draw, title, FONT_TITLE, 230, GOLD)
    draw.line([(WIDTH // 2 - 220, 330), (WIDTH // 2 + 220, 330)], fill=GOLD, width=3)
    draw_wrapped_centered(draw, intro, FONT_INTRO, 370, LIGHT_GRAY, max_width=1000, line_spacing=10)
    return img


def build_outro_card(outro):
    img = BACKGROUND.copy()
    draw = ImageDraw.Draw(img)
    draw_wrapped_centered(draw, outro, FONT_INTRO, 260, WHITE, max_width=1000, line_spacing=10)
    draw.line([(WIDTH // 2 - 220, 400), (WIDTH // 2 + 220, 400)], fill=GOLD, width=3)
    draw_centered_text(draw, "Hollywood Stars: Then & Now", FONT_LABEL, 430, GOLD)
    return img


def build_actor_card(record):
    img = BACKGROUND.copy()
    draw = ImageDraw.Draw(img)

    # Actor name
    draw_centered_text(draw, record["name"], FONT_NAME, 28, WHITE)

    # Photo positions
    left_x = WIDTH // 2 - PHOTO_GAP // 2 - PHOTO_SIZE
    right_x = WIDTH // 2 + PHOTO_GAP // 2
    y = PHOTO_TOP

    # Labels
    label_y = y - 38
    draw_centered_text(draw, "THEN", FONT_LABEL, label_y, LABEL_COLOR, cx=left_x + PHOTO_SIZE // 2)
    draw_centered_text(draw, "NOW", FONT_LABEL, label_y, LABEL_COLOR, cx=right_x + PHOTO_SIZE // 2)

    # Photos
    then_img = load_square_photo(record["then_photo"], PHOTO_SIZE)
    now_img = load_square_photo(record["now_photo"], PHOTO_SIZE)
    paste_with_frame(img, then_img, left_x, y)
    paste_with_frame(img, now_img, right_x, y)

    # Narration
    draw = ImageDraw.Draw(img)
    text_top = y + PHOTO_SIZE + 18
    available = HEIGHT - text_top - 10
    font = FONT_BODY
    lines = wrap_text(draw, record["narration"], font, 1180)
    line_h = text_size(draw, "Ag", font)[1] + 6
    if len(lines) * line_h > available:
        font = FONT_SMALL
        lines = wrap_text(draw, record["narration"], font, 1200)
        line_h = text_size(draw, "Ag", font)[1] + 5
    ty = text_top
    for line in lines:
        if ty + line_h > HEIGHT:
            break
        draw_centered_text(draw, line, font, ty, LIGHT_GRAY)
        ty += line_h

    return img


# ---------------------------------------------------------------------------
# Video writing
# ---------------------------------------------------------------------------
class VideoWriter:
    def __init__(self, path, width, height, fps):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg, "-y",
            "-loglevel", "error",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", "%dx%d" % (width, height),
            "-pix_fmt", "rgb24",
            "-r", str(fps),
            "-i", "-",
            "-an",
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "18",
            "-movflags", "+faststart",
            path,
        ]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        self.frames = 0

    def write(self, frame_bytes):
        self.proc.stdin.write(frame_bytes)
        self.frames += 1

    def close(self):
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait()
        if self.proc.returncode != 0:
            raise RuntimeError("ffmpeg exited with code %s" % self.proc.returncode)


def write_segment(writer, image, seconds, label=""):
    """Write a static card with fade-in and fade-out."""
    base = np.asarray(image.convert("RGB"), dtype=np.uint8)
    base_bytes = base.tobytes()
    base_f = base.astype(np.float32)
    total = int(round(seconds * FPS))
    fade_frames = max(1, int(round(FADE_SECONDS * FPS)))

    for i in range(total):
        if i < fade_frames:
            alpha = (i + 1) / float(fade_frames)
        elif i >= total - fade_frames:
            alpha = (total - i) / float(fade_frames)
        else:
            alpha = 1.0
        # Smoothstep for a nicer ease
        alpha = alpha * alpha * (3 - 2 * alpha)

        if alpha >= 0.999:
            writer.write(base_bytes)
        else:
            frame = (base_f * alpha).astype(np.uint8)
            writer.write(frame.tobytes())

        if label and (i % FPS == 0 or i == total - 1):
            pct = int(100 * (i + 1) / total)
            sys.stdout.write(f"\r  {label:28s} {pct:3d}%")
            sys.stdout.flush()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    actors_data = json.load(open("actors.json", encoding="utf-8"))
    narrative = json.load(open("narrative.json", encoding="utf-8"))

    narration_map = {a["name"]: a["narration"] for a in narrative["actors"]}

    # Attach narration to each actor record
    for a in actors_data:
        a["narration"] = narration_map.get(a["name"], "")

    writer = VideoWriter(OUTPUT_FILE, WIDTH, HEIGHT, FPS)

    # Title card
    title_img = build_title_card(narrative["title"], narrative["intro"])
    write_segment(writer, title_img, TITLE_SECONDS, "Title")
    print()

    # Each actor
    for idx, actor in enumerate(actors_data):
        name = actor["name"]

        then_path = os.path.join(PHOTO_DIR, actor["then_photo"])
        now_path = os.path.join(PHOTO_DIR, actor["now_photo"])

        if not os.path.isfile(then_path) or not os.path.isfile(now_path):
            print(f"  Skipping {name}: missing photos")
            continue

        frame = build_actor_card(actor)
        write_segment(writer, frame, ACTOR_SECONDS, name)
        print()

    # Outro card
    outro_img = build_outro_card(narrative["outro"])
    write_segment(writer, outro_img, OUTRO_SECONDS, "Outro")
    print()

    writer.close()
    print(f"\nDone! Video saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()